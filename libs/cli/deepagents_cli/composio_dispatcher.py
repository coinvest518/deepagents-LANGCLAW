"""composio_dispatcher.py — single-tool entry point for all Composio actions.

Instead of registering 48+ individual LangChain tools (which overwhelms the
LLM's tool-selection), we expose ONE tool: composio_action().

The agent learns which action names exist by reading the composio SKILL.md.
Account routing (connected_account_id) is handled automatically based on the
action prefix, using the composio_router table.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Special prefix mapping: GOOGLESHEETS uses the Drive account (not sheets-native)
_PREFIX_OVERRIDE: dict[str, str] = {
    "googlesheets": "googledrive",
}


def _smart_truncate(data: dict | str, max_chars: int = 6000) -> str:
    """Compress tool results intelligently instead of blind character truncation.

    For dict results (JSON from APIs like Gmail):
    - Preserves metadata fields (labels, folders, ids, subjects, senders)
    - Strips large body/payload/content fields first
    - Summarises list items if there are too many
    - Always produces valid, readable output

    For string results: truncates at a line boundary.
    """
    if isinstance(data, str):
        if len(data) <= max_chars:
            return data
        # Truncate at last newline before limit
        cut = data[:max_chars].rfind("\n")
        if cut < max_chars // 2:
            cut = max_chars - 200
        return data[:cut] + f"\n\n[TRUNCATED — {len(data)} chars total. Use the data above to respond.]"

    # Dict: strip heavy fields, keep metadata
    _HEAVY_KEYS = {"body", "payload", "raw", "htmlBody", "html_body", "content",
                   "textBody", "text_body", "snippet", "raw_content", "data",
                   "attachments", "parts", "headers"}
    _KEEP_KEYS = {"id", "threadId", "labelIds", "label_ids", "subject", "from",
                  "to", "date", "snippet", "name", "email", "folder", "label",
                  "sender", "recipient", "internalDate", "historyId"}

    def _slim(obj: Any, depth: int = 0) -> Any:
        if isinstance(obj, dict):
            slimmed = {}
            for k, v in obj.items():
                if k.lower() in {hk.lower() for hk in _HEAVY_KEYS} and depth > 0:
                    if isinstance(v, str) and len(v) > 200:
                        slimmed[k] = v[:200] + "...[trimmed]"
                    elif isinstance(v, (list, dict)):
                        slimmed[k] = f"[{type(v).__name__}, {len(v)} items — trimmed]"
                    else:
                        slimmed[k] = v
                else:
                    slimmed[k] = _slim(v, depth + 1)
            return slimmed
        elif isinstance(obj, list):
            if len(obj) > 5:
                return [_slim(item, depth + 1) for item in obj[:5]] + [
                    f"...and {len(obj) - 5} more items"
                ]
            return [_slim(item, depth + 1) for item in obj]
        return obj

    slimmed = _slim(data)
    text = json.dumps(slimmed, indent=2, default=str)
    if len(text) > max_chars:
        # Still too big — fall back to line-boundary truncation
        cut = text[:max_chars].rfind("\n")
        if cut < max_chars // 2:
            cut = max_chars - 200
        text = text[:cut] + f"\n\n[TRUNCATED — trimmed result still too large. Use the data above to respond.]"
    return text


def _get_account_id(action: str) -> str | None:
    """Return the connected_account_id for an action based on its toolkit prefix.

    Returns None if the toolkit is unknown (caller should skip connected_account_id).
    """
    raw_prefix = action.split("_", maxsplit=1)[0].lower()
    toolkit = _PREFIX_OVERRIDE.get(raw_prefix, raw_prefix)
    try:
        from deepagents_cli.composio_router import get_account
        return get_account(toolkit)["account_id"]
    except (KeyError, ValueError):
        return None


@tool
def composio_action(action: str, arguments: dict[str, Any] | str | None = None) -> str:
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
    # LLMs sometimes pass arguments as a JSON string instead of a dict — coerce it.
    if isinstance(arguments, str):
        stripped = arguments.strip()
        if stripped in ("", "null", "none", "undefined", "{}", "[]"):
            arguments = {}
        else:
            try:
                arguments = json.loads(stripped)
            except json.JSONDecodeError:
                arguments = {}
    if arguments is None:
        arguments = {}

    api_key = os.environ.get("COMPOSIO_API_KEY", "")
    if not api_key:
        return "ERROR: COMPOSIO_API_KEY not set in environment"

    account_id = _get_account_id(action)

    try:
        from composio import Composio  # type: ignore[import-untyped]
        client = Composio(api_key=api_key)
        kwargs: dict[str, Any] = {
            "dangerously_skip_version_check": True,
        }
        if account_id:
            kwargs["connected_account_id"] = account_id
        result = client.tools.execute(action, arguments=arguments, **kwargs)
        # Normalise result to a clean string — smart compression for large payloads
        if isinstance(result, dict):
            text = json.dumps(result, indent=2, default=str)
        else:
            text = str(result)
        if len(text) > 6000:
            text = _smart_truncate(result if isinstance(result, dict) else text, max_chars=6000)
        return text
    except Exception as exc:  # noqa: BLE001
        logger.warning("composio_action failed: %s %s — %s", action, arguments, exc)
        return f"ERROR: {exc}"
