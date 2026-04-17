"""Server-side graph entry point for `langgraph dev`.

This module is referenced by the generated `langgraph.json` and exposes the CLI
agent graph as a module-level variable that the LangGraph server can load
and serve.

The graph is created at module import time via `make_graph()`, which reads
configuration from `ServerConfig.from_env()` — the same dataclass the CLI uses
to *write* the configuration via `ServerConfig.to_env()`. This shared schema
ensures the two sides stay in sync.

# workspace-version: 2  (bump to force venv rebuild with updated pyproject extras)
"""

from __future__ import annotations

import atexit
import logging
import os
import sys
import threading
import traceback
from typing import Any

from deepagents_cli._server_config import ServerConfig
from deepagents_cli.project_utils import ProjectContext, get_server_project_context

logger = logging.getLogger(__name__)

# Module-level sandbox state kept alive for the server process lifetime.
_sandbox_cm: Any = None
_sandbox_backend: Any = None


def _build_tools(
    config: ServerConfig,
    project_context: ProjectContext | None,
) -> tuple[list[Any], list[Any] | None]:
    """Assemble the tool list based on server config.

    Loads built-in tools (conditionally including web search when Tavily is
    available) and MCP tools when enabled.

    MCP discovery runs synchronously via `asyncio.run` because this function is
    called during module-level graph construction (before the server's async
    event loop is available).

    Args:
        config: Deserialized server configuration.
        project_context: Resolved project context for MCP discovery.

    Returns:
        Tuple of `(tools, mcp_server_info)`.

    Raises:
        FileNotFoundError: If the MCP config file is not found.
        RuntimeError: If MCP tool loading fails.
    """
    from deepagents_cli.config import settings
    from deepagents_cli.cron_tools import CRON_TOOLS
    from deepagents_cli.tools import fetch_url, firecrawl_scrape, http_request, hyperbrowser_scrape, web_search

    tools: list[Any] = [http_request, fetch_url, *CRON_TOOLS]
    if settings.has_tavily:
        tools.append(web_search)

    # Register dedicated scraping tools when API keys are present
    if os.environ.get("HYPERBROWSER_API_KEY"):
        tools.append(hyperbrowser_scrape)
    if os.environ.get("FIRECRAWL_API_KEY"):
        tools.append(firecrawl_scrape)

    # Memory tools — search_memory, save_memory, search_database, save_to_database.
    # Gives the agent direct access to Mem0 (semantic memory) and AstraDB (structured data).
    # Gracefully skipped if neither MEM0_API_KEY nor ASTRA_DB_API_KEY is present.
    if os.environ.get("MEM0_API_KEY") or os.environ.get("ASTRA_DB_API_KEY"):
        try:
            from deepagents_cli.memory_tools import MEMORY_TOOLS
            tools.extend(MEMORY_TOOLS)
            logger.info("Memory tools loaded (%d tools)", len(MEMORY_TOOLS))
        except Exception:
            logger.warning("Memory tools skipped", exc_info=True)

    # Single Composio dispatcher — replaces 48+ individual LangChain tools.
    # The agent reads composio SKILL.md to know available action names, then calls
    # this one tool instead of picking from a 50-tool list.
    # Gracefully skipped if composio SDK is not installed or API key is absent.
    if os.environ.get("COMPOSIO_API_KEY", ""):
        try:
            from deepagents_cli.composio_dispatcher import composio_action, composio_get_schema
            tools.extend([composio_action, composio_get_schema])
            logger.info("Composio dispatcher + schema discovery tools loaded")
        except Exception:
            logger.warning("Composio dispatcher skipped", exc_info=True)

    mcp_server_info: list[Any] | None = None
    if not config.no_mcp:
        import asyncio

        from deepagents_cli.mcp_tools import resolve_and_load_mcp_tools

        try:
            mcp_tools, _, mcp_server_info = asyncio.run(
                resolve_and_load_mcp_tools(
                    explicit_config_path=config.mcp_config_path,
                    no_mcp=config.no_mcp,
                    trust_project_mcp=config.trust_project_mcp,
                    project_context=project_context,
                )
            )
        except FileNotFoundError:
            logger.exception("MCP config file not found: %s", config.mcp_config_path)
            raise
        except RuntimeError:
            logger.exception(
                "Failed to load MCP tools (config: %s)", config.mcp_config_path
            )
            raise

        tools.extend(mcp_tools)
        if mcp_tools:
            logger.info("Loaded %d MCP tool(s)", len(mcp_tools))

    return tools, mcp_server_info


