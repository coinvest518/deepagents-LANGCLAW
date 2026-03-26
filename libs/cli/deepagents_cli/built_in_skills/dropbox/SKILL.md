---
name: dropbox
description: >
  Full control skill for Dropbox via Composio. Use when the owner asks to
  upload, download, list, move, copy, search, or share files and folders in
  Dropbox. Pre-authenticated — execute actions directly, no OAuth needed.
  Trigger phrases: "upload to dropbox", "list my dropbox files", "download
  from dropbox", "share a dropbox link", "move file in dropbox",
  "search dropbox".
license: MIT
compatibility: deepagents-cli
metadata:
  toolkit: dropbox
---

# Dropbox Skill

Full Dropbox control via Composio. All Dropbox actions are available using the
Composio Python client (already configured — `COMPOSIO_API_KEY` in env).

## How to Execute Actions

Use the `composio_action` tool directly — no Python code needed:

```
composio_action("DROPBOX_LIST_FILES_IN_FOLDER", {"path": ""})
```

Or via Python:
```python
import os, json
from composio import Composio
client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
account_id = os.environ["COMPOSIO_DROPBOX_ACCOUNT_ID"]
result = client.tools.execute("DROPBOX_LIST_FILES_IN_FOLDER", arguments={"path": ""}, connected_account_id=account_id, dangerously_skip_version_check=True)
print(json.dumps(result, default=str)[:2000])
```

**RULE:** Use exact slugs from this file. Never guess action names.
**RULE:** If unsure about parameters, call `composio_get_schema("DROPBOX_ACTION_NAME")` first.

---

## Actions — Full Schemas

### DROPBOX_LIST_FILES_IN_FOLDER
List files and folders in a Dropbox folder.
- path (string, REQUIRED): Folder path. Use `""` (empty string) for root.
- recursive (boolean, optional): List recursively. Default: false.
- limit (integer, optional): Max entries to return.

```
composio_action("DROPBOX_LIST_FILES_IN_FOLDER", {"path": "", "limit": 50})
composio_action("DROPBOX_LIST_FILES_IN_FOLDER", {"path": "/Documents"})
```

---

### DROPBOX_UPLOAD_FILE
Upload a file to Dropbox.
- path (string, REQUIRED): Destination path including filename (e.g. `/Documents/report.pdf`)
- file_content (string, REQUIRED): Base64-encoded file content or text content
- mode (string, optional): `"add"` (default) or `"overwrite"`

```
composio_action("DROPBOX_UPLOAD_FILE", {"path": "/Documents/notes.txt", "file_content": "Hello world", "mode": "add"})
```

---

### DROPBOX_EXPORT_FILE
Download/export a file from Dropbox.
- path (string, REQUIRED): File path to download (e.g. `/Documents/report.pdf`)

```
composio_action("DROPBOX_EXPORT_FILE", {"path": "/Documents/report.pdf"})
```

---

### DROPBOX_CREATE_FOLDER
Create a new folder.
- path (string, REQUIRED): Full folder path (e.g. `/Projects/NewFolder`)
- autorename (boolean, optional): Auto-rename if folder exists. Default: false.

```
composio_action("DROPBOX_CREATE_FOLDER", {"path": "/Projects/NewFolder"})
```

---

### DROPBOX_GET_METADATA
Get metadata for a file or folder (size, modified date, etc.).
- path (string, REQUIRED): File or folder path

```
composio_action("DROPBOX_GET_METADATA", {"path": "/Documents/report.pdf"})
```

---

### DROPBOX_MOVE_FILE_OR_FOLDER
Move a file or folder to a new location.
- from_path (string, REQUIRED): Current path
- to_path (string, REQUIRED): Destination path
- autorename (boolean, optional): Auto-rename on conflict. Default: false.

```
composio_action("DROPBOX_MOVE_FILE_OR_FOLDER", {"from_path": "/old/file.txt", "to_path": "/new/file.txt"})
```

---

### DROPBOX_COPY_FILE_OR_FOLDER
Copy a file or folder to a new location.
- from_path (string, REQUIRED): Source path
- to_path (string, REQUIRED): Destination path
- autorename (boolean, optional): Auto-rename on conflict. Default: false.

```
composio_action("DROPBOX_COPY_FILE_OR_FOLDER", {"from_path": "/original.txt", "to_path": "/copy.txt"})
```

---

### DROPBOX_DELETE_FILE
Delete a file or folder permanently.
- path (string, REQUIRED): Path to delete

```
composio_action("DROPBOX_DELETE_FILE", {"path": "/old-file.txt"})
```

---

### DROPBOX_CREATE_SHARED_LINK
Create a shareable link for a file or folder.
- path (string, REQUIRED): File or folder path

```
composio_action("DROPBOX_CREATE_SHARED_LINK", {"path": "/Documents/report.pdf"})
```

---

### DROPBOX_FILES_SEARCH
Search for files by name or content.
- query (string, REQUIRED): Search query
- path (string, optional): Folder to search within (empty = all)
- max_results (integer, optional): Max results to return

```
composio_action("DROPBOX_FILES_SEARCH", {"query": "quarterly report", "max_results": 10})
```

---

### DROPBOX_GET_ABOUT_ME
Get current Dropbox account info (name, email, space usage).

```
composio_action("DROPBOX_GET_ABOUT_ME", {})
```

---

### DROPBOX_LIST_SHARED_LINKS
List all shared links for a file or the entire account.
- path (string, optional): File path to get links for (empty = all links)

```
composio_action("DROPBOX_LIST_SHARED_LINKS", {"path": "/Documents/report.pdf"})
```

---

## Common Mistakes to Avoid

**CRITICAL: Use EXACT slugs from this file. NEVER guess or shorten action names.**

### Wrong slug -> correct slug mapping

| WRONG (will 404) | CORRECT |
|---|---|
| `DROPBOX_LIST_FOLDER` | `DROPBOX_LIST_FILES_IN_FOLDER` |
| `DROPBOX_DOWNLOAD_FILE` | `DROPBOX_EXPORT_FILE` |
| `DROPBOX_GET_FILE_METADATA` | `DROPBOX_GET_METADATA` |
| `DROPBOX_MOVE_FILE` | `DROPBOX_MOVE_FILE_OR_FOLDER` |
| `DROPBOX_COPY_FILE` | `DROPBOX_COPY_FILE_OR_FOLDER` |
| `DROPBOX_SEARCH_FILES` | `DROPBOX_FILES_SEARCH` |
| `DROPBOX_GET_ACCOUNT_INFO` | `DROPBOX_GET_ABOUT_ME` |

### Other rules
- Entity is `"default"` — account ID: `ca__qavNcrS7vNU`
- Paths must start with `/` (except root which is `""`)
- Always use `dangerously_skip_version_check=True` in Python
- Always truncate output: `json.dumps(result, default=str)[:2000]`
- If an action returns a 404, check this table or call `composio_get_schema`

---

## Discover more actions

```python
import os
from composio import Composio
client = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
tools = client.tools.get_raw_composio_tools(toolkits=["dropbox"], limit=20)
for t in tools:
    print(t.slug)
```
