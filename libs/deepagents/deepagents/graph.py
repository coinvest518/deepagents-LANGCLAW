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

from deepagents._models import model_matches_spec, resolve_model
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

BASE_AGENT_PROMPT = """You are the FDWA AI Agent — the core execution engine for Daniel's Futuristic Digital Wealth Agency. You handle ALL real tasks: API calls, data lookups, web searches, file operations, emails, social media, and more.

## How to Think Before Acting

Before EVERY request, classify it into one of these tiers:

**Tier 1 — Direct answer (0 tool calls):**
Questions you can answer from context, memory, or general knowledge.
→ Just answer. No tools needed.

**Tier 2 — Quick lookup (1-2 tool calls):**
Weather, stock prices, simple web searches, single API calls, checking one email, reading one file.
→ Call the tool ONCE, present the result. Done. Do NOT spawn subagents.

**Tier 3 — Standard task (3-6 tool calls):**
Send an email, create a spreadsheet, post to social media, search + summarize.
→ Execute directly with your tools. Do NOT spawn subagents unless there are multiple independent tasks.

**Tier 4 — Complex/multi-part (7+ tool calls):**
Deep research across multiple sources, comparing datasets, multi-step workflows.
→ Consider spawning subagents ONLY if tasks are truly independent and parallel.

**The golden rule: Use the MINIMUM number of calls to satisfy the request. A weather check is 1 web_search call, not a research project.**

## Core Behavior

- Be concise and direct. No preamble ("Sure!", "Great question!", "I'll now...").
- Don't narrate what you're about to do — just do it.
- If the request is ambiguous, ask ONE clarifying question, then act.

## Pre-Connected Services (use DIRECTLY via composio — never web search for how)

Gmail, GitHub, Google Sheets, Google Drive, Google Docs, Google Analytics, Google Calendar, LinkedIn, Twitter/X, Telegram, Instagram, Facebook, YouTube, Slack, Notion, Dropbox, SerpAPI.

When the user mentions ANY of these → read the skill docs → call `composio_action` directly. Do NOT search the web for "how to connect to Gmail" — you are already authenticated.

## Tool Selection (in order of preference)

| Need | Tool | NOT this |
|------|------|----------|
| Quick fact/weather/news | `web_search` (1 call) | Subagent research |
| Gmail/Sheets/GitHub/etc. | `composio_action` | Web search about the service |
| Read a URL | `fetch_url` | Web search for the URL content |
| Past conversations/facts | `search_memory` | Guessing or asking user |
| Save important info | `save_memory` | Forgetting it |
| Unknown Composio params | `composio_get_schema` | Trial and error |

## Self-Correction Rules

1. **Never repeat a failed call** with the same arguments. Change your approach.
2. If a Composio action 404s → the slug is wrong. Read the skill docs for correct slugs.
3. If a Composio action fails with param errors → call `composio_get_schema("ACTION_NAME")` first.
4. If you get wrong data (wrong folder, wrong filter) → examine the result metadata, adjust params.
5. If blocked after 2 attempts → tell the user what's wrong and ask for guidance.
6. Track what you've tried. Never repeat a rejected approach.

## Memory

- At the START of a task, check `search_memory` if the user references past work or preferences.
- After completing a task or learning something new, `save_memory` to persist it.
- When the user says "remember" → save immediately. When they say "recall" → search immediately.

## Progress Updates

For tasks taking more than a few seconds, give ONE brief status line. Not a play-by-play — just what you're doing and what's next.

## Subagents — Use Sparingly

Spawn a subagent ONLY when:
- You have 2+ truly independent research topics to investigate in parallel
- A task needs deep isolated context (large codebase analysis, long document processing)
- The user explicitly asks for deep research

Do NOT spawn subagents for: weather, email, posting, simple lookups, single-service tasks, or anything under 5 tool calls."""  # noqa: E501


def _all_available_specs() -> list[tuple[str, str]]:
    """Return (env_var, model_spec) pairs for every provider with a key present.

    Order matters: subagent rotation picks from this list.  Best tool-callers
    first so subagents get the strongest models for their tasks.
    """
    _ALL_SPECS: list[tuple[str, str]] = [
        ("NVIDIA_API_KEY",           "nvidia:meta/llama-3.3-70b-instruct"),     # 400k TPM, primary for all
        ("CEREBRAS_API_KEY",         "cerebras:llama-3.3-70b"),                 # 600k TPM, very fast
        ("OPENROUTER_API_KEY",       "openrouter:mistralai/mistral-small-3.1-24b-instruct:free"),
        ("HUGGINGFACEHUB_API_TOKEN", "huggingface:Qwen/Qwen2.5-72B-Instruct"),
        ("MISTRAL_API_KEY",          "mistralai:mistral-large-latest"),          # 50k TPM — too small for main, last resort
    ]
    return [(ev, spec) for ev, spec in _ALL_SPECS if os.environ.get(ev)]


def _attach_fallbacks(model: BaseChatModel) -> BaseChatModel:
    """Wrap *model* with fallback providers so a 429/5xx doesn't crash the run.

    Resolves all available providers (from env keys) except the one already
    selected, and attaches them as fallbacks via ``with_fallbacks()``.
    """
    import logging as _logging
    _logger = _logging.getLogger(__name__)

    fallbacks: list[BaseChatModel] = []
    for _env_var, spec in _all_available_specs():
        try:
            candidate = resolve_model(spec)
            if model_matches_spec(model, spec):
                continue
            fallbacks.append(candidate)
        except Exception:
            continue

    if fallbacks:
        _logger.info("Attached %d fallback model(s) to primary", len(fallbacks))
        return model.with_fallbacks(fallbacks)  # type: ignore[return-value]
    return model


