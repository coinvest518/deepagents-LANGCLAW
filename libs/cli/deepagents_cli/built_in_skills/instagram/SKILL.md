---
name: instagram
description: Post to Instagram — images, carousels, reels. Pre-authenticated via Composio. INSTAGRAM_CREATE_POST is wired as a direct tool.
---

# Instagram Skill

## Direct tool (no Python needed)

| Tool | What it does |
|---|---|
| `INSTAGRAM_CREATE_POST` | Publish an image/video post |

## More actions via Python

```python
import os, json
from composio import Composio

client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
account_id = os.environ["COMPOSIO_INSTAGRAM_ACCOUNT_ID"]

# Post an image
result = client.tools.execute(
    "INSTAGRAM_CREATE_MEDIA_CONTAINER",
    arguments={
        "image_url": "https://example.com/photo.jpg",
        "caption": "Check this out! #AI",
    },
    connected_account_id=account_id,
    dangerously_skip_version_check=True,
)
print(json.dumps(result, default=str)[:2000])
```

## Posting workflow (2-step)

Instagram requires creating a container first, then publishing:

```python
import os, json
from composio import Composio
client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
account_id = os.environ["COMPOSIO_INSTAGRAM_ACCOUNT_ID"]

# Step 1: Create media container
container = client.tools.execute(
    "INSTAGRAM_CREATE_MEDIA_CONTAINER",
    arguments={"image_url": "https://example.com/photo.jpg", "caption": "My post"},
    connected_account_id=account_id,
    dangerously_skip_version_check=True,
)
container_id = json.loads(json.dumps(container, default=str)).get("id")

# Step 2: Publish
result = client.tools.execute(
    "INSTAGRAM_CREATE_POST",
    arguments={"creation_id": container_id},
    connected_account_id=account_id,
    dangerously_skip_version_check=True,
)
print(json.dumps(result, default=str)[:2000])
```

## Common actions

| Action | Key arguments |
|---|---|
| `INSTAGRAM_CREATE_MEDIA_CONTAINER` | `image_url`, `caption`, `video_url` |
| `INSTAGRAM_CREATE_POST` | `creation_id` (from container step) |
| `INSTAGRAM_CREATE_CAROUSEL_CONTAINER` | `children` (list of container IDs), `caption` |
| `INSTAGRAM_GET_IG_MEDIA` | `media_id` |
| `INSTAGRAM_DELETE_COMMENT` | `comment_id` |

## Rules
- Use `COMPOSIO_INSTAGRAM_ACCOUNT_ID` env var
- Image URL must be public HTTPS
- Always truncate: `json.dumps(result, default=str)[:2000]`
- Always use `dangerously_skip_version_check=True`
