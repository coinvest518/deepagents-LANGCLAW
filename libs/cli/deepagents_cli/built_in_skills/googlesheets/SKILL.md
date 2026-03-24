---
name: googlesheets
description: Interact with Googlesheets via Composio. Pre-authenticated — execute actions directly without OAuth. Account ID is pre-loaded in env.
---

# Googlesheets Skill

## Execute actions via Python

```python
import os, json
from composio import Composio

client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
account_id = os.environ["COMPOSIO_GOOGLESHEETS_ACCOUNT_ID"]

result = client.tools.execute(
    "GOOGLESHEETS_ADD_SHEET",
    arguments={},   # fill in required args
    connected_account_id=account_id,
    dangerously_skip_version_check=True,
)
print(json.dumps(result, default=str)[:2000])
```

## Available actions (top 15)

- `GOOGLESHEETS_ADD_SHEET`
- `GOOGLESHEETS_AGGREGATE_COLUMN_DATA`
- `GOOGLESHEETS_APPEND_DIMENSION`
- `GOOGLESHEETS_BATCH_CLEAR_VALUES_BY_DATA_FILTER`
- `GOOGLESHEETS_BATCH_GET`
- `GOOGLESHEETS_BATCH_UPDATE`
- `GOOGLESHEETS_BATCH_UPDATE_VALUES_BY_DATA_FILTER`
- `GOOGLESHEETS_CLEAR_BASIC_FILTER`
- `GOOGLESHEETS_CLEAR_VALUES`
- `GOOGLESHEETS_CREATE_CHART`
- `GOOGLESHEETS_CREATE_GOOGLE_SHEET1`
- `GOOGLESHEETS_CREATE_SPREADSHEET_COLUMN`
- `GOOGLESHEETS_CREATE_SPREADSHEET_ROW`
- `GOOGLESHEETS_DELETE_DIMENSION`
- `GOOGLESHEETS_DELETE_SHEET`

## Discover more actions

```python
import os
from composio import Composio
client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
tools = client.tools.get_raw_composio_tools(toolkits=["googlesheets"], limit=20)
for t in tools:
    print(t.slug)
```

## Rules
- Use `COMPOSIO_GOOGLESHEETS_ACCOUNT_ID` env var — never call `accounts.list()`
- Always truncate: `json.dumps(result, default=str)[:2000]`
- Always use `dangerously_skip_version_check=True`
