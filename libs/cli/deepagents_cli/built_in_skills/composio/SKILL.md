---
name: composio
description: Use Composio to interact with connected services — GitHub, Gmail, LinkedIn, Google Sheets, Twitter, Telegram, Google Drive, Google Analytics, and 200+ more tools.
---

# Composio Skill

Composio is your primary gateway to external services. Your account has these **active connected toolkits** — all pre-authenticated:

| Toolkit | What you can do |
|---|---|
| **github** | Create repos, branches, issues, PRs, commits, run actions |
| **gmail** | Read, send, draft, search, label emails |
| **linkedin** | Create posts, articles, comments |
| **googlesheets** | Read, write, update, create spreadsheets |
| **twitter** | Post tweets, read timeline |
| **telegram** | Send messages to Telegram chats/channels |
| **googledrive** | Upload, download, list, share files |
| **google_analytics** | Query analytics data and reports |

## How to execute actions

```python
import os
from composio import Composio
client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])

# Get connected account id
accounts = client.connected_accounts.list()
acc = next(a for a in accounts.items
           if getattr(a.toolkit, "slug", "") == "github"
           and a.data.get("status") == "ACTIVE")

# Execute action
result = client.tools.execute(
    "GITHUB_CREATE_AN_ISSUE",
    arguments={"owner": "myorg", "repo": "myrepo", "title": "Bug", "body": "Details"},
    connected_account_id=acc.id,
    dangerously_skip_version_check=True,
)
```

## Action name format: {TOOLKIT_UPPERCASE}_{ACTION}

Common actions:
- GITHUB_CREATE_AN_ISSUE, GITHUB_LIST_REPOSITORY_ISSUES, GITHUB_CREATE_A_PULL_REQUEST
- GMAIL_SEND_EMAIL, GMAIL_FETCH_EMAILS, GMAIL_CREATE_EMAIL_DRAFT
- GOOGLESHEETS_BATCH_UPDATE, GOOGLESHEETS_BATCH_GET
- GOOGLEDRIVE_UPLOAD_FILE, GOOGLEDRIVE_LIST_FILES
- LINKEDIN_CREATE_LINKED_IN_POST
- TWITTER_CREATION_OF_A_POST

## Discover actions for a toolkit

```python
tools = client.tools.get_raw_composio_tools(toolkits=["github"], limit=50)
for t in tools: print(t.slug)
```

## Notes

- COMPOSIO_API_KEY is always in the environment
- Always use dangerously_skip_version_check=True
- All 8 toolkits pre-authenticated — no OAuth needed
- Test: python scripts/test_composio.py
