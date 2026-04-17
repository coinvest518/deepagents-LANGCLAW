"""Middleware to detect and break infinite tool-call loops.

Some LLMs (especially open-weight models like Llama 3.3 70B) can get stuck
calling the same tool repeatedly without ever generating a text response.
This middleware detects two distinct loop patterns and forces the agent to stop.

Strategy (two levels):
- **Exact loop** (``MAX_REPEATS_EXACT``): same tool + same arguments N times in a
  row.  Classic stuck-LLM pattern.
- **Name loop** (``MAX_REPEATS_NAME``): same tool name N times in a row regardless
  of arguments.  Catches models that vary the args slightly each iteration (e.g.
  NVIDIA llama rewording the ``prompt`` parameter on every ``create_cron_job`` call)
  so the exact-arg check never fires.

Both checks happen in ``after_model`` before the tool is actually invoked.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Overwrite

logger = logging.getLogger("deepagents.loop_detection")

# After this many consecutive identical tool calls (exact args) the loop is broken.
MAX_REPEATS_EXACT = 3
# After this many consecutive calls to the *same tool* (any args) the loop is broken.
MAX_REPEATS_NAME = 10


def _tool_call_signature(tc: dict[str, Any]) -> str:
    """Return a stable string key for a tool call (name + sorted args JSON)."""
    name = tc.get("name", "")
    args = tc.get("args", {})
    try:
        args_str = json.dumps(args, sort_keys=True, default=str)
    except Exception:
        args_str = str(args)
    return f"{name}::{args_str}"


def _count_consecutive_by_signature(messages: list[Any], signature: str) -> int:
    """Walk backwards counting consecutive AIMessages that contain *signature*.

    Skips ToolMessages (they sit between AI calls).  Stops at the first
    non-matching AI message or any non-tool human/system message.
    """
    count = 0
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            continue
        if isinstance(msg, AIMessage) and msg.tool_calls:
            sigs = {_tool_call_signature(tc) for tc in msg.tool_calls}
            if signature in sigs:
                count += 1
            else:
                break
        else:
            break
    return count


def _count_consecutive_by_name(messages: list[Any], tool_name: str) -> int:
    """Walk backwards counting consecutive AIMessages that call *tool_name* (any args).

    Skips ToolMessages.  Stops at the first AI message that does NOT call
    tool_name, or any non-tool message.
    """
    count = 0
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            continue
        if isinstance(msg, AIMessage) and msg.tool_calls:
            names = {tc.get("name") for tc in msg.tool_calls}
            if tool_name in names:
                count += 1
            else:
                break
        else:
            break
    return count


def _count_total_in_session(messages: list[Any], tool_name: str, max_lookback: int = 30) -> int:
    """Count total calls to *tool_name* across the entire recent session.

    Unlike _count_consecutive_by_name this does NOT reset when a non-AI
    message (e.g. user saying "stop") appears in between.  This catches
    models that briefly switch tools or receive user feedback but then
    return to the same stuck tool.

    Only looks at the last *max_lookback* AI messages to bound cost.
    """
    count = 0
    ai_seen = 0
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.tool_calls:
            ai_seen += 1
            if ai_seen > max_lookback:
                break
            for tc in msg.tool_calls:
                if tc.get("name") == tool_name:
                    count += 1
    return count


def _build_cancel_messages(
    tool_calls: list[dict[str, Any]], reason: str
) -> list[ToolMessage]:
    """Build cancellation ToolMessages for all pending tool calls."""
    return [
        ToolMessage(
            content=(
                f"[Loop detected] Tool '{tc['name']}' is being called in a loop. "
                f"{reason} "
                "Please respond to the user with the information you already have."
            ),
            name=tc["name"],
            tool_call_id=tc["id"],
        )
        for tc in tool_calls
    ]


# Hard-stop thresholds — if the LLM ignores soft warnings this many times,
# we strip its tool calls entirely so the agent loop terminates.
_HARD_STOP_EXACT = 3   # 3rd identical call → force stop
_HARD_STOP_NAME = 15   # 15th consecutive call to same tool → force stop


class LoopDetectionMiddleware(AgentMiddleware):
    """Detects and breaks infinite tool-call loops (exact-args and name-level).

    Args:
        max_repeats_exact: Break after this many consecutive identical calls
            (same tool + same args).  Default: 3.
        max_repeats_name: Break after this many consecutive calls to the same
            tool regardless of args.  Default: 5.  Set to 0 to disable.
    """

    def __init__(
        self,
        max_repeats: int = MAX_REPEATS_EXACT,  # kept for backwards compat
        max_repeats_exact: int | None = None,
        max_repeats_name: int = MAX_REPEATS_NAME,
    ) -> None:
        self.max_repeats_exact = max_repeats_exact if max_repeats_exact is not None else max_repeats
        self.max_repeats_name = max_repeats_name

    def _force_stop(self, messages: list[Any], last: AIMessage, reason: str) -> dict[str, Any]:
        """Hard-stop: strip tool calls from the AIMessage so the agent loop ends.

        Replaces the last AIMessage with a text-only version and adds cancel
        ToolMessages so the message history stays consistent.
        """
        cancel = _build_cancel_messages(last.tool_calls, reason)
        # Replace the AIMessage: keep any text content, drop tool_calls
        forced_text = (
            last.content
            or f"I was unable to complete this task — {reason.lower()} "
            "Here is what I found so far."
        )
        forced_ai = last.model_copy(update={"tool_calls": [], "content": forced_text})
        logger.warning("HARD STOP — stripping tool calls. Reason: %s", reason)
        return {"messages": Overwrite([*messages[:-1], forced_ai])}

    def after_model(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:  # noqa: ARG002
        messages = state["messages"]
        if not messages:
            return None

        last = messages[-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return None

        history = messages[:-1]

        for tc in last.tool_calls:
            tool_name = tc.get("name", "unknown")

            # --- Level 1: exact same tool + exact same args ---
            sig = _tool_call_signature(tc)
            exact_count = _count_consecutive_by_signature(history, sig)

            # Hard stop — LLM ignored soft warnings
            if exact_count >= _HARD_STOP_EXACT - 1:
                return self._force_stop(
                    messages, last,
                    f"Tool '{tool_name}' called {exact_count + 1} times with identical args.",
                )

            if exact_count >= self.max_repeats_exact - 1:
                logger.warning(
                    "Loop detected (exact): %s called %d consecutive times with identical args.",
                    tool_name, exact_count + 1,
                )
                cancel = _build_cancel_messages(
                    last.tool_calls,
                    f"It has been called {exact_count + 1} times with the same arguments.",
                )
                return {"messages": Overwrite([*messages, *cancel])}

            # --- Level 2: same tool name, any args (consecutive) ---
            if self.max_repeats_name > 0:
                name_count = _count_consecutive_by_name(history, tool_name)

                # Hard stop — LLM ignored soft warnings
                if name_count >= _HARD_STOP_NAME - 1:
                    return self._force_stop(
                        messages, last,
                        f"Tool '{tool_name}' called {name_count + 1} consecutive times.",
                    )

                if name_count >= self.max_repeats_name - 1:
                    logger.warning(
                        "Loop detected (name): %s called %d consecutive times (args varied). "
                        "Breaking the loop.",
                        tool_name, name_count + 1,
                    )
                    cancel = _build_cancel_messages(
                        last.tool_calls,
                        f"It has been called {name_count + 1} consecutive times "
                        "(with varying arguments — the task was likely completed already).",
                    )
                    return {"messages": Overwrite([*messages, *cancel])}

            # --- Level 3: session-wide total (non-consecutive) ---
            # Catches models that get interrupted by a user message (e.g. "stop")
            # which breaks the consecutive count, but then return to the same tool.
            session_count = _count_total_in_session(history, tool_name)
            # Use a higher threshold for session-wide count since it spans
            # non-consecutive AI messages across the whole session.
            _SESSION_HARD_STOP = 50
            if session_count >= _SESSION_HARD_STOP:
                return self._force_stop(
                    messages, last,
                    f"Tool '{tool_name}' called {session_count + 1} times in this session (across non-consecutive turns).",
                )

        return None

    async def aafter_model(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:  # noqa: ARG002
        return self.after_model(state, runtime)
