"""Tavily provider wrapper.

Small adapter so the rest of the CLI can call Tavily via a stable interface.
"""
from __future__ import annotations

from typing import Any

from deepagents_cli.config import settings


def _get_client() -> Any | None:
    if not getattr(settings, "has_tavily", False):
        return None
    try:
        from tavily import TavilyClient as _TavilyClient

        return _TavilyClient(api_key=settings.tavily_api_key)
    except Exception:
        return None


def search(
    query: str,
    *,
    max_results: int = 5,
    include_raw_content: bool = False,
    topic: str = "general",
    search_depth: str = "basic",
    time_range: str | None = None,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    site_domain: str | None = None,
    session_params: dict | None = None,
    crawl_params: dict | None = None,
) -> Any:
    """Run a Tavily search and return the raw provider response.

    Args:
        query: Search query string.
        max_results: Number of results to return.
        include_raw_content: Include raw page content in results.
        topic: Search category — "general", "news", or "finance".
        search_depth: "basic" (fast) or "advanced" (deeper, slower).
        time_range: Recency filter — "day", "week", "month", "year", or None.
        include_domains: Limit results to these domains.
        exclude_domains: Exclude results from these domains.
        site_domain: Legacy shorthand — adds a single domain to include_domains.
        session_params: Extra SDK kwargs to pass through.
        crawl_params: Extra kwargs for the crawl fallback.

    Raises:
        RuntimeError: If Tavily is not configured/available.
    """
    client = _get_client()
    if client is None:
        raise RuntimeError("Tavily client not configured")

    tav_query = query
    kwargs: dict[str, Any] = {
        "max_results": max_results,
        "include_raw_content": include_raw_content,
        "topic": topic,
        "search_depth": search_depth,
    }
    if time_range:
        kwargs["time_range"] = time_range

    # Build domain filters
    domains: list[str] = list(include_domains or [])
    if site_domain and site_domain not in domains:
        domains.append(site_domain)
    if domains:
        kwargs["include_domains"] = domains
    if exclude_domains:
        kwargs["exclude_domains"] = exclude_domains

    # 1) Try search. If `session_params` contains SDK-specific options, try to
    # pass them through; if the SDK rejects unexpected kwargs, fall back to
    # the simple call.
    try:
        if session_params:
            try:
                out = client.search(tav_query, **kwargs, **session_params)
            except TypeError:
                try:
                    out = client.search(tav_query, **kwargs)
                except Exception:
                    out = None
        else:
            out = client.search(tav_query, **kwargs)
    except Exception:
        out = None

    # normalize helper
    def _normalize(out_obj: Any) -> dict[str, Any]:
        # Expecting dict-like with 'results' or SDK model
        if out_obj is None:
            return {"results": [], "query": query}
        if isinstance(out_obj, dict):
            if out_obj.get("results"):
                return {"results": out_obj.get("results"), "query": query}
            # some SDKs return top-level list
            if isinstance(out_obj.get("items"), list):
                return {"results": out_obj.get("items"), "query": query}
        # fallback: try to coerce list-like
        if isinstance(out_obj, list):
            return {"results": out_obj, "query": query}
        return {"results": [], "query": query}

    normalized = _normalize(out)

    # 2) If site_domain was provided but search returned empty, try extract/crawl
    if (site_domain or domains) and not normalized["results"]:
        site_domain = site_domain or (domains[0] if domains else None)
    if site_domain and not normalized["results"]:
        # Try extract(page) first
        try:
            url = f"https://{site_domain}"
            if hasattr(client, "extract"):
                try:
                    if session_params:
                        extracted = client.extract(url, include_raw_content=include_raw_content, **session_params)
                    else:
                        extracted = client.extract(url, include_raw_content=include_raw_content)
                except TypeError:
                    extracted = client.extract(url, include_raw_content=include_raw_content)
                # Some extract() implementations return dict or model with 'content'/'markdown'
                if isinstance(extracted, dict):
                    content = extracted.get("content") or extracted.get("markdown") or extracted.get("html") or ""
                else:
                    content = getattr(extracted, "content", None) or getattr(extracted, "markdown", None) or getattr(extracted, "html", "")
                if content:
                    return {"results": [{"title": url, "url": url, "content": content, "score": 1.0, "raw": extracted}], "query": query}
        except Exception:
            pass

        # Try crawl if available
        try:
            if hasattr(client, "crawl"):
                try:
                    if crawl_params:
                        crawled = client.crawl(site_domain, max_results=max_results, **crawl_params)
                    else:
                        crawled = client.crawl(site_domain, max_results=max_results)
                except TypeError:
                    crawled = client.crawl(site_domain, max_results=max_results)
                # normalize crawled outputs
                if isinstance(crawled, dict) and crawled.get("results"):
                    return {"results": crawled.get("results"), "query": query}
                if isinstance(crawled, list) and crawled:
                    return {"results": crawled, "query": query}
        except Exception:
            pass

    return normalized


