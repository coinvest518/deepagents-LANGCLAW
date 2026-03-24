---
name: telegram
description: Interact with Telegram via Composio. Pre-authenticated — execute actions directly without OAuth. Account ID is pre-loaded in env.
---

# Telegram Skill

## Execute actions via Python

```python
import os, json
from composio import Composio

client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
account_id = os.environ["COMPOSIO_TELEGRAM_ACCOUNT_ID"]

result = client.tools.execute(
    "TELEGRAM_ANSWER_CALLBACK_QUERY",
    arguments={},   # fill in required args
    connected_account_id=account_id,
    dangerously_skip_version_check=True,
)
print(json.dumps(result, default=str)[:2000])
```

## Available actions (top 15)

- `TELEGRAM_ANSWER_CALLBACK_QUERY`
- `TELEGRAM_CREATE_CHAT_INVITE_LINK`
- `TELEGRAM_DELETE_MESSAGE`
- `TELEGRAM_EDIT_MESSAGE`
- `TELEGRAM_FORWARD_MESSAGE`
- `TELEGRAM_GET_CHAT`
- `TELEGRAM_GET_CHAT_ADMINISTRATORS`
- `TELEGRAM_GET_CHAT_HISTORY`
- `TELEGRAM_GET_CHAT_MEMBER`
- `TELEGRAM_GET_CHAT_MEMBERS_COUNT`
- `TELEGRAM_GET_ME`
- `TELEGRAM_GET_UPDATES`
- `TELEGRAM_SEND_DOCUMENT`
- `TELEGRAM_SEND_LOCATION`
- `TELEGRAM_SEND_MESSAGE`

## Discover more actions

```python
import os
from composio import Composio
client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
tools = client.tools.get_raw_composio_tools(toolkits=["telegram"], limit=20)
for t in tools:
    print(t.slug)
```

## Rules
- Use `COMPOSIO_TELEGRAM_ACCOUNT_ID` env var — never call `accounts.list()`
- Always truncate: `json.dumps(result, default=str)[:2000]`
- Always use `dangerously_skip_version_check=True`
