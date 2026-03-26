---
name: github
description: Interact with GitHub repositories — create/list issues, pull requests, manage code. Pre-authenticated via Composio. The direct tool GITHUB_LIST_REPOSITORY_ISSUES and GITHUB_CREATE_AN_ISSUE are wired as native tools — call them directly without Python.
---

# GitHub Skill

## Direct tools (no Python needed)

These tools are wired directly — call them like any other tool:

| Tool | What it does |
|---|---|
| `GITHUB_LIST_REPOSITORY_ISSUES` | List issues in a repo |
| `GITHUB_CREATE_AN_ISSUE` | Create a new issue |

## More GitHub actions via Python

```python
import os, json
from composio import Composio

client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
account_id = os.environ["COMPOSIO_GITHUB_ACCOUNT_ID"]

# List issues
result = client.tools.execute(
    "GITHUB_LIST_REPOSITORY_ISSUES",
    arguments={"owner": "owner_name", "repo": "repo_name", "state": "open"},
    connected_account_id=account_id,
    dangerously_skip_version_check=True,
)
print(json.dumps(result, default=str)[:2000])
```

## Common actions

| Action | Key arguments |
|---|---|
| `GITHUB_LIST_REPOSITORY_ISSUES` | `owner`, `repo`, `state` (open/closed/all) |
| `GITHUB_CREATE_AN_ISSUE` | `owner`, `repo`, `title`, `body` |
| `GITHUB_CREATE_A_PULL_REQUEST` | `owner`, `repo`, `title`, `head`, `base`, `body` |
| `GITHUB_GET_A_REPOSITORY` | `owner`, `repo` |
| `GITHUB_LIST_REPOSITORIES_FOR_THE_AUTHENTICATED_USER` | `per_page`, `page` |
| `GITHUB_LIST_COMMITS` | `owner`, `repo`, `sha` (branch) |
| `GITHUB_ADD_LABELS_TO_AN_ISSUE` | `owner`, `repo`, `issue_number`, `labels` |
| `GITHUB_CREATE_AN_ISSUE_COMMENT` | `owner`, `repo`, `issue_number`, `body` |

## Discover more actions

```python
import os
from composio import Composio
client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
tools = client.tools.get_raw_composio_tools(toolkits=["github"], limit=20)
for t in tools:
    print(t.slug)
```

## Rules
- Use `COMPOSIO_GITHUB_ACCOUNT_ID` env var — never call `accounts.list()`
- Always truncate output: `json.dumps(result, default=str)[:2000]`
- Always use `dangerously_skip_version_check=True`
