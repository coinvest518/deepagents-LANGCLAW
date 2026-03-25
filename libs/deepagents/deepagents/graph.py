"""Deep Agents come with planning, filesystem, and subagents."""

import os
from collections.abc import Callable, Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware, InterruptOnConfig, TodoListMiddleware
from langchain.agents.middleware.types import AgentMiddleware
from langchain.agents.structured_output import ResponseFormat
try:
    from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware as _AnthropicCachingMiddleware
    _HAS_ANTHROPIC = True
except ImportError:
    _AnthropicCachingMiddleware = None  # type: ignore[assignment, misc]
    _HAS_ANTHROPIC = False
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langgraph.cache.base import BaseCache
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.types import Checkpointer

from deepagents._models import resolve_model
from deepagents.backends import StateBackend
from deepagents.backends.protocol import BackendFactory, BackendProtocol
from deepagents.middleware.async_subagents import AsyncSubAgent, AsyncSubAgentMiddleware
from deepagents.middleware.filesystem import FilesystemMiddleware
from deepagents.middleware.memory import MemoryMiddleware
from deepagents.middleware.loop_detection import LoopDetectionMiddleware
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from deepagents.middleware.skills import SkillsMiddleware
from deepagents.middleware.subagents import (
    GENERAL_PURPOSE_SUBAGENT,
    CompiledSubAgent,
    SubAgent,
    SubAgentMiddleware,
)
from deepagents.middleware.summarization import create_summarization_middleware

BASE_AGENT_PROMPT = """You are a Deep Agent, an AI assistant that helps users accomplish tasks using tools. You respond with text and tool calls. The user can see your responses and tool outputs in real time.

## Core Behavior

- Be concise and direct. Don't over-explain unless asked.
- NEVER add unnecessary preamble (\"Sure!\", \"Great question!\", \"I'll now...\").
- Don't say \"I'll now do X\" — just do it.
- If the request is ambiguous, ask questions before acting.
- If asked how to approach something, explain first, then act.

## Professional Objectivity

- Prioritize accuracy over validating the user's beliefs
- Disagree respectfully when the user is incorrect
- Avoid unnecessary superlatives, praise, or emotional validation

## Doing Tasks

When the user asks you to do something:

1. **Understand first** — read relevant files, check existing patterns. Quick but thorough — gather enough evidence to start, then iterate.
2. **Act** — implement the solution. Work quickly but accurately.
3. **Verify** — check your work against what was asked, not against your own output. Your first attempt is rarely correct — iterate.

Keep working until the task is fully complete. Don't stop partway and explain what you would do — just do it. Only yield back to the user when the task is done or you're genuinely blocked.

**When you receive tool results:**
- Once a tool returns data, present it to the user. Do NOT call the same tool again unless the user asks for different data.
- Never call the same tool with the same arguments more than once — you already have the result.
- If the data is incomplete or truncated, work with what you have. Do not retry.

**When things go wrong:**
- If something fails repeatedly, stop and analyze *why* — don't keep retrying the same approach.
- If you're blocked, tell the user what's wrong and ask for guidance.

## Progress Updates

For longer tasks, provide brief progress updates at reasonable intervals — a concise sentence recapping what you've done and what's next."""  # noqa: E501


def _attach_fallbacks(model: BaseChatModel) -> BaseChatModel:
    """Wrap *model* with fallback providers so a 429/5xx doesn't crash the run.

    Resolves all available providers (from env keys) except the one already
    selected, and attaches them as fallbacks via ``with_fallbacks()``.
    """
    import os
    import logging as _logging
    _logger = _logging.getLogger(__name__)

    _ALL_SPECS: list[tuple[str, str]] = [
        ("MISTRAL_API_KEY",          "mistralai:mistral-large-latest"),
        ("NVIDIA_API_KEY",           "nvidia:meta/llama-3.3-70b-instruct"),
        ("OPENROUTER_API_KEY",       "openrouter:mistralai/mistral-small-3.1-24b-instruct:free"),
        ("CEREBRAS_API_KEY",         "cerebras:llama-3.3-70b"),
        ("HUGGINGFACEHUB_API_TOKEN", "huggingface:Qwen/Qwen2.5-72B-Instruct"),
    ]

    fallbacks: list[BaseChatModel] = []
    for env_var, spec in _ALL_SPECS:
        if not os.environ.get(env_var):
            continue
        try:
            candidate = resolve_model(spec)
            # Skip if this is the same model as primary
            if model_matches_spec(model, spec):
                continue
            fallbacks.append(candidate)
        except Exception:
            continue

    if fallbacks:
        _logger.info("Attached %d fallback model(s) to primary", len(fallbacks))
        return model.with_fallbacks(fallbacks)  # type: ignore[return-value]
    return model


