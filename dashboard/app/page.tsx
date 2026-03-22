'use client'
import { useEffect, useState, useCallback } from 'react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts'
import UploadPanel from '@/components/UploadPanel'
import PreviewPanel from '@/components/PreviewPanel'
import ChatPanel from '@/components/ChatPanel'

// ─── types ────────────────────────────────────────────────────────────────────
interface Run { id: string; name: string; run_type: string; status: string; start_time: string; total_tokens: number; prompt_tokens: number; completion_tokens: number; error?: string; parent_run_id?: string; inputs_preview?: string; outputs_preview?: string }
interface Stats { totalTokens: number; totalRuns: number; errors: number; avgTokens: number; chart: { date: string; tokens: number }[] }
interface Price { symbol: string; price: number }
interface WalletNet { network: string; balance: string; chain: string }
interface Wallet { address: string; balances: WalletNet[]; tokenCount: number }
interface GasEntry { network: string; gwei: string }

// ─── helpers ──────────────────────────────────────────────────────────────────
const STATUS_COLOR: Record<string, string> = { success: '#00ff88', error: '#ff2d55', running: '#00d4ff', pending: '#ff6b00' }
const fmt = (n: number) => n >= 1e6 ? `${(n/1e6).toFixed(1)}M` : n >= 1e3 ? `${(n/1e3).toFixed(1)}K` : String(n)
const ago = (t: string) => { const s = Math.floor((Date.now() - new Date(t).getTime())/1000); return s < 60 ? `${s}s ago` : s < 3600 ? `${Math.floor(s/60)}m ago` : `${Math.floor(s/3600)}h ago` }

