---
name: facebook
description: >
  Full Facebook Page control via Composio — 43 actions. Create posts, photos,
  videos, manage comments, page insights, messaging/inbox, page settings,
  scheduled posts, reactions. Pre-authenticated.
  Trigger phrases: "facebook", "fb post", "facebook page", "facebook message",
  "post to facebook", "facebook insights".
license: MIT
compatibility: deepagents-cli
---

# Facebook Skill — 43 Actions

Call any action with `composio_action`. Account ID is in `COMPOSIO_FACEBOOK_ACCOUNT_ID`.

```
composio_action(
  action="FACEBOOK_<ACTION>",
  params={...},
  connected_account_id=COMPOSIO_FACEBOOK_ACCOUNT_ID
)
```

For param details: `composio_get_schema("FACEBOOK_<ACTION>")`

---

## Posting

| Action | What it does |
|--------|-------------|
| `FACEBOOK_CREATE_POST` | Create a text post on a page — **primary posting action** |
| `FACEBOOK_CREATE_PHOTO_POST` | Post an image |
| `FACEBOOK_CREATE_VIDEO_POST` | Post a video |
| `FACEBOOK_UPLOAD_PHOTO` | Upload a photo (returns photo ID) |
| `FACEBOOK_UPLOAD_PHOTOS_BATCH` | Upload multiple photos |
| `FACEBOOK_UPLOAD_VIDEO` | Upload a video |
| `FACEBOOK_UPDATE_POST` | Edit an existing post |
| `FACEBOOK_DELETE_POST` | Delete a post |
| `FACEBOOK_GET_POST` | Get post details |
| `FACEBOOK_GET_PAGE_POSTS` | List posts on a page |

## Scheduled Posts

| Action | What it does |
|--------|-------------|
| `FACEBOOK_GET_SCHEDULED_POSTS` | List scheduled posts |
| `FACEBOOK_PUBLISH_SCHEDULED_POST` | Publish a scheduled post now |
| `FACEBOOK_RESCHEDULE_POST` | Change scheduled time |

## Comments

| Action | What it does |
|--------|-------------|
| `FACEBOOK_CREATE_COMMENT` | Comment on a post |
| `FACEBOOK_GET_COMMENT` | Get comment details |
| `FACEBOOK_GET_COMMENTS` | List comments on a post |
| `FACEBOOK_UPDATE_COMMENT` | Edit a comment |
| `FACEBOOK_DELETE_COMMENT` | Delete a comment |
| `FACEBOOK_LIKE_POST_OR_COMMENT` | Like a post or comment |
| `FACEBOOK_UNLIKE_POST_OR_COMMENT` | Unlike |

## Messaging / Inbox

| Action | What it does |
|--------|-------------|
| `FACEBOOK_SEND_MESSAGE` | Send a message to a user in Page inbox |
| `FACEBOOK_SEND_MEDIA_MESSAGE` | Send image/video in message |
| `FACEBOOK_GET_PAGE_CONVERSATIONS` | List inbox conversations |
| `FACEBOOK_GET_CONVERSATION_MESSAGES` | Read messages in a conversation |
| `FACEBOOK_GET_MESSAGE_DETAILS` | Get a single message |
| `FACEBOOK_MARK_MESSAGE_SEEN` | Mark message as seen |
| `FACEBOOK_TOGGLE_TYPING_INDICATOR` | Show typing indicator |

## Page Analytics

| Action | What it does |
|--------|-------------|
| `FACEBOOK_GET_PAGE_INSIGHTS` | Get page-level analytics (reach, engagement, fans) |
| `FACEBOOK_GET_POST_INSIGHTS` | Get analytics for a specific post |
| `FACEBOOK_GET_POST_REACTIONS` | Get reaction breakdown (like, love, haha, etc.) |

## Page Management

| Action | What it does |
|--------|-------------|
| `FACEBOOK_GET_PAGE_DETAILS` | Get page name, ID, about, category |
| `FACEBOOK_GET_USER_PAGES` | List pages you manage |
| `FACEBOOK_LIST_MANAGED_PAGES` | List managed pages |
| `FACEBOOK_UPDATE_PAGE_SETTINGS` | Update page settings |
| `FACEBOOK_GET_PAGE_ROLES` | List page admins/editors |
| `FACEBOOK_ASSIGN_PAGE_TASK` | Assign a task to a page role |
| `FACEBOOK_REMOVE_PAGE_TASK` | Remove a task |
| `FACEBOOK_SEARCH_PAGES` | Search for Facebook pages |
| `FACEBOOK_GET_CURRENT_USER` | Get current user info |

## Photos & Albums

| Action | What it does |
|--------|-------------|
| `FACEBOOK_CREATE_PHOTO_ALBUM` | Create a photo album |
| `FACEBOOK_GET_PAGE_PHOTOS` | List photos on the page |
| `FACEBOOK_GET_PAGE_VIDEOS` | List videos on the page |
| `FACEBOOK_GET_PAGE_TAGGED_POSTS` | Get posts that tagged the page |

---

## Common Workflows

**Post text to Facebook Page:** `FACEBOOK_CREATE_POST` with `message` (text content)

**Post image with caption:**
1. `FACEBOOK_UPLOAD_PHOTO` with image URL or file → get photo ID
2. `FACEBOOK_CREATE_PHOTO_POST` with `message` + `attached_media`

**Get Page insights:** `FACEBOOK_GET_PAGE_INSIGHTS` with `metric` (e.g. `page_impressions`, `page_engaged_users`)

**Reply to a message:** `FACEBOOK_SEND_MESSAGE` with `recipient.id` + `message.text`

## Rules

- Use `COMPOSIO_FACEBOOK_ACCOUNT_ID` for `connected_account_id`
- Most actions require a `page_id` — use `FACEBOOK_GET_USER_PAGES` if you don't know it
- Use `composio_get_schema` for param details
