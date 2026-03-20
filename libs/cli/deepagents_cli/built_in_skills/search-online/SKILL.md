---
name: search-online
description: Enable agents to perform web searches using configured providers (Composio/Tavily, HyperBrowser, Firecrawl). Detects available providers from environment and delegates searches to the appropriate tool.
---

# Search Online Skill

This built-in skill teaches agents how to perform web searches using the environment-configured providers.

Key points:

- The CLI can use multiple provider backends for web search. Common providers in this workspace:
  - Composio (used as the Tavily / `searchonline` bridge)
  - HyperBrowser
  - Firecrawl

- Ensure the provider packages are installed in the Python environment (examples):
  - `composio-langchain` or the org-specific composio client
  - `langchain-hyperbrowser` (or the provider package name used in your environment)
  - `firecrawl-py`

- Ensure API keys / connection info are set in environment variables. Typical names present in this repo's `.env`:
  - `COMPOSIO_API_KEY`, `COMPOSIO_API_URL` (Composio / Tavily)
  - `HYPERBROWSER_API_KEY`
  - `FIRECRAWL_API_KEY`

How agents should use this skill

1. Provider detection

   - Prefer providers in this order: Composio (Composio can proxy Tavily-like searches), HyperBrowser, Firecrawl.
   - Use the presence of both the package import and the env key to decide availability.

2. Invocation pattern (recommended)

   - Use `task` to spawn a short-lived subagent to perform web searches and save findings to files. This keeps web requests isolated and auditable.

   Subagent template:

   ```
   Research [TOPIC]. Use the `web_search` or `searchonline` tool provided by the runtime. Save findings to `research_[topic]/findings_[i].md`.
   Use up to N web searches (3-5) and include source URLs and short quotes.
   ```

3. Tool usage details

   - If `COMPOSIO_API_KEY` and `COMPOSIO_API_URL` are present, call the `searchonline` tool (Composio-backed).

   **Composio as gateway:** Composio is a multi-capability connector that can proxy or orchestrate many downstream services (including Tavily). Treat Composio as the primary gateway for web search and related capabilities (fetching, crawling, connectors, and provider integrations). If Composio is available, prefer routing requests through it so the agent can access unified features (Tavily, site connectors, etc.).

   - If a Composio call fails or does not expose a required capability, fall back to provider-specific clients in this order: HyperBrowser, Firecrawl, then native Tavily (if available).
   - If `HYPERBROWSER_API_KEY` is present and its client library is importable, call the HyperBrowser search tool.
   - If `FIRECRAWL_API_KEY` is present and `firecrawl` client is importable, call Firecrawl.

4. No-code setup

   - If an agent/skill already calls the generic `web_search` or `searchonline` tool, and the provider packages + env keys are present, the runtime will route calls to the available provider automatically. No code change required.

5. When to add code

   - Add an explicit provider adapter only if you need provider-specific features (e.g., advanced crawling controls or rate limits). Otherwise rely on the runtime's generic `searchonline`/`web_search` tool.

6. Safety and rate limits

   - Keep searches small (3-5 per subagent) to avoid costs and rate-limits.

7. Validation

   - Use the included quick validation script to confirm packages and keys are visible to the running Python environment.

If you want, I can also add an example `skill` that calls `searchonline` directly (non-subagent), or wire provider-specific adapters. Which would you prefer?
