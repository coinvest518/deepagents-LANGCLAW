# ruff: noqa: E501  # Long prompt strings in MEMORY_SYSTEM_PROMPT
"""Middleware for loading agent memory/context from AGENTS.md files.

This module implements support for the AGENTS.md specification (https://agents.md/),
loading memory/context from configurable sources and injecting into the system prompt.

## Overview

AGENTS.md files provide project-specific context and instructions to help AI agents
work effectively. Unlike skills (which are on-demand workflows), memory is always
loaded and provides persistent context.

## Usage

```python
from deepagents import MemoryMiddleware
from deepagents.backends.filesystem import FilesystemBackend

# Security: FilesystemBackend allows reading/writing from the entire filesystem.
# Either ensure the agent is running within a sandbox OR add human-in-the-loop (HIL)
# approval to file operations.
backend = FilesystemBackend(root_dir="/")

middleware = MemoryMiddleware(
    backend=backend,
    sources=[
        "~/.deepagents/AGENTS.md",
        "./.deepagents/AGENTS.md",
    ],
)

agent = create_deep_agent(middleware=[middleware])
```

## Memory Sources

Sources are simply paths to AGENTS.md files that are loaded in order and combined.
Multiple sources are concatenated in order, with all content included.
Later sources appear after earlier ones in the combined prompt.

## File Format

AGENTS.md files are standard Markdown with no required structure.
Common sections include:
- Project overview
- Build/test commands
- Code style guidelines
- Architecture notes
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Annotated, Any, NotRequired, TypedDict

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from langchain_core.runnables import RunnableConfig
    from langgraph.runtime import Runtime

    from deepagents.backends.protocol import BACKEND_TYPES, BackendProtocol

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ContextT,
    ModelRequest,
    ModelResponse,
    PrivateStateAttr,
    ResponseT,
)
from langchain.tools import ToolRuntime

from deepagents.middleware._utils import append_to_system_message

logger = logging.getLogger(__name__)


class MemoryState(AgentState):
    """State schema for `MemoryMiddleware`.

    Attributes:
        memory_contents: Dict mapping source paths to their loaded content.
            Marked as private so it's not included in the final agent state.
    """

    memory_contents: NotRequired[Annotated[dict[str, str], PrivateStateAttr]]


class MemoryStateUpdate(TypedDict):
    """State update for `MemoryMiddleware`."""

    memory_contents: dict[str, str]


MEMORY_SYSTEM_PROMPT = """<agent_memory>
{agent_memory}
</agent_memory>

<memory_guidelines>
Memory is loaded from files in your filesystem. Use `edit_file` to save new knowledge.

