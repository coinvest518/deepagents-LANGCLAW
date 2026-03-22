---
name: alchemy
description: >
  Blockchain data and wallet intelligence via Alchemy API. Use this skill
  when the user asks about: wallet balances (ETH, tokens, NFTs), token prices,
  transaction history, gas fees, or simulating a transaction. Supports
  Ethereum, Base, Polygon, Arbitrum, and Optimism. API key is in ALCHEMY_API_KEY
  env var (confirmed working). No extra packages needed — uses requests only.
  Trigger phrases: "check my wallet", "check agent wallet", "what's the price of",
  "my token balances", "transaction history", "gas price", "simulate a tx", "how many NFTs".
  Agent wallet address: 0xAfF992D7921cB5c0b55613d14C2dA6B35f9e3439 (Base/ETH, key in AGENT_WALLET_PRIVATE_KEY env).
license: MIT
compatibility: deepagents-cli
---

# Alchemy Skill

Alchemy provides read access to all major EVM chains plus real-time prices.
The agent's API key is in `ALCHEMY_API_KEY`. No SDK install needed.

## Confirmed Working APIs (all tested live)

| API | What it does |
|-----|-------------|
| `eth_getBalance` | Native token balance (ETH, MATIC) |
| `alchemy_getTokenBalances` | All ERC-20 balances for a wallet |
| `alchemy_getTokenMetadata` | Symbol, name, decimals for any token |
| Prices API | Real-time USD price for ETH, BTC, USDC, any symbol |
| `alchemy_getAssetTransfers` | Full transfer history (ETH + tokens + NFTs) |
| NFT API v3 | All NFTs owned by an address |
| `eth_getTransactionByHash` | Transaction details |
| `alchemy_simulateAssetChanges` | Preview tx outcome before sending |
| `eth_gasPrice` | Current gas prices in Gwei |

## Supported Networks

```
eth-mainnet      (Ethereum)
base-mainnet     (Base / Coinbase L2)
polygon-mainnet  (Polygon)
arb-mainnet      (Arbitrum)
opt-mainnet      (Optimism)
```

## How to Use — Run the Script

The bundled script `scripts/alchemy_tools.py` handles everything.
Always use `python scripts/alchemy_tools.py <cmd> <args>` from this skill's directory.

### Check wallet balance
```bash
python scripts/alchemy_tools.py balance 0xYourAddress eth-mainnet
python scripts/alchemy_tools.py balance 0xYourAddress base-mainnet
```

### Get all token balances (with names + amounts)
```bash
python scripts/alchemy_tools.py tokens 0xYourAddress eth-mainnet
```

### Get real-time prices
```bash
python scripts/alchemy_tools.py price ETH,BTC,USDC
python scripts/alchemy_tools.py price ETH,MATIC,LINK,UNI
```

### Get transfer history
```bash
python scripts/alchemy_tools.py transfers 0xYourAddress eth-mainnet
```

### Get NFTs
```bash
python scripts/alchemy_tools.py nfts 0xYourAddress eth-mainnet
```

### Get gas prices
```bash
python scripts/alchemy_tools.py gas eth-mainnet
python scripts/alchemy_tools.py gas base-mainnet
```

### Look up a transaction
```bash
python scripts/alchemy_tools.py tx 0xTransactionHash eth-mainnet
```

### Simulate a transaction (preview before sending)
```bash
python scripts/alchemy_tools.py simulate 0xFromAddress 0xToAddress 0.01 eth-mainnet
```

## Direct Python (for inline use)

```python
import os, sys
sys.path.insert(0, "path/to/alchemy/scripts")
import alchemy_tools as alchemy

# Prices
prices = alchemy.get_prices(["ETH", "BTC"])
# → [{"symbol": "ETH", "price_usd": 2087.94}, ...]

# Balance
bal = alchemy.get_balance("0xYourAddress", "eth-mainnet")
# → {"balance": 1.234, "symbol": "ETH"}

# Token balances
tokens = alchemy.get_token_balances_with_metadata("0xYourAddress", "base-mainnet")
# → [{"symbol": "USDC", "balance": 500.0}, ...]
```

## Agent's Own Wallet

The agent has a dedicated wallet for transacting on Base and Ethereum:

```
Address: 0xAfF992D7921cB5c0b55613d14C2dA6B35f9e3439
Private key: AGENT_WALLET_PRIVATE_KEY (env var — never print this)
Networks: Base mainnet, Base Sepolia testnet, Ethereum mainnet
```

To check the agent's own balance:
```bash
python scripts/alchemy_tools.py balance 0xAfF992D7921cB5c0b55613d14C2dA6B35f9e3439 base-mainnet
python scripts/alchemy_tools.py balance 0xAfF992D7921cB5c0b55613d14C2dA6B35f9e3439 base-sepolia
```

To get test ETH for the agent: https://www.alchemy.com/faucets/base-sepolia

## What the Agent CANNOT Do via Alchemy (yet)

- **Send transactions** — Alchemy is read-only. Signing requires eth_account + AGENT_WALLET_PRIVATE_KEY.
- **Swap tokens** — Use DEX aggregators (1inch, Uniswap). Alchemy can *simulate* the tx outcome first.
- **Get private key / seed phrase** — Never print AGENT_WALLET_PRIVATE_KEY.

## Tips

- If user asks "check my wallet balance" → ask for their address first, then run `balance` + `tokens`
- For prices use symbols (ETH, not ethereum): `price ETH,BTC,USDC`
- For multi-chain check: run `balance` on each network the user cares about
- Simulate before any real transaction to show the user what will change
