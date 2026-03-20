import sys
import types


def test_firecrawl_sdk_path(monkeypatch):
    # Create a fake `firecrawl` package with expected attributes
    mod = types.ModuleType("firecrawl")

    class FakeClient:
        def __init__(self, api_key=None):
            pass

        def search(self, q, limit=None, sources=None):
            return [
                {
                    "title": "SDK Title",
                    "url": "https://example.com/page",
                    "content": "sdk content",
                }
            ]

    mod.Firecrawl = FakeClient

    monkeypatch.setitem(sys.modules, "firecrawl", mod)

    from deepagents_cli.providers import firecrawl as fc

    res = fc.search("test", max_results=1, site_domain="example.com")
    assert isinstance(res, dict)
    assert res.get("results")
    assert any("sdk content" in (r.get("content") or "") for r in res["results"])


def test_firecrawl_rest_fallback(monkeypatch):
    # Ensure SDK is not available so provider uses REST path
    monkeypatch.setitem(sys.modules, "firecrawl", types.ModuleType("firecrawl"))

    import deepagents_cli.providers.firecrawl as fcmod

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
        # return a payload shaped like the Firecrawl REST v2 response
        return FakeResp(
            {
                "data": {
                    "web": [
                        {
                            "title": "REST Title",
                            "url": "https://rest.example",
                            "content": "rest content",
                        }
                    ]
                }
            }
        )

    monkeypatch.setattr(fcmod, "requests", fcmod.requests)
    monkeypatch.setattr(fcmod.requests, "post", fake_post)

    res = fcmod.search("query", max_results=2, site_domain="rest.example")
    assert res.get("results")
    assert any("rest content" in (r.get("content") or "") for r in res["results"])


def test_firecrawl_scrape_wrapper(monkeypatch):
    # Patch provider search to return a simple result and verify tools wrapper
    from deepagents_cli.providers import firecrawl as fc
    from deepagents_cli.tools import firecrawl_scrape

    monkeypatch.setattr(
        fc,
        "search",
        lambda q, max_results=5, site_domain=None: {
            "results": [{"title": "T", "url": "https://a", "content": "c"}]
        },
    )

    out = firecrawl_scrape("example.com", query="q", max_results=1)
    assert out.get("results")
    assert out["results"][0]["score"] >= 0
