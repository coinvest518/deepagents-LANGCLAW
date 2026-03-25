---
name: gmail
description: Send and read Gmail emails, manage labels and drafts. Pre-authenticated via Composio. GMAIL_FETCH_EMAILS and GMAIL_SEND_EMAIL are wired as native direct tools.
---

# Gmail Skill

## Direct tools (no Python needed)

| Tool | What it does |
|---|---|
| `GMAIL_FETCH_EMAILS` | Fetch emails matching a query |
| `GMAIL_SEND_EMAIL` | Send an email |

## More Gmail actions via Python

```python
import os, json
from composio import Composio

client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
account_id = os.environ["COMPOSIO_GMAIL_ACCOUNT_ID"]

# Send email
result = client.tools.execute(
    "GMAIL_SEND_EMAIL",
    arguments={
        "recipient_email": "example@gmail.com",
        "subject": "Hello",
        "body": "Message body here",
    },
    connected_account_id=account_id,
    dangerously_skip_version_check=True,
)
print(json.dumps(result, default=str)[:2000])
```

## Common actions

| Action | Key arguments |
|---|---|
| `GMAIL_FETCH_EMAILS` | `query`, `max_results`, `label_ids`, `include_payload` |
| `GMAIL_SEND_EMAIL` | `recipient_email`, `subject`, `body`, `cc` (optional) |
| `GMAIL_CREATE_EMAIL_DRAFT` | `recipient_email`, `subject`, `body` |
| `GMAIL_LIST_LABELS` | *(no required args)* — returns all labels/folders |
| `GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID` | `message_id` |
| `GMAIL_FETCH_MESSAGE_BY_THREAD_ID` | `thread_id` |
| `GMAIL_ADD_LABEL_TO_EMAIL` | `message_id`, `label_id` |
| `GMAIL_CREATE_LABEL` | `name`, `label_list_visibility`, `message_list_visibility` |

## Fetching from a specific folder / tab

Gmail uses **labels** for folders and tabs. Use `label_ids` array to filter.

**CRITICAL — Gmail tabs vs INBOX:**
- `"INBOX"` = ALL inbox emails (includes Primary + Promotions + Social + Updates)
- `"CATEGORY_PERSONAL"` = **Primary tab ONLY** (what the user means by "main inbox")
- `"CATEGORY_PROMOTIONS"` = Promotions tab only
- `"CATEGORY_SOCIAL"` = Social tab only
- `"CATEGORY_UPDATES"` = Updates tab only

When the user says "main inbox", "primary", or "main folder", use `CATEGORY_PERSONAL`:
```
composio_action("GMAIL_FETCH_EMAILS", {"label_ids": ["CATEGORY_PERSONAL"], "max_results": 5})
```

### All label IDs

| Label ID | What it is |
|----------|-----------|
| `INBOX` | All inbox emails (all tabs combined) |
| `CATEGORY_PERSONAL` | **Primary tab** (personal/important emails) |
| `CATEGORY_PROMOTIONS` | Promotions tab |
| `CATEGORY_SOCIAL` | Social tab |
| `CATEGORY_UPDATES` | Updates tab |
| `CATEGORY_FORUMS` | Forums tab |
| `SENT` | Sent mail |
| `DRAFT` | Drafts |
| `SPAM` | Spam folder |
| `TRASH` | Trash |
| `IMPORTANT` | Important emails |
| `STARRED` | Starred emails |
| `UNREAD` | Unread emails |

### Switching between tabs/folders

If user says "check promotions": `{"label_ids": ["CATEGORY_PROMOTIONS"]}`
If user says "check primary/main": `{"label_ids": ["CATEGORY_PERSONAL"]}`
If user says "check updates": `{"label_ids": ["CATEGORY_UPDATES"]}`
If user says "check all inbox": `{"label_ids": ["INBOX"]}`

**IMPORTANT**: `label_ids` uses AND logic. If you pass `["INBOX", "CATEGORY_PERSONAL"]`,
it returns emails that have BOTH labels. To get Primary tab emails, just use
`["CATEGORY_PERSONAL"]` alone.

**IMPORTANT**: If you already searched one folder and the user says "no, check a different
folder", you MUST change the `label_ids` parameter — do NOT repeat the same call.

To discover custom labels: `composio_action("GMAIL_LIST_LABELS", {})`

## Gmail query syntax examples
- `"from:user@example.com"` — from a sender
- `"subject:Invoice is:unread"` — unread with subject
- `"newer_than:1d"` — last 24 hours
- `"category:primary"` — primary tab (alternative to label_ids)
- `"in:anywhere"` — search all folders

You can combine query with label_ids:
```
composio_action("GMAIL_FETCH_EMAILS", {"query": "from:boss@company.com", "label_ids": ["CATEGORY_PERSONAL"], "max_results": 5})
```

## Rules
- Use `COMPOSIO_GMAIL_ACCOUNT_ID` env var — never call `accounts.list()`
- Always use `dangerously_skip_version_check=True`
- Default to `label_ids: ["CATEGORY_PERSONAL"]` when user says "inbox" or "main"
- When user asks to check a different folder, CHANGE the label_ids — never repeat the same search
- If a search returns nothing useful, try `GMAIL_LIST_LABELS` to discover available labels
- Use `include_payload: false` for listing (faster), `true` only when reading email content
