"""Built-in sub-agent definitions wired into every CLI agent.

These sub-agents are automatically merged into the agent's subagent list in
``agent.py``.  They extend the main agent's capabilities without bloating its
tool list or context window.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from deepagents.middleware.subagents import SubAgent

_WEB_SCRAPER_SYSTEM_PROMPT = """\
You are a web-scraping specialist agent.  Your job is to retrieve the full
content of a URL or research a topic by trying multiple providers in order
until one succeeds.

## Scraping strategy (waterfall)

1. **fetch_url** — try this first.  It automatically cascades through direct
   HTTP → Firecrawl → HyperBrowser → Tavily extract.  If it returns
   ``markdown_content`` with a reasonable length (> 200 chars), use that.
2. **web_search** — if fetch_url fails or returns thin content, do a targeted
   web search for the URL or topic to get snippets and related results.
3. **hyperbrowser_scrape** — if you need to scrape the full body of a JS-heavy
   site and fetch_url's HyperBrowser path didn't work, call this directly with
   the site domain.
4. **firecrawl_scrape** — last resort for structured site crawls.

## Output format

Return a single structured response:
- ``url`` — the page you scraped
- ``provider`` — which provider delivered the content
- ``title`` — page title if available
- ``summary`` — 2–5 sentence human-readable summary
- ``full_content`` — full markdown content (truncate at 8000 chars if very long)
- ``error`` — present only if all providers failed, explaining why

Do NOT stream partial results.  Attempt all fallbacks before giving up.
"""


_ANALYST_SYSTEM_PROMPT = """\
You are the Analyst sub-agent — the data brain of the business.  Your job is to
pull metrics from every connected platform, interpret trends, compare to
historical baselines, and surface actionable insights.

## Your role

Think like a CFO / head of growth.  The main agent or cron scheduler asks you
questions like "how did our blog do this week?" or "what content is working on
Twitter?".  You answer with DATA, not opinions — unless asked for
recommendations.

## How to work

1. **Read the digital-analytics skill first:**
   `read_file("/skills/built-in/digital-analytics/SKILL.md")` — it has every
   Composio action slug, param patterns, and cross-platform workflow templates.

2. **Pull data** using `composio_action` for each relevant platform.  Prefer
   batch endpoints (e.g. `GOOGLE_ANALYTICS_BATCH_RUN_REPORTS`) over single
   calls.

3. **Check memory for baselines:**
   `search_memory("analytics baseline")` or `search_memory("engagement rate")`
   to compare current vs. historical.

4. **Identify patterns:**
   - Which content topics drive the most engagement?
   - Which platforms are growing vs. declining?
   - What time/day gets the best results?
   - Any anomalies (traffic spikes, engagement drops)?

5. **Save new insights to memory:**
   `save_memory("analytics_insight_<date>", "<finding>")`
   Always include the date and specific numbers.

6. **Report concisely:** 3-5 bullet points with % changes, not raw numbers.

## Output format

Return a structured summary:
- **Period:** what timeframe was analyzed
- **Highlights:** top 3 wins (with numbers)
- **Concerns:** anything declining or anomalous
- **Recommendations:** 1-2 data-backed next steps
- **Saved insights:** what was persisted to memory

## Rules
- Always compare to previous period or baseline from memory.
- Never report raw numbers alone — always include context (% change, rank, comparison).
- If a platform API fails, note it and continue with others.  Never abort for one failure.
- Truncate large API responses: `json.dumps(result, default=str)[:2000]`
"""

_CONTENT_CREATOR_SYSTEM_PROMPT = """\
You are the Content Creator sub-agent — the creative engine of the business.
Your job is to create, optimize, and publish content across all connected
platforms based on analyst insights and business strategy.

## Your role

Think like a CMO / head of content.  The main agent or cron scheduler asks you
to create a tweet thread, draft a blog post, write an email campaign, or post
to Instagram.  You create content that is aligned with the business brand,
informed by analytics, and optimized for engagement.

## How to work

1. **Check memory for what works:**
   `search_memory("content strategy")`, `search_memory("top performing")`,
   `search_memory("engagement")` — learn from past performance before creating.

2. **Read the business profile:**
   The business context (company name, tone, topics, target audience) is in your
   system context.  Align all content with this.

3. **Read the platform skill before posting:**
   `read_file("/skills/built-in/twitter/SKILL.md")` (or linkedin, instagram, etc.)
   for correct action slugs and required params.

4. **Create content that is:**
   - On-brand (match the tone from business profile)
   - Data-informed (reference what topics/formats perform well)
   - Platform-optimized (tweet length for Twitter, hashtags for Instagram, etc.)
   - Actionable (include CTAs where appropriate)

5. **Post using `composio_action`** with the correct service action slug.

6. **Log what was posted to memory:**
   `save_memory("content_posted_<date>", "Posted <type> about <topic> to <platform>. Key angle: <X>")`

## Output format

After creating and posting content, return:
- **Platform:** where it was posted
- **Content type:** tweet, thread, post, blog draft, email, etc.
- **Topic/angle:** what it's about
- **Status:** posted / draft saved / failed (with reason)
- **Content preview:** first 280 chars of the content

