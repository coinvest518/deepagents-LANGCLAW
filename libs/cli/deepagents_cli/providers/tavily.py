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
    site_domain: str | None = None,
    session_params: dict | None = None,
    crawl_params: dict | None = None,
) -> Any:
    """Run a Tavily search and return the raw provider response.

    Raises RuntimeError if Tavily is not configured/available.
    """
    client = _get_client()
    if client is None:
        raise RuntimeError("Tavily client not configured")

    tav_query = query
    kwargs: dict[str, Any] = {
        "max_results": max_results,
        "include_raw_content": include_raw_content,
        "topic": topic,
    }
    if site_domain:
        # prefer domain-limited search, but if that returns empty,
        # attempt page extraction or crawl for the site homepage
        kwargs["include_domains"] = [site_domain]

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
