---
name: notion
description: >
  Full control skill for Notion via Composio. Use when the owner asks to
  create, read, update, or organize anything in Notion — pages, databases,
  tables, rows, content blocks, images, or workspace structure. Workspace is
  "CoinVest INC's Space". Contains all action slugs, full parameter schemas,
  block types, and property formats. Trigger phrases: "create a page",
  "update Notion", "add to database", "redesign the page", "read notion page",
  "add a row", "organize notion", "make a table in notion".
license: MIT
compatibility: deepagents-cli
metadata:
  toolkit: notion
  workspace: CoinVest INC's Space
---

# Notion Skill

Full Notion control via Composio. All Notion actions are available using the
Composio Python client (already configured — `COMPOSIO_API_KEY` in env).

## How to Execute Actions

```python
# Quick helper — use this pattern for all Notion actions
python scripts/notion_run.py NOTION_CREATE_NOTION_PAGE '{"parent_id": "a8801897-efe7-4074-8f37-521b8075a840", "title": "My Page", "icon": "📄"}'
```

Or directly in Python:
```python
import os, json
from composio import Composio
client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
# Use pre-loaded account ID — never call accounts.list()
account_id = os.environ["COMPOSIO_NOTION_ACCOUNT_ID"]
result = client.tools.execute("NOTION_CREATE_NOTION_PAGE", arguments={"parent_id": "...", "title": "..."}, connected_account_id=account_id, dangerously_skip_version_check=True)
print(json.dumps(result, default=str)[:2000])
```

## Direct tools (no Python needed)
`NOTION_ADD_PAGE_CONTENT` and `NOTION_SEARCH_NOTION_PAGE` are wired as direct tools — call them without any Python code.

**RULE:** Use exact slugs from this file. Never guess action names.
**RULE:** Use workspace IDs below directly — do NOT call NOTION_FETCH_DATA unless you need a child ID not listed here.
**RULE:** After creating a page, use the returned page_id immediately to add content — no re-fetch needed.

---

## Known Workspace IDs — Use Directly

| Name | ID | Type |
|------|----|------|
| Teamspace Home | a8801897-efe7-4074-8f37-521b8075a840 | page |
| CoinVest AI Command Center | da5b40c6-a5cc-83da-a66e-810e2fc04347 | page |
| AI Products Catalog | c0a35096-58a1-46c1-aea2-f2887097309f | database |
| Docs | aa59ca33-a929-4f88-972e-ca377eb10109 | database |
| Skills (child db) | 394b40c6-a5cc-83e4-bec9-012303c18435 | database |
| Case Studies (child db) | 6dfb40c6-a5cc-820c-928f-01f846369a25 | database |

---

## Actions — Full Schemas

### NOTION_CREATE_NOTION_PAGE
Create a new page inside a page or database. Cannot create root-level pages.
- parent_id (string, REQUIRED): ID of parent page or database. Use known IDs above.
- title (string, REQUIRED): Page title
- markdown (string, optional): Full content in markdown — headings, lists, bold, etc.
- icon (string, optional): Single emoji e.g. "🚀"

```bash
python scripts/notion_run.py NOTION_CREATE_NOTION_PAGE '{"parent_id": "a8801897-efe7-4074-8f37-521b8075a840", "title": "New Page", "markdown": "# Hello\n\nContent here", "icon": "📄"}'
```

---

### NOTION_APPEND_TEXT_BLOCKS
Append content blocks to a page. Pass the page_id as block_id.
- block_id (string, REQUIRED): The page ID to append to
- children (array, REQUIRED): List of block objects (see BLOCK TYPES section)

```bash
python scripts/notion_run.py NOTION_APPEND_TEXT_BLOCKS '{"block_id": "PAGE_ID", "children": [{"type": "heading_1", "content": "Title"}, {"type": "paragraph", "content": "Body text"}]}'
```

---

### NOTION_ADD_MULTIPLE_PAGE_CONTENT
Append richer structured blocks. Alternative to NOTION_APPEND_TEXT_BLOCKS.
- parent_block_id (string, REQUIRED): Page ID
- content_blocks (array, REQUIRED): List of block objects

```bash
python scripts/notion_run.py NOTION_ADD_MULTIPLE_PAGE_CONTENT '{"parent_block_id": "PAGE_ID", "content_blocks": [{"type": "heading_2", "content": "Section"}, {"type": "paragraph", "content": "Text"}]}'
```

