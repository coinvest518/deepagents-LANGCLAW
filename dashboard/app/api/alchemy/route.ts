import { NextResponse } from 'next/server'

const KEY = process.env.ALCHEMY_API_KEY || ''
const WALLET = process.env.AGENT_WALLET_ADDRESS || ''

async function rpc(network: string, method: string, params: any[]) {
  const res = await fetch(`https://${network}.g.alchemy.com/v2/${KEY}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', method, params, id: 1 }),
    next: { revalidate: 60 },
  })
  const d = await res.json()
  return d.result
}

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url)
  const type = searchParams.get('type') || 'prices'

  try {
    if (type === 'prices') {
      const symbols = ['ETH', 'BTC', 'USDC', 'MATIC']
      const qs = symbols.map(s => `symbols=${s}`).join('&')
      const res = await fetch(`https://api.g.alchemy.com/prices/v1/${KEY}/tokens/by-symbol?${qs}`, {
        next: { revalidate: 60 },
      })
      const data = await res.json()
      const prices = (data.data || []).map((item: any) => ({
        symbol: item.symbol,
        price: parseFloat(item.prices?.find((p: any) => p.currency === 'usd')?.value || '0'),
      }))
      return NextResponse.json({ prices })
    }

    if (type === 'wallet') {
      if (!WALLET) return NextResponse.json({ error: 'AGENT_WALLET_ADDRESS not set' })
      const networks = [
        { id: 'eth-mainnet', label: 'ETH' },
        { id: 'base-mainnet', label: 'Base' },
        { id: 'base-sepolia', label: 'Base Testnet' },
      ]
      const balances = await Promise.all(
        networks.map(async (net) => {
          const raw = await rpc(net.id, 'eth_getBalance', [WALLET, 'latest'])
          const bal = raw ? parseInt(raw, 16) / 1e18 : 0
          return { network: net.label, balance: bal.toFixed(6), chain: net.id }
        })
      )
      // Token balances on base
      const tokenRes = await rpc('base-mainnet', 'alchemy_getTokenBalances', [WALLET, 'DEFAULT_TOKENS'])
      const nonZero = (tokenRes?.tokenBalances || []).filter(
        (t: any) => t.tokenBalance !== '0x0000000000000000000000000000000000000000000000000000000000000000'
      ).length
      return NextResponse.json({ address: WALLET, balances, tokenCount: nonZero })
    }

    if (type === 'gas') {
      const networks = ['eth-mainnet', 'base-mainnet', 'polygon-mainnet']
      const gas = await Promise.all(
        networks.map(async (net) => {
          const raw = await rpc(net, 'eth_gasPrice', [])
          return { network: net.replace('-mainnet', ''), gwei: raw ? (parseInt(raw, 16) / 1e9).toFixed(2) : '?' }
        })
      )
      return NextResponse.json({ gas })
    }

    return NextResponse.json({ error: 'Unknown type' }, { status: 400 })
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}
