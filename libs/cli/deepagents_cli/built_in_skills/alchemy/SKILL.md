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

## How to Use — http_request tool ONLY

**IMPORTANT: No script execution. Use `http_request` for ALL Alchemy calls.**

**KEY INJECTION IS AUTOMATIC** — use the bare `/v2/` URL with NO key. The server injects the real key before the request goes out. Never put a key or placeholder in the URL yourself.

Base URL pattern: `https://{network}.g.alchemy.com/v2/`  ← use exactly this, no key appended

### Check native balance (ETH/MATIC)

```
http_request(
  method="POST",
  url="https://base-mainnet.g.alchemy.com/v2/",
  body={"jsonrpc":"2.0","method":"eth_getBalance","params":["0xAddress","latest"],"id":1}
)
```
Convert result hex → decimal ÷ 1e18 to get ETH amount.

### Get all ERC-20 token balances

```
http_request(
  method="POST",
  url="https://base-mainnet.g.alchemy.com/v2/",
  body={"jsonrpc":"2.0","method":"alchemy_getTokenBalances","params":["0xAddress","erc20"],"id":1}
)
```
For each token with non-zero balance, call `alchemy_getTokenMetadata` to get symbol/decimals.

### Get token metadata (symbol, decimals)

```
http_request(
  method="POST",
  url="https://eth-mainnet.g.alchemy.com/v2/",
  body={"jsonrpc":"2.0","method":"alchemy_getTokenMetadata","params":["0xTokenContractAddress"],"id":1}
)
```

### Get real-time prices (ETH, BTC, USDC, etc.)

```
http_request(
  method="GET",
  url="https://api.g.alchemy.com/prices/v1/tokens/by-symbol?symbols=ETH,BTC,USDC"
)
```
Note: The prices API uses a different base (`api.g.alchemy.com/prices/v1/`) — key is also auto-injected.

### Get transfer history

```
http_request(
  method="POST",
  url="https://eth-mainnet.g.alchemy.com/v2/",
  body={"jsonrpc":"2.0","method":"alchemy_getAssetTransfers","params":[{"fromAddress":"0xAddress","category":["external","erc20","erc721"],"withMetadata":true,"maxCount":"0x14"}],"id":1}
)
```

### Get current gas price

```
http_request(
  method="POST",
  url="https://eth-mainnet.g.alchemy.com/v2/",
  body={"jsonrpc":"2.0","method":"eth_gasPrice","params":[],"id":1}
)
```
Convert hex result ÷ 1e9 for Gwei.

### Get NFTs owned by address

```
http_request(
  method="GET",
  url="https://eth-mainnet.g.alchemy.com/nft/v3/getNFTsForOwner?owner=0xAddress&withMetadata=true&pageSize=10"
)
```

## Agent's Own Wallet

```
Address: 0xAfF992D7921cB5c0b55613d14C2dA6B35f9e3439
Private key: AGENT_WALLET_PRIVATE_KEY (env var — never print this)
Networks: Base mainnet, Ethereum mainnet
```

To check the agent's own balance on Base:
```
http_request(
  method="POST",
  url="https://base-mainnet.g.alchemy.com/v2/",
  body={"jsonrpc":"2.0","method":"eth_getBalance","params":["0xAfF992D7921cB5c0b55613d14C2dA6B35f9e3439","latest"],"id":1}
)
```

## What the Agent CANNOT Do via Alchemy (yet)

- **Send transactions** — Alchemy is read-only. Signing requires eth_account + AGENT_WALLET_PRIVATE_KEY.
- **Swap tokens** — Use DEX aggregators (1inch, Uniswap). Alchemy can *simulate* the tx outcome first.
- **Get private key / seed phrase** — Never print AGENT_WALLET_PRIVATE_KEY.

## Wallet Check Protocol

When user asks "check wallet balance" or "check my wallet":
1. **Do NOT ask for an address** — use the agent wallet from Runtime Configuration
2. Check ETH balance on ALL 5 networks in parallel (eth-mainnet, base-mainnet, polygon-mainnet, arb-mainnet, opt-mainnet)
3. Check ERC-20 token balances on each network
4. Check NFTs
5. Get current prices for any tokens found
6. Report everything — do NOT stop after one network and ask "would you like me to check more?"
