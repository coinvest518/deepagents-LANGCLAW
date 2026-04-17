"""Middleware to prevent premature agent exits.

When the model emits a text-only response (no tool calls), the LangGraph agent
routes to END and the turn finishes.  This is correct when the agent has
genuinely completed the task or exhausted its options.  But open-weight models
frequently give up early — emitting "I can't find that" or "I wasn't able to"
*before* trying available tools, reading relevant skills, or attempting
alternative approaches.

This middleware intercepts those premature exits and nudges the model back to
act.  It works by:

1. Detecting "giving-up" language in text-only responses.
2. Checking whether the agent has actually tried enough tools in this turn.
3. If not, removing the giving-up message and injecting a nudge that lists
   untried tools / unread skills the agent could still use.
4. Jumping back to the model for another attempt.

A retry counter prevents infinite loops — after ``max_retries`` nudges the
agent is allowed to exit normally.

This is complementary to:
- ``LoopDetectionMiddleware`` which prevents calling the *same* tool too many
  times (this middleware encourages trying *different* tools).
- ``ReasoningFilterMiddleware`` which catches reasoning-as-content (this
  middleware catches premature-exit-as-content).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.types import hook_config
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime

logger = logging.getLogger("deepagents.early_exit_prevention")

# Max nudges before we let the agent exit regardless.
MAX_EXIT_RETRIES = 2

# Minimum number of distinct tools the agent should have tried before we
# allow a "giving up" exit without nudging.
MIN_TOOLS_TRIED = 2

# Patterns that indicate the model is giving up or stopping prematurely.
_GIVING_UP_PATTERNS = re.compile(
    r"(?i)"
    r"(?:"
    r"(?:I (?:was(?:n't| not)|am (?:not|unable)|could(?:n't| not)|can(?:not|'t)) (?:able to |find|complete|access|locate|retrieve|do|perform|accomplish|help with))"
    r"|(?:(?:unfortunately|sorry),? (?:I |it (?:seems|appears|looks)))"
    r"|(?:I (?:don't|do not) (?:have (?:access|the ability)|see (?:any|a way)|know how))"
    r"|(?:(?:this |that |it )?(?:is(?:n't| not)|does(?:n't| not)|appears to be) (?:possible|available|supported|working))"
    r"|(?:I(?:'m| am) (?:unable|not able|limited|restricted))"
    r"|(?:there (?:is no|are no|doesn't seem|isn't) )"
    r"|(?:I (?:apologize|regret)(?:,| —| but))"
    r"|(?:(?:no |without )?(?:results?|data|information|matches?) (?:found|available|returned))"
    r")"
)

# Patterns that indicate a LEGITIMATE completion (not giving up).
_COMPLETION_PATTERNS = re.compile(
    r"(?i)"
    r"(?:"
    r"(?:(?:here|above) (?:is|are) (?:the |your |a )?(?:result|summary|answer|output|response|data|information))"
    r"|(?:(?:I(?:'ve| have)|successfully|done|completed|finished|created|sent|saved|updated|posted))"
    r"|(?:the (?:task|request|action|operation) (?:is |has been |was )?(?:complete|done|finished|successful))"
    r")"
)


def _is_giving_up(msg: AIMessage) -> bool:
    """Return True if the message looks like the agent is giving up prematurely."""
    if msg.tool_calls:
        return False

    content = msg.content
    if not isinstance(content, str) or len(content.strip()) < 20:
        return False

    text = content.strip()

    # If it looks like a legitimate completion, don't flag it.
    if _COMPLETION_PATTERNS.search(text):
        return False

    # Check for giving-up language.
    return bool(_GIVING_UP_PATTERNS.search(text))


def _collect_tools_used(messages: list[Any]) -> set[str]:
    """Collect the set of distinct tool names the agent has called in this turn.

    Walks backwards from the end of the message list, collecting tool names
    from AIMessage.tool_calls until hitting a HumanMessage (start of turn).
    """
    tools_used: set[str] = set()
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            break
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tools_used.add(tc.get("name", ""))
    tools_used.discard("")
    return tools_used


def _collect_available_tools(messages: list[Any]) -> set[str]:
    """Infer available tool names from ToolMessages in history.

    This is a heuristic — we look at tool names that have appeared in any
    ToolMessage across the conversation.  Not perfect but gives us a
    reasonable set without needing access to the tool registry.
    """
    available: set[str] = set()
    for msg in messages:
        if isinstance(msg, ToolMessage):
            name = getattr(msg, "name", None)
            if name:
                available.add(name)
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                name = tc.get("name", "")
                if name:
                    available.add(name)
    return available


# Core tools the agent should always consider before giving up.
_CORE_TOOLS = {
    "web_search",
    "fetch_url",
    "execute",
    "read_file",
    "composio_action",
    "search_memory",
    "http_request",
}


class EarlyExitPreventionMiddleware(AgentMiddleware):
    """Prevents premature agent exits by nudging the model to try more tools.

    When the model emits text-only "giving up" responses before trying enough
    tools, this middleware removes the response and sends the model back with
    a nudge listing untried tools it could use.

    Args:
        max_retries: Maximum number of nudges before allowing exit.
            Default: 2.
        min_tools_tried: Minimum distinct tools the agent should try before
            a giving-up exit is allowed without nudging.  Default: 2.
    """

    def __init__(
        self,
        max_retries: int = MAX_EXIT_RETRIES,
        min_tools_tried: int = MIN_TOOLS_TRIED,
    ) -> None:
        self._max_retries = max_retries
        self._min_tools_tried = min_tools_tried
        self._consecutive_exits: int = 0

    @hook_config(can_jump_to=["model"])
    def after_model(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:  # noqa: ARG002
        messages = state["messages"]
        if not messages:
            return None

        last = messages[-1]
        if not isinstance(last, AIMessage):
            return None

        # Only intercept text-only responses (no tool calls).
        if last.tool_calls:
            self._consecutive_exits = 0
            return None

        # Check if this looks like giving up.
        if not _is_giving_up(last):
            self._consecutive_exits = 0
            return None

        # Check how many tools the agent has tried this turn.
        tools_used = _collect_tools_used(messages[:-1])
        available_tools = _collect_available_tools(messages)
        # Merge with known core tools.
        all_known = available_tools | _CORE_TOOLS
        untried = all_known - tools_used

        # If the agent has tried enough tools, let it exit.
        if len(tools_used) >= self._min_tools_tried:
            self._consecutive_exits = 0
            return None

        self._consecutive_exits += 1
        logger.warning(
            "Early exit detected (attempt %d/%d): agent tried %d tools (%s), "
            "%d untried tools available. Response: %.200s",
            self._consecutive_exits,
            self._max_retries,
            len(tools_used),
            ", ".join(sorted(tools_used)) or "none",
            len(untried),
            str(last.content)[:200],
        )

        # If we've nudged too many times, let it exit.
        if self._consecutive_exits > self._max_retries:
            logger.warning(
                "Max exit retries (%d) exceeded — allowing exit.",
                self._max_retries,
            )
            self._consecutive_exits = 0
            return None

        # Build the nudge with untried tool suggestions.
        untried_list = sorted(untried)[:8]  # Don't overwhelm with too many.
        tool_suggestions = ", ".join(f"`{t}`" for t in untried_list)

        nudge_parts = [
            "[SYSTEM] You are about to give up without trying enough approaches.",
            f"Tools you've tried so far: {', '.join(sorted(tools_used)) or 'NONE'}.",
            f"Tools you haven't tried yet: {tool_suggestions}.",
            "Do NOT give up. Try a different tool or approach RIGHT NOW.",
            "If you need specific skill instructions, use `read_file` on the relevant skill file.",
            "Execute a tool call immediately — do not respond with text only.",
        ]
        nudge = HumanMessage(content=" ".join(nudge_parts))

        # Remove the giving-up message and inject the nudge.
        return {
            "messages": [*messages[:-1], nudge],
            "jump_to": "model",
        }

    async def aafter_model(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        return self.after_model(state, runtime)
