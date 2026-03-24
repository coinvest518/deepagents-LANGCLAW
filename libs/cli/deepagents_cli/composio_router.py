"""Composio toolkit router.

Single source of truth for entity_id + connected_account_id per toolkit.
Import this everywhere instead of hardcoding account IDs.

Usage:
    from deepagents_cli.composio_router import get_account, TOOLKIT_ROUTING

    info = get_account("gmail")
    # {"entity_id": "pg-test-...", "account_id": "ca_NrnlZqd___sE",
    #  "env_var": "COMPOSIO_GMAIL_ACCOUNT_ID"}

    # Execute via Python:
    result = client.tools.execute(
        "GMAIL_SEND_EMAIL",
        arguments={...},
        connected_account_id=info["account_id"],
        dangerously_skip_version_check=True,
    )
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Entity IDs
# ---------------------------------------------------------------------------
# Most Google + social toolkits live under this entity.
_ENTITY_PRIMARY = os.environ.get(
    "COMPOSIO_ENTITY_ID", "pg-test-e862c589-3f43-4cd7-9023-cc6ec5123c23"
)
# Slack, Notion, Dropbox were connected under the "default" entity.
_ENTITY_DEFAULT = os.environ.get("COMPOSIO_DEFAULT_ENTITY_ID", "default")

# ---------------------------------------------------------------------------
# Routing table
# Each entry: toolkit_key -> {entity_id, env_var, note (optional)}
# account_id is resolved at runtime from the env var so it stays in .env.
# ---------------------------------------------------------------------------
_ROUTING_TABLE: dict[str, dict[str, str]] = {
    # Google
    "gmail": {
        "entity_id": _ENTITY_PRIMARY,
        "env_var": "COMPOSIO_GMAIL_ACCOUNT_ID",
    },
    "googledrive": {
        "entity_id": _ENTITY_PRIMARY,
        "env_var": "COMPOSIO_GOOGLEDRIVE_ACCOUNT_ID",
    },
    "googledocs": {
        "entity_id": _ENTITY_PRIMARY,
        "env_var": "COMPOSIO_GOOGLEDOCS_ACCOUNT_ID",
    },
    # Google Sheets MUST use the Drive connected account — the sheets-native
    # account has broken OAuth scopes.  Always route sheets through drive.
    "googlesheets": {
        "entity_id": _ENTITY_PRIMARY,
        "env_var": "COMPOSIO_GOOGLEDRIVE_ACCOUNT_ID",
        "note": "Uses Drive account (ca_RAPF5e1atKa_) — sheets-native OAuth is broken",
    },
    "google_analytics": {
        "entity_id": _ENTITY_PRIMARY,
        "env_var": "COMPOSIO_GOOGLE_ANALYTICS_ACCOUNT_ID",
    },
    # Social / communication
    "github": {
        "entity_id": _ENTITY_PRIMARY,
        "env_var": "COMPOSIO_GITHUB_ACCOUNT_ID",
    },
    "linkedin": {
        "entity_id": _ENTITY_PRIMARY,
        "env_var": "COMPOSIO_LINKEDIN_ACCOUNT_ID",
    },
    "twitter": {
        "entity_id": _ENTITY_PRIMARY,
        "env_var": "COMPOSIO_TWITTER_ACCOUNT_ID",
    },
    "telegram": {
        "entity_id": _ENTITY_PRIMARY,
        "env_var": "COMPOSIO_TELEGRAM_ACCOUNT_ID",
    },
    "instagram": {
        "entity_id": _ENTITY_PRIMARY,
        "env_var": "COMPOSIO_INSTAGRAM_ACCOUNT_ID",
    },
    "facebook": {
        "entity_id": _ENTITY_PRIMARY,
        "env_var": "COMPOSIO_FACEBOOK_ACCOUNT_ID",
    },
    "youtube": {
        "entity_id": _ENTITY_PRIMARY,
        "env_var": "COMPOSIO_YOUTUBE_ACCOUNT_ID",
    },
    "serpapi": {
        "entity_id": _ENTITY_PRIMARY,
        "env_var": "COMPOSIO_SERPAPI_ACCOUNT_ID",
    },
    # Default-entity toolkits (connected under "default")
    "slack": {
        "entity_id": _ENTITY_DEFAULT,
        "env_var": "COMPOSIO_SLACK_ACCOUNT_ID",
    },
    "notion": {
        "entity_id": _ENTITY_DEFAULT,
        "env_var": "COMPOSIO_NOTION_ACCOUNT_ID",
    },
    "dropbox": {
        "entity_id": _ENTITY_DEFAULT,
        "env_var": "COMPOSIO_DROPBOX_ACCOUNT_ID",
    },
}


def get_account(toolkit: str) -> dict[str, str]:
    """Return routing info for a toolkit.

    Args:
        toolkit: Lowercase toolkit name, e.g. "gmail", "googlesheets", "slack".

    Returns:
        Dict with keys: entity_id, account_id, env_var, note (optional).

    Raises:
        KeyError: If the toolkit is not in the routing table.
        ValueError: If the env var is set but empty, or not set at all.
    """
    key = toolkit.lower().replace("-", "_").replace(" ", "_")
    if key not in _ROUTING_TABLE:
        known = ", ".join(sorted(_ROUTING_TABLE))
        msg = f"Unknown toolkit '{toolkit}'. Known toolkits: {known}"
        raise KeyError(msg)

    entry = dict(_ROUTING_TABLE[key])  # shallow copy
    account_id = os.environ.get(entry["env_var"], "")
    if not account_id:
        msg = (
            f"Toolkit '{toolkit}' account ID not set. "
            f"Set env var {entry['env_var']} and restart."
        )
        raise ValueError(msg)
    entry["account_id"] = account_id
    return entry


def all_toolkits() -> list[str]:
    """Return all known toolkit names."""
    return sorted(_ROUTING_TABLE)


def toolkits_by_entity() -> dict[str, list[str]]:
    """Return toolkits grouped by entity_id."""
    groups: dict[str, list[str]] = {}
    for toolkit, entry in _ROUTING_TABLE.items():
        groups.setdefault(entry["entity_id"], []).append(toolkit)
    return groups


# ---------------------------------------------------------------------------
# Convenience: the two entity→action-list dicts used by server_graph.py
# ---------------------------------------------------------------------------

# Actions loaded for the PRIMARY entity
ACTIONS_PRIMARY: list[str] = [
    # Gmail
    "GMAIL_FETCH_EMAILS", "GMAIL_SEND_EMAIL",
    "GMAIL_LIST_LABELS", "GMAIL_GET_ATTACHMENT",
    # GitHub
    "GITHUB_LIST_REPOSITORY_ISSUES", "GITHUB_CREATE_AN_ISSUE",
    "GITHUB_LIST_COMMITS", "GITHUB_GET_CODE_CHANGES_DIFF_SUMMARY",
    "GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER",
    # Google Drive
    "GOOGLEDRIVE_LIST_FILES", "GOOGLEDRIVE_UPLOAD_FILE",
    "GOOGLEDRIVE_GET_FILE_BY_ID", "GOOGLEDRIVE_CREATE_FOLDER",
    "GOOGLEDRIVE_MOVE_FILE",
    # Google Docs
    "GOOGLEDOCS_CREATE_DOCUMENT", "GOOGLEDOCS_GET_DOCUMENT",
    "GOOGLEDOCS_SEARCH_DOCUMENTS", "GOOGLEDOCS_UPDATE_EXISTING_DOCUMENT",
    # Google Sheets (via Drive account — sheets-native OAuth currently broken)
    "GOOGLESHEETS_BATCH_GET", "GOOGLESHEETS_BATCH_UPDATE",
    # Google Analytics
    "GOOGLEANALYTICS_RUN_A_REPORT", "GOOGLEANALYTICS_LIST_ACCOUNTS",
    # LinkedIn
    "LINKEDIN_CREATE_LINKED_IN_POST",
    "LINKEDIN_GET_PROFILE", "LINKEDIN_GET_USER_INFO",
    # Twitter/X
    "TWITTER_CREATION_OF_A_POST",
    "TWITTER_SEARCH_TWEETS", "TWITTER_HOME_TIMELINE",
    "TWITTER_LOOKUP_USER_BY_USER_NAME",
    # Telegram
    "TELEGRAM_SEND_MESSAGE",
    "TELEGRAM_LIST_CHATS", "TELEGRAM_GET_MESSAGES",
    # Instagram
    "INSTAGRAM_CREATE_POST", "INSTAGRAM_GET_MEDIA_INFO",
    "INSTAGRAM_GET_USER_PROFILE", "INSTAGRAM_FETCH_COMMENTS",
    # Facebook
    "FACEBOOK_POST_PHOTO", "FACEBOOK_GET_USER_FEED",
    "FACEBOOK_CREATE_POST", "FACEBOOK_GET_USER_PAGES",
    "FACEBOOK_GET_PAGE_POSTS", "FACEBOOK_PAGE_POST_MESSAGE",
    # YouTube
    "YOUTUBE_LIST_VIDEOS", "YOUTUBE_SEARCH_YOU_TUBE_VIDEOS",
    "YOUTUBE_GET_VIDEO_DETAILS", "YOUTUBE_LIST_PLAYLISTS",
    "YOUTUBE_GET_CHANNEL_INFORMATION", "YOUTUBE_LIST_COMMENTS",
]

# Actions loaded for the DEFAULT entity (Slack, Notion, Dropbox)
ACTIONS_DEFAULT: list[str] = [
    # Slack
    "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL",
    "SLACK_LIST_CHANNELS", "SLACK_FETCH_CONVERSATION_HISTORY",
    "SLACK_GET_USER_INFO", "SLACK_INVITE_USER_TO_CHANNEL",
    # Notion
    "NOTION_ADD_PAGE_CONTENT", "NOTION_SEARCH_NOTION_PAGE",
    "NOTION_CREATE_PAGE", "NOTION_GET_PAGE",
    "NOTION_CREATE_DATABASE_ENTRY", "NOTION_QUERY_DATABASE",
    # Dropbox
    "DROPBOX_LIST_FOLDER", "DROPBOX_UPLOAD_FILE",
    "DROPBOX_DOWNLOAD_FILE", "DROPBOX_CREATE_FOLDER",
    "DROPBOX_GET_FILE_METADATA", "DROPBOX_MOVE_FILE",
]