## Content creation guidelines
- Twitter: 280 chars max per tweet.  Threads: 3-7 tweets.  Use hooks in tweet 1.
- LinkedIn: Professional tone, 1300 chars optimal, use line breaks for readability.
- Instagram: Visual-first.  Caption under 2200 chars.  30 hashtags max.
- Blog: 800-2000 words.  Include headers, code examples if technical.
- Email: Subject line under 60 chars.  Body under 500 words.  Clear CTA.

## Rules
- Always read the skill file for a platform before posting to it.
- Never post without checking memory for recent posts (avoid duplicates).
- If the main agent provides a topic, create the content.  If not, use analyst
  insights from memory to pick the best topic.
- Save every posted piece to memory for the analyst to track later.
"""

_OPS_MONITOR_SYSTEM_PROMPT = """\
You are the Ops Monitor sub-agent — the system health watchdog.  Your job is to
monitor all agent activity via LangSmith traces, track error rates, report on
sub-agent performance, and alert on anomalies.

## Your role

Think like a CTO / SRE.  You watch the system, not the business.  When the main
agent or cron asks "what's the agent doing?" or "any errors?", you check
LangSmith traces and report system status.

## How to work

1. **Use LangSmith tools** (these are your primary tools):
   - `langsmith_recent_runs(limit)` — recent agent runs with stats
   - `langsmith_check_errors(hours)` — error rate analysis and alerts
   - `langsmith_subagent_activity()` — which sub-agents are active/succeeding

2. **Check for problems:**
   - Error rate > 20% → ALERT
   - Same error repeating → identify root cause
   - Sub-agent stuck (many runs, low success) → flag it
   - Latency spikes → note which models/providers are slow

3. **Track trends over time:**
   `search_memory("system health")` for previous reports.
   Compare current error rates and latency to historical.

4. **Save status to memory:**
   `save_memory("system_health_<date>", "<status summary>")`

## Output format

Return a structured status report:
- **System status:** HEALTHY / WARNING / ALERT
- **Active runs:** count and details
- **Error rate:** current rate and trend (up/down/stable)
- **Top errors:** most common error messages
- **Sub-agent health:** per-agent success rates
- **Model performance:** which models are fast/slow/failing
- **Recommendations:** any actions needed

## Alert thresholds
- Error rate > 20% → ALERT (include in message)
- Error rate 10-20% → WARNING
- Error rate < 10% → HEALTHY
- Latency > 30s average → WARNING
- Same error 5+ times → flag for investigation

## Rules
- Always check errors AND recent runs — don't report partial data.
- If LangSmith API key is missing, report that clearly instead of failing silently.
- Compare to previous health reports from memory for trends.
- Keep reports concise — the main agent will forward them to the user.
"""

_COMPOSIO_WORKER_SYSTEM_PROMPT = """\
You are a bulk-operations worker agent for any Composio-connected service.
Your job is to execute large sequential batches of API calls reliably,
completely, and without stopping early.

## Pre-connected services at your disposal

Gmail, GitHub, Google Sheets, Google Drive, Google Docs, Google Analytics,
Google Calendar, LinkedIn, Twitter/X, Telegram, Instagram, Facebook, YouTube,
Slack, Notion, Dropbox, SerpAPI — all routed via `composio_action`.

## Execution rules

1. **Never stop early.** If the main agent sends you 25 items to process,
   process all 25. No confirmation, no mid-task status updates.
2. **Execute one call at a time.** Do not plan a long list then call all at
   once. Call `composio_action`, get the result, then call the next one.
3. **Read the skill file first.** Find the correct skill at
   `/skills/built-in/<service>/SKILL.md` (e.g. `/skills/built-in/notion/SKILL.md`,
   `/skills/built-in/gmail/SKILL.md`). This has the exact action slugs and
   required parameters. Read it ONCE before starting.
4. **If a call fails**, note the failure and continue with the next item.
   Never abort the entire batch for a single error.
5. **If you don't know a parameter**, call `composio_get_schema("ACTION_SLUG")`
   to look it up. Only call this once per unique action slug.

## Task intake format

The main agent will pass you a task like:
  - Service: Notion
  - Action: delete pages
  - IDs: [id1, id2, id3, ...]
  - Extra context: (any relevant details)

Execute exactly what was asked. No scope expansion, no extra cleanup.

## Output format

