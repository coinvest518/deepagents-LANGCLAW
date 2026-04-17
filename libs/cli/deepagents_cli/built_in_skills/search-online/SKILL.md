---
name: search-online
description: Search the EXTERNAL internet for current prices, news, trends, public info, or anything not stored internally. Uses Tavily (primary) with HyperBrowser fallback for site-scoped scraping. Includes Extract, Crawl, and Map capabilities. NOT for internal system queries.
---

# Search Online Skill

## IMPORTANT: Know when to use this

**USE these tools for:**
- Current prices, news, trending topics, public info
- Researching external websites, companies, people
- Extracting content from specific URLs
- Crawling multi-page sites or documentation
- Discovering a website's page structure
- Anything on the open internet you don't already know

**DO NOT use these tools for:**
- What tools/integrations are connected → you already know them (see system prompt)
- Checking notes, links, or data saved in AstraDB → query the knowledge base directly
- Gmail, GitHub, Google Drive, social media → use `composio_action` tool
- Internal system questions (what's running, what's configured, etc.)

---

## Available web tools

### `web_search` — Tavily-powered internet search

The callable tool is **`web_search`** (not "search-online" — that's this skill's name, not a tool).

```
web_search(
    query="your search query",
    max_results=5,
    topic="general",
    search_depth="basic",
    time_range=None,
    include_domains=None,
    exclude_domains=None,
)
```

**Parameters:**
- `query`: Search terms. Supports `site:domain.com` to scope to a specific website.
- `max_results`: Number of results (default 5).
- `topic`: `"general"` | `"news"` | `"finance"` — picks the right search index.
- `search_depth`: `"basic"` (fast, default) | `"advanced"` (deeper, slower, higher quality results).
- `time_range`: `"day"` | `"week"` | `"month"` | `"year"` | `None` — filter by recency.
- `include_domains`: List of domains to limit results to, e.g. `["reddit.com", "arxiv.org"]`.
- `exclude_domains`: List of domains to exclude from results.

**Returns:** `{results: [{title, url, content, score}, ...], query}`

**When to use `search_depth="advanced"`:**
- Complex research queries needing high-quality, comprehensive results
- When basic search returns insufficient or shallow results
- Academic or technical research

**When to use `time_range`:**
- `"day"` — breaking news, today's prices/scores
- `"week"` — recent developments, this week's news
- `"month"` — recent trends, monthly reports
- `"year"` — annual reviews, yearly data

Falls back to HyperBrowser automatically for site-scoped queries.

---

### `tavily_extract` — Extract content from specific URLs

```
tavily_extract(urls=["https://example.com/page1", "https://example.com/page2"])
```

Use when you have specific URLs and want their full text content. More reliable than `fetch_url` for bot-protected or JavaScript-heavy pages. Can extract from multiple URLs in one call.

**Parameters:**
- `urls`: List of URLs to extract content from.
- `include_raw_content`: Include raw HTML alongside extracted text (default false).

**Returns:** `{results: [{url, content}, ...]}`

---

### `tavily_crawl` — Crawl a multi-page website

```
tavily_crawl(url="https://docs.example.com", max_depth=2, max_pages=10, limit=10)
```

Follows links starting from the given URL up to `max_depth` levels deep. Returns content from each discovered page. Use for documentation sites, multi-page articles, or any site where you need content from many linked pages.

**Parameters:**
- `url`: Starting URL to crawl.
- `max_depth`: How many link levels to follow (default 2).
- `max_pages`: Maximum number of pages to crawl (default 10).
- `limit`: Maximum results to return (default 10).

**Returns:** `{results: [{url, title, content}, ...]}`

---

### `tavily_map` — Discover a website's page structure

```
tavily_map(url="https://example.com", instructions="only blog posts")
```

Returns a sitemap-like list of all discovered URLs on a website. Use to understand a site's structure before extracting or crawling specific pages.

**Parameters:**
- `url`: Website URL to map.
- `instructions`: Optional natural-language filter (e.g. "only blog posts", "pricing pages").

**Returns:** `{urls: ["https://example.com/page1", ...]}`

---

### `fetch_url` — Fetch a single URL as markdown

```
fetch_url(url="https://example.com")
```

Use when you have a specific URL and want the page content. Tries multiple providers (direct HTTP, Firecrawl, HyperBrowser, Tavily extract) until one succeeds.

---

### `http_request` — Raw HTTP requests

```
http_request(url="https://api.example.com/data", method="GET", headers={...})
```

Use for REST APIs that don't have a Composio integration.

---

## Decision matrix: Which tool to use?

| Scenario | Tool |
|----------|------|
| General web search for info | `web_search` |
| Breaking news (today) | `web_search` with `time_range="day"` |
| Domain-specific search (e.g. only Reddit) | `web_search` with `include_domains=["reddit.com"]` |
| Deep research needing quality results | `web_search` with `search_depth="advanced"` |
| Have a specific URL, want its content | `fetch_url` or `tavily_extract` |
| Multiple URLs to read at once | `tavily_extract` with list of URLs |
| Need content from a multi-page site | `tavily_crawl` |
| Want to see all pages on a site | `tavily_map` |
| Map a site, then extract specific pages | `tavily_map` → pick URLs → `tavily_extract` |
| API endpoint (no web page) | `http_request` |

---

## Provider availability

| Provider | Env var needed | Auto-loaded |
|----------|---------------|-------------|
| Tavily | `TAVILY_API_KEY` | Yes — all tavily tools |
| HyperBrowser | `HYPERBROWSER_API_KEY` | Yes — auto-fallback in `web_search` |
| Firecrawl | `FIRECRAWL_API_KEY` | Yes — fallback in `fetch_url` |

---

## Rate limits

Keep searches to 3-5 per task to avoid costs. Use `tavily_map` to discover pages, then `tavily_extract` for targeted reads instead of many separate searches. Spawn a subagent for research-heavy tasks.
