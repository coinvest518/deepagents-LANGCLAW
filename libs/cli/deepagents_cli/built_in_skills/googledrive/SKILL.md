---
name: googledrive
description: >
  Full Google Drive control via Composio — 89 actions available. Use for:
  listing, finding, creating, editing, moving, copying, deleting, downloading,
  uploading, sharing, commenting, versioning files and folders. Shared drives,
  permissions, labels, file watching. Pre-authenticated — no OAuth needed.
  Trigger phrases: "google drive", "gdrive", "my drive", "upload to drive",
  "find file", "share file", "drive folder", "download from drive".
license: MIT
compatibility: deepagents-cli
---

# Google Drive Skill — 89 Actions

Pre-authenticated via Composio. Use `composio_action` with the action slug and args.
Account ID is in `COMPOSIO_GOOGLEDRIVE_ACCOUNT_ID` env var — always pass it as `connected_account_id`.

## How to Call Any Action

```
composio_action(
  action="GOOGLEDRIVE_<ACTION>",
  params={"arg1": "value", ...},
  connected_account_id=COMPOSIO_GOOGLEDRIVE_ACCOUNT_ID
)
```

If you need parameter details for any action: `composio_get_schema("GOOGLEDRIVE_<ACTION>")`

---

## Files — Find & Read

| Action | What it does |
|--------|-------------|
| `GOOGLEDRIVE_FIND_FILE` | Search files by name/query — **use this first when user mentions a file by name** |
| `GOOGLEDRIVE_LIST_FILES` | List files (supports `q` query param for filtering) |
| `GOOGLEDRIVE_GET_FILE_METADATA` | Get full metadata for a file by ID |
| `GOOGLEDRIVE_GET_FILE_V2` | Get file details (v2) |
| `GOOGLEDRIVE_PARSE_FILE` | Extract text content from a file |
| `GOOGLEDRIVE_DOWNLOAD_FILE` | Download file content by ID |
| `GOOGLEDRIVE_DOWNLOAD_FILE2` | Download file (alternative method) |
| `GOOGLEDRIVE_DOWNLOAD_FILE_OPERATION` | Download with full options |
| `GOOGLEDRIVE_EXPORT_GOOGLE_WORKSPACE_FILE` | Export Docs/Sheets/Slides to PDF, DOCX, CSV, etc. |
| `GOOGLEDRIVE_GET_ABOUT` | Get Drive quota, user info, and features |

## Files — Create & Edit

| Action | What it does |
|--------|-------------|
| `GOOGLEDRIVE_CREATE_FILE` | Create a new file |
| `GOOGLEDRIVE_CREATE_FILE_FROM_TEXT` | Create a file with text content — **use for saving text/notes to Drive** |
| `GOOGLEDRIVE_EDIT_FILE` | Edit an existing file's content |
| `GOOGLEDRIVE_UPDATE_FILE_METADATA_PATCH` | Update file name, description, or other metadata |
| `GOOGLEDRIVE_UPDATE_FILE_PUT` | Full file update (replace content) |
| `GOOGLEDRIVE_UPLOAD_FILE` | Upload a file from local path |
| `GOOGLEDRIVE_UPLOAD_FROM_URL` | Upload a file directly from a URL — **use to save web content to Drive** |
| `GOOGLEDRIVE_UPLOAD_UPDATE_FILE` | Upload and update existing file |
| `GOOGLEDRIVE_RESUMABLE_UPLOAD` | Large file upload with resumable session |
| `GOOGLEDRIVE_GENERATE_IDS` | Pre-generate file IDs for batch operations |

## Files — Organize

| Action | What it does |
|--------|-------------|
| `GOOGLEDRIVE_COPY_FILE` | Copy a file |
| `GOOGLEDRIVE_COPY_FILE_ADVANCED` | Copy with extra options (name, parents, etc.) |
| `GOOGLEDRIVE_MOVE_FILE` | Move file to a different folder |
| `GOOGLEDRIVE_CREATE_SHORTCUT_TO_FILE` | Create a shortcut/alias to a file |
| `GOOGLEDRIVE_TRASH_FILE` | Move file to trash |
| `GOOGLEDRIVE_UNTRASH_FILE` | Restore from trash |
| `GOOGLEDRIVE_DELETE_FILE` | Permanently delete a file |
| `GOOGLEDRIVE_GOOGLE_DRIVE_DELETE_FOLDER_OR_FILE_ACTION` | Delete folder or file |
| `GOOGLEDRIVE_EMPTY_TRASH` | Empty the trash permanently |

