---
name: slack
description: Send Slack messages, manage channels and reactions. Pre-authenticated via Composio. SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL is wired as a native direct tool.
---

# Slack Skill

## Direct tools (no Python needed)

| Tool | What it does |
|---|---|
| `SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL` | Send a message to a channel or DM |

## More Slack actions via Python

```python
import os, json
from composio import Composio

client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
account_id = os.environ["COMPOSIO_SLACK_ACCOUNT_ID"]

# Send a message
result = client.tools.execute(
    "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL",
    arguments={
        "channel": "#general",   # or channel ID like "C12345678"
        "text": "Hello from the agent!",
    },
    connected_account_id=account_id,
    dangerously_skip_version_check=True,
)
print(json.dumps(result, default=str)[:2000])
```

## Common actions

| Action | Key arguments |
|---|---|
| `SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL` | `channel` (name or ID), `text` |
| `SLACK_LIST_CONVERSATIONS` | `types` (public_channel,private_channel,im,mpim), `limit` |
| `SLACK_FETCH_CONVERSATION_HISTORY` | `channel`, `limit` |
| `SLACK_ADD_REACTION_TO_AN_ITEM` | `channel`, `timestamp`, `name` (emoji without :) |
| `SLACK_UPLOAD_A_FILE` | `channels`, `filename`, `content`, `filetype` |
| `SLACK_CREATE_A_REMINDER` | `text`, `time`, `user` |

## Discover actions

```python
import os
from composio import Composio
client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
tools = client.tools.get_raw_composio_tools(toolkits=["slack"], limit=20)
for t in tools:
    print(t.slug)
```

## Rules
- Use `COMPOSIO_SLACK_ACCOUNT_ID` env var — never call `accounts.list()`
- Use `#channel-name` or channel ID for `channel` arg
- Always truncate: `json.dumps(result, default=str)[:2000]`
- Always use `dangerously_skip_version_check=True`
