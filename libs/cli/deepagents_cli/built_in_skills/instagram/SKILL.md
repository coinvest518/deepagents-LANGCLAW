---
name: instagram
description: >
  Full Instagram control via Composio — 36 actions. Create posts, carousels,
  stories, read/reply to comments, DMs/inbox, media insights, user analytics.
  Pre-authenticated. Trigger phrases: "instagram", "IG post", "instagram story",
  "post to instagram", "instagram DM", "instagram comment".
license: MIT
compatibility: deepagents-cli
---

# Instagram Skill — 36 Actions

Call any action with `composio_action`. Account ID is in `COMPOSIO_INSTAGRAM_ACCOUNT_ID`.

```
composio_action(
  action="INSTAGRAM_<ACTION>",
  params={...},
  connected_account_id=COMPOSIO_INSTAGRAM_ACCOUNT_ID
)
```

For param details: `composio_get_schema("INSTAGRAM_<ACTION>")`

---

## Posting

| Action | What it does |
|--------|-------------|
| `INSTAGRAM_CREATE_POST` | Publish an image/video post — **primary posting action** |
| `INSTAGRAM_CREATE_MEDIA_CONTAINER` | Create a media container (step 1 of 2-step publish) |
| `INSTAGRAM_CREATE_CAROUSEL_CONTAINER` | Create carousel post container |
| `INSTAGRAM_POST_IG_USER_MEDIA` | Upload media to user account |
| `INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH` | Publish a staged media container |
| `INSTAGRAM_GET_POST_STATUS` | Check publishing status |
| `INSTAGRAM_GET_IG_USER_CONTENT_PUBLISHING_LIMIT` | Check daily publish limit |

## Comments

| Action | What it does |
|--------|-------------|
| `INSTAGRAM_GET_IG_MEDIA_COMMENTS` | Get comments on a post |
| `INSTAGRAM_GET_POST_COMMENTS` | Get post comments (alternate) |
| `INSTAGRAM_POST_IG_MEDIA_COMMENTS` | Comment on a media post |
| `INSTAGRAM_GET_IG_COMMENT_REPLIES` | Get replies to a comment |
| `INSTAGRAM_POST_IG_COMMENT_REPLIES` | Reply to a comment |
| `INSTAGRAM_REPLY_TO_COMMENT` | Reply to a comment |
| `INSTAGRAM_DELETE_COMMENT` | Delete a comment |

## DMs / Messaging

| Action | What it does |
|--------|-------------|
| `INSTAGRAM_GET_PAGE_CONVERSATIONS` | List DM conversations |
| `INSTAGRAM_GET_CONVERSATION` | Get a specific conversation |
| `INSTAGRAM_LIST_ALL_CONVERSATIONS` | List all conversations |
| `INSTAGRAM_LIST_ALL_MESSAGES` | List all messages |
| `INSTAGRAM_SEND_TEXT_MESSAGE` | Send a DM text message |
| `INSTAGRAM_SEND_IMAGE` | Send an image in DM |
| `INSTAGRAM_MARK_SEEN` | Mark conversation as seen |
| `INSTAGRAM_GET_MESSENGER_PROFILE` | Get messaging profile settings |
| `INSTAGRAM_UPDATE_MESSENGER_PROFILE` | Update messaging profile |
| `INSTAGRAM_DELETE_MESSENGER_PROFILE` | Delete messenger profile |

## Media & Content

| Action | What it does |
|--------|-------------|
| `INSTAGRAM_GET_IG_MEDIA` | Get post/media details |
| `INSTAGRAM_GET_IG_MEDIA_CHILDREN` | Get carousel children |
| `INSTAGRAM_GET_IG_USER_MEDIA` | List a user's posts |
| `INSTAGRAM_GET_USER_MEDIA` | Get user media (alternate) |
| `INSTAGRAM_GET_IG_USER_STORIES` | Get active stories |
| `INSTAGRAM_GET_IG_USER_LIVE_MEDIA` | Get live video info |
| `INSTAGRAM_GET_IG_USER_TAGS` | Get posts where user is tagged |
| `INSTAGRAM_POST_IG_USER_MENTIONS` | Handle user mentions |

## Analytics & Insights

| Action | What it does |
|--------|-------------|
| `INSTAGRAM_GET_USER_INFO` | Get account info |
| `INSTAGRAM_GET_USER_INSIGHTS` | Get account-level analytics (reach, impressions, followers) |
| `INSTAGRAM_GET_IG_MEDIA_INSIGHTS` | Get post-level analytics |
| `INSTAGRAM_GET_POST_INSIGHTS` | Get insights for a specific post |

---

## Common Workflows

**Post an image to Instagram:**
1. `INSTAGRAM_CREATE_MEDIA_CONTAINER` with `image_url` + `caption` → get container ID
2. `INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH` with the container ID

Or shortcut: `INSTAGRAM_CREATE_POST` (single step)

**Post a carousel:**
1. `INSTAGRAM_CREATE_MEDIA_CONTAINER` for each image → get container IDs
2. `INSTAGRAM_CREATE_CAROUSEL_CONTAINER` with list of container IDs + caption
3. `INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH` with carousel container ID

**Reply to a comment:** `INSTAGRAM_REPLY_TO_COMMENT` with `comment_id` + `message`

**Get account analytics:** `INSTAGRAM_GET_USER_INSIGHTS` with `metric` + `period`

## Rules

- Use `COMPOSIO_INSTAGRAM_ACCOUNT_ID` for `connected_account_id`
- Images must be publicly accessible URLs for container creation
- Publishing has a daily limit — check with `GET_IG_USER_CONTENT_PUBLISHING_LIMIT`
- Use `composio_get_schema` for unknown params
