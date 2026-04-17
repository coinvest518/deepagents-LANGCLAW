"""Middleware to filter reasoning-as-content from models like NVIDIA Nemotron.

Some models (notably NVIDIA Nemotron) put their chain-of-thought reasoning into
``content`` — either duplicated from ``additional_kwargs.reasoning_content`` or
as raw text with no ``reasoning_content`` field at all.  When the model also
stops without making any tool calls, the graph routes to END and the user sees
the raw reasoning as the "response."

This middleware runs in ``after_model`` and detects reasoning-only AIMessages:
  1. Content matches ``additional_kwargs.reasoning_content`` (exact match).
  2. Content has no tool_calls and looks like internal reasoning (heuristic).

When detected, the reasoning AIMessage is **removed** from history and a
HumanMessage nudge is appended to push the model to actually act.  A retry
counter prevents infinite loops.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.types import hook_config
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

logger = logging.getLogger("deepagents.reasoning_filter")

MAX_REASONING_RETRIES = 2

# Patterns that indicate the model is reasoning/planning instead of responding.
# These fire only when there are NO tool_calls — if the model called a tool,
# any surrounding text is fine.
_REASONING_PATTERNS = re.compile(
    r"(?i)"
    r"(?:^|\n)\s*(?:"
    r"(?:Let me (?:check|search|try|look|examine|see|first|find|read|get|use|call|query|attempt))"
    r"|(?:I (?:need to|should|will|can|must|want to|have to) )"
    r"|(?:Now (?:I (?:need|should|will|can)|let me))"
    r"|(?:First,? (?:I(?:'ll| need| should| will)|let me))"
    r"|(?:I(?:'ll| will) (?:now |then |also |first )?(?:check|search|try|look|examine|use|call|query|read|get|find))"
    r"|(?:(?:I )?(?:don't |do not )?see (?:any |that |evidence |confirmation ))"
    r"|(?:Based on (?:my |the )?(?:search|analysis|review|check|examination))"
    r"|(?:(?:To|In order to) (?:answer|check|verify|confirm|find|do|complete|accomplish) )"
    r"|(?:The memory (?:shows|indicates|contains|has|suggests))"
    r")"
)

# Minimum length for heuristic detection — very short messages are likely real answers
_MIN_REASONING_LENGTH = 200


def _has_reasoning_kwargs(msg: AIMessage) -> bool:
    """Check if additional_kwargs contains reasoning that matches content."""
    additional = msg.additional_kwargs or {}
    reasoning = additional.get("reasoning_content") or additional.get("reasoning") or ""
    if not reasoning:
        return False
    content = msg.content
    if isinstance(content, str) and content.strip() == reasoning.strip():
        return True
    return False


def _looks_like_reasoning(msg: AIMessage) -> bool:
    """Heuristic: content reads like internal reasoning, not a user-facing response.

    Only triggers when:
    - No tool_calls
    - Content is a string (not blocks)
    - Content is long enough to be reasoning (>200 chars)
    - Content matches reasoning language patterns
    - Content does NOT look like a real answer (no direct address to user)
    """
    if msg.tool_calls:
        return False

    content = msg.content
    if not isinstance(content, str) or len(content.strip()) < _MIN_REASONING_LENGTH:
        return False

    text = content.strip()

    # If it starts with or heavily contains reasoning patterns
    matches = list(_REASONING_PATTERNS.finditer(text))
    if not matches:
        return False

    first_match_pos = matches[0].start()

    # 3+ reasoning patterns anywhere = chain-of-thought regardless of position
    if len(matches) >= 3:
        return True

    # If the text starts with a reasoning pattern and is long, likely reasoning
    if first_match_pos < 50 and len(text) > 400:
        return True

    # 2 patterns in the first half of text
    if len(matches) >= 2 and matches[1].start() < len(text) // 2:
        return True

    return False


def _is_reasoning_only(msg: AIMessage) -> bool:
    """Return True if the message content is just the model's reasoning."""
    if msg.tool_calls:
        return False

    # Exact match: content == reasoning_content
    if _has_reasoning_kwargs(msg):
        return True

    # Heuristic: content reads like reasoning
    if _looks_like_reasoning(msg):
        return True

    return False


class ReasoningFilterMiddleware(AgentMiddleware):
    """Strips reasoning-as-content and retries the model call.

    Prevents NVIDIA Nemotron (and similar models) from surfacing internal
    chain-of-thought as the final response.  When reasoning is detected,
    the AI message is removed and a HumanMessage nudge is injected to
    push the model to act.
    """

    def __init__(self, max_retries: int = MAX_REASONING_RETRIES) -> None:
        self._max_retries = max_retries
        self._consecutive_reasoning: int = 0

    @hook_config(can_jump_to=["model"])
    def after_model(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:  # noqa: ARG002
        messages = state["messages"]
        if not messages:
            return None

        last = messages[-1]
        if not isinstance(last, AIMessage):
            return None

        if not _is_reasoning_only(last):
            self._consecutive_reasoning = 0
            return None

        self._consecutive_reasoning += 1
        logger.warning(
            "Reasoning-only AIMessage detected (attempt %d/%d): %.200s",
            self._consecutive_reasoning,
            self._max_retries,
            str(last.content)[:200],
        )

        if self._consecutive_reasoning > self._max_retries:
            # Give up — strip the reasoning content so it doesn't leak, end the turn.
            logger.warning(
                "Max reasoning retries (%d) exceeded — stripping content and ending.",
                self._max_retries,
            )
            self._consecutive_reasoning = 0
            stripped = last.model_copy(update={"content": ""})
            return {"messages": [*messages[:-1], stripped]}

        # Remove the reasoning AIMessage entirely and add a HumanMessage nudge.
        # Using HumanMessage (not modifying AIMessage content) so:
        # 1. The reasoning text never reaches the streaming output
        # 2. The model sees a clear instruction to act
        logger.info("Removing reasoning and nudging model (retry %d)", self._consecutive_reasoning)
        nudge = HumanMessage(
            content=(
                "[SYSTEM] You just output reasoning instead of acting. "
                "Do NOT explain what you plan to do. Execute the next action "
                "immediately using a tool call, or give a final answer to the user."
            )
        )
        return {
            "messages": [*messages[:-1], nudge],
            "jump_to": "model",
        }

    async def aafter_model(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        return self.after_model(state, runtime)