## Folders

| Action | What it does |
|--------|-------------|
| `GOOGLEDRIVE_CREATE_FOLDER` | Create a new folder |
| `GOOGLEDRIVE_FIND_FOLDER` | Search for a folder by name |
| `GOOGLEDRIVE_LIST_CHILDREN_V2` | List contents of a folder |
| `GOOGLEDRIVE_GET_CHILD` | Get a specific child item in a folder |
| `GOOGLEDRIVE_INSERT_CHILD` | Add a file to a folder |
| `GOOGLEDRIVE_DELETE_CHILD` | Remove a file from a folder |
| `GOOGLEDRIVE_ADD_PARENT` | Add a parent folder to a file |
| `GOOGLEDRIVE_DELETE_PARENT` | Remove a parent folder from a file |
| `GOOGLEDRIVE_GET_PARENT` | Get parent folder info |

## Sharing & Permissions

| Action | What it does |
|--------|-------------|
| `GOOGLEDRIVE_CREATE_PERMISSION` | Share file with email (viewer/editor/owner) |
| `GOOGLEDRIVE_LIST_PERMISSIONS` | List all shares on a file |
| `GOOGLEDRIVE_GET_PERMISSION` | Get a specific permission |
| `GOOGLEDRIVE_UPDATE_PERMISSION` | Change permission role |
| `GOOGLEDRIVE_PATCH_PERMISSION` | Partial update permission |
| `GOOGLEDRIVE_DELETE_PERMISSION` | Remove a share |
| `GOOGLEDRIVE_GET_PERMISSION_ID_FOR_EMAIL` | Look up permission ID by email |
| `GOOGLEDRIVE_ADD_FILE_SHARING_PREFERENCE` | Set sharing preferences |
| `GOOGLEDRIVE_LIST_ACCESS_PROPOSALS` | List pending access requests |
| `GOOGLEDRIVE_LIST_APPROVALS` | List pending approvals |

## Comments & Replies

| Action | What it does |
|--------|-------------|
| `GOOGLEDRIVE_CREATE_COMMENT` | Add a comment to a file |
| `GOOGLEDRIVE_LIST_COMMENTS` | List all comments on a file |
| `GOOGLEDRIVE_GET_COMMENT` | Get a specific comment |
| `GOOGLEDRIVE_UPDATE_COMMENT` | Edit a comment |
| `GOOGLEDRIVE_DELETE_COMMENT` | Delete a comment |
| `GOOGLEDRIVE_CREATE_REPLY` | Reply to a comment |
| `GOOGLEDRIVE_LIST_REPLIES` | List replies on a comment |
| `GOOGLEDRIVE_GET_REPLY` | Get a specific reply |
| `GOOGLEDRIVE_UPDATE_REPLY` | Edit a reply |
| `GOOGLEDRIVE_DELETE_REPLY` | Delete a reply |

## Revisions & History

| Action | What it does |
|--------|-------------|
| `GOOGLEDRIVE_LIST_REVISIONS` | List all versions of a file |
| `GOOGLEDRIVE_GET_REVISION` | Get a specific version |
| `GOOGLEDRIVE_UPDATE_FILE_REVISION_METADATA` | Update revision metadata (keep forever, etc.) |
| `GOOGLEDRIVE_DELETE_REVISION` | Delete a specific version |

## File Properties & Labels

