"""Verify available LangChain providers and credential presence.

This script prints a JSON map of discovered providers -> models and then
prints credential availability for a shortlist of providers you mentioned.

Safe: does not transmit keys.
"""

import json

from deepagents_cli.model_config import get_available_models, has_provider_credentials

try:
    available = get_available_models()
    print(json.dumps(available, indent=2))
except Exception as e:
    print("ERROR: failed to get_available_models:", e)

for p in (
    "mistralai",
    "openrouter",
    "nvidia",
    "huggingface",
    "cerebras",
    "apify",
    "composio",
    "hyperbrowser",
    "firecrawl",
):
    try:
        cred = has_provider_credentials(p)
    except Exception as e:
        cred = f"error: {e}"
    print(f"{p}: {cred}")
