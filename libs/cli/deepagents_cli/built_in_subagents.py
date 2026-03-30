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

    return [web_scraper]
