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
| `GMAIL_FETCH_EMAILS` | `query` (Gmail search syntax), `max_results`, `include_payload` |
| `GMAIL_SEND_EMAIL` | `recipient_email`, `subject`, `body`, `cc` (optional) |
| `GMAIL_CREATE_EMAIL_DRAFT` | `recipient_email`, `subject`, `body` |
| `GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID` | `message_id` |
| `GMAIL_FETCH_MESSAGE_BY_THREAD_ID` | `thread_id` |
| `GMAIL_ADD_LABEL_TO_EMAIL` | `message_id`, `label_id` |
| `GMAIL_CREATE_LABEL` | `name`, `label_list_visibility`, `message_list_visibility` |

## Gmail query syntax examples
- `"from:user@example.com"` — from a sender
- `"subject:Invoice is:unread"` — unread with subject
- `"newer_than:1d"` — last 24 hours
- `"label:INBOX"` — inbox messages

## Rules
- Use `COMPOSIO_GMAIL_ACCOUNT_ID` env var — never call `accounts.list()`
- Always truncate output: `json.dumps(result, default=str)[:2000]`
- Always use `dangerously_skip_version_check=True`
