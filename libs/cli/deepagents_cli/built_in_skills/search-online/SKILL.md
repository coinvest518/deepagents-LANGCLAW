---
name: search-online
description: Search the EXTERNAL internet for current prices, news, trends, public info, or anything not stored internally. Uses Tavily (primary) with HyperBrowser fallback for site-scoped scraping. NOT for internal system queries.
---

# Search Online Skill

## IMPORTANT: Know when to use this

**USE `web_search` for:**
- Current prices, news, trending topics, public info
- Researching external websites, companies, people
- Anything on the open internet you don't already know

**DO NOT use `web_search` for:**
- What tools/integrations are connected → you already know them (see system prompt)
- Checking notes, links, or data saved in AstraDB → query the knowledge base directly
- Gmail, GitHub, Google Drive, social media → use `composio_action` tool
- Internal system questions (what's running, what's configured, etc.)

---

## Available web tools

### `web_search` — Tavily-powered internet search

The callable tool is **`web_search`** (not "search-online" — that's this skill's name, not a tool).

```
web_search(query="your search query", max_results=5, topic="general")
```

- `topic`: `"general"` | `"news"` | `"finance"`
- Falls back to HyperBrowser automatically for site-scoped queries (`site:domain.com`)
- Returns: `{results: [{title, url, content, score}, ...], query}`

### `fetch_url` — Fetch a single URL as markdown

```
fetch_url(url="https://example.com")
```

Use when you have a specific URL and want the page content.

### `http_request` — Raw HTTP requests

```
http_request(url="https://api.example.com/data", method="GET", headers={...})
```

Use for REST APIs that don't have a Composio integration.

---

## Provider availability

| Provider | Env var needed | Auto-loaded |
|----------|---------------|-------------|
| Tavily | `TAVILY_API_KEY` | Yes — via `web_search` tool |
| HyperBrowser | `HYPERBROWSER_API_KEY` | Yes — auto-fallback in `web_search` for site-scoped |
| Firecrawl | `FIRECRAWL_API_KEY` | No — use via Python if needed |
| Playwright/Chromium | None (pre-installed) | Via `browser-use` skill |

---

## For deep browser automation (not just search)

If you need to interact with a website (click, fill forms, navigate), use the **`browser-use`** skill instead. Playwright + Chromium are pre-installed in the container.

---

## Rate limits

Keep searches to 3-5 per task to avoid costs. Spawn a subagent for research-heavy tasks.