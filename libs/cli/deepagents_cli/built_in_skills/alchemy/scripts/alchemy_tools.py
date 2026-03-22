"""Alchemy API tools for the AI agent.

All calls use plain requests — no alchemy-sdk required.
API key is read from ALCHEMY_API_KEY environment variable.

Supported networks:
  eth-mainnet, base-mainnet, polygon-mainnet, arb-mainnet, opt-mainnet

Usage:
  python alchemy_tools.py balance <address> [network]
  python alchemy_tools.py tokens <address> [network]
  python alchemy_tools.py price <symbol,...>
  python alchemy_tools.py transfers <address> [network]
  python alchemy_tools.py nfts <address> [network]
  python alchemy_tools.py tx <tx_hash> [network]
  python alchemy_tools.py gas [network]
  python alchemy_tools.py simulate <from> <to> <value_eth> [network]
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

API_KEY = os.environ.get("ALCHEMY_API_KEY", "")

NATIVE_SYMBOL = {
    "eth-mainnet": "ETH",
    "base-mainnet": "ETH",
    "polygon-mainnet": "MATIC",
    "arb-mainnet": "ETH",
    "opt-mainnet": "ETH",
}


def _rpc(network: str, method: str, params: list) -> dict:
    url = f"https://{network}.g.alchemy.com/v2/{API_KEY}"
    payload = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    if "error" in data:
        raise RuntimeError(data["error"])
    return data.get("result")


def _get(url: str, params: dict | None = None) -> dict:
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    req = urllib.request.Request(url, headers={"accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


# ---------------------------------------------------------------------------
# 1. Native balance (ETH / MATIC)
# ---------------------------------------------------------------------------

def get_balance(address: str, network: str = "eth-mainnet") -> dict:
    raw = _rpc(network, "eth_getBalance", [address, "latest"])
    wei = int(raw, 16)
    symbol = NATIVE_SYMBOL.get(network, "ETH")
    return {
        "address": address,
        "network": network,
        "balance_wei": wei,
        "balance": round(wei / 1e18, 6),
        "symbol": symbol,
    }


# ---------------------------------------------------------------------------
# 2. ERC-20 token balances
# ---------------------------------------------------------------------------

def get_token_balances(address: str, network: str = "eth-mainnet") -> list[dict]:
    result = _rpc(network, "alchemy_getTokenBalances", [address, "DEFAULT_TOKENS"])
    balances = []
    for t in result.get("tokenBalances", []):
        raw = t.get("tokenBalance", "0x0")
        if raw and raw != "0x0000000000000000000000000000000000000000000000000000000000000000":
            balances.append({
                "token_address": t["contractAddress"],
                "raw_balance": int(raw, 16),
            })
    return balances


def get_token_metadata(token_address: str, network: str = "eth-mainnet") -> dict:
    return _rpc(network, "alchemy_getTokenMetadata", [token_address])


def get_token_balances_with_metadata(address: str, network: str = "eth-mainnet") -> list[dict]:
    """Returns token balances with symbol, name, decimals and human-readable amount."""
    raw_balances = get_token_balances(address, network)
    results = []
    for b in raw_balances[:20]:  # limit to top 20 to avoid rate limits
        try:
            meta = get_token_metadata(b["token_address"], network)
            decimals = meta.get("decimals") or 18
            amount = round(b["raw_balance"] / (10 ** decimals), 6)
            if amount > 0:
                results.append({
                    "symbol": meta.get("symbol", "?"),
                    "name": meta.get("name", "Unknown"),
                    "balance": amount,
                    "token_address": b["token_address"],
                    "decimals": decimals,
                })
        except Exception:
            pass
    return sorted(results, key=lambda x: x["balance"], reverse=True)


# ---------------------------------------------------------------------------
# 3. Token prices
# ---------------------------------------------------------------------------

def get_prices(symbols: list[str]) -> list[dict]:
    """Get real-time USD prices for token symbols like ETH, BTC, USDC."""
    qs = "&".join(f"symbols={s}" for s in symbols)
    url = f"https://api.g.alchemy.com/prices/v1/{API_KEY}/tokens/by-symbol?{qs}"
    data = _get(url)
    results = []
    for item in data.get("data", []):
        prices = item.get("prices", [])
        usd = next((p["value"] for p in prices if p["currency"] == "usd"), None)
        results.append({
            "symbol": item.get("symbol"),
            "price_usd": float(usd) if usd else None,
            "currency": "usd",
        })
    return results


# ---------------------------------------------------------------------------
# 4. Asset transfer history
# ---------------------------------------------------------------------------

def get_transfers(address: str, network: str = "eth-mainnet",
                  direction: str = "both", limit: int = 10) -> list[dict]:
    """Get recent transfers. direction: 'from', 'to', or 'both'."""
    categories = ["external", "erc20", "erc721", "erc1155"]
    params: dict = {"category": categories, "maxCount": hex(limit), "withMetadata": True}
    transfers = []
    if direction in ("from", "both"):
        params_from = {**params, "fromAddress": address}
        r = _rpc(network, "alchemy_getAssetTransfers", [params_from])
        transfers.extend(r.get("transfers", []))
    if direction in ("to", "both"):
        params_to = {**params, "toAddress": address}
        r = _rpc(network, "alchemy_getAssetTransfers", [params_to])
        transfers.extend(r.get("transfers", []))
    # Sort by block descending, deduplicate
    seen = set()
    result = []
    for t in sorted(transfers, key=lambda x: x.get("blockNum", "0x0"), reverse=True):
        key = t.get("hash", "")
        if key not in seen:
            seen.add(key)
            result.append({
                "hash": t.get("hash"),
                "from": t.get("from"),
                "to": t.get("to"),
                "value": t.get("value"),
                "asset": t.get("asset"),
                "category": t.get("category"),
                "block": int(t.get("blockNum", "0x0"), 16),
            })
    return result[:limit]


# ---------------------------------------------------------------------------
# 5. NFTs
# ---------------------------------------------------------------------------

def get_nfts(address: str, network: str = "eth-mainnet") -> dict:
    url = f"https://{network}.g.alchemy.com/nft/v3/{API_KEY}/getNFTsForOwner"
    data = _get(url, {"owner": address, "pageSize": "20", "withMetadata": "true"})
    nfts = []
    for n in data.get("ownedNfts", []):
        nfts.append({
            "name": n.get("name") or n.get("contract", {}).get("name", "Unknown"),
            "collection": n.get("contract", {}).get("name"),
            "token_id": n.get("tokenId"),
            "contract": n.get("contract", {}).get("address"),
        })
    return {"total": data.get("totalCount", 0), "nfts": nfts}


# ---------------------------------------------------------------------------
# 6. Transaction lookup
# ---------------------------------------------------------------------------

def get_transaction(tx_hash: str, network: str = "eth-mainnet") -> dict:
    tx = _rpc(network, "eth_getTransactionByHash", [tx_hash])
    if not tx:
        return {"error": "Transaction not found"}
    return {
        "hash": tx.get("hash"),
        "from": tx.get("from"),
        "to": tx.get("to"),
        "value_eth": round(int(tx.get("value", "0x0"), 16) / 1e18, 8),
        "block": int(tx.get("blockNumber", "0x0"), 16),
        "gas_price_gwei": round(int(tx.get("gasPrice", "0x0"), 16) / 1e9, 2),
    }


# ---------------------------------------------------------------------------
# 7. Gas prices
# ---------------------------------------------------------------------------

def get_gas(network: str = "eth-mainnet") -> dict:
    gas_hex = _rpc(network, "eth_gasPrice", [])
    gwei = int(gas_hex, 16) / 1e9
    block = _rpc(network, "eth_getBlockByNumber", ["latest", False])
    base_fee_gwei = int(block.get("baseFeePerGas", "0x0"), 16) / 1e9 if block else None
    return {
        "network": network,
        "gas_price_gwei": round(gwei, 2),
        "base_fee_gwei": round(base_fee_gwei, 2) if base_fee_gwei else None,
        "estimated_priority_fee_gwei": 1.0,
    }


# ---------------------------------------------------------------------------
# 8. Simulate transaction
# ---------------------------------------------------------------------------

def simulate_transaction(from_addr: str, to_addr: str,
                         value_eth: float = 0,
                         data: str = "0x",
                         network: str = "eth-mainnet") -> dict:
    """Preview asset changes before sending a transaction."""
    value_hex = hex(int(value_eth * 1e18))
    params = {"from": from_addr, "to": to_addr, "value": value_hex, "data": data}
    result = _rpc(network, "alchemy_simulateAssetChanges", [params])
    changes = []
    for c in result.get("changes", []):
        changes.append({
            "address": c.get("to"),
            "asset_type": c.get("assetType"),
            "symbol": c.get("symbol"),
            "amount": c.get("amount"),
            "change_type": c.get("changeType"),
        })
    return {"changes": changes, "error": result.get("error")}


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def _print(data: object) -> None:
    print(json.dumps(data, indent=2, default=str))


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    cmd = args[0]

    if cmd == "balance":
        addr = args[1]
        net = args[2] if len(args) > 2 else "eth-mainnet"
        _print(get_balance(addr, net))

    elif cmd == "tokens":
        addr = args[1]
        net = args[2] if len(args) > 2 else "eth-mainnet"
        _print(get_token_balances_with_metadata(addr, net))

    elif cmd == "price":
        symbols = args[1].split(",")
        _print(get_prices(symbols))

    elif cmd == "transfers":
        addr = args[1]
        net = args[2] if len(args) > 2 else "eth-mainnet"
        _print(get_transfers(addr, net))

    elif cmd == "nfts":
        addr = args[1]
        net = args[2] if len(args) > 2 else "eth-mainnet"
        _print(get_nfts(addr, net))

    elif cmd == "tx":
        tx_hash = args[1]
        net = args[2] if len(args) > 2 else "eth-mainnet"
        _print(get_transaction(tx_hash, net))

    elif cmd == "gas":
        net = args[1] if len(args) > 1 else "eth-mainnet"
        _print(get_gas(net))

    elif cmd == "simulate":
        from_addr, to_addr = args[1], args[2]
        value = float(args[3]) if len(args) > 3 else 0
        net = args[4] if len(args) > 4 else "eth-mainnet"
        _print(simulate_transaction(from_addr, to_addr, value, network=net))

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)
