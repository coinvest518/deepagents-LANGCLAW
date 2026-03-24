---
name: facebook
description: Post to Facebook pages — text posts, photos, videos, comments. Pre-authenticated via Composio.
---

# Facebook Skill

## Actions via Python

```python
import os, json
from composio import Composio

client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
account_id = os.environ["COMPOSIO_FACEBOOK_ACCOUNT_ID"]

# Create a text post
result = client.tools.execute(
    "FACEBOOK_CREATE_POST",
    arguments={"message": "Hello from the agent!"},
    connected_account_id=account_id,
    dangerously_skip_version_check=True,
)
print(json.dumps(result, default=str)[:2000])
```

## Common actions

| Action | Key arguments |
|---|---|
| `FACEBOOK_CREATE_POST` | `message`, `link` (optional URL) |
| `FACEBOOK_CREATE_PHOTO_POST` | `message`, `url` (image URL) |
| `FACEBOOK_CREATE_VIDEO_POST` | `description`, `file_url` |
| `FACEBOOK_CREATE_PHOTO_ALBUM` | `name`, `message` |
| `FACEBOOK_ADD_PHOTOS_TO_ALBUM` | `album_id`, `url` |
| `FACEBOOK_CREATE_COMMENT` | `object_id`, `message` |
| `FACEBOOK_DELETE_COMMENT` | `comment_id` |

## Discover more actions

```python
import os
from composio import Composio
client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
tools = client.tools.get_raw_composio_tools(toolkits=["facebook"], limit=20)
for t in tools:
    print(t.slug)
```

## Rules
- Use `COMPOSIO_FACEBOOK_ACCOUNT_ID` env var
- Always truncate: `json.dumps(result, default=str)[:2000]`
- Always use `dangerously_skip_version_check=True`