---

### NOTION_REPLACE_PAGE_CONTENT
Wipe a page and rewrite all content from scratch. Use for full redesigns.
- page_id (string, REQUIRED): Page ID to rewrite
- new_children (array, REQUIRED): New content blocks
- backup_content (boolean, optional): Save old content before replacing

```bash
python scripts/notion_run.py NOTION_REPLACE_PAGE_CONTENT '{"page_id": "PAGE_ID", "new_children": [{"type": "heading_1", "content": "New Title"}, {"type": "paragraph", "content": "New content"}]}'
```

---

### NOTION_UPDATE_PAGE
Rename a page, change its icon, or archive it. Does NOT change content.
- page_id (string, REQUIRED)
- title (string, optional): New title
- icon (string, optional): New emoji
- archived (boolean, optional): true to archive/delete

```bash
python scripts/notion_run.py NOTION_UPDATE_PAGE '{"page_id": "PAGE_ID", "title": "New Title", "icon": "✅"}'
```

---

### NOTION_RETRIEVE_PAGE
Get page metadata — title, icon, cover, properties. Does NOT return content blocks.
- page_id (string, REQUIRED)

```bash
python scripts/notion_run.py NOTION_RETRIEVE_PAGE '{"page_id": "PAGE_ID"}'
```

---

### NOTION_FETCH_ALL_BLOCK_CONTENTS
Read all content blocks inside a page. Use before editing.
- block_id (string, REQUIRED): Same as page_id

```bash
python scripts/notion_run.py NOTION_FETCH_ALL_BLOCK_CONTENTS '{"block_id": "PAGE_ID"}'
```

---

### NOTION_CREATE_DATABASE
Create a new table/database inside a PAGE (not inside another database).
- parent_id (string, REQUIRED): Must be a PAGE id
- title (string, REQUIRED): Table name
- properties (array, optional): Column definitions (see DATABASE PROPERTIES)

```bash
python scripts/notion_run.py NOTION_CREATE_DATABASE '{"parent_id": "a8801897-efe7-4074-8f37-521b8075a840", "title": "Email List", "properties": [{"name": "Name", "type": "title"}, {"name": "Email", "type": "email"}, {"name": "Status", "type": "select", "options": [{"name": "Active", "color": "green"}]}]}'
```

---

### NOTION_INSERT_ROW_DATABASE
Add a row with exact property values.
- database_id (string, REQUIRED)
- properties (object, optional): Column values matching schema
- markdown (string, optional): Page content for the row body

```bash
python scripts/notion_run.py NOTION_INSERT_ROW_DATABASE '{"database_id": "DB_ID", "properties": {"Name": "Danny", "Email": "danny@example.com", "Status": "Active"}}'
```

---

### NOTION_INSERT_ROW_FROM_NL
Add a database row using plain English.
- database_id (string, REQUIRED)
- nl_query (string, REQUIRED): Natural language description

```bash
python scripts/notion_run.py NOTION_INSERT_ROW_FROM_NL '{"database_id": "DB_ID", "nl_query": "Add contact Danny, email danny@fdwa.com, status Active"}'
```

---

### NOTION_QUERY_DATABASE
Fetch all rows from a database.
- database_id (string, REQUIRED)
- page_size (integer, optional): default 100
- filter (object, optional): Notion filter object
- sorts (array, optional): Sort order

```bash
python scripts/notion_run.py NOTION_QUERY_DATABASE '{"database_id": "DB_ID", "page_size": 50}'
```

---

### NOTION_QUERY_DATABASE_WITH_FILTER
Query with server-side filtering. More efficient than fetching all rows.
- database_id (string, REQUIRED)
- filter (object, optional)
- sorts (array, optional)
- page_size (integer, optional)

```bash
python scripts/notion_run.py NOTION_QUERY_DATABASE_WITH_FILTER '{"database_id": "DB_ID", "filter": {"property": "Status", "select": {"equals": "Active"}}}'
```

---

### NOTION_UPDATE_ROW_DATABASE
Update an existing row. Get row_id from NOTION_QUERY_DATABASE.
- row_id (string, REQUIRED): Page UUID of the row
- properties (object, REQUIRED): Column values to update

```bash
python scripts/notion_run.py NOTION_UPDATE_ROW_DATABASE '{"row_id": "ROW_PAGE_ID", "properties": {"Status": "Done"}}'
```

---

