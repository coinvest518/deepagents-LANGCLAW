---
name: browser-use
description: Control a real Chromium browser to navigate websites, fill forms, click buttons, extract content, and interact with web apps that require JavaScript.
---

# Browser-Use Skill

`browser-use` is an open-source AI browser agent that controls a real Chromium browser.
Use it when you need to interact with websites that require JavaScript rendering, login flows,
form submissions, or dynamic content — things that a simple HTTP fetch cannot handle.

## When to use browser-use vs. other tools

| Need | Use |
|---|---|
| Static page scraping / crawling | Firecrawl or `fetch_url` |
| Search-engine style queries | `web_search` or HyperBrowser |
| JS-heavy pages, SPAs, login walls | **browser-use** |
| Filling and submitting forms | **browser-use** |
| Taking screenshots of pages | **browser-use** |
| Clicking buttons, navigating flows | **browser-use** |

## Basic usage

```python
import asyncio, os
from browser_use import Agent as BrowserAgent
from browser_use.browser.browser import Browser, BrowserConfig
from langchain.chat_models import init_chat_model

async def browse(task: str, model_name: str = "mistralai:mistral-large-latest") -> str:
    llm = init_chat_model(model_name)
    # Pass --no-sandbox when running as root (required in Docker/Render)
    browser = Browser(config=BrowserConfig(
        extra_chromium_args=["--no-sandbox", "--disable-setuid-sandbox"]
    ))
    agent = BrowserAgent(task=task, llm=llm, browser=browser)
    result = await agent.run()
    return str(result)

# Example
result = asyncio.run(browse("Go to https://example.com and return the page title"))
print(result)
```

## Availability check

browser-use requires Playwright + Chromium. Check availability:

```python
try:
    from browser_use import Agent as BrowserAgent
    import playwright
    BROWSER_USE_AVAILABLE = True
except ImportError:
    BROWSER_USE_AVAILABLE = False
```

## Notes

- Chromium is pre-installed in the Docker container (Playwright install runs at build time)
- For local dev: run `playwright install chromium` once after `pip install browser-use`
- **Docker/Render (runs as root):** Always pass `--no-sandbox` via `BrowserConfig(extra_chromium_args=[...])` — without it Chromium will refuse to start
- browser-use uses a real browser — it's slower than HTTP fetch but handles anything a human can see
- Delegate browser tasks to a subagent to keep the main context clean
- BROWSER_USE_AVAILABLE is False if Playwright is not installed — fall back to firecrawl/hyperbrowser

## Subagent delegation pattern

For long browsing sessions, spawn a subagent:

```
Use the browser-use tool to: [specific browsing task].
Save extracted content to browser_output.md.
Use browser_use.Agent with the task string.
```

## Environment requirements

- No additional API key needed — runs locally in the container
- `PLAYWRIGHT_BROWSERS_PATH` can be set to a custom Chromium location if needed
