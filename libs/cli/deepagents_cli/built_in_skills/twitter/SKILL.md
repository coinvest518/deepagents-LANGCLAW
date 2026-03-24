---
name: twitter
description: Post tweets, manage Twitter/X account. Pre-authenticated via Composio. TWITTER_CREATION_OF_A_POST is wired as a direct tool — no Python needed.
---

# Twitter / X Skill

## Direct tool (no Python needed)

| Tool | What it does |
|---|---|
| `TWITTER_CREATION_OF_A_POST` | Post a tweet |

## More actions via Python

```python
import os, json
from composio import Composio

client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
account_id = os.environ["COMPOSIO_TWITTER_ACCOUNT_ID"]

# Post a tweet
result = client.tools.execute(
    "TWITTER_CREATION_OF_A_POST",
    arguments={"text": "Hello from the agent! #AI"},
    connected_account_id=account_id,
    dangerously_skip_version_check=True,
)
print(json.dumps(result, default=str)[:2000])
```

## Common actions

| Action | Key arguments |
|---|---|
| `TWITTER_CREATION_OF_A_POST` | `text` (max 280 chars) |
| `TWITTER_CREATE_DM_CONVERSATION` | `participant_id`, `text` |
| `TWITTER_ADD_POST_TO_BOOKMARKS` | `tweet_id` |
| `TWITTER_BOOKMARKS_BY_USER` | `id` (user ID), `max_results` |
| `TWITTER_CREATE_LIST` | `name`, `private` |
| `TWITTER_ADD_LIST_MEMBER` | `list_id`, `user_id` |

## Rules
- Use `COMPOSIO_TWITTER_ACCOUNT_ID` env var
- Always truncate: `json.dumps(result, default=str)[:2000]`
- Always use `dangerously_skip_version_check=True`
