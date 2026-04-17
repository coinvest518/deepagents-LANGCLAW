---
name: digital-analytics
description: >
  Cross-platform analytics skill for the analyst sub-agent. Pulls engagement
  metrics, post performance, audience insights, and traffic data from Google
  Analytics, Twitter/X, LinkedIn, Instagram, Facebook, and YouTube via Composio.
  Use this to observe, measure, and learn from real business data.
  Trigger phrases: "analytics", "how did we do", "performance", "metrics",
  "engagement", "traffic", "insights", "what's working".
license: MIT
compatibility: deepagents-cli
---

# Digital Analytics Skill -- Cross-Platform Metrics

This skill is the analyst sub-agent's primary reference for pulling metrics
across all connected platforms. Every action uses `composio_action`.

## Quick Start

```
composio_action(
  action="<SERVICE>_<ACTION>",
  params={...},
  connected_account_id=COMPOSIO_<SERVICE>_ACCOUNT_ID
)
```

For param details: `composio_get_schema("<SERVICE>_<ACTION>")`

---

## Google Analytics (Website Traffic & Behavior)

Account ID env: `COMPOSIO_GOOGLE_ANALYTICS_ACCOUNT_ID`

| Action | What it does |
|--------|-------------|
| `GOOGLE_ANALYTICS_BATCH_RUN_REPORTS` | Run multiple reports in one call (page views, sessions, users) |
| `GOOGLE_ANALYTICS_BATCH_RUN_PIVOT_REPORTS` | Pivot reports (e.g. traffic by source by day) |
| `GOOGLE_ANALYTICS_RUN_REPORT` | Single report with dimensions and metrics |
| `GOOGLE_ANALYTICS_RUN_REALTIME_REPORT` | Live active users right now |
| `GOOGLE_ANALYTICS_CHECK_COMPATIBILITY` | Check which dimensions/metrics work together |
| `GOOGLE_ANALYTICS_CREATE_REPORT_TASK` | Async report for large date ranges |
| `GOOGLE_ANALYTICS_GET_AUDIENCE` | Audience segment details |

### Common Report Patterns

**Daily traffic summary:**
```
composio_action(
  action="GOOGLE_ANALYTICS_BATCH_RUN_REPORTS",
  params={
    "property": "properties/YOUR_PROPERTY_ID",
    "requests": [{
      "dateRanges": [{"startDate": "7daysAgo", "endDate": "today"}],
      "dimensions": [{"name": "date"}],
      "metrics": [
        {"name": "activeUsers"},
        {"name": "sessions"},
        {"name": "screenPageViews"},
        {"name": "bounceRate"}
      ]
    }]
  }
)
```

**Top pages:**
```
composio_action(
  action="GOOGLE_ANALYTICS_BATCH_RUN_REPORTS",
  params={
    "property": "properties/YOUR_PROPERTY_ID",
    "requests": [{
      "dateRanges": [{"startDate": "30daysAgo", "endDate": "today"}],
      "dimensions": [{"name": "pagePath"}],
      "metrics": [{"name": "screenPageViews"}, {"name": "activeUsers"}],
      "orderBys": [{"metric": {"metricName": "screenPageViews"}, "desc": true}],
      "limit": "10"
    }]
  }
)
```

**Traffic sources:**
```
composio_action(
  action="GOOGLE_ANALYTICS_BATCH_RUN_REPORTS",
  params={
    "property": "properties/YOUR_PROPERTY_ID",
    "requests": [{
      "dateRanges": [{"startDate": "7daysAgo", "endDate": "today"}],
      "dimensions": [{"name": "sessionSource"}, {"name": "sessionMedium"}],
      "metrics": [{"name": "sessions"}, {"name": "activeUsers"}]
    }]
  }
)
```

---

## Twitter / X Analytics

Account ID env: `COMPOSIO_TWITTER_ACCOUNT_ID`

| Action | What it does |
|--------|-------------|
| `TWITTER_USER_LOOKUP_ME` | Get your own profile stats (followers, following, tweet count) |
| `TWITTER_SEARCH_TWEETS` | Search for tweets about your brand or topic |
| `TWITTER_GET_USERS_MENTIONS` | See who's mentioning you |
| `TWITTER_USER_TIMELINE` | Get your recent tweets to analyze |
| `TWITTER_GET_TWEET` | Get a specific tweet with engagement metrics |
| `TWITTER_LIST_FOLLOWERS` | Get follower list for growth tracking |

### Measuring Tweet Performance

