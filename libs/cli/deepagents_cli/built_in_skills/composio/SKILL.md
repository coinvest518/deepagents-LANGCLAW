---
name: composio
description: Use Composio to interact with connected services — GitHub, Gmail, LinkedIn, Google Sheets, Twitter, Telegram, Google Drive, Google Docs, Google Analytics, Slack, Notion, Dropbox, Facebook, YouTube, Instagram, and 200+ more. All toolkits are PRE-AUTHENTICATED — execute actions directly, no OAuth needed.
---

# Composio Skill

## IMPORTANT: Use the `composio_action` tool

All Composio operations go through ONE tool: **`composio_action`**

```
composio_action(action="ACTION_NAME", arguments={...})
```

Entity routing (primary vs Slack/Notion/Dropbox default) is handled automatically.
Never use web_search or Python scripts for these — call composio_action directly.

### Quick reference by service

**Gmail:** `GMAIL_FETCH_EMAILS`, `GMAIL_SEND_EMAIL`, `GMAIL_LIST_LABELS`, `GMAIL_GET_ATTACHMENT`

**GitHub:** `GITHUB_LIST_REPOSITORY_ISSUES`, `GITHUB_CREATE_AN_ISSUE`, `GITHUB_LIST_COMMITS`, `GITHUB_COMPARE_TWO_COMMITS`, `GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER`

**Google Drive:** `GOOGLEDRIVE_LIST_FILES`, `GOOGLEDRIVE_UPLOAD_FILE`, `GOOGLEDRIVE_GET_FILE_METADATA`, `GOOGLEDRIVE_CREATE_FOLDER`, `GOOGLEDRIVE_MOVE_FILE`

**Google Docs:** `GOOGLEDOCS_CREATE_DOCUMENT`, `GOOGLEDOCS_GET_DOCUMENT_BY_ID`, `GOOGLEDOCS_SEARCH_DOCUMENTS`, `GOOGLEDOCS_UPDATE_EXISTING_DOCUMENT`

**Google Sheets** (uses Drive OAuth automatically — sheets-native account has broken token):
`GOOGLESHEETS_CREATE_GOOGLE_SHEET1`, `GOOGLESHEETS_BATCH_GET`, `GOOGLESHEETS_BATCH_UPDATE`, `GOOGLESHEETS_SPREADSHEETS_VALUES_APPEND`, `GOOGLESHEETS_CREATE_SPREADSHEET_ROW`, `GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW`, `GOOGLESHEETS_UPSERT_ROWS` — see googlesheets skill for full list

**Google Analytics:** `GOOGLE_ANALYTICS_RUN_REPORT`, `GOOGLE_ANALYTICS_LIST_ACCOUNTS`

**LinkedIn:** `LINKEDIN_CREATE_LINKED_IN_POST`, `LINKEDIN_GET_MY_INFO`

**Twitter/X:** `TWITTER_CREATION_OF_A_POST`, `TWITTER_RECENT_SEARCH`, `TWITTER_USER_HOME_TIMELINE_BY_USER_ID`, `TWITTER_USER_LOOKUP_BY_USERNAME`

**Telegram:** `TELEGRAM_SEND_MESSAGE`, `TELEGRAM_GET_UPDATES`

**Instagram:** `INSTAGRAM_CREATE_POST`, `INSTAGRAM_GET_IG_MEDIA`, `INSTAGRAM_GET_USER_INFO`, `INSTAGRAM_GET_POST_COMMENTS`

**Facebook:** `FACEBOOK_CREATE_PHOTO_POST`, `FACEBOOK_GET_PAGE_POSTS`, `FACEBOOK_CREATE_POST`, `FACEBOOK_GET_USER_PAGES`, `FACEBOOK_GET_PAGE_POSTS`

**YouTube:** `YOUTUBE_LIST_CHANNEL_VIDEOS`, `YOUTUBE_SEARCH_YOU_TUBE`, `YOUTUBE_VIDEO_DETAILS`, `YOUTUBE_LIST_USER_PLAYLISTS`, `YOUTUBE_GET_CHANNEL_STATISTICS`, `YOUTUBE_LIST_COMMENTS`

