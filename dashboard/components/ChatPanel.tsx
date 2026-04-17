'use client'
import { useState, useRef, useEffect, useCallback, useMemo } from 'react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface Message {
  role: 'user' | 'agent' | 'thinking' | 'tool'
  text: string
  ts: number
  toolName?: string
  toolArgs?: any
  toolStatus?: 'pending' | 'running' | 'success' | 'error'
  toolOutput?: string
  toolId?: string
}

// ---------------------------------------------------------------------------
// FormatAgentText — renders markdown AI text as styled React elements
// Supports: headings, bold, italic, inline code, code blocks, bullet/ordered
// lists, blockquotes, horizontal rules, links, and plain paragraphs.
// ---------------------------------------------------------------------------
function FormatAgentText({ text }: { text: string }) {
  const elements = useMemo(() => {
    const lines = text.split('\n')
    const result: React.ReactNode[] = []
    let inList = false
    let listItems: React.ReactNode[] = []
    let listOrdered = false
    let listKey = 0
    // Code block state
    let inCodeBlock = false
    let codeLines: string[] = []
    let codeLang = ''
    let codeKey = 0

    const flushList = () => {
      if (listItems.length === 0) return
      if (listOrdered) {
        result.push(<ol key={`ol-${listKey}`} className="space-y-1 my-2 ml-1">{listItems}</ol>)
      } else {
        result.push(<ul key={`ul-${listKey}`} className="space-y-1 my-2 ml-1">{listItems}</ul>)
      }
      listItems = []
      inList = false
      listKey++
    }

    const flushCodeBlock = () => {
      const code = codeLines.join('\n')
      result.push(
        <div key={`cb-${codeKey++}`} className="my-3 rounded-lg overflow-hidden border border-hud-border/40">
          {codeLang && (
            <div className="px-3 py-1 text-[10px] text-hud-cyan/60 bg-[#060e1a] border-b border-hud-border/30 font-mono tracking-wider uppercase">
              {codeLang}
            </div>
          )}
          <pre className="px-4 py-3 text-[12px] font-mono text-[#a8d8ea] bg-[#060e1a] overflow-x-auto leading-relaxed whitespace-pre">
            <code>{code}</code>
          </pre>
        </div>
      )
      codeLines = []
      codeLang = ''
      inCodeBlock = false
    }

    // Inline formatting: bold, italic, inline code, links
    const formatInline = (s: string): React.ReactNode => {
      // Pattern order matters — inline code first to prevent bold/italic inside it
      const tokenRegex = /(`[^`]+`|\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|__(.+?)__|_(.+?)_|\*([^*]+)\*|\[([^\]]+)\]\((https?:\/\/[^)]+)\))/g
      const parts: React.ReactNode[] = []
      let ki = 0
      let lastIdx = 0
      let match: RegExpExecArray | null
      while ((match = tokenRegex.exec(s)) !== null) {
        if (match.index > lastIdx) {
          parts.push(<span key={ki++}>{s.slice(lastIdx, match.index)}</span>)
        }
        const token = match[0]
        if (token.startsWith('`')) {
          // Inline code
          parts.push(
            <code key={ki++} className="px-1.5 py-0.5 rounded text-[11.5px] font-mono text-hud-cyan/90 bg-[#060e1a] border border-hud-border/40">
              {token.slice(1, -1)}
            </code>
          )
        } else if (match[2]) {
          // Bold + italic ***
          parts.push(<strong key={ki++} className="font-semibold italic text-white/95">{match[2]}</strong>)
        } else if (match[3] || match[4]) {
          // Bold ** or __
          parts.push(<strong key={ki++} className="font-semibold text-white/95">{match[3] || match[4]}</strong>)
        } else if (match[5] || match[6]) {
          // Italic _ or *
          parts.push(<em key={ki++} className="italic text-hud-text/85">{match[5] || match[6]}</em>)
        } else if (match[7] && match[8]) {
          // Link [text](url)
          parts.push(
            <a key={ki++} href={match[8]} target="_blank" rel="noreferrer"
               className="text-hud-cyan underline underline-offset-2 hover:text-white transition-colors">
              {match[7]}
            </a>
          )
        }
        lastIdx = match.index + match[0].length
      }
      if (lastIdx < s.length) {
        parts.push(<span key={ki++}>{s.slice(lastIdx)}</span>)
      }
      return parts.length === 1 ? parts[0] : <>{parts}</>
    }

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i]
      const trimmed = line.trim()

      // --- Code fence ---
      if (trimmed.startsWith('```')) {
        if (inCodeBlock) {
          flushCodeBlock()
        } else {
          flushList()
          inCodeBlock = true
          codeLang = trimmed.slice(3).trim()
        }
        continue
      }
      if (inCodeBlock) {
        codeLines.push(line)
        continue
      }

      // --- Blank line ---
      if (trimmed === '') {
        flushList()
        result.push(<div key={`br-${i}`} className="h-2" />)
        continue
      }

      // --- Horizontal rule ---
      if (/^[-*_]{3,}$/.test(trimmed)) {
        flushList()
        result.push(<hr key={`hr-${i}`} className="my-3 border-0 border-t border-hud-border/40" />)
        continue
      }

      // --- Headings ---
      if (trimmed.startsWith('#### ')) {
        flushList()
        result.push(<div key={`h4-${i}`} className="text-[12px] font-bold text-hud-cyan/80 mt-3 mb-1 tracking-wide">{formatInline(trimmed.slice(5))}</div>)
        continue
      }
      if (trimmed.startsWith('### ')) {
        flushList()
        result.push(<div key={`h3-${i}`} className="text-[13px] font-bold text-hud-cyan/90 mt-3 mb-1 tracking-wide">{formatInline(trimmed.slice(4))}</div>)
        continue
      }
      if (trimmed.startsWith('## ')) {
        flushList()
        result.push(<div key={`h2-${i}`} className="text-[14px] font-bold text-hud-cyan mt-3 mb-1 tracking-wide">{formatInline(trimmed.slice(3))}</div>)
        continue
      }
      if (trimmed.startsWith('# ')) {
        flushList()
        result.push(<div key={`h1-${i}`} className="text-[15px] font-bold text-hud-cyan mt-3 mb-1 tracking-wide">{formatInline(trimmed.slice(2))}</div>)
        continue
      }

      // --- Blockquote ---
      if (trimmed.startsWith('> ')) {
        flushList()
        result.push(
          <div key={`bq-${i}`} className="border-l-2 border-hud-cyan/30 pl-3 my-1 text-hud-text/60 italic text-[13px]">
            {formatInline(trimmed.slice(2))}
          </div>
        )
        continue
      }

      // --- Ordered list ---
      const numMatch = trimmed.match(/^(\d+)\.\s+(.+)/)
      if (numMatch) {
        if (!inList || !listOrdered) { flushList(); inList = true; listOrdered = true }
        listItems.push(
          <li key={`li-${i}`} className="flex gap-2 items-start">
            <span className="text-hud-cyan/70 font-bold min-w-[20px]">{numMatch[1]}.</span>
            <span className="flex-1">{formatInline(numMatch[2])}</span>
          </li>
        )
        continue
      }

      // --- Unordered list ---
      const bulletMatch = trimmed.match(/^[-*•]\s+(.+)/)
      if (bulletMatch) {
        if (!inList || listOrdered) { flushList(); inList = true; listOrdered = false }
        listItems.push(
          <li key={`li-${i}`} className="flex gap-2 items-start">
            <span className="text-hud-cyan/60 mt-[2px]">›</span>
            <span className="flex-1">{formatInline(bulletMatch[1])}</span>
          </li>
        )
        continue
      }

      // --- Paragraph ---
      flushList()
      result.push(<div key={`p-${i}`} className="my-0.5">{formatInline(trimmed)}</div>)
    }

    // Flush anything still open
    flushList()
    if (inCodeBlock && codeLines.length > 0) flushCodeBlock()

    return result
  }, [text])
  return <div className="space-y-0">{elements}</div>
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function newUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

