import os
import sys
import requests

ALCHEMY_API_KEY = os.getenv("ALCHEMY_API_KEY")
WALLET_ADDRESS = "0xAfF992D7921cB5c0b55613d14C2dA6B35f9e3439"

def get_balance(address, network="base-mainnet"):
    """Get ETH balance for a wallet address."""
    url = f"https://{network}.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
    
    # Get native ETH balance
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_getBalance",
        "params": [address, "latest"],
        "id": 1
    }
    
    response = requests.post(url, json=payload)
    result = response.json()
    
    if "result" in result:
        balance_wei = int(result["result"], 16)
        balance_eth = balance_wei / 1e18
        return balance_eth
    else:
        return None

if __name__ == "__main__":
    # Check Base balance
    base_balance = get_balance(WALLET_ADDRESS, "base-mainnet")
    if base_balance:
        print(f"Base (ETH) Balance: {base_balance:.6f} ETH")
    
    # Check Ethereum mainnet balance
    eth_balance = get_balance(WALLET_ADDRESS, "eth-mainnet")
    if eth_balance:
        print(f"Ethereum Mainnet Balance: {eth_balance:.6f} ETH")
