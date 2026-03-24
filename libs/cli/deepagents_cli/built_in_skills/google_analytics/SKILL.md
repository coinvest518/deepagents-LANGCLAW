---
name: google_analytics
description: Interact with Google Analytics via Composio. Pre-authenticated — execute actions directly without OAuth. Account ID is pre-loaded in env.
---

# Google Analytics Skill

## Execute actions via Python

```python
import os, json
from composio import Composio

client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
account_id = os.environ["COMPOSIO_GOOGLE_ANALYTICS_ACCOUNT_ID"]

result = client.tools.execute(
    "GOOGLE_ANALYTICS_ARCHIVE_CUSTOM_DIMENSION",
    arguments={},   # fill in required args
    connected_account_id=account_id,
    dangerously_skip_version_check=True,
)
print(json.dumps(result, default=str)[:2000])
```

## Available actions (top 15)

- `GOOGLE_ANALYTICS_ARCHIVE_CUSTOM_DIMENSION`
- `GOOGLE_ANALYTICS_BATCH_RUN_PIVOT_REPORTS`
- `GOOGLE_ANALYTICS_BATCH_RUN_REPORTS`
- `GOOGLE_ANALYTICS_CHECK_COMPATIBILITY`
- `GOOGLE_ANALYTICS_CREATE_AUDIENCE_EXPORT`
- `GOOGLE_ANALYTICS_CREATE_AUDIENCE_LIST`
- `GOOGLE_ANALYTICS_CREATE_CUSTOM_DIMENSION`
- `GOOGLE_ANALYTICS_CREATE_CUSTOM_METRIC`
- `GOOGLE_ANALYTICS_CREATE_EXPANDED_DATA_SET`
- `GOOGLE_ANALYTICS_CREATE_RECURRING_AUDIENCE_LIST`
- `GOOGLE_ANALYTICS_CREATE_REPORT_TASK`
- `GOOGLE_ANALYTICS_CREATE_ROLLUP_PROPERTY`
- `GOOGLE_ANALYTICS_GET_ACCOUNT`
- `GOOGLE_ANALYTICS_GET_ATTRIBUTION_SETTINGS`
- `GOOGLE_ANALYTICS_GET_AUDIENCE`

## Discover more actions

```python
import os
from composio import Composio
client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
tools = client.tools.get_raw_composio_tools(toolkits=["google_analytics"], limit=20)
for t in tools:
    print(t.slug)
```

## Rules
- Use `COMPOSIO_GOOGLE_ANALYTICS_ACCOUNT_ID` env var — never call `accounts.list()`
- Always truncate: `json.dumps(result, default=str)[:2000]`
- Always use `dangerously_skip_version_check=True`
