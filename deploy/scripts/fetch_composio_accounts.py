"""
Fetch all active Composio connected accounts and print env var lines.
Run: python deploy/scripts/fetch_composio_accounts.py
Then copy the output into your .env and Render env vars.
"""
import os, sys, json
from pathlib import Path

# Load .env
env_file = Path(__file__).parent.parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

api_key = os.environ.get("COMPOSIO_API_KEY", "")
if not api_key:
    print("ERROR: COMPOSIO_API_KEY not set")
    sys.exit(1)

try:
    from composio import Composio
    client = Composio(api_key=api_key)
    accounts = client.connected_accounts.list()
    items = accounts.items or []
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)

print("\n# === Active Composio account IDs ===")
print("# Add these to your .env and Render environment variables\n")

active = {}
for a in items:
    slug = getattr(a.toolkit, "slug", "unknown")
    status = a.data.get("status", "?")
    if status == "ACTIVE":
        key = f"COMPOSIO_{slug.upper().replace('-','_')}_ACCOUNT_ID"
        val = a.id
        active[slug] = {"key": key, "id": val}
        print(f"{key}={val}")

print(f"\n# Total active: {len(active)}")
print("\n# All accounts (including inactive):")
for a in items:
    slug = getattr(a.toolkit, "slug", "?")
    status = a.data.get("status", "?")
    print(f"#   {slug}: {status} (id={a.id})")

# Save to a json file for use by other scripts
out = Path(__file__).parent / "composio_accounts.json"
out.write_text(json.dumps(active, indent=2))
print(f"\n# Saved to {out}")
