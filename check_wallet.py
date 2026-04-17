import os
import requests

ALCHEMY_API_KEY = os.getenv("ALCHEMY_API_KEY")
WALLET_ADDRESS = "0xAfF992D7921cB5c0b55613d14C2dA6B35f9e3439"

def get_balance(address, network="base-mainnet"):
    """Get native token balance for an address."""
    url = f"https://{network}.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_getBalance",
        "params": [address, "latest"],
        "id": 1
    }
    response = requests.post(url, json=payload)
    data = response.json()
    if "result" in data:
        balance_wei = int(data["result"], 16)
        balance_eth = balance_wei / 1e18
        return balance_eth
    return None

def get_token_balances(address, network="base-mainnet"):
    """Get all ERC-20 token balances."""
    url = f"https://{network}.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
    payload = {
        "jsonrpc": "2.0",
        "method": "alchemy_getTokenBalances",
        "params": [address],
        "id": 1
    }
    response = requests.post(url, json=payload)
    data = response.json()
    return data.get("result", {})

if __name__ == "__main__":
    print(f"Checking wallet: {WALLET_ADDRESS}")
    print("\n--- Native Balance (ETH) ---")
    eth_balance = get_balance(WALLET_ADDRESS, "base-mainnet")
    if eth_balance:
        print(f"Base (ETH): {eth_balance:.6f} ETH")
    
    print("\n--- Token Balances ---")
    tokens = get_token_balances(WALLET_ADDRESS, "base-mainnet")
    if tokens and "tokenBalances" in tokens:
        for token in tokens["tokenBalances"]:
            if token.get("tokenBalance", "0") != "0":
                symbol = token.get("symbol", "UNKNOWN")
                balance = token.get("tokenBalance", "0")
                decimals = token.get("decimals", 18)
                if decimals and balance:
                    formatted_balance = int(balance) / (10 ** int(decimals))
                    print(f"{symbol}: {formatted_balance:.6f}")
    else:
        print("No token balances found or error occurred.")
