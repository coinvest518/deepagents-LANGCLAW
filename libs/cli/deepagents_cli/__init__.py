"""Deep Agents CLI - Interactive AI coding assistant."""

from deepagents_cli._version import __version__
from deepagents_cli.main import cli_main

__all__ = [
    "__version__",
    "cli_main",
]

# Export lightweight composio helpers when available so other entrypoints can
# import `composio_action` / `composio_get_schema` from `deepagents_cli`.
try:
    from deepagents_cli.composio_dispatcher import (
        composio_action,
        composio_get_schema,
        dispatch as composio_dispatch,
    )
    __all__.extend(["composio_action", "composio_get_schema", "composio_dispatch"])
except Exception:
    # Optional; keep module import lightweight when dependencies are missing
    pass