**Slack:** `SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL`, `SLACK_LIST_ALL_CHANNELS`, `SLACK_FETCH_CONVERSATION_HISTORY`, `SLACK_FIND_USERS`, `SLACK_INVITE_USER_TO_CHANNEL`

**Notion:** `NOTION_ADD_PAGE_CONTENT`, `NOTION_SEARCH_NOTION_PAGE`, `NOTION_CREATE_NOTION_PAGE`, `NOTION_RETRIEVE_PAGE`, `NOTION_INSERT_ROW_DATABASE`, `NOTION_QUERY_DATABASE`

**Dropbox:** `DROPBOX_LIST_FILES_IN_FOLDER`, `DROPBOX_UPLOAD_FILE`, `DROPBOX_EXPORT_FILE`, `DROPBOX_CREATE_FOLDER`, `DROPBOX_GET_METADATA`, `DROPBOX_MOVE_FILE_OR_FOLDER`

For any other action not in the lists above, use the Python execution pattern below.

---

## Connected Account IDs (pre-loaded — never call accounts.list())

| Service | Env Var | Account ID |
|---------|---------|------------|
| Gmail | `COMPOSIO_GMAIL_ACCOUNT_ID` | ca_NrnlZqd___sE |
| GitHub | `COMPOSIO_GITHUB_ACCOUNT_ID` | ca_yph0f177iznT |
| Google Drive | `COMPOSIO_GOOGLEDRIVE_ACCOUNT_ID` | ca_RAPF5e1atKa_ |
| Google Docs | `COMPOSIO_GOOGLEDOCS_ACCOUNT_ID` | ca_8YkEOhu3T-Wd |
| Google Sheets | Use `COMPOSIO_GOOGLEDRIVE_ACCOUNT_ID` | ca_RAPF5e1atKa_ |
| Google Analytics | `COMPOSIO_GOOGLE_ANALYTICS_ACCOUNT_ID` | ca_E7SnKuBAm4aK |
| LinkedIn | `COMPOSIO_LINKEDIN_ACCOUNT_ID` | ca_AxYGMiT-jtOU |
| Twitter/X | `COMPOSIO_TWITTER_ACCOUNT_ID` | ca_TrHN1O3jZ58f |
| Telegram | `COMPOSIO_TELEGRAM_ACCOUNT_ID` | ca_qn0hWMpwTYTm |
| Instagram | `COMPOSIO_INSTAGRAM_ACCOUNT_ID` | ca_J8db7D84W8m6 |
| Facebook | `COMPOSIO_FACEBOOK_ACCOUNT_ID` | ca_qujf8XxJkcZc |
| YouTube | `COMPOSIO_YOUTUBE_ACCOUNT_ID` | ca_WsQIrwNqA_l_ |
| Slack | `COMPOSIO_SLACK_ACCOUNT_ID` | ca_nbRXg7EeJgvx |
| Notion | `COMPOSIO_NOTION_ACCOUNT_ID` | ca_VCkrXCRVWUVp |
| Dropbox | `COMPOSIO_DROPBOX_ACCOUNT_ID` | ca__qavNcrS7vNU |
| SerpAPI | `COMPOSIO_SERPAPI_ACCOUNT_ID` | ca_gImhMFTfT1n3 |

---

## Execute any action via Python