### NOTION_UPSERT_ROW_DATABASE
Insert if not exists, update if exists.
- database_id (string, REQUIRED)
- filter_properties (object, REQUIRED): Match key
- update_properties (object, REQUIRED): Values to set

```bash
python scripts/notion_run.py NOTION_UPSERT_ROW_DATABASE '{"database_id": "DB_ID", "filter_properties": {"Name": "Danny"}, "update_properties": {"Status": "Active"}}'
```

---

### NOTION_FETCH_ROW
Get a specific row's properties by its page ID.
- row_id (string, REQUIRED)

```bash
python scripts/notion_run.py NOTION_FETCH_ROW '{"row_id": "ROW_PAGE_ID"}'
```

---

### NOTION_FETCH_DATABASE
Get a database's schema — column names, types, options.
- database_id (string, REQUIRED)

```bash
python scripts/notion_run.py NOTION_FETCH_DATABASE '{"database_id": "DB_ID"}'
```

---

### NOTION_UPDATE_SCHEMA_DATABASE
Add, rename, or change columns.
- database_id (string, REQUIRED)
- title (string, optional)
- properties (object, optional): Schema changes

```bash
python scripts/notion_run.py NOTION_UPDATE_SCHEMA_DATABASE '{"database_id": "DB_ID", "properties": {"New Column": {"type": "rich_text"}}}'
```

---

### NOTION_SEARCH_NOTION_PAGE
Find pages or databases by title. Only needed for IDs NOT in the known workspace above.
- query (string, optional)
- filter_value (string, optional): "page" or "database"
- page_size (integer, optional)

```bash
python scripts/notion_run.py NOTION_SEARCH_NOTION_PAGE '{"query": "My Page", "page_size": 10}'
```

---

### NOTION_DELETE_BLOCK
Archive (soft-delete) a block, page, or database.
- block_id (string, REQUIRED)

```bash
python scripts/notion_run.py NOTION_DELETE_BLOCK '{"block_id": "BLOCK_ID"}'
```

---

### NOTION_MOVE_PAGE
Move a page to a different parent.
- page_id (string, REQUIRED)
- new_parent_id (string, REQUIRED)

```bash
python scripts/notion_run.py NOTION_MOVE_PAGE '{"page_id": "PAGE_ID", "new_parent_id": "a8801897-efe7-4074-8f37-521b8075a840"}'
```

---

### NOTION_CREATE_COMMENT
Add a comment to a page.
- parent_page_id (string, REQUIRED)
- rich_text (array, REQUIRED): `[{"type": "text", "text": {"content": "Comment"}}]`

```bash
python scripts/notion_run.py NOTION_CREATE_COMMENT '{"parent_page_id": "PAGE_ID", "rich_text": [{"type": "text", "text": {"content": "Comment text"}}]}'
```

---

### NOTION_FETCH_DATA
List all accessible pages and databases. Only call when you need an ID not in the known workspace.
- get_all (boolean, optional)
- get_pages / get_databases (boolean, optional)
- query (string, optional)
- page_size (integer, optional, max 100)

```bash
python scripts/notion_run.py NOTION_FETCH_DATA '{"get_all": true, "page_size": 50}'
```

---

## Block Types — Content Building

Use in `children`, `content_blocks`, or `new_children` arrays:

```json
{"type": "paragraph",           "content": "Regular text"}
{"type": "heading_1",           "content": "Large heading"}
{"type": "heading_2",           "content": "Medium heading"}
{"type": "heading_3",           "content": "Small heading"}
{"type": "quote",               "content": "Quoted text"}
{"type": "callout",             "content": "Highlighted note", "icon": "💡"}
{"type": "to_do",               "content": "Task item", "checked": false}
{"type": "toggle",              "content": "Toggle section header"}
{"type": "divider"}
{"type": "bulleted_list_item",  "content": "Bullet point"}
{"type": "numbered_list_item",  "content": "Numbered step"}
{"type": "image",    "content": "https://example.com/photo.jpg"}
{"type": "video",    "content": "https://youtube.com/watch?v=..."}
{"type": "bookmark", "content": "https://example.com"}
{"type": "embed",    "content": "https://example.com"}
{"type": "file",     "content": "https://example.com/doc.pdf"}
{"type": "code",     "content": "print('hello')", "language": "python"}
```

> **Image rule:** Always use external HTTPS URLs. Notion-hosted uploads expire after 1 hour.

---

## Database Property Types

