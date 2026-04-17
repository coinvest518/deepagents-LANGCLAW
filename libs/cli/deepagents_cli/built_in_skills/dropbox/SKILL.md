---
name: dropbox
description: >
  Full Dropbox control via Composio â€” 177 actions. Upload, download, list,
  move, copy, search, share files and folders. File revisions, restore,
  shared links, Paper docs, team folders, groups, members, space usage.
  Pre-authenticated. Trigger phrases: "dropbox", "upload to dropbox",
  "download from dropbox", "share a dropbox link", "move file in dropbox".
license: MIT
compatibility: deepagents-cli
metadata:
  toolkit: dropbox
---

# Dropbox Skill â€” 177 Actions

Call any action with `composio_action`. Account ID is in `COMPOSIO_DROPBOX_ACCOUNT_ID`.

```
composio_action(
  action="DROPBOX_<ACTION>",
  params={...},
  connected_account_id=COMPOSIO_DROPBOX_ACCOUNT_ID
)
```

For param details: `composio_get_schema("DROPBOX_<ACTION>")`

---

## Files â€” Core Operations

| Action | What it does |
|--------|-------------|
| `DROPBOX_LIST_FILES_IN_FOLDER` | List files/folders â€” use `""` for root |
| `DROPBOX_UPLOAD_FILE` | Upload a file |
| `DROPBOX_ALPHA_UPLOAD_FILE` | Upload with extended metadata support |
| `DROPBOX_READ_FILE` | Read file contents |
| `DROPBOX_EXPORT_FILE` | Download/export a file |
| `DROPBOX_DOWNLOAD_ZIP` | Download a folder as ZIP |
| `DROPBOX_GET_METADATA` | Get file/folder metadata (size, dates) |
| `DROPBOX_GET_METADATA_ALPHA` | Extended metadata |
| `DROPBOX_DELETE_FILE` | Delete a file (single) |
| `DROPBOX_DELETE_FILE_OR_FOLDER` | Delete file or folder |
| `DROPBOX_DELETE_BATCH` | Delete multiple files |
| `DROPBOX_COPY_FILE_OR_FOLDER` | Copy file/folder |
| `DROPBOX_COPY_BATCH` | Copy multiple items |
| `DROPBOX_MOVE_FILE_OR_FOLDER` | Move file/folder |
| `DROPBOX_MOVE_BATCH` | Move multiple items |
| `DROPBOX_CREATE_FOLDER` | Create folder |
| `DROPBOX_CREATE_FOLDER_BATCH` | Create multiple folders |
| `DROPBOX_GET_COPY_REFERENCE` | Get a copy reference token |
| `DROPBOX_SAVE_COPY_REFERENCE` | Save a copy using reference token |

## Files â€” Upload Sessions (large files)

| Action | What it does |
|--------|-------------|
| `DROPBOX_START_UPLOAD_SESSION` | Start chunked upload session |
| `DROPBOX_START_UPLOAD_SESSION_BATCH` | Start multiple upload sessions |
| `DROPBOX_APPEND_UPLOAD_SESSION` | Append chunk to session |
| `DROPBOX_APPEND_UPLOAD_SESSION_BATCH` | Append to multiple sessions |
| `DROPBOX_FINISH_UPLOAD_SESSION` | Finalize single upload session |
| `DROPBOX_FINISH_UPLOAD_SESSION_BATCH` | Finalize multiple sessions |
| `DROPBOX_GET_TEMPORARY_UPLOAD_LINK` | Get temporary upload URL |
| `DROPBOX_CHECK_UPLOAD_BATCH` | Check batch upload status |

## Files â€” Search

| Action | What it does |
|--------|-------------|
| `DROPBOX_FILES_SEARCH` | Search files by name/content |
| `DROPBOX_SEARCH_FILE_OR_FOLDER` | Search files or folders |
| `DROPBOX_SEARCH_CONTINUE` | Paginate search results |
| `DROPBOX_SEARCH_FILE_PROPERTIES` | Search by custom properties |