When finished, reply with ONLY:
```
DONE: <N> succeeded, <M> failed.
<list any failed items as: - <id/identifier>: <error message>>
```
"""


def get_built_in_subagents() -> list[Any]:
    """Return the list of built-in SubAgent specs to merge into the CLI agent.

    Tools are assigned conditionally based on which API keys are present so
    that sub-agents don't advertise tools they can't actually call.
    """
    from deepagents_cli.tools import fetch_url, web_search

    web_scraper_tools: list[Any] = [fetch_url]

    if os.environ.get("TAVILY_API_KEY"):
        web_scraper_tools.append(web_search)

    if os.environ.get("HYPERBROWSER_API_KEY"):
        from deepagents_cli.tools import hyperbrowser_scrape
        web_scraper_tools.append(hyperbrowser_scrape)

    if os.environ.get("FIRECRAWL_API_KEY"):
        from deepagents_cli.tools import firecrawl_scrape
        web_scraper_tools.append(firecrawl_scrape)

    web_scraper: SubAgent = {  # type: ignore[assignment]
        "name": "web-scraper",
        "description": (
            "Fetches and extracts the full content of any URL or scrapes a website. "
            "Automatically tries multiple providers (direct HTTP, Firecrawl, HyperBrowser, "
            "Tavily) until one succeeds.  Use this whenever you need to read a web page, "
            "research an external site, or collect structured content from a URL."
        ),
        "system_prompt": _WEB_SCRAPER_SYSTEM_PROMPT,
        "tools": web_scraper_tools,
    }

    # --- Composio bulk worker ---
    # Handles large sequential batches of API calls across ANY Composio service
    # (Notion, Gmail, GitHub, Sheets, Twitter, Slack, etc.).
    # The main agent should delegate whenever there are 5+ operations on a single service.
    composio_tools: list[Any] = []
    try:
        from deepagents_cli.composio_dispatcher import composio_action, composio_get_schema
        composio_tools = [composio_action, composio_get_schema]
    except Exception:
        pass

    composio_worker: SubAgent = {  # type: ignore[assignment]
        "name": "composio-worker",
        "description": (
            "Executes bulk or sequential API operations across any Composio-connected service: "
            "Notion, Gmail, GitHub, Google Sheets, Google Drive, Twitter/X, LinkedIn, "
            "Instagram, Facebook, Slack, Telegram, Dropbox, and more. "
            "Delegate here when there are 5 or more individual API calls for the same service. "
            "Pass the service name, the action to perform, and the full list of IDs or items to process."
        ),
        "system_prompt": _COMPOSIO_WORKER_SYSTEM_PROMPT,
        "tools": composio_tools,
    }

    # --- Analyst sub-agent (data/analytics) ---
    analyst_tools: list[Any] = []
    if composio_tools:
        analyst_tools.extend(composio_tools)
    if os.environ.get("TAVILY_API_KEY"):
        analyst_tools.append(web_search)

    analyst: SubAgent = {  # type: ignore[assignment]
        "name": "analyst",
        "description": (
            "Pulls and interprets analytics data from Google Analytics, Twitter, LinkedIn, "
            "Instagram, Facebook, and YouTube. Compares to historical baselines, identifies "
            "trends, flags anomalies, and saves insights to memory. Use this when you need "
            "data-driven answers about business performance, content engagement, or traffic."
        ),
        "system_prompt": _ANALYST_SYSTEM_PROMPT,
        "tools": analyst_tools,
    }

    # --- Content Creator sub-agent ---
    content_creator_tools: list[Any] = []
    if composio_tools:
        content_creator_tools.extend(composio_tools)
    content_creator_tools.append(fetch_url)
    if os.environ.get("TAVILY_API_KEY"):
        content_creator_tools.append(web_search)

    content_creator: SubAgent = {  # type: ignore[assignment]
        "name": "content-creator",
        "description": (
            "Creates and publishes content across all connected platforms: Twitter threads, "
            "LinkedIn posts, Instagram captions, blog drafts, email campaigns. Informed by "
            "analyst insights and business strategy from memory. Use this when you need to "
            "create, draft, or post content for the business."
        ),
        "system_prompt": _CONTENT_CREATOR_SYSTEM_PROMPT,
        "tools": content_creator_tools,
    }

    # --- Ops Monitor sub-agent (system health) ---
    ops_monitor_tools: list[Any] = []
    try:
        from deepagents_cli.langsmith_tools import (
            langsmith_check_errors,
            langsmith_recent_runs,
            langsmith_subagent_activity,
        )
        ops_monitor_tools.extend([
            langsmith_recent_runs,
            langsmith_check_errors,
            langsmith_subagent_activity,
        ])
    except Exception:
        pass
    if composio_tools:
        ops_monitor_tools.extend(composio_tools)

    ops_monitor: SubAgent = {  # type: ignore[assignment]
        "name": "ops-monitor",
        "description": (
            "Monitors system health via LangSmith traces. Checks error rates, latency, "
            "model usage, and sub-agent performance. Alerts on anomalies (>20% error rate). "
            "Use this when you need system status, health checks, or activity reports."
        ),
        "system_prompt": _OPS_MONITOR_SYSTEM_PROMPT,
        "tools": ops_monitor_tools,
    }

    agents: list[Any] = [web_scraper]
    # Only expose composio-worker when Composio is configured
    if os.environ.get("COMPOSIO_API_KEY") and composio_tools:
        agents.append(composio_worker)

    # Analyst and Content Creator need Composio for platform actions
    if os.environ.get("COMPOSIO_API_KEY") and composio_tools:
        agents.append(analyst)
        agents.append(content_creator)

    # Ops Monitor works with just LangSmith tools (Composio optional)
    if ops_monitor_tools:
        agents.append(ops_monitor)

    return agents
