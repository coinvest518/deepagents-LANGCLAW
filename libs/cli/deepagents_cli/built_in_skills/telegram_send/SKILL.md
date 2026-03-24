---
name: telegram_send
description: Send Telegram messages to chats/groups via Composio. TELEGRAM_SEND_MESSAGE is wired as a direct tool — no Python needed for basic messaging.
---

# Telegram Send Skill

## Direct tool (no Python needed)

| Tool | What it does |
|---|---|
| `TELEGRAM_SEND_MESSAGE` | Send a message to a Telegram chat |

## More Telegram actions via Python

```python
import os, json
from composio import Composio

client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
account_id = os.environ["COMPOSIO_TELEGRAM_ACCOUNT_ID"]

# Send a message
result = client.tools.execute(
    "TELEGRAM_SEND_MESSAGE",
    arguments={
        "chat_id": "-1003331527610",  # group ID or @username
        "text": "Hello from the agent!",
        "parse_mode": "HTML",         # optional: HTML or Markdown
    },
    connected_account_id=account_id,
    dangerously_skip_version_check=True,
)
print(json.dumps(result, default=str)[:2000])
```

## Common actions

| Action | Key arguments |
|---|---|
| `TELEGRAM_SEND_MESSAGE` | `chat_id`, `text`, `parse_mode` (HTML/Markdown) |
| `TELEGRAM_EDIT_MESSAGE` | `chat_id`, `message_id`, `text` |
| `TELEGRAM_DELETE_MESSAGE` | `chat_id`, `message_id` |
| `TELEGRAM_FORWARD_MESSAGE` | `chat_id`, `from_chat_id`, `message_id` |
| `TELEGRAM_GET_CHAT` | `chat_id` |
| `TELEGRAM_GET_CHAT_HISTORY` | `chat_id`, `limit` |
| `TELEGRAM_CREATE_CHAT_INVITE_LINK` | `chat_id`, `expire_date`, `member_limit` |
| `TELEGRAM_GET_CHAT_ADMINISTRATORS` | `chat_id` |

## Known chat IDs
- Main group: `-1003331527610`
- Always listen group: `-1002377223844`

## Rules
- Use `COMPOSIO_TELEGRAM_ACCOUNT_ID` env var
- chat_id can be numeric ID or @username
- HTML parse_mode supports: `<b>bold</b>`, `<i>italic</i>`, `<code>code</code>`, `<a href="url">link</a>`
- Always truncate: `json.dumps(result, default=str)[:2000]`
- Always use `dangerously_skip_version_check=True`
