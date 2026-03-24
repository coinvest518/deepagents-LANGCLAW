"""composio_dispatcher.py — single-tool entry point for all Composio actions.

Instead of registering 48+ individual LangChain tools (which overwhelms the
LLM's tool-selection), we expose ONE tool: composio_action().

The agent learns which action names exist by reading the composio SKILL.md.
Entity routing (primary vs default) is handled automatically based on the
action prefix.

Supported toolkit prefixes → entity mapping:
  slack, notion, dropbox  → default entity
  everything else         → primary entity
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Toolkits that live under the "default" entity (not the primary pg-test- entity)
_DEFAULT_ENTITY_TOOLKITS = frozenset({"slack", "notion", "dropbox"})


def _get_entity_id(action: str) -> str:
    """Return the correct entity_id for an action based on its toolkit prefix."""
    from deepagents_cli.composio_router import _ENTITY_DEFAULT, _ENTITY_PRIMARY
    prefix = action.split("_", maxsplit=1)[0].lower()
    return _ENTITY_DEFAULT if prefix in _DEFAULT_ENTITY_TOOLKITS else _ENTITY_PRIMARY


@tool
def composio_action(action: str, arguments: dict[str, Any] | None = None) -> str:
    """Execute any Composio action by name.

    Use this for ALL connected service operations: Gmail, GitHub, Google Drive,
    Google Docs, Google Sheets, Google Analytics, LinkedIn, Twitter, Telegram,
    Instagram, Facebook, YouTube, Slack, Notion, Dropbox, SerpAPI, and more.

    Read the 'composio' skill to find available action names and their required
    arguments. The skill lists actions grouped by service.

    Args:
        action: Composio action slug in SCREAMING_SNAKE_CASE.
                Examples: "GMAIL_SEND_EMAIL", "GITHUB_LIST_REPOSITORY_ISSUES",
                "GOOGLEDRIVE_LIST_FILES", "SLACK_FETCH_CHANNELS",
                "TWITTER_CREATION_OF_A_POST"
        arguments: Dict of arguments the action requires.
                   Pass an empty dict {} or omit for actions with no required args.

    Returns:
        Action result as a JSON string, or an error message starting with ERROR:.

    Examples:
        composio_action("GMAIL_FETCH_EMAILS", {"max_results": 5})
        composio_action("GITHUB_LIST_REPOSITORY_ISSUES",
                        {"owner": "octocat", "repo": "Hello-World"})
        composio_action("GOOGLEDRIVE_LIST_FILES", {})
        composio_action("SLACK_FETCH_CHANNELS", {})
        composio_action("TWITTER_CREATION_OF_A_POST", {"text": "Hello world!"})
    """
    if arguments is None:
        arguments = {}

    api_key = os.environ.get("COMPOSIO_API_KEY", "")
    if not api_key:
        return "ERROR: COMPOSIO_API_KEY not set in environment"

    entity_id = _get_entity_id(action)

    try:
        from composio import Composio  # type: ignore[import-untyped]
        client = Composio(api_key=api_key)
        result = client.tools.execute(
            action,
            arguments=arguments,
            entity_id=entity_id,
        )
        # Normalise result to a clean string
        if isinstance(result, dict):
            return json.dumps(result, indent=2, default=str)
        return str(result)
    except Exception as exc:  # noqa: BLE001
        logger.warning("composio_action failed: %s %s — %s", action, arguments, exc)
        return f"ERROR: {exc}"
