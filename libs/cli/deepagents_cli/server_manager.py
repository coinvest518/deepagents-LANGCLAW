"""Server lifecycle orchestration for the CLI.

Provides `start_server_and_get_agent` which handles the full flow of:

1. Building a `ServerConfig` from CLI arguments
2. Writing config to env vars via `ServerConfig.to_env()`
3. Scaffolding a workspace (langgraph.json, checkpointer, pyproject)
4. Starting the `langgraph dev` server
5. Returning a `RemoteAgent` client

Also provides `server_session`, an async context manager that wraps
server startup and guaranteed cleanup so callers don't need to
duplicate try/finally teardown.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from deepagents_cli.mcp_tools import MCPSessionManager
    from deepagents_cli.remote_client import RemoteAgent
    from deepagents_cli.server import ServerProcess

from deepagents_cli._server_config import ServerConfig
from deepagents_cli._server_constants import ENV_PREFIX as _ENV_PREFIX
from deepagents_cli.project_utils import ProjectContext

logger = logging.getLogger(__name__)


def _set_or_clear_server_env(name: str, value: str | None) -> None:
    """Set or clear a `DA_SERVER_*` environment variable.

    Args:
        name: Suffix after `DA_SERVER_`.
        value: String value to set, or `None` to clear the variable.
    """
    key = f"{_ENV_PREFIX}{name}"
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value


def _apply_server_config(config: ServerConfig) -> None:
    """Write a `ServerConfig` to `DA_SERVER_*` env vars.

    Uses `ServerConfig.to_env()` so that the set of variables and their
    serialization format are defined in one place (the `ServerConfig` dataclass)
    rather than maintained independently here and in the
    reader (`ServerConfig.from_env()`).

    Args:
        config: Fully resolved server configuration.
    """
    for suffix, value in config.to_env().items():
        _set_or_clear_server_env(suffix, value)


def _capture_project_context() -> ProjectContext | None:
    """Capture the user's project context for the server subprocess.

    Returns:
        Explicit project context, or `None` when cwd cannot be determined.
    """
    try:
        return ProjectContext.from_user_cwd(Path.cwd())
    except OSError:
        logger.warning("Could not determine working directory for server")
        return None


# ------------------------------------------------------------------
# Workspace scaffolding
# ------------------------------------------------------------------


def _scaffold_workspace(work_dir: Path) -> None:
    """Prepare the server working directory with all required files.

    Copies the server graph entry point into *work_dir* and generates
    the auxiliary files (checkpointer module, `pyproject.toml`,
    `langgraph.json`) that `langgraph dev` needs to boot.

    Args:
        work_dir: Temporary directory that will become the server's cwd.
    """
    from deepagents_cli.server import generate_langgraph_json

    server_graph_src = Path(__file__).parent / "server_graph.py"
    server_graph_dst = work_dir / "server_graph.py"
    shutil.copy2(server_graph_src, server_graph_dst)

    _write_checkpointer(work_dir)
    _write_pyproject(work_dir)

    checkpointer_path = work_dir / "checkpointer.py"
    # Use a module-style reference for the graph. The server subprocess's
    # cwd will be `work_dir` so `server_graph` can be imported directly. Avoid
    # passing an absolute path which can produce invalid module names on
    # Windows (paths with spaces) and cause ModuleNotFoundError at import time.
    generate_langgraph_json(
        work_dir,
        graph_ref="server_graph:graph",
        checkpointer_path=f"{checkpointer_path.resolve()}:create_checkpointer",
    )


def _write_checkpointer(work_dir: Path) -> None:
    """Write a checkpointer module that reads its DB path from the environment.

    The generated module reads `DA_SERVER_DB_PATH` at runtime so the path is
    never baked into generated source. This avoids fragile code-generation via
    f-string interpolation and is consistent with the `DA_SERVER_*` env-var
    communication pattern used elsewhere.

    Args:
        work_dir: Server working directory.
    """
    from deepagents_cli.sessions import get_db_path

    # Set the env var that the generated module will read at import time.
    os.environ[f"{_ENV_PREFIX}DB_PATH"] = str(get_db_path())

    content = '''\
"""Persistent SQLite checkpointer for the LangGraph dev server."""

import os
from contextlib import asynccontextmanager


@asynccontextmanager
async def create_checkpointer():
    """Yield an AsyncSqliteSaver connected to the CLI sessions DB.

    The database path is read from the `DA_SERVER_DB_PATH` env var
    (set by the CLI before server startup) rather than hard-coded, so
    the checkpointer module works without code generation.
    """
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    db_path = os.environ.get("DA_SERVER_DB_PATH")
    if not db_path:
        raise RuntimeError(
            "DA_SERVER_DB_PATH not set. The CLI must set this env var before "
            "server startup."
        )
    async with AsyncSqliteSaver.from_conn_string(db_path) as saver:
        yield saver
'''
    (work_dir / "checkpointer.py").write_text(content)


def _write_pyproject(work_dir: Path) -> None:
    """Write a minimal pyproject.toml for the server working directory.

    The `langgraph dev` server needs to install the project dependencies.
    We point it at the CLI package which transitively pulls in the SDK.

    Args:
        work_dir: Server working directory.
    """
    cli_dir = Path(__file__).parent.parent
    deepagents_dir = cli_dir.parent / "deepagents"
    content = f"""[project]