1. Get recent tweets: `TWITTER_USER_TIMELINE` with your user ID
2. For each tweet, the response includes `public_metrics`:
   - `retweet_count`, `reply_count`, `like_count`, `quote_count`, `impression_count`
3. Compare against historical averages (from memory) to flag winners/losers

---

## LinkedIn Analytics

Account ID env: `COMPOSIO_LINKEDIN_ACCOUNT_ID`

| Action | What it does |
|--------|-------------|
| `LINKEDIN_GET_PROFILE` | Your profile stats (connections, followers) |
| `LINKEDIN_GET_ALL_POSTS` | Get your recent posts with engagement data |
| `LINKEDIN_GET_SINGLE_POST` | Get specific post with full metrics |
| `LINKEDIN_GET_COMPANY_PROFILE` | Company page stats |

### Post Performance Pattern

1. Pull recent posts: `LINKEDIN_GET_ALL_POSTS`
2. Each post includes: likes, comments, shares, impressions
3. Calculate engagement rate: `(likes + comments + shares) / impressions * 100`
4. Save top-performing topics to memory for content strategy

---

## Instagram Analytics

Account ID env: `COMPOSIO_INSTAGRAM_ACCOUNT_ID`

| Action | What it does |
|--------|-------------|
| `INSTAGRAM_GET_MEDIA_INSIGHTS` | Engagement metrics for a specific post |
| `INSTAGRAM_GET_USER_INSIGHTS` | Account-level metrics (reach, impressions, followers) |
| `INSTAGRAM_GET_MEDIA_LIST` | List recent posts |
| `INSTAGRAM_GET_STORY_INSIGHTS` | Story performance metrics |
| `INSTAGRAM_GET_BASIC_USER_INFO` | Profile stats |

### Content Performance Pattern

1. Get media list: `INSTAGRAM_GET_MEDIA_LIST`
2. For each post, get insights: `INSTAGRAM_GET_MEDIA_INSIGHTS`
3. Metrics include: impressions, reach, engagement, saves, shares
4. Track which content types (carousel, reel, image) perform best

---

## Facebook Analytics

Account ID env: `COMPOSIO_FACEBOOK_ACCOUNT_ID`

| Action | What it does |
|--------|-------------|
| `FACEBOOK_GET_PAGE_INSIGHTS` | Page-level metrics (reach, engagement, followers) |
| `FACEBOOK_GET_POST_INSIGHTS` | Individual post performance |
| `FACEBOOK_GET_PAGE_POSTS` | List recent posts |
| `FACEBOOK_GET_PAGE_FANS` | Follower/fan count over time |

---

## YouTube Analytics

Account ID env: `COMPOSIO_YOUTUBE_ACCOUNT_ID`

| Action | What it does |
|--------|-------------|
| `YOUTUBE_LIST_CHANNELS` | Channel stats (subscribers, views, video count) |
| `YOUTUBE_LIST_VIDEOS` | Recent videos with view counts |
| `YOUTUBE_LIST_CHANNEL_ANALYTICS` | Detailed analytics (watch time, CTR, audience retention) |

---

## Cross-Platform Analysis Workflow

The analyst sub-agent should follow this pattern for a full business health check:

1. **Pull all platform metrics** (parallel where possible):
   - Google Analytics: traffic, top pages, sources
   - Twitter: profile stats, recent tweet performance
   - LinkedIn: post engagement, follower growth
   - Instagram: content insights, reach
   - YouTube: video performance, subscriber growth

2. **Compare to baselines** (from memory):
   - `search_memory("analytics baseline")` for historical averages
   - Flag anything > 2x or < 0.5x the baseline

3. **Identify winners and losers**:
   - Which content topics got the most engagement?
   - Which platforms are growing vs declining?
   - What time/day gets the best results?

4. **Save insights to memory**:
   ```
   save_memory("analytics_insight_YYYY-MM-DD", "Twitter engagement up 40% this week. Top topic: AI agents. Best time: 10am EST. Instagram reels outperform static posts 3:1.")
   ```

5. **Report to user or feed into content agent**:
   - Summarize findings in 3-5 bullet points
   - Recommend actions based on data

## Rules

- Always truncate large responses: `json.dumps(result, default=str)[:2000]`
- Use `composio_get_schema("<ACTION>")` if unsure about parameters
- Save all significant findings to memory for trend tracking
- Compare current metrics to previous periods before reporting
- Never report raw numbers without context (always include % change or comparison)