## Files â€” Revisions & Restore

| Action | What it does |
|--------|-------------|
| `DROPBOX_LIST_FILE_REVISIONS` | List revisions of a file |
| `DROPBOX_RESTORE_FILE` | Restore file to a prior revision |
| `DROPBOX_SAVE_URL` | Save file from URL to Dropbox |
| `DROPBOX_CHECK_SAVE_URL_STATUS` | Check save-from-URL status |

## Files â€” Folder Sync

| Action | What it does |
|--------|-------------|
| `DROPBOX_GET_FOLDER_CURSOR` | Get latest folder cursor |
| `DROPBOX_LIST_FOLDER_CONTINUE` | Poll for folder changes |
| `DROPBOX_MOUNT_FOLDER` | Mount a shared folder |
| `DROPBOX_UNMOUNT_FOLDER` | Unmount a shared folder |

## Files â€” Locks

| Action | What it does |
|--------|-------------|
| `DROPBOX_GET_FILE_LOCK_BATCH` | Get lock status for files |
| `DROPBOX_UNLOCK_FILE_BATCH` | Unlock locked files |

## Files â€” Properties & Tags

| Action | What it does |
|--------|-------------|
| `DROPBOX_ADD_FILE_PROPERTIES` | Add custom metadata properties |
| `DROPBOX_REMOVE_FILE_PROPERTIES` | Remove properties |
| `DROPBOX_UPDATE_FILE_PROPERTIES` | Update properties |
| `DROPBOX_OVERWRITE_FILE_PROPERTIES` | Overwrite all properties |
| `DROPBOX_ADD_FILE_TAGS` | Add tags to a file |
| `DROPBOX_GET_FILE_TAGS` | Get file tags |
| `DROPBOX_REMOVE_FILE_TAG` | Remove a tag |
| `DROPBOX_GET_FILE_METADATA_BATCH` | Batch metadata fetch |

## Files â€” Previews & Thumbnails

| Action | What it does |
|--------|-------------|
| `DROPBOX_GET_THUMBNAIL` | Get image thumbnail |
| `DROPBOX_GET_THUMBNAIL_V2` | Get thumbnail (v2) |
| `DROPBOX_GET_THUMBNAIL_BATCH` | Get multiple thumbnails |
| `DROPBOX_GET_FILE_PREVIEW` | Get preview of a file |
| `DROPBOX_GET_TEMPORARY_LINK` | Get temporary download link |

## Files â€” Batch checks

| Action | What it does |
|--------|-------------|
| `DROPBOX_CHECK_COPY_BATCH` | Check batch copy status |
| `DROPBOX_CHECK_DELETE_BATCH` | Check batch delete status |
| `DROPBOX_CHECK_MOVE_BATCH` | Check batch move status |
| `DROPBOX_CHECK_JOB_STATUS` | Check generic job status |
| `DROPBOX_CHECK_FOLDER_BATCH` | Check folder batch status |

## Sharing â€” Links

| Action | What it does |
|--------|-------------|
| `DROPBOX_CREATE_SHARED_LINK` | Create a share link |
| `DROPBOX_CREATE_SHARED_LINK_SIMPLE` | Create simple share link |
| `DROPBOX_LIST_SHARED_LINKS` | List share links |
| `DROPBOX_GET_SHARED_LINK_METADATA` | Get link metadata |
| `DROPBOX_GET_SHARED_LINK_FILE` | Download via shared link |
| `DROPBOX_MODIFY_SHARED_LINK_SETTINGS` | Update link settings (expiry, password) |
| `DROPBOX_REVOKE_SHARED_LINK` | Revoke a share link |

## Sharing â€” Folders