name = "deepagents-server-runtime"
version = "0.0.1"
requires-python = ">=3.11"
dependencies = [
    "deepagents @ file://{deepagents_dir}",
    "deepagents-cli[nvidia,ollama,openai,mistralai,anthropic,huggingface,cerebras] @ file://{cli_dir}",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"""
    (work_dir / "pyproject.toml").write_text(content)


# ------------------------------------------------------------------
# Workspace caching
# ------------------------------------------------------------------

_WORKSPACE_HASH_FILE = ".scaffold_hash"


def _workspace_cache_dir() -> Path:
    """Return the persistent server workspace directory under ``~/.deepagents``.

    Using a fixed path means ``langgraph dev`` can reuse the ``.venv`` it
    created on the first run, skipping the 30-60 second dependency-install
    step on every subsequent startup.

    Returns:
        Path to the cache directory (created if absent).
    """
    cache_dir = Path.home() / ".deepagents" / "server_workspace"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _scaffold_hash() -> str:
    """Compute a short hash over the source files that make up the workspace.

    When ``server_graph.py`` or the CLI's ``pyproject.toml`` changes (e.g.
    after a CLI upgrade), the hash changes and the workspace is re-scaffolded
    so ``langgraph dev`` reinstalls the correct dependencies.

    Returns:
        First 16 hex digits of the SHA-256 hash.
    """
    h = hashlib.sha256()
    src = Path(__file__).parent / "server_graph.py"
    if src.exists():
        h.update(src.read_bytes())
    cli_pyproject = Path(__file__).parent.parent / "pyproject.toml"
    if cli_pyproject.exists():
        h.update(cli_pyproject.read_bytes())
    return h.hexdigest()[:16]


def _scaffold_workspace_cached(work_dir: Path) -> None:
    """Scaffold *work_dir*, skipping the full scaffold when files are unchanged.

    On a cache hit the only action is updating ``DA_SERVER_DB_PATH`` in the
    current environment so the existing ``checkpointer.py`` picks up the right
    database path at server startup.

    On a cache miss the full :func:`_scaffold_workspace` runs and the new hash
    is written, so ``langgraph dev`` will reinstall dependencies.

    Args:
        work_dir: Persistent workspace directory.
    """
    hash_file = work_dir / _WORKSPACE_HASH_FILE
    current_hash = _scaffold_hash()

    required_files = (
        "langgraph.json",
        "server_graph.py",
        "checkpointer.py",
        "pyproject.toml",
    )
    cache_valid = (
        hash_file.exists()
        and hash_file.read_text(encoding="utf-8").strip() == current_hash
        and all((work_dir / f).exists() for f in required_files)
    )

    if cache_valid:
        logger.info("Server workspace cache hit -- skipping scaffold (hash=%s)", current_hash)  # noqa: E501
        # Still need to refresh DA_SERVER_DB_PATH; the path can change between
        # runs (e.g. different user or relocated home directory).
        from deepagents_cli._server_constants import ENV_PREFIX as _ENV_PREFIX_LOCAL
        from deepagents_cli.sessions import get_db_path

        os.environ[f"{_ENV_PREFIX_LOCAL}DB_PATH"] = str(get_db_path())
        return

    logger.info("Server workspace cache miss -- scaffolding (hash=%s)", current_hash)
    _scaffold_workspace(work_dir)
    hash_file.write_text(current_hash, encoding="utf-8")


# ------------------------------------------------------------------
# Server startup
# ------------------------------------------------------------------


async def start_server_and_get_agent(
    *,
    assistant_id: str,
    model_name: str | None = None,
    model_params: dict[str, Any] | None = None,
    auto_approve: bool = False,
    sandbox_type: str = "none",
    sandbox_id: str | None = None,
    sandbox_setup: str | None = None,
    enable_shell: bool = True,
    enable_ask_user: bool = False,
    enable_memory: bool = True,
    enable_skills: bool = True,
    mcp_config_path: str | None = None,
    no_mcp: bool = False,
    trust_project_mcp: bool | None = None,
    interactive: bool = True,
    host: str = "127.0.0.1",
    port: int = 2024,
) -> tuple[RemoteAgent, ServerProcess, MCPSessionManager | None]:
    """Start a LangGraph server and return a connected remote agent client.

    Args:
        assistant_id: Agent identifier.
        model_name: Model spec string.
        model_params: Extra model kwargs.
        auto_approve: Auto-approve all tools.
        sandbox_type: Sandbox type.
        sandbox_id: Existing sandbox ID to reuse.
        sandbox_setup: Path to setup script for the sandbox.
        enable_shell: Enable shell execution tools.
        enable_ask_user: Enable ask_user tool.
        enable_memory: Enable memory tools.
        enable_skills: Enable skills tools.
        mcp_config_path: Path to MCP config.
        no_mcp: Disable MCP.
        trust_project_mcp: Trust project MCP servers.
        interactive: Whether the agent is interactive.
        host: Server host.
        port: Server port.

    Returns:
        Tuple of `(remote_agent, server_process, mcp_session_manager)`.
            The `mcp_session_manager` is currently always `None` (MCP lifecycle
            is handled server-side).
    """
    from deepagents_cli.remote_client import RemoteAgent
    from deepagents_cli.server import ServerProcess

    project_context = _capture_project_context()

    config = ServerConfig.from_cli_args(
        project_context=project_context,
        model_name=model_name,
        model_params=model_params,
        assistant_id=assistant_id,
        auto_approve=auto_approve,
        sandbox_type=sandbox_type,
        sandbox_id=sandbox_id,
        sandbox_setup=sandbox_setup,
        enable_shell=enable_shell,
        enable_ask_user=enable_ask_user,
        enable_memory=enable_memory,
        enable_skills=enable_skills,
        mcp_config_path=mcp_config_path,
        no_mcp=no_mcp,
        trust_project_mcp=trust_project_mcp,
        interactive=interactive,
    )
    _apply_server_config(config)

    work_dir = _workspace_cache_dir()
    _scaffold_workspace_cached(work_dir)

    # owns_config_dir=False — the cache dir is persistent; we never delete it.
    server = ServerProcess(
        host=host, port=port, config_dir=work_dir, owns_config_dir=False
    )
    try:
        await server.start()
    except Exception:
        server.stop()
        raise

    agent = RemoteAgent(
        url=server.url,
        graph_name="agent",
        # Local langgraph dev server doesn't validate the key, but the SDK
        # requires *something* to be set or it raises an auth error.
        api_key=os.environ.get("LANGSMITH_API_KEY") or "local",
    )

    return agent, server, None


# ------------------------------------------------------------------
# Session context manager
# ------------------------------------------------------------------


@asynccontextmanager
async def server_session(
    *,
    assistant_id: str,
    model_name: str | None = None,
    model_params: dict[str, Any] | None = None,
    auto_approve: bool = False,
    sandbox_type: str = "none",
    sandbox_id: str | None = None,
    sandbox_setup: str | None = None,
    enable_shell: bool = True,
    enable_ask_user: bool = False,
    enable_memory: bool = True,
    enable_skills: bool = True,
    mcp_config_path: str | None = None,
    no_mcp: bool = False,
    trust_project_mcp: bool | None = None,
    interactive: bool = True,
    host: str = "127.0.0.1",
    port: int = 2024,
) -> AsyncIterator[tuple[RemoteAgent, ServerProcess]]:
    """Async context manager that starts a server and guarantees cleanup.

    Wraps `start_server_and_get_agent` so callers don't need to duplicate the
    try/finally pattern for stopping the server.

    Args:
        assistant_id: Agent identifier.
        model_name: Model spec string.
        model_params: Extra model kwargs.
        auto_approve: Auto-approve all tools.
        sandbox_type: Sandbox type.
        sandbox_id: Existing sandbox ID to reuse.
        sandbox_setup: Path to setup script for the sandbox.
        enable_shell: Enable shell execution tools.
        enable_ask_user: Enable ask_user tool.
        enable_memory: Enable memory tools.
        enable_skills: Enable skills tools.
        mcp_config_path: Path to MCP config.
        no_mcp: Disable MCP.
        trust_project_mcp: Trust project MCP servers.
        interactive: Whether the agent is interactive.
        host: Server host.
        port: Server port.

    Yields:
        Tuple of `(remote_agent, server_process)`.
    """
    server_proc: ServerProcess | None = None
    mcp_session_manager: MCPSessionManager | None = None
    try:
        agent, server_proc, mcp_session_manager = await start_server_and_get_agent(
            assistant_id=assistant_id,
            model_name=model_name,
            model_params=model_params,
            auto_approve=auto_approve,
            sandbox_type=sandbox_type,
            sandbox_id=sandbox_id,
            sandbox_setup=sandbox_setup,
            enable_shell=enable_shell,
            enable_ask_user=enable_ask_user,
            enable_memory=enable_memory,
            enable_skills=enable_skills,
            mcp_config_path=mcp_config_path,
            no_mcp=no_mcp,
            trust_project_mcp=trust_project_mcp,
            interactive=interactive,
            host=host,
            port=port,
        )
        yield agent, server_proc
    finally:
        if mcp_session_manager is not None:
            try:
                await mcp_session_manager.cleanup()
            except Exception:
                logger.warning("MCP session cleanup failed", exc_info=True)
        if server_proc is not None:
            server_proc.stop()