| Type | Definition | Row value |
|------|-----------|-----------|
| title | `{"name": "Name", "type": "title"}` | `"Text string"` |
| rich_text | `{"name": "Notes", "type": "rich_text"}` | `"Text string"` |
| select | `{"name": "Status", "type": "select", "options": [{"name": "Active", "color": "green"}]}` | `"Active"` |
| multi_select | `{"name": "Tags", "type": "multi_select", "options": [{"name": "A"}]}` | `["A", "B"]` |
| checkbox | `{"name": "Done", "type": "checkbox"}` | `true` or `false` |
| date | `{"name": "Date", "type": "date"}` | `"2026-03-17"` |
| number | `{"name": "Price", "type": "number"}` | `49` |
| url | `{"name": "Website", "type": "url"}` | `"https://example.com"` |
| email | `{"name": "Email", "type": "email"}` | `"user@example.com"` |
| phone_number | `{"name": "Phone", "type": "phone_number"}` | `"555-123-4567"` |
| status | `{"name": "Stage", "type": "status"}` | `"In Progress"` |

Read-only (cannot set): formula, rollup, created_time, created_by, last_edited_time, unique_id

---

## Common Workflows

### Create a page with content
```
1. NOTION_CREATE_NOTION_PAGE  →  get back new page_id
2. NOTION_APPEND_TEXT_BLOCKS  →  pass new page_id as block_id
```

### Add data to a database
```
Option A (simple): NOTION_INSERT_ROW_FROM_NL  →  plain English
Option B (exact):  NOTION_INSERT_ROW_DATABASE  →  typed properties object
```

### Redesign an existing page
```
1. NOTION_UPDATE_PAGE          →  rename + new icon
2. NOTION_REPLACE_PAGE_CONTENT →  wipe and rewrite with new blocks
```

### Read before editing
```
1. NOTION_RETRIEVE_PAGE            →  title, icon, properties
2. NOTION_FETCH_ALL_BLOCK_CONTENTS →  content blocks
```

---

## Common Mistakes to Avoid

**CRITICAL: Use EXACT slugs from this file. NEVER guess or shorten action names.**

If unsure, call `composio_get_schema("NOTION_ACTION_NAME")` to verify.

### Wrong slug → correct slug mapping

| WRONG (will 404) | CORRECT |
|---|---|
| `NOTION_FETCH_PAGE` | `NOTION_RETRIEVE_PAGE` |
| `NOTION_FETCH_PAGES` | `NOTION_SEARCH_NOTION_PAGE` or `NOTION_FETCH_DATA` |
| `NOTION_GET_PAGE` | `NOTION_RETRIEVE_PAGE` |
| `NOTION_LIST_PAGES` | `NOTION_FETCH_DATA` with `get_pages: true` |
| `NOTION_SEARCH` | `NOTION_SEARCH_NOTION_PAGE` |
| `NOTION_CREATE_PAGE` | `NOTION_CREATE_NOTION_PAGE` |
| `NOTION_GET_DATABASE` | `NOTION_FETCH_DATABASE` |
| `NOTION_LIST_DATABASES` | `NOTION_FETCH_DATA` with `get_databases: true` |
| `NOTION_FETCH_BLOCK` | `NOTION_FETCH_ALL_BLOCK_CONTENTS` |
| `NOTION_APPEND_BLOCK` | `NOTION_APPEND_TEXT_BLOCKS` |
| `NOTION_ADD_BLOCK` | `NOTION_APPEND_TEXT_BLOCKS` |
| `NOTION_ADD_BLOCKS` | `NOTION_APPEND_TEXT_BLOCKS` |
| `NOTION_ADD_CONTENT` | `NOTION_ADD_MULTIPLE_PAGE_CONTENT` or `NOTION_APPEND_TEXT_BLOCKS` |
| `NOTION_UPDATE_CONTENT` | `NOTION_REPLACE_PAGE_CONTENT` |

### Other rules
- `NOTION_CREATE_DATABASE` parent must be a PAGE id, not a database id
- `NOTION_CREATE_NOTION_PAGE` without parent_id always fails
- Cannot create workspace root-level pages — always needs a parent
- Do NOT call NOTION_FETCH_DATA before using known workspace IDs above
- If an action returns a 404 error, check this table or call `composio_get_schema`

---

## Quick Reference

```bash
# List all notion action slugs
python scripts/notion_run.py --list-actions
```