def get_default_model() -> BaseChatModel:
    """Get the default model for deep agents.

    Auto-detects the best available model ranked by **tool-calling reliability**,
    not just quota size.  Models that reliably follow tool schemas and know when
    to stop calling tools are prioritised over high-quota but weaker models.

    Returns:
        A `BaseChatModel` instance.
    """
    import os

    # Priority: reliable direct-API providers first (own rate limits),
    # then free-tier proxies (shared rate limits, can 429 easily).
    # fmt: off
    _CANDIDATES: list[tuple[str, str]] = [
        # (env_var,                   model_spec)
        # --- Direct API keys = own rate limit, most reliable ---
        ("MISTRAL_API_KEY",          "mistralai:mistral-large-latest"),               # good native tool calling, 50k TPM
        ("NVIDIA_API_KEY",           "nvidia:meta/llama-3.3-70b-instruct"),           # decent tools, 400k TPM free
        # --- Free-tier proxies (shared rate limits, can 429) ---
        ("OPENROUTER_API_KEY",       "openrouter:mistralai/mistral-small-3.1-24b-instruct:free"),
        ("CEREBRAS_API_KEY",         "cerebras:llama-3.3-70b"),                       # fast, moderate tool calling
        ("HUGGINGFACEHUB_API_TOKEN", "huggingface:Qwen/Qwen2.5-72B-Instruct"),       # fallback
        # --- Direct premium keys (if added later) ---
        ("ANTHROPIC_API_KEY",        "anthropic:claude-sonnet-4-6"),
        ("OPENAI_API_KEY",           "openai:gpt-4o"),
        ("GOOGLE_API_KEY",           "google_genai:gemini-2.0-flash"),
    ]
    # fmt: on

    import logging as _logging
    _logger = _logging.getLogger(__name__)

    available: list[BaseChatModel] = []
    for env_var, spec in _CANDIDATES:
        if os.environ.get(env_var):
            try:
                available.append(resolve_model(spec))
                _logger.info("Model available: %s", spec)
            except Exception:
                _logger.warning("Model failed to resolve: %s", spec, exc_info=True)

    if not available:
        msg = (
            "No LLM API key found. Set one of: MISTRAL_API_KEY, NVIDIA_API_KEY, "
            "OPENROUTER_API_KEY, CEREBRAS_API_KEY, HUGGINGFACEHUB_API_TOKEN."
        )
        raise RuntimeError(msg)

    # Single model — return as-is.  Multiple — wrap with fallbacks so a 429
    # or transient error on the primary automatically tries the next provider.
    primary = available[0]
    if len(available) > 1:
        _logger.info(
            "Model with %d fallback(s): primary=%s",
            len(available) - 1, type(primary).__name__,
        )
        return primary.with_fallbacks(available[1:])  # type: ignore[return-value]
    return primary


