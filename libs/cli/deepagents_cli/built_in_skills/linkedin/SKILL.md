---
name: linkedin
description: Post to LinkedIn — articles, posts, comments. Pre-authenticated via Composio. LINKEDIN_CREATE_LINKED_IN_POST is wired as a direct tool.
---

# LinkedIn Skill

## Direct tool (no Python needed)

| Tool | What it does |
|---|---|
| `LINKEDIN_CREATE_LINKED_IN_POST` | Create a LinkedIn post |

## More actions via Python

```python
import os, json
from composio import Composio

client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
account_id = os.environ["COMPOSIO_LINKEDIN_ACCOUNT_ID"]

# Create a post
result = client.tools.execute(
    "LINKEDIN_CREATE_LINKED_IN_POST",
    arguments={
        "text": "Excited to share our latest update! #AI #Innovation",
        "visibility": "PUBLIC",
    },
    connected_account_id=account_id,
    dangerously_skip_version_check=True,
)
print(json.dumps(result, default=str)[:2000])
```

## Common actions

| Action | Key arguments |
|---|---|
| `LINKEDIN_CREATE_LINKED_IN_POST` | `text`, `visibility` (PUBLIC/CONNECTIONS) |
| `LINKEDIN_CREATE_ARTICLE_OR_URL_SHARE` | `text`, `url`, `title` |
| `LINKEDIN_CREATE_COMMENT_ON_POST` | `post_id`, `text` |
| `LINKEDIN_DELETE_LINKED_IN_POST` | `post_id` |

## Rules
- Use `COMPOSIO_LINKEDIN_ACCOUNT_ID` env var
- Always truncate: `json.dumps(result, default=str)[:2000]`
- Always use `dangerously_skip_version_check=True`