const STORAGE_KEY = 'da_dashboard_thread_id'

/**
 * Always returns a brand-new thread ID for this page load.
 * The previous ID is saved under STORAGE_KEY only so the "load history"
 * feature can access it explicitly — it is NOT reused automatically.
 * This ensures every page load / new tab starts a clean context.
 */
function newSessionThreadId(): string {
  const id = newUUID()
  // Persist so the history panel could reference it, but never read it back on start
  if (typeof window !== 'undefined') {
    localStorage.setItem(STORAGE_KEY, id)
  }
  return id
}

/** Format tool args for short display */
function formatToolArgs(args: any): string {
  if (!args || typeof args !== 'object') return ''
  const keys = Object.keys(args)
  if (keys.length === 0) return ''
  // Show the most important arg value, abbreviated
  const first = args[keys[0]]
  const val = typeof first === 'string' ? first : JSON.stringify(first)
  return val.length > 80 ? val.slice(0, 77) + '…' : val
}

// ---------------------------------------------------------------------------
// Spinner component (matches CLI's LoadingWidget)
// ---------------------------------------------------------------------------
function Spinner({ label }: { label: string }) {
  const [frame, setFrame] = useState(0)
  const [elapsed, setElapsed] = useState(0)
  const frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
  useEffect(() => {
    const iv = setInterval(() => {
      setFrame(f => (f + 1) % frames.length)
      setElapsed(e => e + 1)
    }, 100)
    return () => clearInterval(iv)
  }, [])
  return (
    <div className="flex items-center gap-2.5 text-[12px] text-hud-cyan/80">
      <span className="text-hud-cyan font-mono">{frames[frame]}</span>
      <span>{label}</span>
      <span className="text-hud-text/25 text-[10px]">{(elapsed / 10).toFixed(0)}s</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ToolCallCard — matches CLI's ToolCallMessage widget
// ---------------------------------------------------------------------------
function ToolCallCard({ msg }: { msg: Message }) {
  const [expanded, setExpanded] = useState(false)
  const statusColor = msg.toolStatus === 'success' ? '#00ff88'
    : msg.toolStatus === 'error' ? '#ff2d55'
    : msg.toolStatus === 'running' ? '#00d4ff'
    : '#ff6b00'
  const statusIcon = msg.toolStatus === 'success' ? '✓'
    : msg.toolStatus === 'error' ? '✗'
    : msg.toolStatus === 'running' ? '⟳'
    : '◦'
  const shortArgs = formatToolArgs(msg.toolArgs)

  return (
    <div className="rounded-lg border border-hud-border/40 bg-[#0a1628]/80 ml-4 overflow-hidden">
      {/* Tool header — clickable to expand */}
      <div
        className="flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-hud-cyan/5 transition-colors"
        onClick={() => msg.toolOutput && setExpanded(!expanded)}
      >
        <span className="text-[11px] font-mono" style={{ color: statusColor }}>{statusIcon}</span>
        <span className="text-[12px] text-hud-text/80 font-medium">{msg.toolName || 'tool'}</span>
        {shortArgs && <span className="text-[11px] text-hud-text/40 truncate flex-1">({shortArgs})</span>}
        {msg.toolStatus === 'running' && (
          <span className="inline-flex gap-0.5 ml-auto">
            {[0,1,2].map(i => <span key={i} className="thinking-dot w-1 h-1 rounded-full bg-hud-cyan inline-block" />)}
          </span>
        )}
        {msg.toolOutput && (
          <span className="text-[9px] text-hud-text/25 ml-auto">{expanded ? '▲' : '▼'}</span>
        )}
      </div>
      {/* Tool output — collapsible (like CLI Ctrl+E) */}
      {expanded && msg.toolOutput && (
        <div className="px-3 py-2 border-t border-hud-border/20 text-[11px] text-hud-text/50 whitespace-pre-wrap max-h-48 overflow-y-auto font-mono leading-relaxed">
          {msg.toolOutput}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// AskUserPanel — renders agent's pending questions so the user knows to reply
// ---------------------------------------------------------------------------
function AskUserPanel({ questions }: { questions: any[] }) {
  return (
    <div className="mt-2 p-3 border border-hud-amber/50 bg-hud-amber/5 rounded-lg">
      <div className="flex items-center gap-2 text-[9px] text-hud-amber tracking-widest font-bold mb-2.5 uppercase">
        <span className="w-1.5 h-1.5 rounded-full bg-hud-amber animate-pulse" />
        Agent is waiting for your reply
      </div>
      <div className="space-y-2.5">
        {questions.map((q: any, i: number) => (
          <div key={i} className="text-[12px] text-hud-text/80">
            <div className="flex gap-2">
              <span className="text-hud-amber/60 font-bold min-w-[16px]">{i + 1}.</span>
              <span>{q.question || String(q)}</span>
            </div>
            {q.choices && Array.isArray(q.choices) && (
              <div className="mt-1.5 ml-5 flex flex-wrap gap-1.5">
                {q.choices.map((c: any, j: number) => (
                  <span key={j} className="text-[10px] border border-hud-amber/30 px-2 py-0.5 rounded text-hud-text/50">
                    {c.value || c.label || String(c)}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="text-[10px] text-hud-text/30 mt-2.5">↓ Type your answer in the input below</div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main ChatPanel
// ---------------------------------------------------------------------------
export default function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [spinnerLabel, setSpinnerLabel] = useState('Thinking')
  const [status, setStatus] = useState<'unknown' | 'ok' | 'offline'>('unknown')
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const [showThinking, setShowThinking] = useState(true)
  const [streamingText, setStreamingText] = useState('')  // Accumulates during stream
  const [pendingAskUser, setPendingAskUser] = useState<any[] | null>(null)  // Questions from ask_user interrupt
  const threadId = useRef<string>('')
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    // Always generate a fresh thread on mount — no stale context from previous sessions
    threadId.current = newSessionThreadId()
  }, [])

  useEffect(() => {
    fetch('/api/agent-chat')
      .then(r => r.json())
      .then(d => setStatus(d.status === 'ok' || d.model ? 'ok' : 'offline'))
      .catch(() => setStatus('offline'))
  }, [])

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
  }, [messages, streamingText])

  // ------------------------------------------------------------------
  // SSE streaming send
  // ------------------------------------------------------------------
  const send = useCallback(async () => {
    const msg = input.trim()
    if (!msg || loading) return
    setInput('')
    setPendingAskUser(null)  // clear any pending ask_user questions on every send
    setMessages(prev => [...prev, { role: 'user', text: msg, ts: Date.now() }])
    setLoading(true)
    setStreamingText('')
    setSpinnerLabel('Thinking')

    let timedOut = false
    try {
      const controller = new AbortController()
      abortRef.current = controller
      const timeout = setTimeout(() => { timedOut = true; controller.abort() }, 300_000) // 5 min for complex tasks

      const r = await fetch('/api/agent-chat-stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: msg,
          thread_id: threadId.current,
        }),
        signal: controller.signal,
      })
      clearTimeout(timeout)

      if (!r.ok) {
        const err = await r.json().catch(() => ({ error: r.statusText }))
        setMessages(prev => [...prev, { role: 'agent', text: `Error: ${err.error || r.statusText}`, ts: Date.now() }])
        setLoading(false)
        return
      }

      // Parse SSE stream
      const reader = r.body?.getReader()
      if (!reader) {
        setMessages(prev => [...prev, { role: 'agent', text: 'No stream available', ts: Date.now() }])
        setLoading(false)
        return
      }

      const decoder = new TextDecoder()
      let buffer = ''
      let accumulatedText = ''
      let gotDone = false
      // These MUST be outside the while loop so SSE state survives chunk boundaries.
      // If event: and data: arrive in different read() calls (common for large payloads),
      // declaring them inside would reset currentEvent before data arrives → silent drop.
      let currentEvent = ''
      let currentData = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // Parse SSE lines from buffer
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''  // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            currentData = line.slice(6)
          } else if (line === '' && currentEvent && currentData) {
            // Complete event — dispatch
            try {
              const payload = JSON.parse(currentData)
              switch (currentEvent) {
                case 'status': {
                  const state = payload.state as string
                  if (state === 'thinking') {
                    setSpinnerLabel('Thinking')
                  } else if (state?.startsWith('tool:')) {
                    setSpinnerLabel(`Running ${state.slice(5)}`)
                  } else if (state === 'interrupted') {
                    // Agent is paused waiting for user input — stop spinner and unlock input
                    setSpinnerLabel('Waiting for reply')
                    setLoading(false)
                  }
                  break
                }

                case 'text': {
                  const chunk = payload.content as string
                  accumulatedText += chunk
                  setStreamingText(accumulatedText)
                  break
                }

                case 'tool_start': {
                  // If the agent called ask_user, capture the questions for display
                  if (payload.name === 'ask_user') {
                    const qs = payload.args?.questions || payload.args?.question
                      ? [{ question: payload.args.question }]
                      : []
                    if (Array.isArray(payload.args?.questions)) {
                      setPendingAskUser(payload.args.questions)
                    } else if (qs.length) {
                      setPendingAskUser(qs)
                    }
                  }
                  if (showThinking) {
                    setMessages(prev => [...prev, {
                      role: 'tool',
                      text: `${payload.name}(${formatToolArgs(payload.args)})`,
                      ts: Date.now(),
                      toolName: payload.name,
                      toolArgs: payload.args,
                      toolStatus: 'running',
                      toolId: payload.id,
                    }])
                  }
                  break
                }

                case 'tool_end': {
                  if (showThinking) {
                    setMessages(prev => prev.map(m =>
                      m.toolId === payload.id
                        ? {
                            ...m,
                            toolStatus: payload.status as 'success' | 'error',
                            toolOutput: payload.output,
                          }
                        : m
                    ))
                  }
                  break
                }

                case 'done': {
                  gotDone = true
                  const finalText = accumulatedText.trim() || payload.response || 'No response'
                  setStreamingText('')
                  setMessages(prev => [...prev, {
                    role: 'agent',
                    text: finalText,
                    ts: Date.now(),
                  }])
                  break
                }

                case 'error': {
                  setStreamingText('')
                  setMessages(prev => [...prev, {
                    role: 'agent',
                    text: `Error: ${payload.message}`,
                    ts: Date.now(),
                  }])
                  break
                }
              }
            } catch {
              // Skip malformed JSON
            }
            currentEvent = ''
            currentData = ''
          }
        }
      }

      // Only add if stream ended WITHOUT a 'done' event (e.g. connection dropped)
      if (!gotDone && accumulatedText.trim()) {
        setStreamingText('')
        setMessages(prev => [...prev, {
          role: 'agent',
          text: accumulatedText.trim(),
          ts: Date.now(),
        }])
      }

    } catch (e: any) {
      setStreamingText('')
      const errMsg = e.name === 'AbortError'
        ? (timedOut ? 'Agent took too long (>5 min). Try again or check logs.' : 'Task stopped.')
        : `Error: ${e.message}`
      setMessages(prev => [...prev, { role: 'agent', text: errMsg, ts: Date.now() }])
    } finally {
      abortRef.current = null
      setLoading(false)
      setStreamingText('')
    }
  }, [input, loading, showThinking])


  const stopTask = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  const resetThread = useCallback(() => {
    const id = newUUID()
    localStorage.setItem(STORAGE_KEY, id)
    threadId.current = id
    setMessages([])
    setHistoryLoaded(false)
    setStreamingText('')
  }, [])

  const toggleThinking = useCallback(() => {
    setShowThinking(prev => !prev)
  }, [])

  const statusColor = status === 'ok' ? '#00ff88' : status === 'offline' ? '#ff2d55' : '#ff6b00'
  const statusLabel = status === 'ok' ? 'ONLINE' : status === 'offline' ? 'OFFLINE' : 'CHECKING'

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Status bar */}
      <div className="flex items-center gap-3 mb-4 text-[10px] tracking-widest flex-wrap">
        <span className="inline-block w-2 h-2 rounded-full" style={{ background: statusColor, boxShadow: `0 0 6px ${statusColor}` }} />
        <span style={{ color: statusColor }}>{statusLabel}</span>
        <span className="text-hud-amber font-bold">MAIN AGENT</span>
        <span className="text-hud-text/30 ml-auto">
          THREAD: {threadId.current ? threadId.current.slice(-8) : '...'}
        </span>
        <button
          onClick={toggleThinking}
          className={`px-2 py-0.5 rounded text-[8px] border transition-colors ${
            showThinking
              ? 'border-hud-cyan/40 text-hud-cyan hover:bg-hud-cyan/10'
              : 'border-hud-text/20 text-hud-text/40 hover:border-hud-text/40'
          }`}
          title="Toggle tool call visibility"
        >
          {showThinking ? '🔧 TOOLS' : '🙈 HIDE'}
        </button>
        <button
          onClick={resetThread}
          className="text-hud-text/30 hover:text-hud-amber ml-1 border border-hud-text/20 hover:border-hud-amber/40 px-2 py-0.5 rounded text-[8px] transition-colors"
          title="Start a new conversation (clears messages and creates fresh thread)"
        >
          ✚ NEW CHAT
        </button>
      </div>

      {/* Messages */}
      <div ref={messagesContainerRef} className="flex-1 overflow-y-auto space-y-3 min-h-0 pr-1 scrollbar-thin">
        {messages.length === 0 && !loading && (
          <div className="text-center text-hud-text/25 text-sm pt-16 tracking-widest">
            <div className="text-4xl mb-3 text-hud-cyan/40">◈</div>
            <div className="text-[11px]">SEND A MESSAGE TO THE AGENT</div>
            <div className="text-[10px] mt-2 text-hud-text/30">
              Main Agent — same as CLI, with Musa as sub-agent
            </div>
          </div>
        )}

        {messages.map((m, i) => {
          // Tool calls get the special card treatment
          if (m.role === 'tool') {
            return <ToolCallCard key={i} msg={m} />
          }

          return (
            <div key={i} className={`rounded-lg ${
              m.role === 'user'
                ? 'bg-hud-cyan/8 border border-hud-cyan/20 text-hud-cyan ml-12 p-3.5'
                : m.role === 'thinking'
                ? 'bg-hud-blue/8 border border-hud-blue/30 text-hud-blue ml-6 p-3 text-[12px]'
                : 'bg-[#0a1628] border border-hud-border/60 text-[#d0e4f0] p-4'
            }`}>
              <div className="text-[9px] mb-2 opacity-40 tracking-widest font-medium">
                {m.role === 'user' ? 'YOU' : 'AGENT'} · {new Date(m.ts).toLocaleTimeString()}
              </div>
              {m.role === 'agent' ? (
                <div className="text-[13.5px] leading-[1.7]"><FormatAgentText text={m.text} /></div>
              ) : (
                <div className="whitespace-pre-wrap leading-relaxed text-[13px]">{m.text}</div>
              )}
            </div>
          )
        })}

        {/* Live streaming text — shows as it arrives, word by word */}
        {streamingText && (
          <div className="bg-[#0a1628] border border-hud-border/60 rounded-lg text-[#d0e4f0] p-4">
            <div className="text-[9px] mb-2 opacity-40 tracking-widest font-medium">
              AGENT · streaming
            </div>
            <div className="text-[13.5px] leading-[1.7]">
              <FormatAgentText text={streamingText} />
              <span className="inline-block w-[2px] h-[14px] bg-hud-cyan/70 ml-0.5 animate-pulse" />
            </div>
          </div>
        )}

        {/* Loading spinner — like CLI's LoadingWidget */}
        {loading && !streamingText && (
          <div className="bg-[#0a1628] border border-hud-border/60 rounded-lg p-4 mr-4">
            <Spinner label={spinnerLabel} />
          </div>
        )}

      </div>

      {/* Input */}
      <div className="mt-3 pt-3 border-t border-hud-border/30">
        <div className="flex gap-2">
        {pendingAskUser && <AskUserPanel questions={pendingAskUser} />}
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
          placeholder={
            status === 'offline'
              ? 'Agent offline — start local server or check AGENT_API_URL'
              : pendingAskUser
              ? 'Type your answer here and press Enter…'
              : loading
              ? 'Agent is working…'
              : 'Send a message or task…'
          }
          disabled={status === 'offline' || (loading && !pendingAskUser)}
          className="flex-1 bg-[#0a1628] border border-hud-border/60 rounded-lg px-4 py-3 text-[13px] text-hud-text placeholder-hud-text/30 focus:outline-none focus:border-hud-cyan/50 focus:ring-1 focus:ring-hud-cyan/20 disabled:opacity-40 transition-colors"
        />
        {loading ? (
          <button
            onClick={stopTask}
            className="px-4 py-3 text-[11px] border border-red-500/60 text-red-400 rounded-lg hover:bg-red-500/10 transition-colors tracking-widest font-medium"
            title="Stop the current task"
          >
            STOP
          </button>
        ) : (
          <button
            onClick={send}
            disabled={!input.trim() || status === 'offline'}
            className="px-5 py-3 text-[11px] border border-hud-cyan/40 text-hud-cyan rounded-lg hover:bg-hud-cyan/10 transition-colors disabled:opacity-30 tracking-widest font-medium"
          >
            SEND
          </button>
        )}
        </div>
      </div>
    </div>
  )
}
