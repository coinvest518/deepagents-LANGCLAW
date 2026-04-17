---
name: slack
description: >
  Full Slack control via Composio — 151 actions. Send messages, manage channels,
  upload files, search messages, manage users and workspaces, create canvases,
  set reminders, handle DMs, reactions, pins, user groups. Pre-authenticated.
  Trigger phrases: "slack", "send to slack", "slack channel", "slack message",
  "dm on slack", "slack notification".
license: MIT
compatibility: deepagents-cli
---

# Slack Skill — 151 Actions

Call any action with `composio_action`. Account ID is in `COMPOSIO_SLACK_ACCOUNT_ID`.

```
composio_action(
  action="SLACK_<ACTION>",
  params={...},
  connected_account_id=COMPOSIO_SLACK_ACCOUNT_ID
)
```

For param details: `composio_get_schema("SLACK_<ACTION>")`

---

## Messaging — Most Used

| Action | What it does |
|--------|-------------|
| `SLACK_SEND_MESSAGE` | Send a message to a channel or DM — **primary action for sending** |
| `SLACK_UPDATES_A_SLACK_MESSAGE` | Edit an existing message |
| `SLACK_DELETES_A_MESSAGE_FROM_A_CHAT` | Delete a message |
| `SLACK_SEND_EPHEMERAL_MESSAGE` | Send message only visible to one user |
| `SLACK_SEND_ME_MESSAGE` | Send a /me message |
| `SLACK_SCHEDULE_MESSAGE` | Schedule message for a future time |
| `SLACK_DELETE_SCHEDULED_MESSAGE` | Cancel a scheduled message |
| `SLACK_LIST_SCHEDULED_MESSAGES` | List pending scheduled messages |
| `SLACK_RETRIEVE_MESSAGE_PERMALINK_URL` | Get permalink for a message |

## Channels

| Action | What it does |
|--------|-------------|
| `SLACK_CREATE_CHANNEL` | Create a new channel |
| `SLACK_CREATE_CHANNEL_BASED_CONVERSATION` | Create channel-based conversation |
| `SLACK_FIND_CHANNELS` | Search/find channels by name |
| `SLACK_LIST_ALL_CHANNELS` | List all channels in workspace |
| `SLACK_LIST_CONVERSATIONS` | List conversations |
| `SLACK_RETRIEVE_CONVERSATION_INFORMATION` | Get channel info |
| `SLACK_RETRIEVE_CONVERSATION_MEMBERS_LIST` | List members of a channel |
| `SLACK_FETCH_CONVERSATION_HISTORY` | Get message history |
| `SLACK_FETCH_MESSAGE_THREAD_FROM_A_CONVERSATION` | Get thread replies |
| `SLACK_INVITE_USERS_TO_A_SLACK_CHANNEL` | Add users to channel |
| `SLACK_INVITE_USER_TO_CHANNEL` | Invite one user |
| `SLACK_REMOVE_USER_FROM_CONVERSATION` | Remove user from channel |
| `SLACK_JOIN_AN_EXISTING_CONVERSATION` | Join a channel |
| `SLACK_LEAVE_CONVERSATION` | Leave a channel |
| `SLACK_ARCHIVE_CONVERSATION` | Archive a channel |
| `SLACK_UNARCHIVE_CHANNEL` | Unarchive a channel |
| `SLACK_DELETE_CHANNEL` | Delete a channel |
| `SLACK_RENAME_CONVERSATION` | Rename a channel |
| `SLACK_SET_THE_TOPIC_OF_A_CONVERSATION` | Set channel topic |
| `SLACK_SET_CONVERSATION_PURPOSE` | Set channel purpose |
| `SLACK_CONVERT_CHANNEL_TO_PRIVATE` | Convert to private channel |
| `SLACK_SET_READ_CURSOR_IN_A_CONVERSATION` | Mark channel as read |

## Files

| Action | What it does |
|--------|-------------|
| `SLACK_UPLOAD_OR_CREATE_A_FILE_IN_SLACK` | Upload a file — **use for sharing files** |
| `SLACK_DOWNLOAD_SLACK_FILE` | Download a file |
| `SLACK_RETRIEVE_DETAILED_INFORMATION_ABOUT_A_FILE` | Get file info |
| `SLACK_LIST_FILES_WITH_FILTERS_IN_SLACK` | List files with filters |
| `SLACK_DELETE_FILE` | Delete a file |
| `SLACK_ENABLE_PUBLIC_SHARING_OF_A_FILE` | Make file public |
| `SLACK_REVOKE_FILE_PUBLIC_SHARING` | Make file private |
| `SLACK_ADD_REMOTE_FILE` | Add remote (external) file |
| `SLACK_GET_REMOTE_FILE` | Get remote file info |
| `SLACK_UPDATE_REMOTE_FILE` | Update remote file |
| `SLACK_REMOVE_REMOTE_FILE` | Remove remote file reference |
| `SLACK_SHARE_REMOTE_FILE` | Share remote file to channel |
| `SLACK_LIST_REMOTE_FILES` | List remote files |

## Direct Messages (DMs)

| Action | What it does |
|--------|-------------|
| `SLACK_OPEN_DM` | Open a DM with a user |
| `SLACK_CLOSE_DM` | Close a DM |

## Users