- Learn from ALL interactions: explicit requests ("remember X") AND implicit signals (corrections, preferences, repeated patterns).
- When you need to remember something, update memory IMMEDIATELY — before responding or calling other tools.
- Capture WHY something is better/worse, not just the specific correction.
- Ask for missing context (IDs, emails) rather than guessing. Save provided info for future use.
- DO save: user preferences, role descriptions, feedback, tool-use context, recurring patterns.
- Do NOT save: transient info, one-time requests, small talk, API keys, passwords, or credentials.
</memory_guidelines>
"""


class MemoryMiddleware(AgentMiddleware[MemoryState, ContextT, ResponseT]):
    """Middleware for loading agent memory from `AGENTS.md` files.

    Loads memory content from configured sources and injects into the system prompt.

    Supports multiple sources that are combined together.

    Args:
        backend: Backend instance or factory function for file operations.
        sources: List of `MemorySource` configurations specifying paths and names.
    """

    state_schema = MemoryState

    def __init__(
        self,
        *,
        backend: BACKEND_TYPES,
        sources: list[str],
    ) -> None:
        """Initialize the memory middleware.

        Args:
            backend: Backend instance or factory function that takes runtime
                     and returns a backend. Use a factory for StateBackend.
            sources: List of memory file paths to load (e.g., `["~/.deepagents/AGENTS.md",
                     "./.deepagents/AGENTS.md"]`).

                     Display names are automatically derived from the paths.

                     Sources are loaded in order.
        """
        self._backend = backend
        self.sources = sources
        self._mem0_store: Any = None
        self._mem0_checked = False

    def _get_backend(self, state: MemoryState, runtime: Runtime, config: RunnableConfig) -> BackendProtocol:
        """Resolve backend from instance or factory.

        Args:
            state: Current agent state.
            runtime: Runtime context for factory functions.
            config: Runnable config to pass to backend factory.

        Returns:
            Resolved backend instance.
        """
        if callable(self._backend):
            # Construct an artificial tool runtime to resolve backend factory
            tool_runtime = ToolRuntime(
                state=state,
                context=runtime.context,
                stream_writer=runtime.stream_writer,
                store=runtime.store,
                config=config,
                tool_call_id=None,
            )
            return self._backend(tool_runtime)  # ty: ignore[call-top-callable, invalid-argument-type]
        return self._backend

    def _format_agent_memory(self, contents: dict[str, str]) -> str:
        """Format memory with locations and contents paired together.

        Args:
            contents: Dict mapping source paths to content.

        Returns:
            Formatted string with location+content pairs wrapped in <agent_memory> tags.
        """
        if not contents:
            return MEMORY_SYSTEM_PROMPT.format(agent_memory="(No memory loaded)")

        sections = [f"{path}\n{contents[path]}" for path in self.sources if contents.get(path)]

        if not sections:
            return MEMORY_SYSTEM_PROMPT.format(agent_memory="(No memory loaded)")

        memory_body = "\n\n".join(sections)
        return MEMORY_SYSTEM_PROMPT.format(agent_memory=memory_body)

    def before_agent(self, state: MemoryState, runtime: Runtime, config: RunnableConfig) -> MemoryStateUpdate | None:  # ty: ignore[invalid-method-override]
        """Load memory content before agent execution (synchronous).

        Loads memory from all configured sources and stores in state.
        Only loads if not already present in state.

        Args:
            state: Current agent state.
            runtime: Runtime context.
            config: Runnable config.

        Returns:
            State update with memory_contents populated.
        """
        # Skip if already loaded
        if "memory_contents" in state:
            return None

        backend = self._get_backend(state, runtime, config)
        contents: dict[str, str] = {}

        results = backend.download_files(list(self.sources))
        for path, response in zip(self.sources, results, strict=True):
            if response.error is not None:
                if response.error == "file_not_found":
                    continue
                msg = f"Failed to download {path}: {response.error}"
                raise ValueError(msg)
            if response.content is not None:
                contents[path] = response.content.decode("utf-8")
                logger.debug("Loaded memory from: %s", path)

        return MemoryStateUpdate(memory_contents=contents)

    async def abefore_agent(self, state: MemoryState, runtime: Runtime, config: RunnableConfig) -> MemoryStateUpdate | None:  # ty: ignore[invalid-method-override]
        """Load memory content before agent execution.

        Loads memory from all configured sources and stores in state.
        Only loads if not already present in state.

        Args:
            state: Current agent state.
            runtime: Runtime context.
            config: Runnable config.

        Returns:
            State update with memory_contents populated.
        """
        # Skip if already loaded
        if "memory_contents" in state:
            return None

        backend = self._get_backend(state, runtime, config)
        contents: dict[str, str] = {}

        results = await backend.adownload_files(list(self.sources))
        for path, response in zip(self.sources, results, strict=True):
            if response.error is not None:
                if response.error == "file_not_found":
                    continue
                msg = f"Failed to download {path}: {response.error}"
                raise ValueError(msg)
            if response.content is not None:
                contents[path] = response.content.decode("utf-8")
                logger.debug("Loaded memory from: %s", path)

        return MemoryStateUpdate(memory_contents=contents)

    def modify_request(self, request: ModelRequest[ContextT]) -> ModelRequest[ContextT]:
        """Inject memory content into the system message.

        Args:
            request: Model request to modify.

        Returns:
            Modified request with memory injected into system message.
        """
        contents = request.state.get("memory_contents", {})
        agent_memory = self._format_agent_memory(contents)

        new_system_message = append_to_system_message(request.system_message, agent_memory)

        return request.override(system_message=new_system_message)

    def wrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], ModelResponse[ResponseT]],
    ) -> ModelResponse[ResponseT]:
        """Wrap model call to inject memory into system prompt.

        Args:
            request: Model request being processed.
            handler: Handler function to call with modified request.

        Returns:
            Model response from handler.
        """
        modified_request = self.modify_request(request)
        return handler(modified_request)

    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
    ) -> ModelResponse[ResponseT]:
        """Async wrap model call to inject memory into system prompt.

        Args:
            request: Model request being processed.
            handler: Async handler function to call with modified request.

        Returns:
            Model response from handler.
        """
        modified_request = self.modify_request(request)
        return await handler(modified_request)

    # ------------------------------------------------------------------
    # Auto-learning hooks — feed each completed turn to Mem0 so facts
    # and preferences are extracted automatically without the agent
    # having to decide to call save_memory explicitly.
    # ------------------------------------------------------------------

    def _get_mem0_store(self) -> Any:
        """Return a cached Mem0Store, or None if MEM0_API_KEY is absent.

        Returns:
            Mem0Store instance or None.
        """
        if not self._mem0_checked:
            self._mem0_checked = True
            if os.environ.get("MEM0_API_KEY"):
                try:
                    from deepagents.store_adapters.mem0_store import Mem0Store
                    self._mem0_store = Mem0Store.from_env()
                    logger.info("MemoryMiddleware: Mem0Store ready for auto-learning")
                except Exception:
                    logger.warning("MemoryMiddleware: Mem0Store init failed", exc_info=True)
        return self._mem0_store

    @staticmethod
    def _get_real_text(msg: Any) -> str:
        """Extract real text from a message, filtering out reasoning content.

        NVIDIA Nemotron (and similar models) can put chain-of-thought reasoning
        into ``content`` and duplicate it in ``additional_kwargs.reasoning_content``.
        We skip that so Mem0 only learns from actual user-facing text.
        """
        content = getattr(msg, "content", "") or ""
        text = content if isinstance(content, str) else " ".join(
            b.get("text", "") if isinstance(b, dict) else str(b)
            for b in content
            if not isinstance(b, dict) or b.get("type", "text") == "text"
        )
        if not text.strip():
            return ""

        # Filter out reasoning-as-content
        additional = getattr(msg, "additional_kwargs", None) or {}
        reasoning = additional.get("reasoning_content") or additional.get("reasoning") or ""
        if reasoning and text.strip() == reasoning.strip():
            return ""

        return text.strip()

    def _extract_last_turn(self, state: MemoryState) -> tuple[str, str] | None:
        """Pull the last user + assistant message pair from state.

        Filters out:
        - Reasoning-as-content (from ``additional_kwargs.reasoning_content``)
        - System nudge messages injected by ReasoningFilterMiddleware
        - Tool messages

        Args:
            state: Current agent state containing messages.

        Returns:
            ``(user_text, assistant_text)`` or ``None`` if either is missing.
        """
        messages = state.get("messages", [])
        user_text = assistant_text = ""
        for msg in reversed(messages):
            role = getattr(msg, "type", None) or getattr(msg, "role", None)
            text = self._get_real_text(msg)
            if not text:
                continue
            if role in ("ai", "assistant") and not assistant_text:
                # Skip AI messages that are just tool calls with no real text
                if getattr(msg, "tool_calls", None):
                    continue
                assistant_text = text
            elif role in ("human", "user") and not user_text:
                # Skip system nudge messages from ReasoningFilterMiddleware
                if text.startswith("[SYSTEM]"):
                    continue
                user_text = text
            if user_text and assistant_text:
                break
        if user_text and assistant_text:
            logger.debug(
                "Auto-learn turn extracted: user=%d chars, assistant=%d chars",
                len(user_text), len(assistant_text),
            )
            return user_text, assistant_text
        logger.debug("Auto-learn: no valid turn found (user=%r, assistant=%r)",
                     bool(user_text), bool(assistant_text))
        return None

    def after_agent(self, state: MemoryState, runtime: Runtime) -> None:  # ty: ignore[invalid-method-override]
        """Auto-learn from the completed turn by feeding it to Mem0.

        Extracts the last user/assistant message pair and calls
        `learn_from_conversation` so Mem0 can extract preferences, facts,
        and context without the agent having to explicitly call `save_memory`.

        This is a best-effort operation — failures are logged and swallowed
        so they never interrupt the agent response.

        Args:
            state: Current agent state after the turn completes.
            runtime: Runtime context (unused but required by interface).
        """
        turn = self._extract_last_turn(state)
        if turn is None:
            logger.info("MemoryMiddleware.after_agent: no turn to learn from")
            return
        store = self._get_mem0_store()
        if store is None:
            logger.info("MemoryMiddleware.after_agent: no Mem0 store (MEM0_API_KEY missing?)")
            return
        user_msg, assistant_msg = turn
        try:
            store.learn_from_conversation(user_msg, assistant_msg)
            logger.info(
                "MemoryMiddleware: auto-learned from turn (user=%d chars, assistant=%d chars)",
                len(user_msg), len(assistant_msg),
            )
        except Exception:
            logger.warning("MemoryMiddleware.after_agent: auto-learn FAILED", exc_info=True)

    async def aafter_agent(self, state: MemoryState, runtime: Runtime) -> None:  # ty: ignore[invalid-method-override]
        """Async auto-learn from the completed turn by feeding it to Mem0.

        Args:
            state: Current agent state after the turn completes.
            runtime: Runtime context (unused but required by interface).
        """
        turn = self._extract_last_turn(state)
        if turn is None:
            logger.info("MemoryMiddleware.aafter_agent: no turn to learn from")
            return
        store = self._get_mem0_store()
        if store is None:
            logger.info("MemoryMiddleware.aafter_agent: no Mem0 store (MEM0_API_KEY missing?)")
            return
        user_msg, assistant_msg = turn
        try:
            await store.alearn_from_conversation(user_msg, assistant_msg)
            logger.info(
                "MemoryMiddleware: async auto-learned from turn (user=%d chars, assistant=%d chars)",
                len(user_msg), len(assistant_msg),
            )
        except Exception:
            logger.warning("MemoryMiddleware.aafter_agent: auto-learn FAILED", exc_info=True)