```python
import os, json
from composio import Composio

client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])

ACCOUNT_IDS = {
    "gmail":            os.environ.get("COMPOSIO_GMAIL_ACCOUNT_ID"),
    "github":           os.environ.get("COMPOSIO_GITHUB_ACCOUNT_ID"),
    "googledrive":      os.environ.get("COMPOSIO_GOOGLEDRIVE_ACCOUNT_ID"),
    "googledocs":       os.environ.get("COMPOSIO_GOOGLEDOCS_ACCOUNT_ID"),
    "googlesheets":     os.environ.get("COMPOSIO_GOOGLEDRIVE_ACCOUNT_ID"),  # use Drive account!
    "google_analytics": os.environ.get("COMPOSIO_GOOGLE_ANALYTICS_ACCOUNT_ID"),
    "linkedin":         os.environ.get("COMPOSIO_LINKEDIN_ACCOUNT_ID"),
    "twitter":          os.environ.get("COMPOSIO_TWITTER_ACCOUNT_ID"),
    "telegram":         os.environ.get("COMPOSIO_TELEGRAM_ACCOUNT_ID"),
    "instagram":        os.environ.get("COMPOSIO_INSTAGRAM_ACCOUNT_ID"),
    "facebook":         os.environ.get("COMPOSIO_FACEBOOK_ACCOUNT_ID"),
    "youtube":          os.environ.get("COMPOSIO_YOUTUBE_ACCOUNT_ID"),
    "slack":            os.environ.get("COMPOSIO_SLACK_ACCOUNT_ID"),
    "notion":           os.environ.get("COMPOSIO_NOTION_ACCOUNT_ID"),
    "dropbox":          os.environ.get("COMPOSIO_DROPBOX_ACCOUNT_ID"),
    "serpapi":          os.environ.get("COMPOSIO_SERPAPI_ACCOUNT_ID"),
}

result = client.tools.execute(
    "GOOGLEDOCS_CREATE_DOCUMENT",         # action slug
    arguments={"title": "My Doc", "text": "Hello world"},
    connected_account_id=ACCOUNT_IDS["googledocs"],
    dangerously_skip_version_check=True,
)

# ALWAYS truncate — Composio returns large JSON
print(json.dumps(result, default=str)[:2000])
```

---

## Toolkit reference

### Google Drive
**To LIST files/spreadsheets/docs** → `GOOGLEDRIVE_LIST_FILES` with optional `query`:
- Sheets: `query="mimeType='application/vnd.google-apps.spreadsheet'"`
- Docs: `query="mimeType='application/vnd.google-apps.document'"`
- Folders: `query="mimeType='application/vnd.google-apps.folder'"`

Key slugs: `GOOGLEDRIVE_LIST_FILES`, `GOOGLEDRIVE_GET_FILE_METADATA`, `GOOGLEDRIVE_UPLOAD_FILE`, `GOOGLEDRIVE_CREATE_FOLDER`, `GOOGLEDRIVE_MOVE_FILE`, `GOOGLEDRIVE_COPY_FILE`, `GOOGLEDRIVE_DELETE_FILE`, `GOOGLEDRIVE_CREATE_FILE_FROM_TEXT`, `GOOGLEDRIVE_FIND_FILE`, `GOOGLEDRIVE_ADD_FILE_SHARING_PREFERENCE`

### Google Sheets
**CRITICAL — use `COMPOSIO_GOOGLEDRIVE_ACCOUNT_ID` (ca_RAPF5e1atKa_), NOT the sheets-specific account.**

**To find a spreadsheet_id**: call `GOOGLEDRIVE_LIST_FILES` with `query="mimeType='application/vnd.google-apps.spreadsheet'"` → use `id` field.
Or extract from URL: `https://docs.google.com/spreadsheets/d/<spreadsheet_id>/edit`

**`GOOGLESHEETS_BATCH_GET` requires:**
- `spreadsheet_id` — real ID, NOT optional, NOT "null"
- `ranges` — **list** of range strings: `["Sheet1!A1:Z100"]` — NOT a string, NOT null

**DO NOT call `GOOGLESHEETS_BATCH_GET` until you have a real spreadsheet_id.**
**`GOOGLESHEETS_LIST_SPREADSHEETS` does NOT exist** — use `GOOGLEDRIVE_LIST_FILES`.

Key slugs: `GOOGLESHEETS_BATCH_GET`, `GOOGLESHEETS_BATCH_UPDATE`, `GOOGLESHEETS_CREATE_GOOGLE_SHEET1`, `GOOGLESHEETS_SPREADSHEETS_VALUES_APPEND`, `GOOGLESHEETS_CLEAR_VALUES`, `GOOGLESHEETS_CREATE_SPREADSHEET_ROW`, `GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW`

### Google Docs
Key slugs: `GOOGLEDOCS_CREATE_DOCUMENT`, `GOOGLEDOCS_GET_DOCUMENT_BY_ID`, `GOOGLEDOCS_SEARCH_DOCUMENTS`, `GOOGLEDOCS_UPDATE_EXISTING_DOCUMENT`, `GOOGLEDOCS_GET_DOCUMENT_PLAINTEXT`, `GOOGLEDOCS_CREATE_DOCUMENT_MARKDOWN`