def extract(urls: list[str], *, include_raw_content: bool = False) -> dict[str, Any]:
    """Extract content from one or more URLs using Tavily Extract.

    Args:
        urls: List of URLs to extract content from.
        include_raw_content: Include raw HTML alongside extracted content.

    Returns:
        Dict with `results` list (each with url, content, raw_content).

    Raises:
        RuntimeError: If Tavily is not configured.
    """
    client = _get_client()
    if client is None:
        raise RuntimeError("Tavily client not configured")

    try:
        out = client.extract(urls=urls, include_raw_content=include_raw_content)
    except TypeError:
        # Older SDK versions may not accept include_raw_content
        out = client.extract(urls=urls)

    if isinstance(out, dict):
        return {"results": out.get("results", []), "urls": urls}
    if isinstance(out, list):
        return {"results": out, "urls": urls}
    return {"results": [], "urls": urls}


def crawl(
    url: str,
    *,
    max_depth: int = 2,
    max_pages: int = 10,
    limit: int = 10,
) -> dict[str, Any]:
    """Crawl a website starting from a URL using Tavily Crawl.

    Args:
        url: Starting URL to crawl.
        max_depth: Maximum link depth to follow.
        max_pages: Maximum number of pages to crawl.
        limit: Maximum results to return.

    Returns:
        Dict with `results` list of crawled pages.

    Raises:
        RuntimeError: If Tavily is not configured.
    """
    client = _get_client()
    if client is None:
        raise RuntimeError("Tavily client not configured")

    kwargs: dict[str, Any] = {"max_depth": max_depth, "limit": limit}
    try:
        out = client.crawl(url, **kwargs)
    except TypeError:
        out = client.crawl(url)

    if isinstance(out, dict):
        return {"results": out.get("results", []), "url": url}
    if isinstance(out, list):
        return {"results": out, "url": url}
    return {"results": [], "url": url}


def map_url(url: str, *, instructions: str | None = None) -> dict[str, Any]:
    """Map a website's structure using Tavily Map (returns sitemap-like URLs).

    Args:
        url: Website URL to map.
        instructions: Optional natural-language instructions for filtering.

    Returns:
        Dict with `urls` list of discovered page URLs.

    Raises:
        RuntimeError: If Tavily is not configured or Map is not available.
    """
    client = _get_client()
    if client is None:
        raise RuntimeError("Tavily client not configured")

    if not hasattr(client, "map"):
        raise RuntimeError("Tavily Map not available in this SDK version")

    kwargs: dict[str, Any] = {}
    if instructions:
        kwargs["instructions"] = instructions

    try:
        out = client.map(url, **kwargs)
    except TypeError:
        out = client.map(url)

    if isinstance(out, dict):
        return {"urls": out.get("urls", out.get("results", [])), "url": url}
    if isinstance(out, list):
        return {"urls": out, "url": url}
    return {"urls": [], "url": url}
