---
name: composio
description: Use Composio to interact with connected services — GitHub, Gmail, LinkedIn, Google Sheets, Twitter, Telegram, Google Drive, Google Analytics, Notion, Slack, and 200+ more. All toolkits are PRE-AUTHENTICATED — execute actions directly, no OAuth needed.
---

# Composio Skill

## IMPORTANT: Try direct tools first

The following Composio actions are already wired as **direct tools** — call them without any Python code:
`GMAIL_FETCH_EMAILS`, `GMAIL_SEND_EMAIL`, `GITHUB_LIST_REPOSITORY_ISSUES`, `GITHUB_CREATE_AN_ISSUE`,
`SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL`, `GOOGLESHEETS_BATCH_GET`, `GOOGLESHEETS_BATCH_UPDATE`,
`NOTION_ADD_PAGE_CONTENT`, `NOTION_SEARCH_NOTION_PAGE`, `TWITTER_CREATION_OF_A_POST`,
`LINKEDIN_CREATE_LINKED_IN_POST`, `GOOGLEDRIVE_LIST_FILES`, `GOOGLEDRIVE_UPLOAD_FILE`,
`TELEGRAM_SEND_MESSAGE`, `INSTAGRAM_CREATE_POST`

For any other action not in the list above, use the Python execution pattern below.

---

## Execute any other action via Python

```python
import os, json
from composio import Composio

client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])

# Account IDs are pre-loaded — no list() call needed
ACCOUNT_IDS = {
    "github":           os.environ.get("COMPOSIO_GITHUB_ACCOUNT_ID"),
    "gmail":            os.environ.get("COMPOSIO_GMAIL_ACCOUNT_ID"),
    "googlesheets":     os.environ.get("COMPOSIO_GOOGLESHEETS_ACCOUNT_ID"),
    "slack":            os.environ.get("COMPOSIO_SLACK_ACCOUNT_ID"),
    "notion":           os.environ.get("COMPOSIO_NOTION_ACCOUNT_ID"),
    "facebook":         os.environ.get("COMPOSIO_FACEBOOK_ACCOUNT_ID"),
    "instagram":        os.environ.get("COMPOSIO_INSTAGRAM_ACCOUNT_ID"),
    "twitter":          os.environ.get("COMPOSIO_TWITTER_ACCOUNT_ID"),
    "telegram":         os.environ.get("COMPOSIO_TELEGRAM_ACCOUNT_ID"),
    "linkedin":         os.environ.get("COMPOSIO_LINKEDIN_ACCOUNT_ID"),
    "googledrive":      os.environ.get("COMPOSIO_GOOGLEDRIVE_ACCOUNT_ID"),
    "youtube":          os.environ.get("COMPOSIO_YOUTUBE_ACCOUNT_ID"),
    "googledocs":       os.environ.get("COMPOSIO_GOOGLEDOCS_ACCOUNT_ID"),
    "google_analytics": os.environ.get("COMPOSIO_GOOGLE_ANALYTICS_ACCOUNT_ID"),
    "dropbox":          os.environ.get("COMPOSIO_DROPBOX_ACCOUNT_ID"),
}

result = client.tools.execute(
    "GOOGLESHEETS_CREATE_SPREADSHEET",           # action name
    arguments={"title": "My Sheet"},
    connected_account_id=ACCOUNT_IDS["googlesheets"],
    dangerously_skip_version_check=True,
)

# ALWAYS truncate — Composio returns large JSON
print(json.dumps(result, default=str)[:2000])
```

## Discover actions for a toolkit

```python
import os
from composio import Composio
client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
tools = client.tools.get_raw_composio_tools(toolkits=["notion"], limit=20)
for t in tools:
    print(t.slug)
```

## Google Sheets — how to use correctly

**To LIST what spreadsheets exist** → use `GOOGLEDRIVE_LIST_FILES` (no spreadsheet_id needed):
```
GOOGLEDRIVE_LIST_FILES with query="mimeType='application/vnd.google-apps.spreadsheet'"
```
This returns file names and their IDs. Use the `id` field as `spreadsheet_id` for BATCH_GET.

**`GOOGLESHEETS_BATCH_GET` requires a real `spreadsheet_id`** — it is NOT optional.
- Get it from `GOOGLEDRIVE_LIST_FILES` results, or from the Google Sheets URL:
  `https://docs.google.com/spreadsheets/d/<spreadsheet_id>/edit`
- `ranges` must be a **list** of range strings, e.g. `["Sheet1!A1:Z100"]` — not a string, not null
- Do NOT call `GOOGLESHEETS_BATCH_GET` until you have a real spreadsheet_id

**GOOGLESHEETS_LIST_SPREADSHEETS does NOT exist** — use `GOOGLEDRIVE_LIST_FILES` to discover sheets.

## CRITICAL rules

- Direct tools (listed above) need NO Python code — just call them
- For Python execution: use pre-loaded `ACCOUNT_IDS` dict above — never call `accounts.list()`
- Always use `dangerously_skip_version_check=True`
- **Always truncate output**: `json.dumps(result, default=str)[:2000]`
- If an action name is unknown, use discover actions first (limit=20)
- **Never pass `"null"` or `"None"` as an argument value** — omit optional args entirely