### Gmail
Key slugs: `GMAIL_FETCH_EMAILS`, `GMAIL_SEND_EMAIL`, `GMAIL_LIST_LABELS`, `GMAIL_GET_ATTACHMENT`, `GMAIL_CREATE_LABEL`, `GMAIL_REPLY_TO_THREAD`, `GMAIL_DELETE_MESSAGE`, `GMAIL_MODIFY_THREAD_LABELS`, `GMAIL_ADD_LABEL_TO_EMAIL`, `GMAIL_BATCH_MODIFY_MESSAGES`, `GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID`

### GitHub
Key slugs: `GITHUB_LIST_REPOSITORY_ISSUES`, `GITHUB_CREATE_AN_ISSUE`, `GITHUB_LIST_COMMITS`, `GITHUB_COMPARE_TWO_COMMITS`, `GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER`, `GITHUB_LIST_PULL_REQUESTS`, `GITHUB_CREATE_A_PULL_REQUEST`, `GITHUB_LIST_REPOSITORIES_FOR_THE_AUTHENTICATED_USER`, `GITHUB_GET_A_REPOSITORY`, `GITHUB_CREATE_AN_ORGANIZATION_WEBHOOK`, `GITHUB_GET_REPOSITORY_CONTENT`

### Slack
Entity: `"default"` (ca_nbRXg7EeJgvx)
Key slugs: `SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL`, `SLACK_LIST_ALL_CHANNELS`, `SLACK_FETCH_CONVERSATION_HISTORY`, `SLACK_FIND_USERS`, `SLACK_INVITE_USER_TO_CHANNEL`, `SLACK_CREATE_CHANNEL`, `SLACK_ARCHIVE_CONVERSATION`, `SLACK_LIST_WORKSPACE_USERS`, `SLACK_FIND_USER_BY_EMAIL_ADDRESS`, `SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL` *(use thread_ts for replies)*, `SLACK_REMOVE_REACTION_FROM_ITEM`, `SLACK_ADD_REACTION_TO_AN_ITEM`, `SLACK_PINS_AN_ITEM_TO_A_CHANNEL`

### Notion
Entity: `"default"` (ca_VCkrXCRVWUVp)
Key slugs: `NOTION_ADD_PAGE_CONTENT`, `NOTION_SEARCH_NOTION_PAGE`, `NOTION_CREATE_NOTION_PAGE`, `NOTION_RETRIEVE_PAGE`, `NOTION_UPDATE_PAGE`, `NOTION_DELETE_BLOCK`, `NOTION_INSERT_ROW_DATABASE`, `NOTION_QUERY_DATABASE`, `NOTION_FETCH_DATABASE`, `NOTION_LIST_USERS`, `NOTION_GET_ABOUT_USER`, `NOTION_FETCH_ALL_BLOCK_CONTENTS`, `NOTION_CREATE_COMMENT`

### Dropbox
Entity: `"default"` (ca__qavNcrS7vNU)
Key slugs: `DROPBOX_LIST_FILES_IN_FOLDER`, `DROPBOX_UPLOAD_FILE`, `DROPBOX_EXPORT_FILE`, `DROPBOX_CREATE_FOLDER`, `DROPBOX_GET_METADATA`, `DROPBOX_MOVE_FILE_OR_FOLDER`, `DROPBOX_DELETE_FILE`, `DROPBOX_COPY_FILE_OR_FOLDER`, `DROPBOX_CREATE_SHARED_LINK`, `DROPBOX_FILES_SEARCH`, `DROPBOX_GET_ABOUT_ME`, `DROPBOX_LIST_SHARED_LINKS`

### Twitter/X
Key slugs: `TWITTER_CREATION_OF_A_POST`, `TWITTER_RECENT_SEARCH`, `TWITTER_USER_HOME_TIMELINE_BY_USER_ID`, `TWITTER_USER_LOOKUP_BY_USERNAME`, `TWITTER_RECENT_SEARCH` *(with mentions query)*, `TWITTER_POST_DELETE_BY_POST_ID`, `TWITTER_USER_LOOKUP_ME`, `TWITTER_FOLLOW_USER`, `TWITTER_UNFOLLOW_USER`, `TWITTER_USER_LIKE_POST`, `TWITTER_UNLIKE_POST`, `TWITTER_RETWEET_POST`, `TWITTER_LIST_POST_LIKERS`

