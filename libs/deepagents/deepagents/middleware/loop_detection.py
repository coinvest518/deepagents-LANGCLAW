"""Middleware to detect and break infinite tool-call loops.

Some LLMs (especially open-weight models like Llama 3.3 70B) can get stuck
calling the same tool with the same arguments repeatedly without ever
generating a text response.  This middleware detects that pattern and
forces the agent to stop looping.

Strategy:
- ``after_model``: inspect the latest AI message's tool calls.  Walk
  backwards through message history counting consecutive identical calls
  (same tool name + same arguments).  If the count hits MAX_REPEATS,
  strip the tool calls from the AI message and replace with a text nudge
  so the agent terminates its loop and responds to the user.
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

# After this many consecutive identical tool calls the loop is broken.
MAX_REPEATS = 3


def _tool_call_signature(tc: dict[str, Any]) -> str:
    """Return a stable string key for a tool call (name + sorted args JSON)."""
    name = tc.get("name", "")
    args = tc.get("args", {})
    try:
        args_str = json.dumps(args, sort_keys=True, default=str)
    except Exception:
        args_str = str(args)
    return f"{name}::{args_str}"


def _count_consecutive_identical_calls(
    messages: list[Any], signature: str
) -> int:
    """Walk backwards through messages counting consecutive matching tool calls.

    We look for the pattern:  AIMessage(tool_calls=[X]) → ToolMessage → AIMessage(tool_calls=[X]) → …
    Returns the number of consecutive times the same signature appears at the
    tail of the conversation (not counting the current/latest one).
    """
    count = 0
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            # Skip tool result messages — they sit between the AI calls
            continue
        if isinstance(msg, AIMessage) and msg.tool_calls:
            # Check if this AI message has the same tool call
            sigs = {_tool_call_signature(tc) for tc in msg.tool_calls}
            if signature in sigs:
                count += 1
            else:
                break
        else:
            # Hit a non-tool message (human, system, or text-only AI) — stop
            break
    return count


class LoopDetectionMiddleware(AgentMiddleware):
    """Detects and breaks infinite tool-call loops.

    When the same tool is called with the same arguments ``max_repeats``
    times in a row, the middleware strips the tool calls from the AI
    message and injects a text response so the agent stops looping.
    """

    def __init__(self, max_repeats: int = MAX_REPEATS) -> None:
        self.max_repeats = max_repeats

    def after_model(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:  # noqa: ARG002
        messages = state["messages"]
        if not messages:
            return None

        last = messages[-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return None

        # Check each tool call in the latest message
        for tc in last.tool_calls:
            sig = _tool_call_signature(tc)
            # Count how many times this exact call already appears in history
            # (excluding the current message)
            prior_count = _count_consecutive_identical_calls(messages[:-1], sig)

            if prior_count >= self.max_repeats - 1:
                tool_name = tc.get("name", "unknown")
                logger.warning(
                    "Loop detected: %s called %d consecutive times with identical args. "
                    "Breaking the loop.",
                    tool_name,
                    prior_count + 1,
                )

                # Build cancellation ToolMessages for all pending tool calls
                # so message history stays consistent, then add a nudge.
                cancel_messages: list[Any] = []
                for tool_call in last.tool_calls:
                    cancel_messages.append(
                        ToolMessage(
                            content=(
                                f"[Loop detected] Tool '{tool_call['name']}' has been called "
                                f"{prior_count + 1} times consecutively with the same arguments. "
                                "The data has already been retrieved successfully. "
                                "Please respond to the user with the information you have."
                            ),
                            name=tool_call["name"],
                            tool_call_id=tool_call["id"],
                        )
                    )

                # Return the original AI message (with tool_calls intact for
                # history consistency) plus the cancel ToolMessages.
                # The agent will see the ToolMessages and on the next model
                # call the LLM should generate a text response.
                return {"messages": Overwrite([*messages, *cancel_messages])}

        return None

    # Async version delegates to sync — the logic is pure message inspection.
    async def aafter_model(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        return self.after_model(state, runtime)