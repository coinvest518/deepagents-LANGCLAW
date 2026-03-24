"""Middleware to patch dangling tool calls in the messages history."""

import json
import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Overwrite

logger = logging.getLogger("deepagents.patch_tool_calls")

# Maps tool_name → {arg_name: expected_type} for args the LLM commonly
# serializes as JSON strings instead of native Python objects.
_COERCE_ARGS: dict[str, dict[str, str]] = {
    "write_todos": {"todos": "list"},
    "composio_action": {"arguments": "dict"},
    "web_search": {"session_params": "dict", "crawl_params": "dict"},
    "GOOGLESHEETS_BATCH_GET": {"ranges": "list"},
    "GOOGLESHEETS_BATCH_UPDATE": {"data": "list"},
}

# String values that represent "no value" — open-weight LLMs send these
# instead of omitting optional params. Strip them so Pydantic uses defaults.
_NULL_STRINGS: frozenset[str] = frozenset({"null", "none", "undefined"})


def _strip_null_string_args(args: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Remove args whose value is a null-sentinel string like 'null' or 'None'."""
    cleaned = {k: v for k, v in args.items() if not (isinstance(v, str) and v.strip().lower() in _NULL_STRINGS)}
    return cleaned, len(cleaned) != len(args)


def _coerce_tool_call_args(tool_call: dict[str, Any]) -> dict[str, Any]:
    """Coerce string-serialized args to their expected Python types.

    Two passes:
    1. Generic: strip any arg whose value is "null"/"None"/"undefined" (open-weight
       LLMs send these for optional params instead of omitting them).
    2. Specific: per-tool coercion map for args that must be a list or dict.
    """
    name = tool_call.get("name", "")
    args = dict(tool_call.get("args", {}))
    changed = False

    # Pass 1 — generic null-string stripping (applies to ALL tools)
    args, stripped = _strip_null_string_args(args)
    if stripped:
        changed = True
        logger.debug("Stripped null-string args from %s: remaining keys %s", name, list(args.keys()))

    # Pass 2 — per-tool type coercion
    coerce_map = _COERCE_ARGS.get(name, {})
    for arg_name, expected_type in coerce_map.items():
        val = args.get(arg_name)
        if not isinstance(val, str):
            continue
        try:
            parsed = json.loads(val)
        except Exception:
            parsed = None

        if expected_type == "list":
            if isinstance(parsed, list):
                args[arg_name] = parsed
                changed = True
            elif val.strip() in ("", "[]"):
                args[arg_name] = []
                changed = True
        elif expected_type == "dict":
            if isinstance(parsed, dict):
                args[arg_name] = parsed
                changed = True
            elif val.strip() in ("", "{}"):
                args[arg_name] = {}
                changed = True
            else:
                args.pop(arg_name, None)
                changed = True

    if not changed:
        return tool_call

    logger.debug("Coerced args for %s: %s", name, {k: type(v).__name__ for k, v in args.items()})
    return {**tool_call, "args": args}


class PatchToolCallsMiddleware(AgentMiddleware):
    """Middleware to patch dangling tool calls and coerce malformed args.

    Two responsibilities:
    1. **Dangling tool calls** (``before_agent``): If a previous AIMessage has
       tool calls that were never answered with a ToolMessage, insert a
       cancellation ToolMessage so the message history stays consistent.
    2. **Arg type coercion** (``after_model``): Some LLMs pass list/dict
       arguments as JSON strings.  We parse them back to native Python types
       before Pydantic validation runs at tool dispatch time.
    """

    def before_agent(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:  # noqa: ARG002
        """Before the agent runs, handle dangling tool calls from any AIMessage."""
        messages = state["messages"]
        if not messages or len(messages) == 0:
            return None

        patched_messages = []
        # Iterate over the messages and add any dangling tool calls
        for i, msg in enumerate(messages):
            patched_messages.append(msg)
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    corresponding_tool_msg = next(
                        (msg for msg in messages[i:] if msg.type == "tool" and msg.tool_call_id == tool_call["id"]),  # ty: ignore[unresolved-attribute]
                        None,
                    )
                    if corresponding_tool_msg is None:
                        # We have a dangling tool call which needs a ToolMessage
                        tool_msg = (
                            f"Tool call {tool_call['name']} with id {tool_call['id']} was "
                            "cancelled - another message came in before it could be completed."
                        )
                        patched_messages.append(
                            ToolMessage(
                                content=tool_msg,
                                name=tool_call["name"],
                                tool_call_id=tool_call["id"],
                            )
                        )

        return {"messages": Overwrite(patched_messages)}

    def after_model(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:  # noqa: ARG002
        """After the LLM responds, coerce string-serialized tool call args."""
        messages = state["messages"]
        if not messages:
            return None

        last = messages[-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return None

        coerced = [_coerce_tool_call_args(tc) for tc in last.tool_calls]
        if coerced == last.tool_calls:
            return None  # nothing changed

        patched = last.model_copy(update={"tool_calls": coerced})
        return {"messages": Overwrite([*messages[:-1], patched])}