| Action | What it does |
|--------|-------------|
| `DROPBOX_SHARE_FOLDER` | Share a folder |
| `DROPBOX_UNSHARE_FOLDER` | Stop sharing a folder |
| `DROPBOX_UNSHARE_FILE` | Stop sharing a file |
| `DROPBOX_LIST_SHARED_FOLDERS` | List folders you've shared |
| `DROPBOX_LIST_FOLDERS` | List shared folders |
| `DROPBOX_LIST_FOLDERS_CONTINUE` | Paginate shared folder list |
| `DROPBOX_LIST_MOUNTABLE_FOLDERS` | List mountable shared folders |
| `DROPBOX_LIST_MOUNTABLE_FOLDERS_CONTINUE` | Paginate |
| `DROPBOX_GET_SHARED_FOLDER_METADATA` | Get folder share details |
| `DROPBOX_UPDATE_FOLDER_POLICY` | Change folder sharing policy |
| `DROPBOX_CHECK_SHARE_JOB_STATUS` | Check async share status |

## Sharing â€” Members

| Action | What it does |
|--------|-------------|
| `DROPBOX_ADD_FILE_MEMBER` | Add member to a file |
| `DROPBOX_ADD_FOLDER_MEMBER_ACTION` | Add member to a folder |
| `DROPBOX_LIST_FILE_MEMBERS` | List members of a file |
| `DROPBOX_LIST_FILE_MEMBERS_BATCH` | Batch file member list |
| `DROPBOX_LIST_FOLDER_MEMBERS` | List members of a folder |
| `DROPBOX_LIST_FOLDER_MEMBERS_CONTINUE` | Paginate |
| `DROPBOX_REMOVE_FILE_MEMBER` | Remove file member |
| `DROPBOX_REMOVE_FOLDER_MEMBER` | Remove folder member |
| `DROPBOX_UPDATE_FILE_MEMBER` | Update file member permissions |
| `DROPBOX_UPDATE_FOLDER_MEMBER` | Update folder member permissions |
| `DROPBOX_GET_SHARED_FILE_METADATA` | Get file share details |
| `DROPBOX_LIST_RECEIVED_FILES` | Files shared with you |

## Sharing â€” Allowlist

| Action | What it does |
|--------|-------------|
| `DROPBOX_ADD_SHARING_ALLOWLIST` | Add domains/emails to allowlist |
| `DROPBOX_REMOVE_SHARING_ALLOWLIST` | Remove from allowlist |
| `DROPBOX_LIST_SHARING_ALLOWLIST` | List allowlist entries |
| `DROPBOX_LIST_TEAM_SHARING_ALLOWLIST_CONTINUE` | Paginate allowlist |

## File Requests

| Action | What it does |
|--------|-------------|
| `DROPBOX_CREATE_FILE_REQUEST` | Create a file request (collect files) |
| `DROPBOX_GET_FILE_REQUEST` | Get file request details |
| `DROPBOX_LIST_FILE_REQUESTS` | List file requests |
| `DROPBOX_LIST_FILE_REQUESTS_CONTINUE` | Paginate |
| `DROPBOX_UPDATE_FILE_REQUEST` | Update file request |
| `DROPBOX_DELETE_FILE_REQUESTS` | Delete file requests |
| `DROPBOX_DELETE_ALL_CLOSED_FILE_REQUESTS` | Delete all closed requests |
| `DROPBOX_COUNT_FILE_REQUESTS` | Count file requests |

## Paper Documents

| Action | What it does |
|--------|-------------|
| `DROPBOX_CREATE_PAPER_DOCUMENT` | Create a Dropbox Paper doc |
| `DROPBOX_CREATE_PAPER_FOLDER` | Create a Paper folder |
| `DROPBOX_UPDATE_PAPER_DOCUMENT` | Update Paper doc content |
| `DROPBOX_LIST_PAPER_DOCS` | List Paper documents |
| `DROPBOX_LIST_PAPER_DOCS_CONTINUE` | Paginate Paper docs |

## Account & Space

| Action | What it does |
|--------|-------------|
| `DROPBOX_GET_ABOUT_ME` | Get current account info |
| `DROPBOX_GET_ACCOUNT` | Get info for another account |
| `DROPBOX_GET_ACCOUNT_BATCH` | Batch account info |
| `DROPBOX_GET_SPACE_USAGE` | Get space used/available |
| `DROPBOX_GET_USER_FEATURES` | Get feature flags for user |
| `DROPBOX_SET_PROFILE_PHOTO` | Set profile photo |
| `DROPBOX_GET_OPENID_CONFIG` | Get OpenID configuration |
| `DROPBOX_GET_JWKS` | Get JWKS keys |