| Action | What it does |
|--------|-------------|
| `SLACK_FIND_USERS` | Search for users |
| `SLACK_FIND_USER_BY_EMAIL_ADDRESS` | Find user by email |
| `SLACK_LIST_ALL_USERS` | List all workspace users |
| `SLACK_RETRIEVE_DETAILED_USER_INFORMATION` | Get user profile |
| `SLACK_RETRIEVE_USER_PROFILE_INFORMATION` | Get user profile fields |
| `SLACK_RETRIEVE_A_USER_S_IDENTITY_DETAILS` | Get user identity |
| `SLACK_GET_USER_PRESENCE` | Check if user is online |
| `SLACK_SET_USER_PROFILE` | Update user profile |
| `SLACK_SET_USER_ACTIVE` | Set user as active |
| `SLACK_SET_USER_PRESENCE` | Set presence (auto/away) |
| `SLACK_SET_PROFILE_PHOTO` | Set profile photo |
| `SLACK_DELETE_USER_PROFILE_PHOTO` | Remove profile photo |
| `SLACK_INVITE_USER_TO_WORKSPACE` | Invite user to workspace |
| `SLACK_REMOVE_USER_FROM_WORKSPACE` | Remove user from workspace |
| `SLACK_RESET_USER_SESSIONS` | Force logout a user |

## Reactions & Pins

| Action | What it does |
|--------|-------------|
| `SLACK_ADD_REACTION_TO_AN_ITEM` | Add emoji reaction |
| `SLACK_REMOVE_REACTION_FROM_ITEM` | Remove reaction |
| `SLACK_FETCH_ITEM_REACTIONS` | List reactions on a message |
| `SLACK_LIST_USER_REACTIONS` | List a user's reactions |
| `SLACK_PIN_ITEM` | Pin a message |
| `SLACK_UNPIN_ITEM` | Unpin a message |
| `SLACK_LIST_PINNED_ITEMS` | List pinned messages |
| `SLACK_ADD_STAR` | Star an item |
| `SLACK_REMOVE_STAR` | Unstar an item |
| `SLACK_LIST_STARRED_ITEMS` | List starred items |

## Reminders

| Action | What it does |
|--------|-------------|
| `SLACK_CREATE_A_REMINDER` | Create a reminder |
| `SLACK_GET_REMINDER` | Get reminder details |
| `SLACK_LIST_REMINDERS` | List all reminders |
| `SLACK_DELETE_REMINDER` | Delete a reminder |
| `SLACK_MARK_REMINDER_AS_COMPLETE` | Mark reminder done |

## Search

| Action | What it does |
|--------|-------------|
| `SLACK_SEARCH_MESSAGES` | Search through messages |
| `SLACK_SEARCH_ALL` | Search messages and files |

## Canvases

| Action | What it does |
|--------|-------------|
| `SLACK_CREATE_CANVAS` | Create a canvas |
| `SLACK_GET_CANVAS` | Get canvas content |
| `SLACK_EDIT_CANVAS` | Edit canvas |
| `SLACK_DELETE_CANVAS` | Delete canvas |
| `SLACK_LIST_CANVASES` | List canvases |
| `SLACK_LOOKUP_CANVAS_SECTIONS` | Find sections in canvas |

## User Groups

| Action | What it does |
|--------|-------------|
| `SLACK_CREATE_USER_GROUP` | Create a user group |
| `SLACK_LIST_USER_GROUPS` | List user groups |
| `SLACK_ENABLE_USER_GROUP` | Enable a group |
| `SLACK_DISABLE_USER_GROUP` | Disable a group |
| `SLACK_UPDATE_USER_GROUP` | Update group details |
| `SLACK_UPDATE_USER_GROUP_MEMBERS` | Change group members |
| `SLACK_LIST_USER_GROUP_MEMBERS` | List group members |

## Workspace Settings

| Action | What it does |
|--------|-------------|
| `SLACK_FETCH_TEAM_INFO` | Get workspace info |
| `SLACK_GET_WORKSPACE_SETTINGS` | Get workspace settings |
| `SLACK_SET_WORKSPACE_NAME` | Update workspace name |
| `SLACK_SET_WORKSPACE_DESCRIPTION` | Update description |
| `SLACK_SET_WORKSPACE_ICON` | Update workspace icon |
| `SLACK_LIST_WORKSPACE_ADMINS` | List workspace admins |
| `SLACK_LIST_WORKSPACE_OWNERS` | List workspace owners |
| `SLACK_LIST_WORKSPACE_USERS` | List all workspace users |

## DND Status

| Action | What it does |
|--------|-------------|
| `SLACK_GET_USER_DND_STATUS` | Get user's DND status |
| `SLACK_RETRIEVE_CURRENT_USER_DND_STATUS` | Get your DND status |
| `SLACK_SET_DND_DURATION` | Set DND for N minutes |
| `SLACK_END_DND` | End DND immediately |
| `SLACK_END_SNOOZE` | End snooze period |

---

## Common Workflows

**Send a message to a channel:**
`SLACK_SEND_MESSAGE` with `channel` (#channel-name or channel ID) + `text`

**Send a DM to a user:**
1. `SLACK_FIND_USER_BY_EMAIL_ADDRESS` or `SLACK_FIND_USERS` → get user ID
2. `SLACK_OPEN_DM` with user ID → get DM channel ID
3. `SLACK_SEND_MESSAGE` with the DM channel ID

**Reply to a message (thread):**
`SLACK_SEND_MESSAGE` with `channel`, `text`, and `thread_ts` (timestamp of the parent message)

**Upload a file to a channel:**
`SLACK_UPLOAD_OR_CREATE_A_FILE_IN_SLACK` with `channels` + `content` or `file` path

**Schedule a message:**
`SLACK_SCHEDULE_MESSAGE` with `channel`, `text`, `post_at` (Unix timestamp)

## Rules

- Use `COMPOSIO_SLACK_ACCOUNT_ID` for `connected_account_id`
- Channel IDs (C...) are more reliable than names — use `FIND_CHANNELS` first if you only have a name
- For `composio_get_schema` call before any action if params are unclear
