"""Firecrawl provider wrapper.

Provides a minimal `search` adapter that prefers the SDK if available
and falls back to the public REST v2 endpoint.
"""
from __future__ import annotations

from typing import Any

import requests

from deepagents_cli.config import settings


def search(query: str, *, max_results: int = 5, site_domain: str | None = None) -> dict[str, Any]:
    fq = f"site:{site_domain} {query}" if site_domain else query

    # Try SDK first
    try:
        import firecrawl as _firecrawl  # type: ignore

        Firecrawl = getattr(_firecrawl, "Firecrawl", None)
        if callable(Firecrawl):
            client = Firecrawl(api_key=getattr(settings, "firecrawl_api_key", None))
            try:
                # name depends on SDK; attempt generic call
                out = client.search(fq, limit=max_results, sources=["web"])
                return out if isinstance(out, dict) else {"results": out, "query": query}
            except Exception:
                pass
    except Exception:
        pass

    # REST fallback
    key = getattr(settings, "firecrawl_api_key", None)
    if not key:
        return {"results": [], "query": query}

    try:
        resp = requests.post(
            "https://api.firecrawl.dev/v2/search",
            headers={"Authorization": f"Bearer {key}"},
            json={"query": fq, "limit": max_results, "sources": ["web"]},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        # normalize to data.web when present
        if isinstance(data, dict):
            payload = data.get("data") or data
            if isinstance(payload, dict) and payload.get("web"):
                return {"results": payload.get("web", []), "query": query}
        return {"results": [], "query": query}
    except Exception:
        return {"results": [], "query": query}