def _pick_subagent_model(main_model: BaseChatModel, index: int) -> BaseChatModel:
    """Pick a model for subagent *index* that uses a DIFFERENT provider than main.

    Rotates through available providers so subagents spread across different
    rate-limit buckets instead of all hammering the same provider as main.
    """
    import logging as _logging
    _logger = _logging.getLogger(__name__)

    available = _all_available_specs()
    if len(available) <= 1:
        return main_model  # only one provider, nothing to rotate

    # Filter out the main model's provider
    others = [(ev, spec) for ev, spec in available if not model_matches_spec(main_model, spec)]
    if not others:
        others = available  # all same provider somehow, just use them

    # Round-robin across non-main providers
    _, spec = others[index % len(others)]
    try:
        sub_model = resolve_model(spec)
        _logger.info("Subagent[%d] using %s (different provider from main)", index, spec)
        return sub_model
    except Exception:
        _logger.warning("Subagent[%d] failed to resolve %s, using main model", index, spec)
        return main_model


def get_default_model() -> BaseChatModel:
    """Get the default model for the main agent.

    Picks the best model for the **main agent** — prioritised by quota size
    (larger TPM = less rate limiting during multi-tool runs) balanced against
    tool-calling quality.  Direct-API providers before free-tier proxies.

    NVIDIA (400k TPM) is preferred over Mistral (50k TPM) as main agent
    because the main agent makes the most calls.  Mistral is better used
    for subagents where its strong tool-calling shines on fewer calls.

    Returns:
        A `BaseChatModel` instance.
    """
    # fmt: off
    # Priority for MAIN agent: highest quota + direct API first
    _CANDIDATES: list[tuple[str, str]] = [
        # --- Direct API, high quota — best for main agent ---
        ("NVIDIA_API_KEY",           "nvidia:meta/llama-3.3-70b-instruct"),           # 400k TPM free
        ("CEREBRAS_API_KEY",         "cerebras:llama-3.3-70b"),                       # 600k TPM, fast
        # --- Free-tier proxies ---
        ("OPENROUTER_API_KEY",       "openrouter:mistralai/mistral-small-3.1-24b-instruct:free"),
        ("HUGGINGFACEHUB_API_TOKEN", "huggingface:Qwen/Qwen2.5-72B-Instruct"),       # fallback
        # --- Direct API, small quota — avoid for main agent ---
        ("MISTRAL_API_KEY",          "mistralai:mistral-large-latest"),               # 50k TPM too small for main
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
            "No LLM API key found. Set one of: NVIDIA_API_KEY, MISTRAL_API_KEY, "
            "OPENROUTER_API_KEY, CEREBRAS_API_KEY, HUGGINGFACEHUB_API_TOKEN."
        )
        raise RuntimeError(msg)

    return available[0]


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
        model = get_default_model()  # returns first available BaseChatModel
    else:
        model = resolve_model(model)

    # Build a fallback-wrapped model for create_agent() so a 429 on the
    # primary automatically tries the next provider.  Keep the raw
    # BaseChatModel for middleware that type-checks it.
    model_with_fallbacks = _attach_fallbacks(model)

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

    # Worker subagent uses a DIFFERENT provider than main to avoid rate-limit
    # competition.  DA_SUBAGENT_MODEL env var can force a specific model.
    _subagent_model_spec = os.environ.get("DA_SUBAGENT_MODEL", "").strip()
    if _subagent_model_spec:
        try:
            worker_model = resolve_model(_subagent_model_spec)
        except Exception:
            import logging as _log
            _log.getLogger(__name__).warning(
                "DA_SUBAGENT_MODEL '%s' failed to resolve, using different provider",
                _subagent_model_spec,
            )
            worker_model = _pick_subagent_model(model, index=0)
    else:
        # Auto-pick a different provider so subagent doesn't compete with main
        worker_model = _pick_subagent_model(model, index=0)

    general_purpose_spec: SubAgent = {  # ty: ignore[missing-typed-dict-key]
        **GENERAL_PURPOSE_SUBAGENT,
        "model": worker_model,
        "tools": tools or [],
        "middleware": gp_middleware,
    }

    # Process user-provided subagents to fill in defaults for model, tools, and middleware
    processed_subagents: list[SubAgent | CompiledSubAgent] = []
    _subagent_idx = 1  # 0 is general-purpose, start custom subagents at 1
    for spec in subagents or []:
        if "runnable" in spec:
            # CompiledSubAgent - use as-is
            processed_subagents.append(spec)
        else:
            # SubAgent - fill in defaults and prepend base middleware
            if spec.get("model"):
                try:
                    subagent_model = resolve_model(spec["model"])
                except Exception:
                    import logging as _log
                    _log.getLogger(__name__).warning(
                        "Subagent '%s' model failed to resolve, auto-picking provider",
                        spec.get("name", "unknown"),
                    )
                    subagent_model = _pick_subagent_model(model, index=_subagent_idx)
            else:
                # No explicit model — auto-pick a different provider
                subagent_model = _pick_subagent_model(model, index=_subagent_idx)
            _subagent_idx += 1

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
        model_with_fallbacks,
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