## Team Folders

| Action | What it does |
|--------|-------------|
| `DROPBOX_CREATE_TEAM_FOLDER` | Create a team folder |
| `DROPBOX_ACTIVATE_TEAM_FOLDER` | Activate a team folder |
| `DROPBOX_ARCHIVE_TEAM_FOLDER` | Archive a team folder |
| `DROPBOX_DELETE_TEAM_FOLDER_PERMANENTLY` | Permanently delete |
| `DROPBOX_RENAME_TEAM_FOLDER` | Rename a team folder |
| `DROPBOX_GET_TEAM_FOLDER_INFO` | Get team folder details |
| `DROPBOX_LIST_TEAM_FOLDERS` | List team folders |
| `DROPBOX_LIST_TEAM_FOLDERS_CONTINUE` | Paginate |
| `DROPBOX_UPDATE_TEAM_FOLDER_SYNC_SETTINGS` | Update sync settings |
| `DROPBOX_CHECK_TEAM_FOLDER_ARCHIVE` | Check archive status |

## Team Members & Groups

| Action | What it does |
|--------|-------------|
| `DROPBOX_ADD_TEAM_MEMBERS` | Add team members |
| `DROPBOX_ADD_TEAM_MEMBERS_SECONDARY_EMAILS` | Add secondary emails |
| `DROPBOX_GET_TEAM_MEMBERS_INFO` | Get member details |
| `DROPBOX_LIST_TEAM_MEMBERS` | List all team members |
| `DROPBOX_LIST_TEAM_MEMBERS_CONTINUE` | Paginate |
| `DROPBOX_UPDATE_TEAM_MEMBER_PROFILE` | Update member profile |
| `DROPBOX_UPDATE_TEAM_MEMBER_PROFILE_PHOTO` | Update profile photo |
| `DROPBOX_DELETE_TEAM_MEMBER_PROFILE_PHOTO` | Delete profile photo |
| `DROPBOX_UPDATE_TEAM_MEMBER_ADMIN_PERMISSIONS` | Change admin role |
| `DROPBOX_SEND_TEAM_MEMBER_WELCOME_EMAIL` | Send welcome email |
| `DROPBOX_DELETE_TEAM_MEMBERS_SECONDARY_EMAILS` | Remove secondary emails |
| `DROPBOX_RESEND_SECONDARY_EMAIL_VERIFICATION` | Resend verification |
| `DROPBOX_CHECK_REMOVE_MEMBER` | Check member removal status |
| `DROPBOX_CHECK_MOVE_FORMER_MEMBER_FILES_JOB_STATUS` | Check file move status |
| `DROPBOX_GET_TEAM_MEMBERS_ADD_JOB_STATUS` | Check add-member job |
| `DROPBOX_CREATE_TEAM_GROUP` | Create a team group |
| `DROPBOX_DELETE_TEAM_GROUP` | Delete a team group |
| `DROPBOX_UPDATE_TEAM_GROUP` | Update group details |
| `DROPBOX_ADD_TEAM_GROUP_MEMBERS` | Add members to group |
| `DROPBOX_REMOVE_GROUP_MEMBERS` | Remove members from group |
| `DROPBOX_UPDATE_GROUP_MEMBER_ACCESS_TYPE` | Change member access |
| `DROPBOX_GET_TEAM_GROUPS_INFO` | Get group info |
| `DROPBOX_LIST_TEAM_GROUPS` | List all groups |
| `DROPBOX_LIST_TEAM_GROUPS_CONTINUE` | Paginate |
| `DROPBOX_LIST_TEAM_GROUP_MEMBERS` | List group members |
| `DROPBOX_LIST_TEAM_GROUPS_MEMBERS_CONTINUE` | Paginate members |
| `DROPBOX_GET_TEAM_GROUPS_JOB_STATUS` | Check group job status |
| `DROPBOX_GET_AVAILABLE_TEAM_MEMBER_ROLES` | List available roles |

