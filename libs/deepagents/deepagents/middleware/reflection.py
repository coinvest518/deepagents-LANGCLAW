"""Self-critique middleware that reviews and optionally improves final agent responses.

After the agent produces a final answer (a model response with no tool calls),
this middleware runs a single lightweight reflection pass:

1. Ask the model to review its own response.
2. If the model replies "RESPONSE_OK", return the original response unchanged.
3. Otherwise treat the model's reply as an improved answer and return it.

The extra model call is skipped when:
- The response contains tool calls (not a final answer yet).
- The ``<reflection_done>`` marker is already present in the conversation
  (prevents an infinite loop on the second pass).
- ``max_tokens_to_reflect`` threshold is not met (skips reflection for very
  short replies that likely don't benefit from a review).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated, Any, NotRequired

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from langchain_core.messages import AIMessage
    from langchain_core.runnables import RunnableConfig
    from langgraph.runtime import Runtime

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ModelRequest,
    ModelResponse,
    PrivateStateAttr,
)

logger = logging.getLogger(__name__)

# Marker injected into the system prompt so a second reflection pass is skipped.
_REFLECTION_DONE_MARKER = "<reflection_done>"

# Prompt sent to the model to review its own response.
_REFLECTION_PROMPT = (
    "Review your previous response carefully. "
    "If it is accurate, complete, and fully addresses the request, reply with exactly: RESPONSE_OK\n"
    "If you can meaningfully improve it, provide the improved response directly "
    "(no preamble, no explanation of what changed)."
)


class _ReflectionState(AgentState):
    reflection_count: NotRequired[Annotated[int, PrivateStateAttr]]


class ReflectionMiddleware(AgentMiddleware[_ReflectionState, Any, Any]):
    """Run a single self-critique pass after each final agent response.

    Args:
        min_content_length: Minimum character length of the response content
            before reflection is attempted. Short replies (greetings, one-liners)
            are returned as-is. Defaults to 100.
    """

    state_schema = _ReflectionState

    def __init__(self, *, min_content_length: int = 100) -> None:
        self.min_content_length = min_content_length

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_final_response(self, response: ModelResponse) -> bool:
        """Return True when the response has no tool calls (agent is done)."""
        for msg in response.result:
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                return False
        return True

    def _already_reflected(self, request: ModelRequest) -> bool:
        """Return True when the reflection marker is present in the conversation."""
        system = request.system_message
        if system is not None:
            content = getattr(system, "content", "") or ""
            if _REFLECTION_DONE_MARKER in content:
                return True
        return any(
            _REFLECTION_DONE_MARKER in str(getattr(m, "content", ""))
            for m in request.messages
        )

    def _get_response_text(self, response: ModelResponse) -> str:
        """Extract plain text from the first AIMessage in the response."""
        for msg in response.result:
            content = getattr(msg, "content", None)
            if content and isinstance(content, str):
                return content
            if content and isinstance(content, list):
                # Content blocks (Anthropic style)
                parts = [
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in content
                ]
                return "".join(parts)
        return ""

    # ------------------------------------------------------------------
    # Async wrap
    # ------------------------------------------------------------------

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Run handler, then optionally run a single reflection pass."""
        response = await handler(request)

        # Skip reflection when tools are still being called.
        if not self._is_final_response(response):
            return response

        # Skip when this is already the reflection pass.
        if self._already_reflected(request):
            return response

        # Skip for very short responses.
        response_text = self._get_response_text(response)
        if len(response_text) < self.min_content_length:
            return response

        # Build the reflection conversation: full history + draft response + review ask.
        from langchain_core.messages import HumanMessage

        reflection_messages = [
            *(request.messages or []),
            *response.result,
            HumanMessage(content=_REFLECTION_PROMPT),
        ]

        try:
            critique: AIMessage = await request.model.ainvoke(reflection_messages)
            critique_text: str = getattr(critique, "content", "") or ""
        except Exception:
            logger.debug("ReflectionMiddleware: critique call failed", exc_info=True)
            return response

        # "RESPONSE_OK" means the model is happy with its answer.
        if not critique_text or "RESPONSE_OK" in critique_text.upper():
            logger.debug("ReflectionMiddleware: response approved as-is")
            return response

        # The model produced an improved answer — wrap it in a marked request and
        # call the handler once more so the framework processes it normally.
        logger.debug("ReflectionMiddleware: applying improved response")
        from langchain_core.messages import HumanMessage, SystemMessage

        marked_system_content = (
            (
                getattr(request.system_message, "content", "") or ""
                if request.system_message
                else ""
            )
            + f"\n{_REFLECTION_DONE_MARKER}"
        )
        marked_system = SystemMessage(content=marked_system_content)

        # Append the critique as a hint for the second pass.
        hint = HumanMessage(
            content=(
                f"Reflection note (use this to improve your reply, don't mention it): "
                f"{critique_text}"
            )
        )
        augmented_request = request.override(
            system_message=marked_system,
            messages=[*(request.messages or []), hint],
        )

        try:
            return await handler(augmented_request)
        except Exception:
            logger.debug(
                "ReflectionMiddleware: second-pass handler failed, using original",
                exc_info=True,
            )
            return response

    # Sync fallback — delegates to async via asyncio.run (only used in sync contexts).
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Sync pass-through — reflection runs async only."""
        return handler(request)