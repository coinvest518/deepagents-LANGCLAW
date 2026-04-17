"""Middleware to enforce self-correction when tool calls fail.

The system prompt tells the model to "never repeat a failed call with the same
arguments" and to "change your approach."  But models (especially open-weight)
frequently ignore prompt-level instructions and either:

1. Retry the exact same call that just failed.
2. Give up entirely after one failure instead of trying alternatives.

This middleware enforces self-correction at the code level by:

- Tracking tool calls that returned errors in the current turn.
- When the model tries to repeat a failed call (same tool + same or similar
  args), intercepting it and injecting a correction nudge.
- Providing concrete suggestions for what to try instead based on the tool
  that failed and the error message.

This is complementary to:
- ``LoopDetectionMiddleware`` which detects repeated *successful* calls (this
  middleware specifically tracks *failed* calls and prevents retrying them).
- ``EarlyExitPreventionMiddleware`` which catches premature exits (this
  middleware catches failed-retry loops that happen *before* exit).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.types import hook_config
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Overwrite

logger = logging.getLogger("deepagents.self_correction")

# After this many correction nudges for the same tool, stop nudging and
# let LoopDetection / EarlyExitPrevention handle it.
MAX_CORRECTIONS_PER_TOOL = 3


# Known tool fallback chains: when tool X fails, suggest tool Y.
_TOOL_FALLBACKS: dict[str, list[str]] = {
    "web_search": ["fetch_url", "execute"],
    "fetch_url": ["web_search", "execute"],
    "composio_action": ["composio_get_schema", "execute"],
    "http_request": ["fetch_url", "web_search", "execute"],
    "read_file": ["ls", "glob", "grep"],
    "edit_file": ["read_file", "write_file"],
    "grep": ["glob", "read_file", "web_search"],
    "glob": ["grep", "ls", "read_file"],
}

# Error patterns and their specific correction advice.
_ERROR_CORRECTIONS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"(?i)404|not found|does not exist|no such file"),
        "The resource doesn't exist. Check the path/URL is correct, or search for the right one using `glob`, `grep`, `ls`, or `web_search`.",
    ),
    (
        re.compile(r"(?i)401|unauthorized|forbidden|403|auth"),
        "Authentication failed. Check if the API key is correct in your environment. Try `read_file` on the relevant skill for correct credentials.",
    ),
    (
        re.compile(r"(?i)429|rate.?limit|too many requests|quota"),
        "Rate limited. Try a different tool or endpoint. If using `web_search`, try `fetch_url` directly. If using an API, try `execute` with a different provider.",
    ),
    (
        re.compile(r"(?i)timeout|timed? ?out|connection.?(?:refused|reset|error)"),
        "Connection failed. Try a different tool or endpoint. If a URL is down, try `web_search` for cached or alternative sources.",
    ),
    (
        re.compile(r"(?i)param|argument|invalid|missing.?(?:required|field|param)|validation"),
        "Parameter error. Call `composio_get_schema` to check correct parameters, or `read_file` on the relevant skill for working examples.",
    ),
    (
        re.compile(r"(?i)windows.?(?:absolute|path)|drive.?letter|C:\\\\|C:/Users"),
        "Windows path error. Use virtual paths only: `/workspace/...` for files, `/skills/...` for skills. Never use drive-letter paths.",
    ),
]


def _tool_call_key(tc: dict[str, Any]) -> str:
    """Stable key for a tool call: name + sorted args."""
    name = tc.get("name", "")
    args = tc.get("args", {})
    try:
        args_str = json.dumps(args, sort_keys=True, default=str)
    except Exception:
        args_str = str(args)
    return f"{name}::{args_str}"


def _is_error_result(msg: ToolMessage) -> bool:
    """Check if a ToolMessage represents an error/failure."""
    content = msg.content if isinstance(msg.content, str) else str(msg.content)
    content_lower = content.lower()

    # Explicit error status.
    status = getattr(msg, "status", None)
    if status == "error":
        return True

    # Common error indicators in content.
    error_indicators = [
        "error", "failed", "exception", "traceback", "errno",
        "status_code: 4", "status_code: 5",  # 4xx, 5xx
        "could not", "unable to", "permission denied",
        "not found", "does not exist", "no such",
    ]
    return any(indicator in content_lower for indicator in error_indicators)


def _get_error_advice(content: str) -> str:
    """Match error content against known patterns and return specific advice."""
    for pattern, advice in _ERROR_CORRECTIONS:
        if pattern.search(content):
            return advice
    return ""


class SelfCorrectionMiddleware(AgentMiddleware):
    """Enforces self-correction by tracking failed tool calls and preventing retries.

    Runs in ``after_model`` to intercept tool calls that repeat a previously
    failed call.  Also runs a lightweight check after tool execution to track
    which calls failed.

    Args:
        max_corrections_per_tool: Maximum correction nudges per tool name
            before deferring to other middleware. Default: 3.
    """

    def __init__(
        self,
        max_corrections_per_tool: int = MAX_CORRECTIONS_PER_TOOL,
    ) -> None:
        self._max_corrections = max_corrections_per_tool
        # Track failed tool call signatures in the current session.
        self._failed_signatures: set[str] = set()
        # Track failed tool names for fallback suggestions.
        self._failed_tool_names: set[str] = set()
        # Count corrections per tool name to avoid infinite nudging.
        self._correction_count: dict[str, int] = {}

    def _collect_failures_from_history(self, messages: list[Any]) -> None:
        """Scan message history to populate failure tracking state.

        Called once per turn to catch up on any failures we haven't tracked
        (e.g. from a previous middleware pass or context compaction).
        """
        # Walk through looking for AIMessage→ToolMessage pairs where
        # the ToolMessage indicates an error.
        for i, msg in enumerate(messages):
            if not isinstance(msg, AIMessage) or not msg.tool_calls:
                continue
            # Look for corresponding ToolMessages after this AIMessage.
            for tc in msg.tool_calls:
                tc_id = tc.get("id", "")
                for j in range(i + 1, min(i + len(msg.tool_calls) + 5, len(messages))):
                    candidate = messages[j]
                    if (
                        isinstance(candidate, ToolMessage)
                        and getattr(candidate, "tool_call_id", None) == tc_id
                        and _is_error_result(candidate)
                    ):
                        sig = _tool_call_key(tc)
                        self._failed_signatures.add(sig)
                        self._failed_tool_names.add(tc.get("name", ""))
                        break

    @hook_config(can_jump_to=["model"])
    def after_model(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:  # noqa: ARG002
        messages = state["messages"]
        if not messages:
            return None

        last = messages[-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return None

        # Scan history to catch up on failures.
        self._collect_failures_from_history(messages[:-1])

        if not self._failed_signatures:
            return None

        # Check if any of the new tool calls repeat a failed call.
        repeated_calls: list[dict[str, Any]] = []
        ok_calls: list[dict[str, Any]] = []
        for tc in last.tool_calls:
            sig = _tool_call_key(tc)
            tool_name = tc.get("name", "")
            if sig in self._failed_signatures:
                repeated_calls.append(tc)
            elif tool_name in self._failed_tool_names:
                # Same tool but different args — allow it (model changed approach).
                ok_calls.append(tc)
            else:
                ok_calls.append(tc)

        if not repeated_calls:
            return None

        # Check per-tool correction limits.
        for tc in repeated_calls:
            tool_name = tc.get("name", "")
            count = self._correction_count.get(tool_name, 0)
            if count >= self._max_corrections:
                # Too many corrections for this tool — let it through and
                # let LoopDetection handle it.
                logger.info(
                    "Self-correction limit reached for '%s' (%d corrections) — "
                    "deferring to loop detection.",
                    tool_name, count,
                )
                return None

        # Build correction nudge.
        names = sorted({tc.get("name", "") for tc in repeated_calls})
        for name in names:
            self._correction_count[name] = self._correction_count.get(name, 0) + 1

        # Find the original error messages for context.
        error_context_parts: list[str] = []
        for tc in repeated_calls:
            tc_id = tc.get("id", "")
            tool_name = tc.get("name", "")

            # Find the original error from history.
            for msg in reversed(messages[:-1]):
                if isinstance(msg, ToolMessage) and msg.name == tool_name and _is_error_result(msg):
                    error_text = msg.content if isinstance(msg.content, str) else str(msg.content)
                    advice = _get_error_advice(error_text)
                    error_context_parts.append(
                        f"- `{tool_name}` previously failed: {error_text[:200]}"
                        + (f"\n  Suggestion: {advice}" if advice else "")
                    )
                    break

        # Suggest fallback tools.
        fallback_suggestions: list[str] = []
        for tc in repeated_calls:
            tool_name = tc.get("name", "")
            fallbacks = _TOOL_FALLBACKS.get(tool_name, [])
            unused_fallbacks = [f for f in fallbacks if f not in self._failed_tool_names]
            if unused_fallbacks:
                fallback_suggestions.append(
                    f"Instead of `{tool_name}`, try: {', '.join(f'`{f}`' for f in unused_fallbacks)}"
                )

        nudge_parts = [
            "[SYSTEM] SELF-CORRECTION: You are about to repeat a tool call that already failed.",
            "Repeating the same call will produce the same error.",
        ]

        if error_context_parts:
            nudge_parts.append("\nPrevious failures:")
            nudge_parts.extend(error_context_parts)

        if fallback_suggestions:
            nudge_parts.append("\nAlternative approaches:")
            nudge_parts.extend(f"- {s}" for s in fallback_suggestions)

        nudge_parts.append(
            "\nChange your approach NOW: use a different tool, different arguments, "
            "or read the relevant skill file for correct parameters."
        )

        nudge = HumanMessage(content="\n".join(nudge_parts))

        logger.warning(
            "Self-correction: blocking repeated failed calls to %s (corrections: %s)",
            names,
            {n: self._correction_count.get(n, 0) for n in names},
        )

        # If some calls are OK and some are repeated failures, keep the OK ones
        # and only nudge about the failed ones.
        if ok_calls:
            patched = last.model_copy(update={"tool_calls": ok_calls})
            # Add cancel messages for the blocked calls.
            cancel_msgs = [
                ToolMessage(
                    content=f"[Self-correction] Blocked: this exact call to '{tc['name']}' "
                    "already failed. Use a different approach.",
                    name=tc["name"],
                    tool_call_id=tc["id"],
                )
                for tc in repeated_calls
            ]
            return {"messages": Overwrite([*messages[:-1], patched, *cancel_msgs])}

        # All calls are repeats — remove them all and nudge.
        return {
            "messages": [*messages[:-1], nudge],
            "jump_to": "model",
        }

    async def aafter_model(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        return self.after_model(state, runtime)
