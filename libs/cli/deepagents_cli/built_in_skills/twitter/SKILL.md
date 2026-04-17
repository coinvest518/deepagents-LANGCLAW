---
name: twitter
description: >
  Full Twitter/X control via Composio — 79 actions. Post tweets, reply, retweet,
  like, DMs, manage lists, search tweets, get analytics, upload media, manage
  followers. Pre-authenticated. Trigger phrases: "tweet", "post to twitter",
  "twitter", "X post", "retweet", "twitter DM".
license: MIT
compatibility: deepagents-cli
---

# Twitter / X Skill — 79 Actions

Call any action with `composio_action`. Account ID is in `COMPOSIO_TWITTER_ACCOUNT_ID`.

```
composio_action(
  action="TWITTER_<ACTION>",
  params={...},
  connected_account_id=COMPOSIO_TWITTER_ACCOUNT_ID
)
```

For param details: `composio_get_schema("TWITTER_<ACTION>")`

---

## Posting

| Action | What it does |
|--------|-------------|
| `TWITTER_CREATION_OF_A_POST` | Post a tweet — **primary posting action** |
| `TWITTER_POST_DELETE_BY_POST_ID` | Delete a tweet |
| `TWITTER_RETWEET_POST` | Retweet a tweet |
| `TWITTER_UNRETWEET_POST` | Undo a retweet |
| `TWITTER_USER_LIKE_POST` | Like a tweet |
| `TWITTER_UNLIKE_POST` | Unlike a tweet |
| `TWITTER_HIDE_REPLIES` | Hide a reply on your tweet |
| `TWITTER_ADD_POST_TO_BOOKMARKS` | Bookmark a tweet |
| `TWITTER_REMOVE_POST_FROM_BOOKMARKS` | Remove bookmark |
| `TWITTER_BOOKMARKS_BY_USER` | Get your bookmarks |

## Media Upload

| Action | What it does |
|--------|-------------|
| `TWITTER_UPLOAD_MEDIA` | Upload image/video for attaching to tweet |
| `TWITTER_UPLOAD_LARGE_MEDIA` | Upload large media file |
| `TWITTER_INITIALIZE_MEDIA_UPLOAD` | Start chunked media upload |
| `TWITTER_APPEND_MEDIA_UPLOAD` | Append chunk to upload |
| `TWITTER_GET_MEDIA_UPLOAD_STATUS` | Check upload status |

## Search & Lookup

| Action | What it does |
|--------|-------------|
| `TWITTER_RECENT_SEARCH` | Search recent tweets (last 7 days) |
| `TWITTER_FULL_ARCHIVE_SEARCH` | Search full tweet archive |
| `TWITTER_POST_LOOKUP_BY_POST_ID` | Get tweet by ID |
| `TWITTER_POST_LOOKUP_BY_POST_IDS` | Get multiple tweets by IDs |
| `TWITTER_RETRIEVE_POSTS_THAT_QUOTE_A_POST` | Get quote tweets |
| `TWITTER_GET_POST_RETWEETERS_ACTION` | Get people who retweeted |
| `TWITTER_GET_POST_RETWEETS` | Get retweets list |
| `TWITTER_LIST_POST_LIKERS` | List people who liked a tweet |

## Timelines

| Action | What it does |
|--------|-------------|
| `TWITTER_USER_HOME_TIMELINE_BY_USER_ID` | Get home timeline for user |
| `TWITTER_RETURNS_POST_OBJECTS_LIKED_BY_THE_PROVIDED_USER_ID` | Get liked tweets |
| `TWITTER_LIST_POSTS_TIMELINE_BY_LIST_ID` | Get timeline from a list |

## Users

| Action | What it does |
|--------|-------------|
| `TWITTER_USER_LOOKUP_ME` | Get your own profile |
| `TWITTER_USER_LOOKUP_BY_USERNAME` | Find user by @handle |
| `TWITTER_USER_LOOKUP_BY_USERNAMES` | Find multiple users |
| `TWITTER_GET_USERS_BY_IDS` | Get users by IDs |
| `TWITTER_GET_USER_BY_ID` | Get a single user by ID |
| `TWITTER_FOLLOW_USER` | Follow a user |
| `TWITTER_UNFOLLOW_USER` | Unfollow a user |
| `TWITTER_FOLLOWERS_BY_USER_ID` | Get a user's followers |
| `TWITTER_FOLLOWING_BY_USER_ID` | Get who a user follows |
| `TWITTER_MUTE_USER` | Mute a user |
| `TWITTER_UNMUTE_USER` | Unmute a user |
| `TWITTER_GET_MUTED_USERS` | List muted users |
| `TWITTER_GET_BLOCKED_USERS` | List blocked users |