## Team Admin & Devices

| Action | What it does |
|--------|-------------|
| `DROPBOX_GET_TEAM_INFO` | Get team info |
| `DROPBOX_GET_TEAM_FEATURE_VALUES` | Get team features |
| `DROPBOX_GET_TEAM_LOG_EVENTS` | Get audit logs |
| `DROPBOX_GET_TEAM_LOG_EVENTS_CONTINUE` | Paginate audit logs |
| `DROPBOX_LIST_TEAM_DEVICES` | List all team devices |
| `DROPBOX_LIST_TEAM_MEMBER_DEVICES` | List devices for member |
| `DROPBOX_LIST_TEAM_NAMESPACES` | List team namespaces |
| `DROPBOX_LIST_TEAM_NAMESPACES_CONTINUE` | Paginate |
| `DROPBOX_LIST_TEAM_LINKED_APPS` | List all linked apps |
| `DROPBOX_LIST_MEMBER_LINKED_APPS` | List member's linked apps |
| `DROPBOX_GET_TEAM_MEMBER_CUSTOM_QUOTA` | Get custom quota |
| `DROPBOX_SET_TEAM_MEMBER_CUSTOM_QUOTA` | Set custom quota |
| `DROPBOX_REMOVE_TEAM_MEMBER_CUSTOM_QUOTA` | Remove custom quota |
| `DROPBOX_ADD_MEMBER_SPACE_LIMITS_EXCLUDED_USERS` | Exclude from limits |
| `DROPBOX_REMOVE_TEAM_MEMBER_SPACE_LIMITS_EXCLUDED_USERS` | Remove exclusion |
| `DROPBOX_LIST_MEMBER_SPACE_LIMITS_EXCLUDED_USERS` | List excluded users |
| `DROPBOX_LIST_EXCLUDED_USERS_CONTINUE` | Paginate |
| `DROPBOX_DELETE_MANUAL_CONTACTS_BATCH` | Delete manual contacts |
| `DROPBOX_CHECK_USER` | Check user status |

## Team Properties Templates

| Action | What it does |
|--------|-------------|
| `DROPBOX_ADD_TEAM_PROPERTIES_TEMPLATE` | Add property template |
| `DROPBOX_GET_TEAM_PROPERTIES_TEMPLATE` | Get template details |
| `DROPBOX_LIST_TEMPLATES_FOR_TEAM` | List team templates |
| `DROPBOX_LIST_USER_TEMPLATES` | List user templates |
| `DROPBOX_REMOVE_FILE_PROPERTIES_TEMPLATE_FOR_TEAM` | Remove template |
| `DROPBOX_UPDATE_PROPERTY_TEMPLATE_FOR_TEAM` | Update template |

---

## Common Workflows

**List files in root:** `DROPBOX_LIST_FILES_IN_FOLDER` with `path=""`

**Upload a text file:** `DROPBOX_UPLOAD_FILE` with `path="/Documents/notes.txt"`, `file_content="text content"`

**Download a file:** `DROPBOX_EXPORT_FILE` with `path="/Documents/report.pdf"`

**Create share link:** `DROPBOX_CREATE_SHARED_LINK` with `path="/Documents/report.pdf"`

**Search files:** `DROPBOX_FILES_SEARCH` with `query="budget report"`

**Get space usage:** `DROPBOX_GET_SPACE_USAGE` (no params)

**Restore a file:** `DROPBOX_LIST_FILE_REVISIONS` â†’ pick revision â†’ `DROPBOX_RESTORE_FILE`

## Rules

- Use `COMPOSIO_DROPBOX_ACCOUNT_ID` for `connected_account_id`
- Root folder path is `""` (empty string), not `"/"`
- All other paths start with `/`
- Use `composio_get_schema` for unknown params
