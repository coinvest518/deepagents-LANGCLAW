"""Test and demo script for Composio integration.

This script attempts multiple safe import/initialization patterns for Composio and
exercises a small set of capabilities: listing available tools/connectors and
running a short search if supported.

Run with the workspace venv:
    pip install python-dotenv composio composio-client composio-langchain || true
    python libs/cli/deepagents_cli/built_in_skills/composio/scripts/test_composio.py
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


def _maybe_load_env() -> None:
    if load_dotenv is None:
        return
    # walk up to repo root and load .env
    p = Path(__file__).resolve()
    for parent in [p] + list(p.parents):
        candidate = parent / ".env"
        if candidate.exists():
            load_dotenv(dotenv_path=str(candidate))
            print(f"Loaded .env from {candidate}")
            return


def try_init_composio() -> Any:
    """Try common composio client constructors; return client or None.

    This implementation is purposely simple and avoids deeply nested try/except
    blocks that can confuse some parsers or maintainers.
    """
    import importlib

    candidates = [
        ("composio", "ComposioClient"),
        ("composio", "Client"),
        ("composio_client", "ComposioClient"),
        ("composio_client", "Client"),
    ]

    api_key = os.getenv("COMPOSIO_API_KEY")
    api_url = os.getenv("COMPOSIO_API_URL")
    if api_key is None:
        print("COMPOSIO_API_KEY not set; cannot initialize client")
        return None

    for module_name, ctor_name in candidates:
        try:
            mod = importlib.import_module(module_name)
        except Exception:
            continue

        # Try constructor names
        ctor = getattr(mod, ctor_name, None)
        if callable(ctor):
            # try a few common signatures
            for args in (
                (api_key,),
                (api_key, api_url),
                (),
            ):  # order: key, key+url, no-args
                try:
                    client = ctor(*args)
                    print(
                        f"Initialized composio client via {module_name}.{ctor_name} with args {args}"
                    )
                    return client
                except TypeError:
                    # signature mismatch - try next
                    continue
                except Exception as e:
                    print(
                        f"Client init attempt failed ({module_name}.{ctor_name}): {e}"
                    )
                    break

        # Try factory function
        factory = getattr(mod, "create_client", None) or getattr(
            mod, "from_api_key", None
        )
        if callable(factory):
            try:
                client = factory(api_key=api_key, url=api_url)
                print(
                    f"Initialized composio client via {module_name}.create_client/from_api_key"
                )
                return client
            except Exception as e:
                print(f"Factory init failed ({module_name}): {e}")

    print("No composio client factory found in installed packages.")
    return None


def safe_list_tools(client: Any) -> None:
    """Attempt to list tools/connectors exposed by the client."""
    if client is None:
        print("No client to list tools.")
        return
    # try common method names
    for name in ("list_tools", "tools", "get_tools", "list_connectors"):
        fn = getattr(client, name, None)
        if fn:
            try:
                result = fn() if callable(fn) else fn
                print(f"Tools via {name}: {type(result).__name__}")
                if isinstance(result, (list, tuple)):
                    for t in result[:10]:
                        print(" -", getattr(t, "name", t))
                else:
                    print(result)
                return
            except Exception as e:
                print(f"Listing via {name} failed: {e}")

    print(
        "Could not list tools/connectors from client; inspect `dir(client)` manually."
    )


def safe_search(client: Any, query: str = "latest news about tavily") -> None:
    if client is None:
        print("No client to run search.")
        return
    for method in ("search", "searchonline", "run_search"):
        fn = getattr(client, method, None)
        if callable(fn):
            try:
                print(f"Calling {method}(...)")
                out = (
                    fn(query, max_results=3)
                    if "max_results" in fn.__code__.co_varnames
                    else fn(query)
                )
                print("Search output type:", type(out))
                print(out)
                return
            except Exception as e:
                print(f"{method} failed: {e}")

    print("No compatible search method found on client.")


def main() -> int:
    _maybe_load_env()
    print("COMPOSIO_API_KEY=" + str(bool(os.getenv("COMPOSIO_API_KEY"))))
    client = try_init_composio()
    safe_list_tools(client)
    safe_search(client)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