def create_deep_agent(  # noqa: C901, PLR0912  # Complex graph assembly logic with many conditional branches
    model: str | BaseChatModel | None = None,
    tools: Sequence[BaseTool | Callable | dict[str, Any]] | None = None,
    *,
    system_prompt: str | SystemMessage | None = None,
    middleware: Sequence[AgentMiddleware] = (),
    subagents: Sequence[SubAgent | CompiledSubAgent] | None = None,
    async_subagents: list[AsyncSubAgent] | None = None,
    skills: list[str] | None = None,
    memory: list[str] | None = None,
    response_format: ResponseFormat | None = None,
    context_schema: type[Any] | None = None,
    checkpointer: Checkpointer | None = None,
    store: BaseStore | None = None,
    backend: BackendProtocol | BackendFactory | None = None,
    interrupt_on: dict[str, bool | InterruptOnConfig] | None = None,
    debug: bool = False,
    name: str | None = None,
    cache: BaseCache | None = None,
) -> CompiledStateGraph:
    """Create a deep agent.

    !!! warning "Deep agents require a LLM that supports tool calling!"

    By default, this agent has access to the following tools:

    - `write_todos`: manage a todo list
    - `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`: file operations
    - `execute`: run shell commands
    - `task`: call subagents

    The `execute` tool allows running shell commands if the backend implements `SandboxBackendProtocol`.
    For non-sandbox backends, the `execute` tool will return an error message.

    Args:
        model: The model to use.

            Defaults to `claude-sonnet-4-6`.

            Use the `provider:model` format (e.g., `openai:gpt-5`) to quickly switch between models.

            If an `openai:` model is used, the agent will use the OpenAI
            Responses API by default. To use OpenAI chat completions instead,
            initialize the model with
            `init_chat_model("openai:...", use_responses_api=False)` and pass
            the initialized model instance here. To disable data retention with
            the Responses API, use
            `init_chat_model("openai:...", use_responses_api=True, store=False, include=["reasoning.encrypted_content"])`
            and pass the initialized model instance here.
        tools: The tools the agent should have access to.

            In addition to custom tools you provide, deep agents include built-in tools for planning,
            file management, and subagent spawning.
        system_prompt: Custom system instructions to prepend before the base deep agent
            prompt.

            If a string, it's concatenated with the base prompt.
        middleware: Additional middleware to apply after the standard middleware stack
            (`TodoListMiddleware`, `FilesystemMiddleware`, `SubAgentMiddleware`,
            `SummarizationMiddleware`, `AnthropicPromptCachingMiddleware`,
            `PatchToolCallsMiddleware`).
        subagents: The subagents to use.

            Each subagent should be a `dict` with the following keys:

            - `name`
            - `description` (used by the main agent to decide whether to call the sub agent)
            - `system_prompt` (used as the system prompt in the subagent)
            - (optional) `tools`
            - (optional) `model` (either a `LanguageModelLike` instance or `dict` settings)
            - (optional) `middleware` (list of `AgentMiddleware`)
        async_subagents: Optional list of async subagent specs for remote LangGraph servers.

            Each spec should be an `AsyncSubAgent` dict with `name`, `description`,
            and `graph_id`. Optionally include `url` for remote deployments (omit
            for ASGI transport). Async subagents run as background jobs with tools
            for launching, checking, updating, cancelling, and listing jobs.
        skills: Optional list of skill source paths (e.g., `["/skills/user/", "/skills/project/"]`).

            Paths must be specified using POSIX conventions (forward slashes) and are relative
            to the backend's root. When using `StateBackend` (default), provide skill files via
            `invoke(files={...})`. With `FilesystemBackend`, skills are loaded from disk relative
            to the backend's `root_dir`. Later sources override earlier ones for skills with the
            same name (last one wins).
        memory: Optional list of memory file paths (`AGENTS.md` files) to load
            (e.g., `["/memory/AGENTS.md"]`).

            Display names are automatically derived from paths.

            Memory is loaded at agent startup and added into the system prompt.
        response_format: A structured output response format to use for the agent.
        context_schema: The schema of the deep agent.
        checkpointer: Optional `Checkpointer` for persisting agent state between runs.
        store: Optional store for persistent storage (required if backend uses `StoreBackend`).
        backend: Optional backend for file storage and execution.

            Pass either a `Backend` instance or a callable factory like `lambda rt: StateBackend(rt)`.
            For execution support, use a backend that implements `SandboxBackendProtocol`.
        interrupt_on: Mapping of tool names to interrupt configs.

            Pass to pause agent execution at specified tool calls for human approval or modification.

            Example: `interrupt_on={"edit_file": True}` pauses before every edit.
        debug: Whether to enable debug mode. Passed through to `create_agent`.
        name: The name of the agent. Passed through to `create_agent`.
        cache: The cache to use for the agent. Passed through to `create_agent`.

    Returns:
        A configured deep agent.
    """
    if model is None:
        model = get_default_model()  # already has fallbacks built in
    else:
        model = resolve_model(model)
        # Attach fallbacks from other available providers so a 429 on the
        # primary doesn't kill the entire run.
        model = _attach_fallbacks(model)

    backend = backend if backend is not None else (StateBackend)

    # Build general-purpose subagent with default middleware stack
    gp_middleware: list[AgentMiddleware[Any, Any, Any]] = [
        TodoListMiddleware(),
        FilesystemMiddleware(backend=backend),
        create_summarization_middleware(model, backend),
        *([_AnthropicCachingMiddleware(unsupported_model_behavior="ignore")] if _HAS_ANTHROPIC else []),
        PatchToolCallsMiddleware(),
    ]
    if skills is not None:
        gp_middleware.append(SkillsMiddleware(backend=backend, sources=skills))
    if interrupt_on is not None:
        gp_middleware.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_on))

    # Worker subagent can use a stronger model than the coordinator.
    # Set DA_SUBAGENT_MODEL env var to override (e.g. mistral-large while
    # coordinator runs mistral-small).  Defaults to same model as coordinator.
    _subagent_model_spec = os.environ.get("DA_SUBAGENT_MODEL", "").strip()
    if _subagent_model_spec:
        try:
            worker_model = resolve_model(_subagent_model_spec)
        except Exception:
            import logging as _log
            _log.getLogger(__name__).warning(
                "DA_SUBAGENT_MODEL '%s' failed to resolve, falling back to main model",
                _subagent_model_spec,
            )
            worker_model = model
    else:
        worker_model = model

    general_purpose_spec: SubAgent = {  # ty: ignore[missing-typed-dict-key]
        **GENERAL_PURPOSE_SUBAGENT,
        "model": worker_model,
        "tools": tools or [],
        "middleware": gp_middleware,
    }

    # Process user-provided subagents to fill in defaults for model, tools, and middleware
    processed_subagents: list[SubAgent | CompiledSubAgent] = []
    for spec in subagents or []:
        if "runnable" in spec:
            # CompiledSubAgent - use as-is
            processed_subagents.append(spec)
        else:
            # SubAgent - fill in defaults and prepend base middleware
            subagent_model = spec.get("model", model)
            try:
                subagent_model = resolve_model(subagent_model)
            except Exception:
                import logging as _log
                _log.getLogger(__name__).warning(
                    "Subagent '%s' model failed to resolve, using main model",
                    spec.get("name", "unknown"),
                )
                subagent_model = model

            # Build middleware: base stack + skills (if specified) + user's middleware
            subagent_middleware: list[AgentMiddleware[Any, Any, Any]] = [
                TodoListMiddleware(),
                FilesystemMiddleware(backend=backend),
                create_summarization_middleware(subagent_model, backend),
                *([_AnthropicCachingMiddleware(unsupported_model_behavior="ignore")] if _HAS_ANTHROPIC else []),
                PatchToolCallsMiddleware(),
            ]
            subagent_skills = spec.get("skills")
            if subagent_skills:
                subagent_middleware.append(SkillsMiddleware(backend=backend, sources=subagent_skills))
            subagent_middleware.extend(spec.get("middleware", []))

            processed_spec: SubAgent = {  # ty: ignore[missing-typed-dict-key]
                **spec,
                "model": subagent_model,
                "tools": spec.get("tools", tools or []),
                "middleware": subagent_middleware,
            }
            processed_subagents.append(processed_spec)

    if any(spec["name"] == GENERAL_PURPOSE_SUBAGENT["name"] for spec in processed_subagents):
        # If an agent with general purpose name already exists in subagents, then don't add it
        # This is how you overwrite/configure general purpose subagent
        all_subagents: list[SubAgent | CompiledSubAgent] = processed_subagents
    else:
        # Otherwise - add it!
        all_subagents = [general_purpose_spec, *processed_subagents]

    # Build main agent middleware stack
    deepagent_middleware: list[AgentMiddleware[Any, Any, Any]] = [
        TodoListMiddleware(),
    ]
    if memory is not None:
        deepagent_middleware.append(MemoryMiddleware(backend=backend, sources=memory))
    if skills is not None:
        deepagent_middleware.append(SkillsMiddleware(backend=backend, sources=skills))
    deepagent_middleware.extend(
        [
            FilesystemMiddleware(backend=backend),
            SubAgentMiddleware(
                backend=backend,
                subagents=all_subagents,
            ),
            create_summarization_middleware(model, backend),
            *([_AnthropicCachingMiddleware(unsupported_model_behavior="ignore")] if _HAS_ANTHROPIC else []),
            LoopDetectionMiddleware(),
            PatchToolCallsMiddleware(),
        ]
    )

    if async_subagents:
        deepagent_middleware.append(AsyncSubAgentMiddleware(async_subagents=async_subagents))

    if middleware:
        deepagent_middleware.extend(middleware)
    if interrupt_on is not None:
        deepagent_middleware.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_on))

    # Combine system_prompt with BASE_AGENT_PROMPT
    if system_prompt is None:
        final_system_prompt: str | SystemMessage = BASE_AGENT_PROMPT
    elif isinstance(system_prompt, SystemMessage):
        final_system_prompt = SystemMessage(content_blocks=[*system_prompt.content_blocks, {"type": "text", "text": f"\n\n{BASE_AGENT_PROMPT}"}])
    else:
        # String: simple concatenation
        final_system_prompt = system_prompt + "\n\n" + BASE_AGENT_PROMPT

    return create_agent(
        model,
        system_prompt=final_system_prompt,
        tools=tools,
        middleware=deepagent_middleware,
        response_format=response_format,
        context_schema=context_schema,
        checkpointer=checkpointer,
        store=store,
        debug=debug,
        name=name,
        cache=cache,
    ).with_config(
        {
            "recursion_limit": 50,
            "metadata": {
                "ls_integration": "deepagents",
            },
        }
    )
