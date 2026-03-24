---
name: composio
description: Use Composio to interact with connected services — GitHub, Gmail, LinkedIn, Google Sheets, Twitter, Telegram, Google Drive, Google Analytics, and 200+ more tools. All 8 toolkits are PRE-AUTHENTICATED — execute actions directly, no OAuth needed.
---

# Composio Skill

All services below are **already connected and authenticated**. Execute actions directly.

| Toolkit | Common actions |
|---|---|
| **googlesheets** | GOOGLESHEETS_BATCH_GET, GOOGLESHEETS_BATCH_UPDATE, GOOGLESHEETS_CREATE_SPREADSHEET |
| **gmail** | GMAIL_FETCH_EMAILS, GMAIL_SEND_EMAIL, GMAIL_CREATE_EMAIL_DRAFT |
| **github** | GITHUB_CREATE_AN_ISSUE, GITHUB_LIST_REPOSITORY_ISSUES, GITHUB_CREATE_A_PULL_REQUEST |
| **linkedin** | LINKEDIN_CREATE_LINKED_IN_POST |
| **googledrive** | GOOGLEDRIVE_UPLOAD_FILE, GOOGLEDRIVE_LIST_FILES |
| **google_analytics** | GOOGLE_ANALYTICS_LIST_ACCOUNTS |
| **twitter** | TWITTER_CREATION_OF_A_POST |
| **telegram** | TELEGRAM_SEND_MESSAGE |

## Execute an action (copy this pattern exactly)

```python
import os, json
from composio import Composio

client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])

# Step 1: get the connected account id for the toolkit you need
accounts = client.connected_accounts.list()
acc = next(
    (a for a in accounts.items
     if getattr(a.toolkit, "slug", "") == "googlesheets"  # change toolkit name here
     and a.data.get("status") == "ACTIVE"),
    None,
)
if acc is None:
    print("googlesheets not connected")
else:
    print(f"Connected account id: {acc.id}")

    # Step 2: execute the action
    result = client.tools.execute(
        "GOOGLESHEETS_BATCH_GET",  # action name
        arguments={"spreadsheet_id": "YOUR_ID", "ranges": ["Sheet1!A1:Z100"]},
        connected_account_id=acc.id,
        dangerously_skip_version_check=True,
    )

    # IMPORTANT: always truncate output — Composio returns large JSON
    print(json.dumps(result, default=str)[:2000])
```

## List connected accounts (quick check)

```python
import os
from composio import Composio
client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
accounts = client.connected_accounts.list()
for a in accounts.items:
    slug = getattr(a.toolkit, "slug", "?")
    status = a.data.get("status", "?")
    print(f"  {slug}: {status} (id={a.id})")
```

## Discover available actions for a toolkit

```python
import os
from composio import Composio
client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
tools = client.tools.get_raw_composio_tools(toolkits=["googlesheets"], limit=20)
for t in tools:
    print(t.slug)
```

## CRITICAL rules

- `COMPOSIO_API_KEY` is always in the environment — never ask for it
- Always use `dangerously_skip_version_check=True`
- **Always truncate output**: `print(json.dumps(result, default=str)[:2000])`
- Never print the full `accounts.items` list — it can be thousands of lines
- If an action name is unknown, use discover actions first (limit=20)