### LinkedIn
Key slugs: `LINKEDIN_CREATE_LINKED_IN_POST`, `LINKEDIN_GET_MY_INFO`, `LINKEDIN_DELETE_POST`, `LINKEDIN_GET_SHARE_STATS`, `LINKEDIN_GET_POST_CONTENT`, `LINKEDIN_GET_NETWORK_SIZE`

### Instagram
Key slugs: `INSTAGRAM_CREATE_POST`, `INSTAGRAM_GET_IG_MEDIA`, `INSTAGRAM_GET_USER_INFO`, `INSTAGRAM_GET_POST_COMMENTS`, `INSTAGRAM_GET_USER_INSIGHTS`, `INSTAGRAM_REPLY_TO_COMMENT`

### Facebook
Key slugs: `FACEBOOK_CREATE_PHOTO_POST`, `FACEBOOK_GET_PAGE_POSTS`, `FACEBOOK_CREATE_POST`, `FACEBOOK_GET_USER_PAGES`, `FACEBOOK_GET_PAGE_POSTS`, `FACEBOOK_GET_PAGE_INSIGHTS`, `FACEBOOK_LIKE_POST_OR_COMMENT`, `FACEBOOK_CREATE_COMMENT`, `FACEBOOK_GET_COMMENTS`, `FACEBOOK_DELETE_POST`

### YouTube
Key slugs: `YOUTUBE_LIST_CHANNEL_VIDEOS`, `YOUTUBE_SEARCH_YOU_TUBE`, `YOUTUBE_VIDEO_DETAILS`, `YOUTUBE_LIST_USER_PLAYLISTS`, `YOUTUBE_GET_CHANNEL_STATISTICS`, `YOUTUBE_LIST_COMMENTS`, `YOUTUBE_POST_COMMENT`, `YOUTUBE_RATE_VIDEO`, `YOUTUBE_SUBSCRIBE_CHANNEL`, `YOUTUBE_LIST_VIDEO_CATEGORIES`, `YOUTUBE_LIST_PLAYLIST_ITEMS`

### Telegram
Key slugs: `TELEGRAM_SEND_MESSAGE`, `TELEGRAM_GET_UPDATES`, `TELEGRAM_SEND_PHOTO`, `TELEGRAM_SEND_DOCUMENT`, `TELEGRAM_DELETE_MESSAGE`, `TELEGRAM_FORWARD_MESSAGE`, `TELEGRAM_GET_CHAT`, `TELEGRAM_GET_CHAT_MEMBERS_COUNT`

### Google Analytics
Key slugs: `GOOGLE_ANALYTICS_RUN_REPORT`, `GOOGLE_ANALYTICS_LIST_ACCOUNTS`, `GOOGLE_ANALYTICS_LIST_PROPERTIES`, `GOOGLE_ANALYTICS_GET_METADATA`, `GOOGLE_ANALYTICS_RUN_REALTIME_REPORT`, `GOOGLE_ANALYTICS_RUN_PIVOT_REPORT`

---

## Discover actions for any toolkit

```python
import os
from composio import Composio
client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
tools = client.tools.get_raw_composio_tools(toolkits=["notion"], limit=20)
for t in tools:
    print(t.slug)
```

---

## CRITICAL rules

- Direct tools (listed above) need NO Python code — just call them
- For Python execution: use `ACCOUNT_IDS` dict above — **never call `accounts.list()`**
- **Google Sheets** must use `ACCOUNT_IDS["googlesheets"]` = Drive account (`ca_RAPF5e1atKa_`)
- **Slack, Notion, Dropbox** are under entity `"default"` — direct tools work, Python uses their account IDs
- Always use `dangerously_skip_version_check=True`
- **Always truncate output**: `json.dumps(result, default=str)[:2000]`
- If an action slug is unknown, use discover actions first (limit=20)
- **Never pass `"null"`, `"none"`, or `"undefined"` as an argument value** — omit optional args entirely
- `ranges` in GOOGLESHEETS_BATCH_GET must be a **list**: `["Sheet1!A1:Z100"]`
- Always get a real `spreadsheet_id` via `GOOGLEDRIVE_LIST_FILES` before calling any Sheets action