## Lists

| Action | What it does |
|--------|-------------|
| `TWITTER_CREATE_LIST` | Create a Twitter list |
| `TWITTER_GET_LIST` | Get list details |
| `TWITTER_UPDATE_LIST` | Edit list name/description |
| `TWITTER_DELETE_LIST` | Delete a list |
| `TWITTER_ADD_LIST_MEMBER` | Add user to list |
| `TWITTER_REMOVE_LIST_MEMBER` | Remove user from list |
| `TWITTER_GET_LIST_MEMBERS` | Get list members |
| `TWITTER_GET_LIST_FOLLOWERS` | Get list followers |
| `TWITTER_FOLLOW_LIST` | Follow a list |
| `TWITTER_UNFOLLOW_LIST` | Unfollow a list |
| `TWITTER_PIN_LIST` | Pin a list |
| `TWITTER_UNPIN_LIST` | Unpin a list |
| `TWITTER_GET_USER_OWNED_LISTS` | Get your lists |
| `TWITTER_GET_USER_FOLLOWED_LISTS` | Lists you follow |
| `TWITTER_GET_USER_PINNED_LISTS` | Your pinned lists |
| `TWITTER_GET_USER_LIST_MEMBERSHIPS` | Lists you're a member of |

## DMs

| Action | What it does |
|--------|-------------|
| `TWITTER_SEND_A_NEW_MESSAGE_TO_A_USER` | Send a DM |
| `TWITTER_CREATE_DM_CONVERSATION` | Create a DM conversation |
| `TWITTER_SEND_DM_TO_CONVERSATION` | Send to existing DM conversation |
| `TWITTER_DELETE_DM` | Delete a DM |
| `TWITTER_GET_DM_EVENT` | Get a DM event |
| `TWITTER_GET_RECENT_DM_EVENTS` | Get recent DMs |
| `TWITTER_GET_DM_CONVERSATION_EVENTS` | Get events in a DM conversation |
| `TWITTER_RETRIEVE_DM_CONVERSATION_EVENTS` | Retrieve DM conversation |

## Analytics

| Action | What it does |
|--------|-------------|
| `TWITTER_GET_POST_ANALYTICS` | Get engagement stats for a tweet |
| `TWITTER_GET_POST_USAGE` | Get usage metrics |
| `TWITTER_SEARCH_RECENT_COUNTS` | Count matching tweets |
| `TWITTER_SEARCH_FULL_ARCHIVE_COUNTS` | Count in full archive |

## Spaces

| Action | What it does |
|--------|-------------|
| `TWITTER_GET_SPACE_BY_ID` | Get Space details |
| `TWITTER_GET_SPACES_BY_IDS` | Get multiple Spaces |
| `TWITTER_GET_SPACES_BY_CREATORS` | Get Spaces by creator |
| `TWITTER_SEARCH_SPACES` | Search Spaces |
| `TWITTER_GET_SPACE_POSTS` | Get tweets from a Space |
| `TWITTER_GET_SPACE_TICKET_BUYERS` | Get ticket holders |

---

## Common Workflows

**Post a tweet:** `TWITTER_CREATION_OF_A_POST` with `text`

**Post tweet with image:**
1. `TWITTER_UPLOAD_MEDIA` with image file → get `media_id`
2. `TWITTER_CREATION_OF_A_POST` with `text` + `media_ids=[media_id]`

**Reply to a tweet:** `TWITTER_CREATION_OF_A_POST` with `text` + `reply.in_reply_to_tweet_id`

**Search recent tweets:** `TWITTER_RECENT_SEARCH` with `query` (supports operators: from:, to:, #hashtag, lang:en)

**Get your own profile:** `TWITTER_USER_LOOKUP_ME`

## Rules

- Use `COMPOSIO_TWITTER_ACCOUNT_ID` for `connected_account_id`
- Tweet text max 280 chars (2800 with Twitter Blue)
- Use `composio_get_schema` if params are unclear
