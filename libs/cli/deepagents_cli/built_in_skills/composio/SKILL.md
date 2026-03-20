---
name: composio
description: Use Composio as the primary gateway to Tavily and other connected services. Provides guidance and examples for agents to call Composio-backed capabilities.
---

# Composio Skill

Composio is a multi-capability connector (gateway) that can proxy or orchestrate downstream services such as Tavily, site connectors (GitHub, Gmail), and other crawlers. Treat Composio as the preferred path for web-search, crawling, connector access, and other remote capabilities.

Usage guidance for agents and developers

- Environment: ensure `COMPOSIO_API_KEY` and `COMPOSIO_API_URL` are set in the environment (or project `.env`).
- Import: the runtime may expose a `composio` client from the `composio` or `composio_client` package. The test script in this folder demonstrates safe client initialization.
- Preferred routing: call Composio first for `search`, `fetch`, or connector operations. If Composio reports the capability is unavailable, call provider-specific adapters (HyperBrowser, Firecrawl).

Agent pattern (recommended)

1. Decide to search the web. Use `task` to spawn a short subagent with the narrow prompt:

   ```
   Research [TOPIC]. Use the `composio.search` or runtime `web_search` tool (which prefers Composio).
   Save findings to `research_[topic]/findings_[i].md` using `write_file`.
   Limit to 3-5 searches.
   ```

2. Synthesis: After subagents finish, read files and synthesize final answer.

Developer notes

- See `scripts/test_composio.py` for a safe, multi-attempt client initialization and examples of `list tools` and `search` calls.
- The runtime `web_search` tool should be extended to call Composio first and fall back to other providers; consider adding an adapter in `libs/cli/deepagents_cli/tools.py`.

Security & rate limits

- Avoid large-scale crawling without explicit approval. Keep parallel searches small.
- Sanitize user-provided URLs and queries where applicable.
