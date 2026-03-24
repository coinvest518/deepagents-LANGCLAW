---
name: googledrive
description: Interact with Googledrive via Composio. Pre-authenticated — execute actions directly without OAuth. Account ID is pre-loaded in env.
---

# Googledrive Skill

## Execute actions via Python

```python
import os, json
from composio import Composio

client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
account_id = os.environ["COMPOSIO_GOOGLEDRIVE_ACCOUNT_ID"]

result = client.tools.execute(
    "GOOGLEDRIVE_ADD_FILE_SHARING_PREFERENCE",
    arguments={},   # fill in required args
    connected_account_id=account_id,
    dangerously_skip_version_check=True,
)
print(json.dumps(result, default=str)[:2000])
```

## Available actions (top 15)

- `GOOGLEDRIVE_ADD_FILE_SHARING_PREFERENCE`
- `GOOGLEDRIVE_ADD_PARENT`
- `GOOGLEDRIVE_ADD_PROPERTY`
- `GOOGLEDRIVE_COPY_FILE`
- `GOOGLEDRIVE_COPY_FILE_ADVANCED`
- `GOOGLEDRIVE_CREATE_COMMENT`
- `GOOGLEDRIVE_CREATE_DRIVE`
- `GOOGLEDRIVE_CREATE_FILE`
- `GOOGLEDRIVE_CREATE_FILE_FROM_TEXT`
- `GOOGLEDRIVE_CREATE_FOLDER`
- `GOOGLEDRIVE_CREATE_PERMISSION`
- `GOOGLEDRIVE_CREATE_REPLY`
- `GOOGLEDRIVE_CREATE_SHORTCUT_TO_FILE`
- `GOOGLEDRIVE_CREATE_TEAM_DRIVE`
- `GOOGLEDRIVE_DELETE_CHILD`

## Discover more actions

```python
import os
from composio import Composio
client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
tools = client.tools.get_raw_composio_tools(toolkits=["googledrive"], limit=20)
for t in tools:
    print(t.slug)
```

## Rules
- Use `COMPOSIO_GOOGLEDRIVE_ACCOUNT_ID` env var — never call `accounts.list()`
- Always truncate: `json.dumps(result, default=str)[:2000]`
- Always use `dangerously_skip_version_check=True`
