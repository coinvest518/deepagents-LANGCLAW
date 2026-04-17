"""
Test that _inject_api_key and http_request work correctly with real credentials.

Loads .env, verifies key injection logic, then makes a real Alchemy call
to check the agent wallet balance on Base mainnet.
"""

import os
import sys
from pathlib import Path

# Load .env from repo root
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

# Add CLI to path so we can import tools directly
sys.path.insert(0, str(Path(__file__).parent.parent / "libs" / "cli"))

from deepagents_cli.tools import _inject_api_key, http_request

KEY = os.environ.get("ALCHEMY_API_KEY", "")
WALLET = os.environ.get("AGENT_WALLET_ADDRESS", "0xAfF992D7921cB5c0b55613d14C2dA6B35f9e3439")
BASE_URL = "https://base-mainnet.g.alchemy.com/v2/"

print("=" * 60)
print("1. KEY INJECTION LOGIC TESTS")
print("=" * 60)

# Case 1: bare /v2/ — agent sends URL with no key
url = "https://base-mainnet.g.alchemy.com/v2/"
result = _inject_api_key(url)
assert result == BASE_URL + KEY, f"FAIL bare /v2/: got {result}"
print(f"  PASS  bare /v2/       -> ...v2/{KEY[:6]}***")

# Case 2: trailing /v2 no slash
url = "https://base-mainnet.g.alchemy.com/v2"
result = _inject_api_key(url)
assert result == BASE_URL + KEY, f"FAIL trailing /v2: got {result}"
print(f"  PASS  trailing /v2    -> ...v2/{KEY[:6]}***")

# Case 3: /v2/demo placeholder
url = "https://base-mainnet.g.alchemy.com/v2/demo"
result = _inject_api_key(url)
assert result == BASE_URL + KEY, f"FAIL demo placeholder: got {result}"
print(f"  PASS  /v2/demo        -> ...v2/{KEY[:6]}***")

# Case 4: already has real key — should not double-inject
url = BASE_URL + KEY
result = _inject_api_key(url)
assert result == BASE_URL + KEY, f"FAIL already-keyed URL: got {result}"
print(f"  PASS  already keyed  -> unchanged")

# Case 5: non-Alchemy URL — untouched
url = "https://api.coingecko.com/api/v3/ping"
result = _inject_api_key(url)
assert result == url, f"FAIL non-alchemy URL: got {result}"
print(f"  PASS  non-alchemy    -> unchanged")

print()
print("=" * 60)
print("2. REAL ALCHEMY CALL — ETH balance on Base mainnet")
print(f"   Wallet: {WALLET}")
print("=" * 60)

resp = http_request(
    url=BASE_URL,   # bare /v2/ — key injected automatically
    method="POST",
    headers={"Content-Type": "application/json"},
    data={
        "jsonrpc": "2.0",
        "method": "eth_getBalance",
        "params": [WALLET, "latest"],
        "id": 1,
    },
)

print(f"  HTTP status : {resp['status_code']}")
print(f"  URL used    : {resp['url']}")

assert resp["status_code"] == 200, f"Expected 200, got {resp['status_code']}: {resp['content']}"

content = resp["content"]
assert "result" in content, f"Missing 'result' in response: {content}"

raw_hex = content["result"]
eth_wei = int(raw_hex, 16)
eth = eth_wei / 1e18
print(f"  Raw hex     : {raw_hex}")
print(f"  Balance     : {eth:.8f} ETH")

assert "error" not in content, f"Alchemy error: {content['error']}"
print()
print("  ALL TESTS PASSED — key injection working, Alchemy responding correctly.")
