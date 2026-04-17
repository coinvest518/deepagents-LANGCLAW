import json
from unittest.mock import patch, MagicMock

from deepagents_cli import composio_dispatcher


def make_resp(status=200, body=None):
    m = MagicMock()
    m.status_code = status
    if body is None:
        body = {"ok": True, "data": {"hello": "world"}}
    m.json.return_value = body
    m.text = json.dumps(body)
    return m


def test_dispatch_success():
    import os
    os.environ["COMPOSIO_API_KEY"] = "x"
    os.environ["COMPOSIO_API_URL"] = "https://api.example"
    with patch("deepagents_cli.composio_dispatcher.requests.post") as p:
        p.return_value = make_resp(200, {"result": {"files": []}})
        res = composio_dispatcher.dispatch("GOOGLEDRIVE_LIST_FILES", {})
        assert res["success"] is True
        assert "result" in res


def test_composio_action_wrapper_success():
    import os
    os.environ["COMPOSIO_API_KEY"] = "x"
    os.environ["COMPOSIO_API_URL"] = "https://api.example"
    with patch("deepagents_cli.composio_dispatcher.requests.post") as p:
        p.return_value = make_resp(200, {"files": []})
        res = composio_dispatcher.dispatch("GOOGLEDRIVE_LIST_FILES", {})
        assert res["success"] is True
        # wrapper readability: ensure dispatch returns parseable result
        assert isinstance(res.get("result"), dict) or isinstance(res.get("result"), list)


def test_dispatch_error_propagates():
    with patch("deepagents_cli.composio_dispatcher.requests.post") as p:
        p.return_value = make_resp(500, {"error": "server"})
        res = composio_dispatcher.dispatch("GMAIL_SEND_EMAIL", {"to": "a@b"})
        assert res["success"] is False
        assert "error" in res