def make_graph() -> Any:  # noqa: ANN401
    """Create the CLI agent graph from environment-based configuration.

    Reads `DA_SERVER_*` env vars via `ServerConfig.from_env()` (the inverse of
    `ServerConfig.to_env()` used by the CLI process), resolves a model,
    assembles tools, and compiles the agent graph.

    Returns:
        Compiled LangGraph agent graph.
    """
    config = ServerConfig.from_env()
    project_context = get_server_project_context()

    from deepagents_cli.agent import create_cli_agent, load_async_subagents
    from deepagents_cli.config import create_model, settings

    if project_context is not None:
        settings.reload_from_environment(start_path=project_context.user_cwd)

    # Ensure a generous max_tokens so the model is never truncated mid-reasoning.
    # The NVIDIA NIM API can default to 1024 if not explicitly set, which causes
    # finish_reason=length and empty tool_calls — hanging the graph at END.
    _model_params: dict[str, object] = dict(config.model_params or {})
    _model_params.setdefault("max_tokens", 8192)

    try:
        result = create_model(config.model, extra_kwargs=_model_params)
    except Exception as model_err:
        logger.warning(
            "Primary model '%s' failed (%s), trying fallback providers",
            config.model, model_err,
        )
        # Try fallback providers we have keys for — best tool-callers first
        for fallback in (
            "openrouter:deepseek/deepseek-chat-v3-0324:free",
            "openrouter:meta-llama/llama-4-maverick:free",
            "openrouter:qwen/qwen3.5-72b-instruct:free",
            "moonshot:kimi-k2.5",
            "cloudflare:@cf/meta/llama-4-scout-instruct",
            "cerebras:llama-4-scout-17b-16e-instruct",
            "nvidia:qwen/qwen3.5-397b-a17b",
            "nvidia:deepseek-ai/deepseek-v3.2",
            "mistralai:mistral-large-latest",
        ):
            try:
                result = create_model(fallback, extra_kwargs=_model_params)
                logger.info("Fallback model '%s' loaded successfully", fallback)
                break
            except Exception:
                continue
        else:
            raise model_err  # re-raise original if all fallbacks fail
    result.apply_to_settings()

    tools, mcp_server_info = _build_tools(config, project_context)

    # Create sandbox backend if a sandbox provider is configured.
    # The context manager is held open at module level and cleaned up via
    # atexit so the sandbox lives for the entire server process lifetime.
    global _sandbox_cm, _sandbox_backend  # noqa: PLW0603
    sandbox_backend = None
    if config.sandbox_type:
        from deepagents_cli.integrations.sandbox_factory import create_sandbox

        try:
            _sandbox_cm = create_sandbox(
                config.sandbox_type,
                sandbox_id=config.sandbox_id,
                setup_script_path=config.sandbox_setup,
            )
            _sandbox_backend = _sandbox_cm.__enter__()  # noqa: PLC2801  # Context manager kept open for server process lifetime
            sandbox_backend = _sandbox_backend

            def _cleanup_sandbox() -> None:
                if _sandbox_cm is not None:
                    _sandbox_cm.__exit__(None, None, None)

            atexit.register(_cleanup_sandbox)
        except ImportError:
            logger.exception(
                "Sandbox provider '%s' is not installed", config.sandbox_type
            )
            print(  # noqa: T201  # stderr fallback — logger may not reach parent process
                f"Sandbox provider '{config.sandbox_type}' is not installed",
                file=sys.stderr,
            )
            sys.exit(1)
        except NotImplementedError:
            logger.exception("Sandbox type '%s' is not supported", config.sandbox_type)
            print(  # noqa: T201  # stderr fallback — logger may not reach parent process
                f"Sandbox type '{config.sandbox_type}' is not supported",
                file=sys.stderr,
            )
            sys.exit(1)
        except Exception as exc:
            logger.exception("Sandbox creation failed for '%s'", config.sandbox_type)
            print(  # noqa: T201  # stderr fallback — logger may not reach parent process
                f"Sandbox creation failed for '{config.sandbox_type}': {exc}",
                file=sys.stderr,
            )
            sys.exit(1)

    async_subagents = load_async_subagents() or None

    agent, _ = create_cli_agent(
        model=result.model,
        assistant_id=config.assistant_id,
        tools=tools,
        sandbox=sandbox_backend,
        sandbox_type=config.sandbox_type,
        system_prompt=config.system_prompt,
        interactive=config.interactive,
        auto_approve=config.auto_approve,
        enable_memory=config.enable_memory,
        enable_skills=config.enable_skills,
        enable_shell=config.enable_shell,
        mcp_server_info=mcp_server_info,
        cwd=project_context.user_cwd if project_context is not None else config.cwd,
        project_context=project_context,
        async_subagents=async_subagents,
    )
    # If the CLI passed Telegram details via env vars, send a non-blocking
    # startup notification so the operator knows the server came online.
    # Support both `DA_SERVER_*` (CLI-to-server) and the user's existing
    # `TELEGRAM_*` env var names as a fallback so local `.env` files work.
    bot_token = (
        os.environ.get("DA_SERVER_BOT_TOKEN")
        or os.environ.get("TELEGRAM_BOT_TOKEN")
        or os.environ.get("TELEGRAM_YBOT_TOKEN")
    )
    chat_id = os.environ.get("DA_SERVER_CHAT_ID") or os.environ.get(
        "TELEGRAM_AI_OWNER_CHAT_ID"
    )
    if bot_token:
        logger.info("Telegram notifier configured (using provided env vars)")
    else:
        logger.debug("No Telegram bot token found in environment")

    def _send_startup_message(token: str, cid: str) -> None:
        try:
            import requests

            url = f"https://api.telegram.org/bot{token}/sendMessage"
            text = "DeepAgents server started and agent is ready."
            # Ensure chat_id is safe for URL/JSON usage
            payload = {"chat_id": cid, "text": text}
            requests.post(url, json=payload, timeout=10)
        except Exception:
            logger.debug("Failed to send Telegram startup message", exc_info=True)

    if bot_token and chat_id:
        try:
            t = threading.Thread(
                target=_send_startup_message, args=(bot_token, chat_id), daemon=True
            )
            t.start()
        except Exception:
            logger.debug("Could not start Telegram notifier thread", exc_info=True)
    elif bot_token and not chat_id:
        logger.warning(
            "Telegram bot token found but no chat id "
            "(DA_SERVER_CHAT_ID or TELEGRAM_AI_OWNER_CHAT_ID)."
        )

    return agent


try:
    graph = make_graph()
except BaseException as exc:  # BaseException catches SystemExit from inner sys.exit() calls
    logger.critical("Failed to initialize server graph", exc_info=True)
    print(  # noqa: T201  # stderr fallback — logger may not reach parent process
        f"DEEPAGENTS STARTUP FAILURE: {type(exc).__name__}: {exc}\n{traceback.format_exc()}",
        file=sys.stderr,
        flush=True,
    )
    sys.exit(1)
