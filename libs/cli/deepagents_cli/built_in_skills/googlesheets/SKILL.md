---
name: googlesheets
description: Interact with Google Sheets via Composio. Pre-authenticated — execute actions directly without OAuth. CRITICAL: Always use COMPOSIO_GOOGLEDRIVE_ACCOUNT_ID (not the sheets-native account).
---

# Google Sheets Skill

## CRITICAL: Account ID

**Always use `COMPOSIO_GOOGLEDRIVE_ACCOUNT_ID`** for ALL Google Sheets actions.
The sheets-native account has a broken token. This is handled automatically by `composio_action`.

## Core actions (most common)

| Action | What it does |
|--------|-------------|
| `GOOGLESHEETS_CREATE_GOOGLE_SHEET1` | Create a new spreadsheet (`title`) |
| `GOOGLESHEETS_BATCH_GET` | Read ranges (`spreadsheet_id`, `ranges` as list) |
| `GOOGLESHEETS_BATCH_UPDATE` | Write to ranges |
| `GOOGLESHEETS_SPREADSHEETS_VALUES_APPEND` | Append rows |
| `GOOGLESHEETS_CREATE_SPREADSHEET_ROW` | Insert a row |
| `GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW` | Find a row |
| `GOOGLESHEETS_UPSERT_ROWS` | Insert or update rows |
| `GOOGLESHEETS_CLEAR_VALUES` | Clear a range |
| `GOOGLESHEETS_ADD_SHEET` | Add a new tab |
| `GOOGLESHEETS_GET_SHEET_NAMES` | List all tabs |
| `GOOGLESHEETS_FORMAT_CELL` | Format cells |
| `GOOGLESHEETS_CREATE_CHART` | Create a chart |
| `GOOGLESHEETS_FIND_REPLACE` | Find & replace text |
| `GOOGLESHEETS_EXECUTE_SQL` | SQL-like query on data |
| `GOOGLESHEETS_GET_SPREADSHEET_INFO` | Get spreadsheet metadata |

## More actions (discover on demand)

Use `composio_get_schema("GOOGLESHEETS_<ACTION>")` to get parameters for any action.

Additional actions available: `SEARCH_SPREADSHEETS`, `DELETE_SHEET`, `FIND_WORKSHEET_BY_TITLE`, `UPDATE_SHEET_PROPERTIES`, `VALUES_GET`, `VALUES_UPDATE`, `UPDATE_VALUES_BATCH`, `CREATE_SPREADSHEET_COLUMN`, `SHEET_FROM_JSON`, `AGGREGATE_COLUMN_DATA`, `QUERY_TABLE`, `LIST_TABLES`, `GET_TABLE_SCHEMA`, `SET_BASIC_FILTER`, `CLEAR_BASIC_FILTER`, `SET_DATA_VALIDATION_RULE`, `AUTO_RESIZE_DIMENSIONS`, `INSERT_DIMENSION`, `DELETE_DIMENSION`, `UPDATE_DIMENSION_PROPERTIES`, `APPEND_DIMENSION`, `GET_CONDITIONAL_FORMAT_RULES`, `MUTATE_CONDITIONAL_FORMAT_RULES`, `SEARCH_DEVELOPER_METADATA`, `UPDATE_SPREADSHEET_PROPERTIES`, `SPREADSHEETS_SHEETS_COPY_TO`, `GET_BATCH_VALUES`, `BATCH_CLEAR_VALUES_BY_DATA_FILTER`, `BATCH_UPDATE_VALUES_BY_DATA_FILTER`, `SPREADSHEETS_VALUES_BATCH_CLEAR`, `SPREADSHEETS_VALUES_BATCH_GET_BY_DATA_FILTER`, `GET_SPREADSHEET_BY_DATA_FILTER`, `GET_DATA_VALIDATION_RULES`

(All prefixed with `GOOGLESHEETS_`)

## Key rules

- **Finding spreadsheet_id**: Use `GOOGLEDRIVE_LIST_FILES` with `query="mimeType='application/vnd.google-apps.spreadsheet'"` — or extract from URL
- **`ranges` must be a list**: `["Sheet1!A1:Z100"]` — NOT a string
- **Get a real `spreadsheet_id` before calling read/write actions**
- To discover parameters: `composio_get_schema("GOOGLESHEETS_BATCH_GET")`
