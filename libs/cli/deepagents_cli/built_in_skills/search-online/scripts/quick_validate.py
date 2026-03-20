"""Quick validation script for search-online providers.

Checks for environment keys and attempts to import common provider clients.
Run locally to confirm the running Python environment can access keys and packages.
"""

from __future__ import annotations

import os
from pathlib import Path

# Optional dotenv loading: will be used if python-dotenv is installed.
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None  # type: ignore


def _maybe_load_dotenv() -> None:
    """Load `.env` file into the process environment if python-dotenv is available."""
    if load_dotenv is None:
        return
    # Walk upward from this script location and load the first `.env` found.
    script_path = Path(__file__).resolve()
    for parent in [script_path] + list(script_path.parents):
        candidate = parent / ".env"
        if candidate.exists():
            load_dotenv(dotenv_path=str(candidate))
            print(f"Loaded .env from {candidate}")
            return


def check_env() -> list[str]:
    keys = [
        ("COMPOSIO_API_KEY", os.getenv("COMPOSIO_API_KEY")),
        ("COMPOSIO_API_URL", os.getenv("COMPOSIO_API_URL")),
        ("HYPERBROWSER_API_KEY", os.getenv("HYPERBROWSER_API_KEY")),
        ("FIRECRAWL_API_KEY", os.getenv("FIRECRAWL_API_KEY")),
    ]
    missing = [k for k, v in keys if not v]
    found = [k for k, v in keys if v]
    print("Environment: found=", found)
    if missing:
        print("Environment: missing=", missing)
    return missing


def try_import(name: str) -> bool:
    try:
        __import__(name)
        print(f"Import OK: {name}")
        return True
    except Exception:
        print(f"Import FAIL: {name}")
        return False


def main() -> int:
    print("Validating search-online providers")
    _maybe_load_dotenv()
    missing_env = check_env()

    imports = [
        ("composio", "composio"),
        ("composio-langchain", "composio"),
        ("langchain_hyperbrowser", "langchain_hyperbrowser"),
        ("firecrawl", "firecrawl"),
    ]
    results = {}
    for label, module in imports:
        results[label] = try_import(module)

    ok = any(results.values()) and not (
        "COMPOSIO_API_KEY" in missing_env
        and "HYPERBROWSER_API_KEY" in missing_env
        and "FIRECRAWL_API_KEY" in missing_env
    )
    print("Summary:", results)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