| Action | What it does |
|--------|-------------|
| `GOOGLEDRIVE_ADD_PROPERTY` | Add custom property to a file |
| `GOOGLEDRIVE_GET_FILE_PROPERTY` | Get a custom property |
| `GOOGLEDRIVE_LIST_FILE_PROPERTIES` | List all custom properties |
| `GOOGLEDRIVE_UPDATE_FILE_PROPERTY` | Update a custom property |
| `GOOGLEDRIVE_PATCH_PROPERTY` | Partial update of a property |
| `GOOGLEDRIVE_DELETE_PROPERTY` | Remove a custom property |
| `GOOGLEDRIVE_LIST_FILE_LABELS` | List labels on a file |
| `GOOGLEDRIVE_MODIFY_FILE_LABELS` | Add/remove labels on a file |

## Shared Drives (Team Drives)

| Action | What it does |
|--------|-------------|
| `GOOGLEDRIVE_CREATE_DRIVE` | Create a shared drive |
| `GOOGLEDRIVE_LIST_SHARED_DRIVES` | List all shared drives |
| `GOOGLEDRIVE_GET_DRIVE` | Get shared drive details |
| `GOOGLEDRIVE_UPDATE_DRIVE` | Update shared drive settings |
| `GOOGLEDRIVE_DELETE_DRIVE` | Delete a shared drive |
| `GOOGLEDRIVE_HIDE_DRIVE` | Hide a shared drive |
| `GOOGLEDRIVE_UNHIDE_DRIVE` | Unhide a shared drive |
| `GOOGLEDRIVE_CREATE_TEAM_DRIVE` | Create a team drive (legacy) |
| `GOOGLEDRIVE_LIST_TEAM_DRIVES` | List team drives |
| `GOOGLEDRIVE_GET_TEAM_DRIVE` | Get team drive details |
| `GOOGLEDRIVE_UPDATE_TEAM_DRIVE` | Update team drive |
| `GOOGLEDRIVE_DELETE_TEAM_DRIVE` | Delete team drive |

## Change Tracking & Webhooks

| Action | What it does |
|--------|-------------|
| `GOOGLEDRIVE_LIST_CHANGES` | List recent changes across Drive |
| `GOOGLEDRIVE_GET_CHANGE` | Get a specific change event |
| `GOOGLEDRIVE_GET_CHANGES_START_PAGE_TOKEN` | Get token to start watching changes |
| `GOOGLEDRIVE_WATCH_CHANGES` | Subscribe to Drive-wide changes |
| `GOOGLEDRIVE_WATCH_FILE` | Subscribe to changes on a specific file |
| `GOOGLEDRIVE_STOP_WATCH_CHANNEL` | Stop a watch subscription |

## Apps

| Action | What it does |
|--------|-------------|
| `GOOGLEDRIVE_GET_APP` | Get info about a Drive-connected app |

---

## Common Workflows

**Find and read a file:**
1. `GOOGLEDRIVE_FIND_FILE` with name/query → get file ID
2. `GOOGLEDRIVE_PARSE_FILE` or `GOOGLEDRIVE_DOWNLOAD_FILE` with the ID

**Save text content to Drive:**
→ `GOOGLEDRIVE_CREATE_FILE_FROM_TEXT` — pass filename + text content directly

**Share a file with someone:**
→ `GOOGLEDRIVE_CREATE_PERMISSION` with `emailAddress` + `role` (reader/writer/owner)

**Upload a web resource:**
→ `GOOGLEDRIVE_UPLOAD_FROM_URL` — pass the URL, it downloads and saves to Drive

**Export a Google Doc as PDF/Word:**
→ `GOOGLEDRIVE_EXPORT_GOOGLE_WORKSPACE_FILE` with `mimeType=application/pdf` or `application/vnd.openxmlformats-officedocument.wordprocessingml.document`

**List contents of a folder:**
→ `GOOGLEDRIVE_LIST_FILES` with `q="'FOLDER_ID' in parents"` or `GOOGLEDRIVE_LIST_CHILDREN_V2`

## Rules

- Use `COMPOSIO_GOOGLEDRIVE_ACCOUNT_ID` env var for `connected_account_id` — never call `accounts.list()`
- For unknown params: call `composio_get_schema("GOOGLEDRIVE_<ACTION>")` first
- File IDs are required for most operations — use `FIND_FILE` or `FIND_FOLDER` first when you only have a name
