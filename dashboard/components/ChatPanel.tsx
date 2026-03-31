'use client'
import { useState, useRef, useEffect, useCallback } from 'react'

interface Message { role: 'user' | 'agent'; text: string; ts: number }

/** RFC-4122 v4 UUID without any external dependency */
function newUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

const STORAGE_KEY = 'da_dashboard_thread_id'

function getOrCreateThreadId(): string {
  if (typeof window === 'undefined') return newUUID()
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored) return stored
  const id = newUUID()
  localStorage.setItem(STORAGE_KEY, id)
  return id
}

export default function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState<'unknown' | 'ok' | 'offline'>('unknown')
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const threadId = useRef<string>('')

  // Initialise thread_id from localStorage (stable across refreshes)
  useEffect(() => {
    threadId.current = getOrCreateThreadId()
  }, [])

  // Check agent health
  useEffect(() => {
    fetch('/api/agent-chat')
      .then(r => r.json())
      .then(d => setStatus(d.status === 'ok' || d.model ? 'ok' : 'offline'))
      .catch(() => setStatus('offline'))
  }, [])

  // Load conversation history for this thread on mount
  useEffect(() => {
    if (historyLoaded) return
    const tid = threadId.current
    if (!tid) return
    fetch(`/api/agent-history?thread_id=${encodeURIComponent(tid)}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.messages?.length) {
          setMessages(data.messages.map((m: { role: string; text: string }) => ({
            role: m.role as 'user' | 'agent',
            text: m.text,
            ts: Date.now(),
          })))
        }
        setHistoryLoaded(true)
      })
      .catch(() => setHistoryLoaded(true))
  }, [historyLoaded])

  const messagesContainerRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = messagesContainerRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages])

  const send = useCallback(async () => {
    const msg = input.trim()
    if (!msg || loading) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', text: msg, ts: Date.now() }])
    setLoading(true)
    try {
      const r = await fetch('/api/agent-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, thread_id: threadId.current }),
      })
      const data = await r.json()
      setMessages(prev => [...prev, {
        role: 'agent',
        text: data.response || data.error || 'No response',
        ts: Date.now(),
      }])
      // If task was marked incomplete, show a hint
      if (data.status === 'incomplete') {
        setMessages(prev => [...prev, {
          role: 'agent',
          text: '⚠ Task incomplete — rate limit or error. Send again to retry.',
          ts: Date.now(),
        }])
      }
    } catch (e: any) {
      setMessages(prev => [...prev, { role: 'agent', text: `Error: ${e.message}`, ts: Date.now() }])
    } finally {
      setLoading(false)
    }
  }, [input, loading])

  const resetThread = useCallback(() => {
    const id = newUUID()
    localStorage.setItem(STORAGE_KEY, id)
    threadId.current = id
    setMessages([])
    setHistoryLoaded(false)
  }, [])

  const statusColor = status === 'ok' ? '#00ff88' : status === 'offline' ? '#ff2d55' : '#ff6b00'
  const statusLabel = status === 'ok' ? 'ONLINE' : status === 'offline' ? 'OFFLINE' : 'CHECKING'

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Status bar */}
      <div className="flex items-center gap-2 mb-3 text-[9px] tracking-widest">
        <span className="inline-block w-2 h-2 rounded-full" style={{ background: statusColor, boxShadow: `0 0 6px ${statusColor}` }} />
        <span style={{ color: statusColor }}>{statusLabel}</span>
        <span className="text-hud-text/30 ml-auto">
          THREAD: {threadId.current ? threadId.current.slice(-8) : '...'}
        </span>
        <button
          onClick={resetThread}
          className="text-hud-text/30 hover:text-hud-amber ml-1"
          title="New conversation"
        >
          ↺ RESET
        </button>
      </div>

      {/* Messages */}
      <div ref={messagesContainerRef} className="flex-1 overflow-y-auto space-y-2 min-h-0 pr-1">
        {messages.length === 0 && (
          <div className="text-center text-hud-text/20 text-[10px] pt-8 tracking-widest">
            <div className="text-2xl mb-2">◈</div>
            <div>SEND A MESSAGE TO THE AGENT</div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`text-[11px] rounded p-2.5 ${
            m.role === 'user'
              ? 'bg-hud-cyan/10 border border-hud-cyan/20 text-hud-cyan ml-6'
              : 'bg-hud-bg border border-hud-border text-hud-text/90 mr-6'
          }`}>
            <div className="text-[8px] mb-1 opacity-50 tracking-widest">
              {m.role === 'user' ? 'YOU' : 'AGENT'} · {new Date(m.ts).toLocaleTimeString()}
            </div>
            <div className="whitespace-pre-wrap leading-relaxed">{m.text}</div>
          </div>
        ))}
        {loading && (
          <div className="bg-hud-bg border border-hud-border rounded p-2.5 mr-6">
            <div className="text-[8px] mb-1 text-hud-text/40 tracking-widest">AGENT · thinking</div>
            <span className="inline-flex gap-1">
              {[0,1,2].map(i => (
                <span key={i} className="thinking-dot w-1.5 h-1.5 rounded-full bg-hud-cyan inline-block" />
              ))}
            </span>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="flex gap-2 mt-3 pt-3 border-t border-hud-border/30">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
          placeholder={status === 'offline' ? 'Agent offline — start local server or check AGENT_API_URL' : 'Send a message or task…'}
          disabled={loading || status === 'offline'}
          className="flex-1 bg-hud-bg border border-hud-border rounded px-3 py-2 text-[11px] text-hud-text placeholder-hud-text/25 focus:outline-none focus:border-hud-cyan/50 disabled:opacity-40"
        />
        <button
          onClick={send}
          disabled={loading || !input.trim() || status === 'offline'}
          className="px-4 py-2 text-[10px] border border-hud-cyan/40 text-hud-cyan rounded hover:bg-hud-cyan/10 transition-colors disabled:opacity-30 tracking-widest"
        >
          {loading ? '…' : 'SEND'}
        </button>
      </div>
    </div>
  )
}