// ─── sub-components ───────────────────────────────────────────────────────────
function Panel({ title, tag, children, className = '' }: { title: string; tag?: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`hud-panel bracket p-4 ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-[10px] tracking-widest text-hud-cyan uppercase font-bold">{title}</span>
        {tag && <span className="text-[9px] text-hud-text/50 tracking-wider">{tag}</span>}
      </div>
      {children}
    </div>
  )
}

function LiveDot({ color = '#00d4ff' }: { color?: string }) {
  return <span className="inline-block w-2 h-2 rounded-full mr-2 dot-live" style={{ background: color, boxShadow: `0 0 6px ${color}` }} />
}

function ThinkingDots() {
  return (
    <span className="inline-flex gap-1 ml-2">
      {[0,1,2].map(i => <span key={i} className="thinking-dot w-1 h-1 rounded-full bg-hud-cyan inline-block" />)}
    </span>
  )
}

function StatBox({ label, value, sub, color = 'text-hud-cyan' }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span className={`text-xl font-bold ${color}`}>{value}</span>
      <span className="text-[9px] text-hud-text/60 uppercase tracking-widest">{label}</span>
      {sub && <span className="text-[9px] text-hud-text/40">{sub}</span>}
    </div>
  )
}

// ─── main page ────────────────────────────────────────────────────────────────
export default function CommandCenter() {
  const [runs, setRuns] = useState<Run[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [prices, setPrices] = useState<Price[]>([])
  const [wallet, setWallet] = useState<Wallet | null>(null)
  const [gas, setGas] = useState<GasEntry[]>([])
  const [tick, setTick] = useState(0)
  const [loading, setLoading] = useState(true)
  const [time, setTime] = useState('')
  const [previewOpen, setPreviewOpen] = useState(false)

  const load = useCallback(async () => {
    try {
      const [r, s, p, w, g] = await Promise.allSettled([
        fetch('/api/langsmith?type=runs').then(r => r.json()),
        fetch('/api/langsmith?type=stats').then(r => r.json()),
        fetch('/api/alchemy?type=prices').then(r => r.json()),
        fetch('/api/alchemy?type=wallet').then(r => r.json()),
        fetch('/api/alchemy?type=gas').then(r => r.json()),
      ])
      if (r.status === 'fulfilled') setRuns(r.value.runs || [])
      if (s.status === 'fulfilled') setStats(s.value)
      if (p.status === 'fulfilled') setPrices(p.value.prices || [])
      if (w.status === 'fulfilled' && !w.value.error) setWallet(w.value)
      if (g.status === 'fulfilled') setGas(g.value.gas || [])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const iv = setInterval(() => { load(); setTick(t => t+1) }, 15000)
    const clock = setInterval(() => setTime(new Date().toUTCString().slice(0,25)), 1000)
    return () => { clearInterval(iv); clearInterval(clock) }
  }, [load])

  const activeRuns = runs.filter(r => r.status === 'running')
  const recentRuns = runs.slice(0, 12)
  const latestOutput = runs.find(r => r.status === 'success' && r.outputs_preview)?.outputs_preview

  return (
    <div className="min-h-screen bg-hud-bg font-mono flex">
    {/* ── Main content ── */}
    <div className={`flex-1 min-w-0 p-4 transition-all ${previewOpen ? 'mr-0' : ''}`}>
      {/* ── Header ── */}
      <header className="flex items-center justify-between mb-6 border-b border-hud-border pb-3">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-hud-cyan glow-cyan dot-live" />
            <span className="text-hud-cyan font-bold text-lg tracking-widest">DEEPAGENTS</span>
            <span className="text-hud-text/40 text-xs">COMMAND CENTER</span>
          </div>
          <div className="hidden md:flex gap-2 text-[9px] text-hud-text/40 tracking-widest">
            <span className="border border-hud-border px-2 py-0.5 rounded">v1.0</span>
            <span className="border border-hud-border px-2 py-0.5 rounded text-hud-green">ONLINE</span>
          </div>
        </div>
        <div className="flex items-center gap-4 text-[10px] text-hud-text/50">
          {activeRuns.length > 0 && (
            <span className="flex items-center text-hud-cyan"><LiveDot />{activeRuns.length} ACTIVE<ThinkingDots /></span>
          )}
          <span className="hidden sm:block">{time}</span>
          <span className="text-hud-text/30">TICK {tick}</span>
          <button
            onClick={() => setPreviewOpen(!previewOpen)}
            className={`px-3 py-1 rounded border text-[9px] tracking-widest transition-colors ${previewOpen ? 'border-hud-cyan text-hud-cyan bg-hud-cyan/10' : 'border-hud-border text-hud-text/50 hover:border-hud-cyan/50 hover:text-hud-cyan'}`}
          >
            ◈ PREVIEW
          </button>
        </div>
      </header>

      {/* ── Prices bar ── */}
      <div className="flex gap-4 mb-6 overflow-x-auto pb-1">
        {prices.map(p => (
          <div key={p.symbol} className="hud-panel px-4 py-2 flex items-center gap-3 whitespace-nowrap glow-cyan">
            <span className="text-[10px] text-hud-text/60">{p.symbol}</span>
            <span className="text-hud-cyan font-bold">${p.price.toLocaleString(undefined, {maximumFractionDigits: 2})}</span>
          </div>
        ))}
        {gas.map(g => (
          <div key={g.network} className="hud-panel px-4 py-2 flex items-center gap-3 whitespace-nowrap">
            <span className="text-[10px] text-hud-text/60">{g.network.toUpperCase()} GAS</span>
            <span className="text-hud-amber font-bold">{g.gwei} gwei</span>
          </div>
        ))}
      </div>

      {/* ── Main grid ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">

        {/* Token stats */}
        <Panel title="TOKEN INTELLIGENCE" tag="LANGSMITH" className="glow-cyan">
          {stats ? (
            <>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <StatBox label="total tokens" value={fmt(stats.totalTokens)} color="text-hud-cyan" />
                <StatBox label="total runs" value={stats.totalRuns} color="text-hud-blue" />
                <StatBox label="avg / run" value={fmt(stats.avgTokens)} color="text-hud-text" />
                <StatBox label="errors" value={stats.errors} color={stats.errors > 0 ? 'text-hud-red' : 'text-hud-green'} />
              </div>
              {stats.chart.length > 0 && (
                <ResponsiveContainer width="100%" height={80}>
                  <AreaChart data={stats.chart}>
                    <defs>
                      <linearGradient id="tg" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#00d4ff" stopOpacity={0.4} />
                        <stop offset="100%" stopColor="#00d4ff" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="date" tick={{ fontSize: 8, fill: '#a8c4d4' }} />
                    <YAxis hide />
                    <Tooltip contentStyle={{ background: '#071628', border: '1px solid #0a2540', fontSize: 10 }} />
                    <Area type="monotone" dataKey="tokens" stroke="#00d4ff" fill="url(#tg)" strokeWidth={1.5} />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </>
          ) : <div className="text-hud-text/40 text-xs">Loading...<ThinkingDots /></div>}
        </Panel>

        {/* Agent wallet */}
        <Panel title="AGENT WALLET" tag="ALCHEMY" className="glow-green">
          {wallet ? (
            <>
              <div className="text-[9px] text-hud-text/40 mb-3 truncate">{wallet.address}</div>
              <div className="space-y-2 mb-3">
                {wallet.balances.map(b => (
                  <div key={b.chain} className="flex justify-between items-center border-b border-hud-border/30 pb-1">
                    <span className="text-[10px] text-hud-text/60">{b.network}</span>
                    <span className={`font-bold text-sm ${parseFloat(b.balance) > 0 ? 'text-hud-green' : 'text-hud-text/40'}`}>
                      {b.balance} ETH
                    </span>
                  </div>
                ))}
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[9px] text-hud-text/40">ERC-20 TOKENS:</span>
                <span className="text-hud-cyan text-xs font-bold">{wallet.tokenCount}</span>
              </div>
            </>
          ) : (
            <div className="text-hud-text/40 text-xs">
              {loading ? <>Loading...<ThinkingDots /></> : 'Set AGENT_WALLET_ADDRESS env var'}
            </div>
          )}
        </Panel>

        {/* LLM status */}
        <Panel title="LLM CONNECTIONS" tag="MODELS">
          <div className="space-y-3">
            {[
              { name: 'Mistral Large', key: 'MISTRAL', tier: 'PAID', role: 'COORDINATOR + TASKS' },
              { name: 'Mistral Small', key: 'MISTRAL', tier: 'PAID', role: 'CASUAL CHAT' },
              { name: 'Ollama 1B', key: 'OLLAMA', tier: 'FREE', role: 'FAST PATH' },
              { name: 'NVIDIA LLaMA 70B', key: 'NVIDIA', tier: 'FREE TIER', role: 'FALLBACK' },
              { name: 'OpenRouter LLaMA', key: 'OPENROUTER', tier: 'FREE', role: 'FALLBACK' },
            ].map(m => (
              <div key={m.name} className="flex items-center justify-between text-[10px]">
                <div className="flex items-center gap-2">
                  <LiveDot color={m.tier === 'FREE' || m.tier === 'FREE TIER' ? '#00ff88' : '#00d4ff'} />
                  <span className="text-hud-text">{m.name}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-hud-text/40">{m.role}</span>
                  <span className={`px-1.5 py-0.5 rounded text-[8px] ${m.tier === 'PAID' ? 'bg-hud-amber/20 text-hud-amber' : 'bg-hud-green/20 text-hud-green'}`}>{m.tier}</span>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-3 pt-3 border-t border-hud-border/30 text-[9px] text-hud-text/40">
            ROUTING: casual→ollama → tasks→mistral-large
          </div>
        </Panel>
      </div>

      {/* ── Chat + Activity ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
        {/* Agent Chat */}
        <Panel title="AGENT CHAT" tag="DIRECT CONTROL" className="glow-cyan" >
          <div className="flex flex-col" style={{ height: '380px' }}>
            <ChatPanel />
          </div>
        </Panel>
      </div>

      {/* ── Agent Activity ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">

        {/* Live runs */}
        <Panel title="AGENT ACTIVITY STREAM" tag={`${recentRuns.length} RUNS`} className="glow-cyan">
          <div className="space-y-1.5 max-h-72 overflow-y-auto">
            {recentRuns.length === 0 && <div className="text-hud-text/40 text-xs">No recent runs<ThinkingDots /></div>}
            {recentRuns.map(run => (
              <div key={run.id} className={`border border-hud-border/30 rounded p-2 text-[10px] ${run.status === 'running' ? 'border-hud-cyan/40 bg-hud-cyan/5' : ''}`}>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span style={{ color: STATUS_COLOR[run.status] || '#a8c4d4' }}>●</span>
                    <span className="text-hud-text font-bold truncate max-w-[180px]">{run.name || run.run_type}</span>
                    {run.status === 'running' && <ThinkingDots />}
                  </div>
                  <div className="flex items-center gap-3 text-hud-text/40">
                    {run.total_tokens > 0 && <span className="text-hud-cyan">{fmt(run.total_tokens)}t</span>}
                    <span>{run.start_time ? ago(run.start_time) : ''}</span>
                  </div>
                </div>
                {run.parent_run_id && <div className="text-hud-text/30 text-[8px] pl-4">↳ subagent</div>}
                {run.error && <div className="text-hud-red text-[9px] truncate">⚠ {run.error.slice(0, 80)}</div>}
                {run.outputs_preview && !run.error && (
                  <div className="text-hud-text/30 text-[8px] truncate pl-4 mt-0.5">{run.outputs_preview}</div>
                )}
              </div>
            ))}
          </div>
        </Panel>

        {/* Token usage bar chart */}
        <Panel title="TOKEN USAGE BY RUN" tag="LAST 12">
          {recentRuns.filter(r => r.total_tokens > 0).length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={recentRuns.filter(r => r.total_tokens > 0).slice(0,10).reverse()} layout="vertical">
                <XAxis type="number" tick={{ fontSize: 8, fill: '#a8c4d4' }} />
                <YAxis type="category" dataKey="name" width={100} tick={{ fontSize: 8, fill: '#a8c4d4' }} />
                <Tooltip
                  contentStyle={{ background: '#071628', border: '1px solid #0a2540', fontSize: 10 }}
                  formatter={(v: any) => [fmt(v), 'tokens']}
                />
                <Bar dataKey="prompt_tokens" stackId="a" fill="#0066ff" />
                <Bar dataKey="completion_tokens" stackId="a" fill="#00d4ff" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-64 text-hud-text/30 text-xs">
              {loading ? <><ThinkingDots /> Loading runs...</> : 'No token data yet'}
            </div>
          )}
        </Panel>
      </div>

      {/* ── Subagents + Memory ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Subagents */}
        <Panel title="SUBAGENT HIERARCHY" tag="WORKERS">
          <div className="space-y-2">
            {runs.filter(r => r.parent_run_id).slice(0, 8).map(r => (
              <div key={r.id} className="flex items-center gap-2 text-[10px] border-b border-hud-border/20 pb-1">
                <span style={{ color: STATUS_COLOR[r.status] || '#a8c4d4' }}>◆</span>
                <span className="text-hud-text/70 truncate flex-1">{r.name || r.run_type}</span>
                <span className="text-hud-cyan text-[9px]">{fmt(r.total_tokens)}t</span>
              </div>
            ))}
            {runs.filter(r => r.parent_run_id).length === 0 && (
              <div className="text-hud-text/30 text-xs">No subagent runs in window</div>
            )}
          </div>
          <div className="mt-3 pt-2 border-t border-hud-border/30 text-[9px] text-hud-text/40">
            SUBAGENTS DETECTED: {runs.filter(r => r.parent_run_id).length}
          </div>
        </Panel>

        {/* Knowledge Base Upload */}
        <Panel title="KNOWLEDGE BASE" tag="UPLOAD + SEARCH">
          <UploadPanel />
        </Panel>

        {/* System info */}
        <Panel title="SYSTEM OVERVIEW" tag="CONFIG">
          <div className="space-y-2 text-[10px]">
            {[
              { k: 'DEPLOYMENT', v: 'Render (Docker)', c: 'text-hud-green' },
              { k: 'MEMORY', v: 'Mem0 + AstraDB', c: 'text-hud-cyan' },
              { k: 'TRACING', v: 'LangSmith', c: 'text-hud-cyan' },
              { k: 'CHAT', v: 'Telegram Bot', c: 'text-hud-blue' },
              { k: 'WALLET', v: '0xAfF9...3439', c: 'text-hud-amber' },
              { k: 'NETWORKS', v: 'ETH+Base+Poly+Arb+Opt', c: 'text-hud-text' },
              { k: 'COMPOSIO', v: '8 toolkits active', c: 'text-hud-green' },
              { k: 'AUTO-APPROVE', v: 'ENABLED', c: 'text-hud-amber' },
            ].map(({ k, v, c }) => (
              <div key={k} className="flex justify-between items-center border-b border-hud-border/20 pb-1">
                <span className="text-hud-text/50 tracking-wider">{k}</span>
                <span className={`font-bold ${c}`}>{v}</span>
              </div>
            ))}
          </div>
          <div className="mt-3 text-[9px] text-hud-text/30 text-center">
            AUTO-REFRESH: 15s
          </div>
        </Panel>
      </div>

      {/* Footer */}
      <footer className="mt-6 pt-3 border-t border-hud-border/30 flex justify-between text-[9px] text-hud-text/25 tracking-widest">
        <span>DEEPAGENTS COMMAND CENTER — COINVEST518</span>
        <span>POWERED BY LANGSMITH · ALCHEMY · MISTRAL</span>
      </footer>
    </div>

    {previewOpen && (
      <div className="w-96 shrink-0 border-l border-hud-border bg-hud-bg/95 p-4 flex flex-col sticky top-0 h-screen overflow-hidden">
        <PreviewPanel
          latestOutput={latestOutput}
          onClose={() => setPreviewOpen(false)}
        />
      </div>
    )}
    </div>
  )
}
