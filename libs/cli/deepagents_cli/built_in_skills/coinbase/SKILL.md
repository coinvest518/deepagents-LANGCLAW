---
name: coinbase
description: >
  Coinbase and CDP (Coinbase Developer Platform) data. Use this skill for:
  top cryptocurrencies by market cap or volume, real-time crypto prices,
  Coinbase exchange trading pairs, portfolio data, CDP wallet operations,
  and market overview. No SDK needed — uses http_request only.
  Trigger phrases: "top coins", "top tokens", "crypto prices", "market cap",
  "coinbase prices", "CDP", "what's bitcoin at", "best performing crypto".
  CDP keys: CDP_API_KEY_ID, CDP_API_KEY_SECRET, CDP_NETWORK_ID (base-sepolia) in env.
license: MIT
compatibility: deepagents-cli
---

# Coinbase / CDP Skill

Access crypto market data via Coinbase public APIs and CoinGecko. No API key needed for market data.
CDP wallet operations use keys from env (auto-injected — never ask the user for them).

## Available APIs

| API | Key needed | What it does |
|-----|-----------|-------------|
| Coinbase Prices | No | Spot price for any pair (BTC-USD, ETH-USD, etc.) |
| Coinbase Exchange Products | No | All trading pairs, volumes, 24h stats |
| CoinGecko Markets | No | Top N coins by market cap with full stats |
| CoinGecko Trending | No | Trending coins in last 24h |
| CDP REST API | Yes (auto-injected) | Wallet creation, transfers, on-chain ops |

## How to Use — http_request only

### Top 10 coins by market cap (most useful for "top coins today")

```
http_request(
  method="GET",
  url="https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=10&page=1&sparkline=false&price_change_percentage=24h"
)
```
Returns: name, symbol, current_price, market_cap, 24h volume, price_change_percentage_24h

### Spot price for a single pair

```
http_request(
  method="GET",
  url="https://api.coinbase.com/v2/prices/BTC-USD/spot"
)
```
Works for any pair: ETH-USD, SOL-USD, USDC-USD, etc.

### Coinbase Exchange — 24h stats for top pairs

```
http_request(
  method="GET",
  url="https://api.exchange.coinbase.com/products/BTC-USD/stats"
)
```

### All Coinbase Exchange trading pairs

```
http_request(
  method="GET",
  url="https://api.exchange.coinbase.com/products"
)
```

### Trending coins (last 24h)

```
http_request(
  method="GET",
  url="https://api.coingecko.com/api/v3/search/trending"
)
```

### Global crypto market stats

```
http_request(
  method="GET",
  url="https://api.coingecko.com/api/v3/global"
)
```

### Specific coin details (price, market cap, volume, links)

```
http_request(
  method="GET",
  url="https://api.coingecko.com/api/v3/coins/bitcoin?localization=false&tickers=false&community_data=false&sparkline=false"
)
```
Replace `bitcoin` with coingecko ID (ethereum, solana, chainlink, etc.)

## CDP Wallet Operations (base-sepolia testnet)

CDP keys are in env: `CDP_API_KEY_ID`, `CDP_API_KEY_SECRET`, `CDP_NETWORK_ID=base-sepolia`.
The CDP REST API base: `https://api.cdp.coinbase.com`

⚠️ CDP uses JWT authentication — this is complex. For wallet ops, prefer using the `cdp-sdk` if available.
If CDP SDK is not installed, CDP REST calls require a signed JWT from the key secret.

## "Top 10 coins today" Protocol

When user asks for top coins, tokens, or crypto market overview — do ALL of these WITHOUT ASKING:
1. Call CoinGecko markets (top 10 by market cap) — gives price, market cap, 24h change
2. Call CoinGecko trending — gives what's hot right now
3. Call CoinGecko global — gives total market cap, BTC dominance, market direction
4. Present a clean table: rank, name, symbol, price, 24h change %, market cap
5. Add trending section and market summary
Do NOT just do a web_search — use the actual APIs above for real-time accurate data.
