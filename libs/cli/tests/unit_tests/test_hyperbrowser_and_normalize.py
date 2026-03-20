import sys
import types

import pytest


def test_hyperbrowser_sdk_path(monkeypatch):
    # Create a fake `hyperbrowser` package with expected attributes
    mod = types.ModuleType("hyperbrowser")

    class FakeScrapeResp:
        def __init__(self, data):
            self.data = data

        def __repr__(self):
            return f"FakeScrapeResp({self.data!r})"

    class FakeSDK:
        def __init__(self, api_key=None):
            class Scraper:
                @staticmethod
                def start_and_wait(params):
                    return FakeScrapeResp(
                        {
                            "markdown": "sdk markdown",
                            "metadata": {
                                "title": "SDK Title",
                                "url": "https://example.com",
                            },
                        }
                    )

            self.scrape = Scraper()

    mod.Hyperbrowser = FakeSDK

    sub = types.ModuleType("hyperbrowser.models.scrape")

    class StartScrapeJobParams:
        def __init__(self, url=None):
            self.url = url

    sub.StartScrapeJobParams = StartScrapeJobParams

    monkeypatch.setitem(sys.modules, "hyperbrowser", mod)
    monkeypatch.setitem(sys.modules, "hyperbrowser.models.scrape", sub)

    from deepagents_cli.providers import hyperbrowser as hb_provider

    res = hb_provider.search_site("example.com", query="sdk-test", max_results=1)
    assert isinstance(res, dict)
    assert res.get("results")
    assert "sdk markdown" in res["results"][0]["content"]


def test_hyperbrowser_rest_polling(monkeypatch):
    # Ensure any real hyperbrowser SDK is removed so provider uses REST path
    import importlib
    import sys
    import types

    # Ensure importing `hyperbrowser` inside the provider will fail to provide
    # the `Hyperbrowser` class so the provider takes the REST fallback path.
    monkeypatch.setitem(sys.modules, "hyperbrowser", types.ModuleType("hyperbrowser"))
    monkeypatch.setitem(sys.modules, "hyperbrowser.models.scrape", types.ModuleType("hyperbrowser.models.scrape"))

    # Patch requests used inside the provider to simulate job polling
    import deepagents_cli.providers.hyperbrowser as hbmod
    importlib.reload(hbmod)

    class FakeResp:
        def __init__(self, json_data, status=200):
            self._json = json_data
            self.status_code = status

        def raise_for_status(self):
            if self.status_code >= 400:
                raise Exception("status")

        def json(self):
            return self._json

    def fake_post(url, headers=None, json=None, timeout=None):
        if url.endswith("/api/session"):
            return FakeResp({"id": "sess1"})
        return FakeResp({"jobId": "jid"})

    def fake_get(url, headers=None, timeout=None):
        if url.endswith("/status"):
            return FakeResp({"status": "completed"})
        return FakeResp(
            {
                "jobId": "jid",
                "status": "completed",
                "data": {
                    "markdown": "rest markdown",
                    "metadata": {
                        "title": "REST Title",
                        "url": "https://consumerai.info",
                    },
                },
            }
        )

    monkeypatch.setattr(hbmod, "requests", hbmod.requests)
    monkeypatch.setattr(hbmod.requests, "post", fake_post)
    monkeypatch.setattr(hbmod.requests, "get", fake_get)

    res = hbmod.search_site("consumerai.info", query="rest-test", max_results=2)
    assert res.get("results")
    assert "rest markdown" in res["results"][0]["content"]


def test_normalize_and_score_results():
    from deepagents_cli.tools import normalize_and_score_results

    raw = {
        "results": [
            {"title": "T", "url": "https://consumerai.info/page", "content": "x" * 300}
        ]
    }
    out = normalize_and_score_results(
        raw, query="q", site_domain="consumerai.info", max_results=5
    )
    assert out["results"]
    assert out["results"][0]["score"] > 0
