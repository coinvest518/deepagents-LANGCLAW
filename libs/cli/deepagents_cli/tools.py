"""Custom tools for the CLI agent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from tavily import TavilyClient

_UNSET = object()
_tavily_client: TavilyClient | object | None = _UNSET


def _get_tavily_client() -> TavilyClient | None:
    """Get or initialize the lazy Tavily client singleton."""
    from deepagents_cli.config import settings

    global _tavily_client
    if _tavily_client is not _UNSET:
        return _tavily_client  # type: ignore[return-value]

    if getattr(settings, "has_tavily", False):
        try:
            from tavily import TavilyClient as _TavilyClient

            _tavily_client = _TavilyClient(api_key=settings.tavily_api_key)
        except Exception:
            _tavily_client = None
    else:
        _tavily_client = None

    return _tavily_client  # type: ignore[return-value]


def http_request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: str | dict | None = None,
    params: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """Make HTTP requests to APIs and web services.

    Args:
        url: Target URL
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        headers: HTTP headers to include
        data: Request body data (string or dict)
        params: URL query parameters
        timeout: Request timeout in seconds

    Returns:
        Dictionary with response data including status, headers, and content
    """
    import requests

    try:
        kwargs: dict[str, Any] = {}

        if headers:
            kwargs["headers"] = headers
        if params:
            kwargs["params"] = params
        if data:
            if isinstance(data, dict):
                kwargs["json"] = data
            else:
                kwargs["data"] = data

        response = requests.request(method.upper(), url, timeout=timeout, **kwargs)

        try:
            content = response.json()
        except (ValueError, requests.exceptions.JSONDecodeError):
            content = response.text

        return {
            "success": response.status_code < 400,  # noqa: PLR2004  # HTTP status code threshold
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "content": content,
            "url": response.url,
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "status_code": 0,
            "headers": {},
            "content": f"Request timed out after {timeout} seconds",
            "url": url,
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "status_code": 0,
            "headers": {},
            "content": f"Request error: {e!s}",
            "url": url,
        }


def web_search(  # noqa: ANN201 - Tavily-first web search adapter
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
    *,
    fallback_to_hyperbrowser: bool = True,
):
    """Search the EXTERNAL internet for current prices, news, trends, public info.

    Use for: real-time prices, news, public company/person info, external research.
    Do NOT use for: connected integrations, AstraDB queries, Gmail/GitHub/Drive
    or social media (use composio_action for those), or internal system questions.

    Args:
        query: Search query. Supports site:domain.com to scope to a specific site.
        max_results: Number of results to return (default 5).
        topic: Search category — "general", "news", or "finance".
        include_raw_content: Include raw page content in results.

    Returns:
        Dict with `results` list and `query`, or `error` key on failure.
    """
    import re

    # Parse optional site:domain from the query
    site_domain: str | None = None
    stripped_query = query
    m = re.search(r"\bsite:([\w\.-]+)\b", query)
    if m:
        site_domain = m.group(1)
        stripped_query = re.sub(r"\bsite:[\w\.-]+\b", "", query).strip()

    # Call the Tavily provider wrapper
    try:
        from deepagents_cli.providers import tavily as tavily_provider
        out = tavily_provider.search(
            stripped_query or query,
            max_results=max_results,
            include_raw_content=include_raw_content,
            topic=topic,
            site_domain=site_domain,
        )
    except Exception as e:
        return {"error": f"Tavily web search failed: {e!s}", "query": query}

    # Normalize and score outputs from the provider, producing a consistent
    # structure the agents can consume: {results: [{title,url,content,score,raw},...], query: str}
    try:
        normalized = normalize_and_score_results(out, query=query, site_domain=site_domain, max_results=max_results)
        # If no results from Tavily and hyperbrowser fallback is enabled, try HyperBrowser for site-scoped queries
        if (not normalized.get("results")) and site_domain and fallback_to_hyperbrowser:
            try:
                from deepagents_cli.providers import hyperbrowser as hb

                hb_out = hb.search_site(site_domain, query=stripped_query or query, max_results=max_results)
                if hb_out:
                    normalized = normalize_and_score_results(hb_out, query=query, site_domain=site_domain, max_results=max_results)
            except Exception:
                pass
        return normalized
    except Exception as e:
        return {"error": f"Normalization failed: {e!s}", "query": query}


def fetch_url(url: str, timeout: int = 30) -> dict[str, Any]:
    """Fetch content from a URL and convert HTML to markdown format.

    This tool fetches web page content and converts it to clean markdown text,
    making it easy to read and process HTML content. After receiving the markdown,
    you MUST synthesize the information into a natural, helpful response for the user.

    Args:
        url: The URL to fetch (must be a valid HTTP/HTTPS URL)
        timeout: Request timeout in seconds (default: 30)

    Returns:
        Dictionary containing:
        - success: Whether the request succeeded
        - url: The final URL after redirects
        - markdown_content: The page content converted to markdown
        - status_code: HTTP status code
        - content_length: Length of the markdown content in characters

    IMPORTANT: After using this tool:
    1. Read through the markdown content
    2. Extract relevant information that answers the user's question
    3. Synthesize this into a clear, natural language response
    4. NEVER show the raw markdown to the user unless specifically requested
    """
    try:
        import requests
        from markdownify import markdownify
    except ImportError as exc:
        return {
            "error": f"Required package not installed: {exc.name}. "
            "Install with: pip install 'deepagents[cli]'",
            "url": url,
        }

    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (compatible; DeepAgents/1.0)"},
        )
        response.raise_for_status()

        # Convert HTML content to markdown
        markdown_content = markdownify(response.text)

        return {
            "url": str(response.url),
            "markdown_content": markdown_content,
            "status_code": response.status_code,
            "content_length": len(markdown_content),
        }
    except requests.exceptions.RequestException as e:
        return {"error": f"Fetch URL error: {e!s}", "url": url}


def hyperbrowser_scrape(site_domain: str, *, query: str | None = None, max_results: int = 5) -> dict[str, Any]:
    """Run a HyperBrowser scrape for a site and return normalized results.

    This is a thin wrapper around `deepagents_cli.providers.hyperbrowser.search_site`
    to expose HyperBrowser as a first-class tool for agents.
    """
    try:
        from deepagents_cli.providers import hyperbrowser as hb

        out = hb.search_site(site_domain, query=query, max_results=max_results)
        return normalize_and_score_results(out, query=query or f"site:{site_domain}", site_domain=site_domain, max_results=max_results)
    except Exception as e:
        return {"error": f"HyperBrowser scrape failed: {e!s}", "query": query or f"site:{site_domain}"}


def firecrawl_scrape(site_domain: str, *, query: str | None = None, max_results: int = 5) -> dict[str, Any]:
    """Run a Firecrawl search scoped to a site and return normalized results.

    Thin wrapper around `deepagents_cli.providers.firecrawl.search` to expose
    Firecrawl as a first-class tool for agents. Returns normalized output via
    `normalize_and_score_results` on success or an error dict on failure.
    """
    try:
        from deepagents_cli.providers import firecrawl as fc

        out = fc.search(query or "", max_results=max_results, site_domain=site_domain)
        return normalize_and_score_results(out, query=query or f"site:{site_domain}", site_domain=site_domain, max_results=max_results)
    except Exception as e:
        return {"error": f"Firecrawl search failed: {e!s}", "query": query or f"site:{site_domain}"}


def normalize_and_score_results(
    raw: Any,
    *,
    query: str,
    site_domain: str | None = None,
    max_results: int = 5,
) -> dict[str, Any]:
    """Normalize provider outputs into a consistent list of results and score them.

    The returned shape is:
    {
        "query": str,
        "results": [
            {"title": str, "url": str, "content": str, "score": float, "raw": Any}
        ]
    }
    """
    from urllib.parse import urlparse

    def extract_from_item(item: Any) -> dict:
        if not isinstance(item, dict):
            text = str(item)
            return {"title": text[:120], "url": "", "content": text, "raw": item}

        # prefer explicit fields, fall back to common alternatives
        title = item.get("title") or item.get("name") or item.get("headline") or ""
        url = item.get("url") or item.get("link") or item.get("href") or item.get("uri") or ""
        content = (
            item.get("content")
            or item.get("snippet")
            or item.get("excerpt")
            or item.get("raw_content")
            or item.get("text")
            or ""
        )
        return {"title": title, "url": url, "content": content, "raw": item}

    items: list[dict] = []

    # Accept dicts with 'results' or 'data' keys, lists, or single dicts
    if isinstance(raw, dict):
        if "results" in raw and isinstance(raw["results"], list):
            candidates = raw["results"]
        elif "data" in raw and isinstance(raw["data"], dict) and isinstance(raw["data"].get("web"), list):
            candidates = raw["data"]["web"]
        elif "raw" in raw:
            candidates = [raw["raw"]]
        else:
            # treat the dict itself as a single item
            candidates = [raw]
    elif isinstance(raw, list):
        candidates = raw
    else:
        candidates = [raw]

    for c in candidates:
        items.append(extract_from_item(c))

    scored: list[dict] = []
    for it in items:
        score = 0.0
        content = it.get("content") or ""
        title = it.get("title") or ""
        url = it.get("url") or ""

        # signal if content present and substantial
        if isinstance(content, str) and len(content) > 200:
            score += 0.5
        elif isinstance(content, str) and len(content) > 80:
            score += 0.25

        # small boost for title presence
        if title:
            score += 0.15

        # boost when URL matches requested site_domain
        try:
            if site_domain and url:
                p = urlparse(url)
                hostname = (p.hostname or "").lower()
                if site_domain.lower() in hostname:
                    score += 0.25
        except Exception:
            pass

        # clamp
        score = min(score, 1.0)

        scored.append({"title": title, "url": url, "content": content, "score": round(float(score), 3), "raw": it.get("raw")})

    # sort by score desc and trim
    scored.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    top = scored[: max(0, int(max_results))]

    return {"query": query, "results": top}
