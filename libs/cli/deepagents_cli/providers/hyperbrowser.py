"""HyperBrowser provider wrapper.

Provides a simple scrape/search wrapper that returns a normalized single
result where possible. Uses SDK `start_and_wait` when available and
falls back to REST endpoints.
"""
from __future__ import annotations

import time
from typing import Any

import requests

from deepagents_cli.config import settings


def search_site(site_domain: str, *, query: str | None = None, max_results: int = 5) -> dict[str, Any]:
    key = getattr(settings, "hyperbrowser_api_key", None)
    if not key:
        return {"results": [], "query": query or ""}

    # Try SDK
    try:
        from hyperbrowser import Hyperbrowser  # type: ignore
        from hyperbrowser.models.scrape import StartScrapeJobParams  # type: ignore

        c = Hyperbrowser(api_key=key)
        params = StartScrapeJobParams(url=f"https://{site_domain}")
        resp = c.scrape.start_and_wait(params)
        # resp may be a model or dict; try to extract markdown/html
        data = getattr(resp, "data", None) or (resp if isinstance(resp, dict) else None)
        content = ""
        url = f"https://{site_domain}"
        if isinstance(data, dict):
            content = data.get("markdown") or data.get("html") or ""
            url = data.get("url") or url
        else:
            url = getattr(data, "url", url)
            content = getattr(data, "markdown", None) or getattr(data, "html", "")

        return {"results": [{"title": url, "url": url, "content": content, "score": 1.0, "raw": resp}], "query": query or ""}
    except Exception:
        pass

    # REST fallback: create session (optional) then POST /api/scrape
    try:
        session_id = None
        try:
            sess = requests.post(
                "https://api.hyperbrowser.ai/api/session",
                headers={"x-api-key": key, "Content-Type": "application/json"},
                json={"useStealth": True},
                timeout=15,
            )
            sess.raise_for_status()
            sd = sess.json()
            session_id = sd.get("id") or sd.get("session", {}).get("id")
        except Exception:
            session_id = None

        payload = {"url": f"https://{site_domain}", "prompt": query or "", "limit": max_results}
        if session_id:
            payload["sessionId"] = session_id

        resp = requests.post(
            "https://api.hyperbrowser.ai/api/scrape",
            headers={"x-api-key": key, "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        # If returned jobId, poll status until complete then fetch result
        if isinstance(data, dict) and data.get("jobId"):
            job_id = data.get("jobId")
            status_url = f"https://api.hyperbrowser.ai/api/scrape/{job_id}/status"
            get_url = f"https://api.hyperbrowser.ai/api/scrape/{job_id}"
            start_t = time.time()
            timeout_total = 120
            sleep_sec = 1
            final_data = None
            while time.time() - start_t < timeout_total:
                try:
                    st = requests.get(status_url, headers={"x-api-key": key}, timeout=10)
                    st.raise_for_status()
                    stj = st.json()
                    status = stj.get("status")
                    if status == "completed":
                        g = requests.get(get_url, headers={"x-api-key": key}, timeout=30)
                        g.raise_for_status()
                        final_data = g.json()
                        break
                    if status in {"failed", "error"}:
                        final_data = stj
                        break
                except Exception:
                    # transient error; continue polling until timeout
                    pass
                time.sleep(sleep_sec)
                sleep_sec = min(sleep_sec * 2, 10)

            if final_data and isinstance(final_data, dict):
                # Normalize final_data if it contains `data` or markdown
                if final_data.get("data"):
                    d = final_data.get("data")
                    # batch vs single
                    if isinstance(d, list):
                        results = []
                        for item in d[:max_results]:
                            content = item.get("markdown") or item.get("html") or ""
                            url = item.get("url") or item.get("sourceURL") or item.get("metadata", {}).get("url") or f"https://{site_domain}"
                            results.append({"title": item.get("metadata", {}).get("title") or url, "url": url, "content": content, "score": 1.0, "raw": item})
                        return {"results": results, "query": query or ""}
                    content = d.get("markdown") or d.get("html") or ""
                    url = d.get("url") or d.get("sourceURL") or d.get("metadata", {}).get("url") or f"https://{site_domain}"
                    return {"results": [{"title": d.get("metadata", {}).get("title") or url, "url": url, "content": content, "score": 1.0, "raw": final_data}], "query": query or ""}

            # If we couldn't fetch final result, return job info for caller to handle
            return {"results": [], "raw": data, "query": query or ""}

        # Normalize if possible when response contains data directly
        if isinstance(data, dict) and data.get("data"):
            d = data.get("data")
            content = d.get("markdown") or d.get("html") or ""
            url = d.get("url") or f"https://{site_domain}"
            return {"results": [{"title": url, "url": url, "content": content, "score": 1.0, "raw": data}], "query": query or ""}

        return {"results": [], "query": query or ""}
    except Exception:
        return {"results": [], "query": query or ""}
