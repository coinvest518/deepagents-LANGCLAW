'use client'
import { useState, useRef, useCallback } from 'react'

type ViewMode = 'output' | 'html' | 'markdown'

interface PreviewPanelProps {
  latestOutput?: string
  onClose: () => void
}

function renderMarkdown(text: string): string {
  return text
    .replace(/^### (.+)$/gm, '<h3 style="color:#00d4ff;margin:8px 0 4px">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 style="color:#00d4ff;margin:10px 0 6px">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 style="color:#00d4ff;margin:12px 0 8px">$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong style="color:#e0f0ff">$1</strong>')
    .replace(/`([^`]+)`/g, '<code style="background:#0a1628;color:#00d4ff;padding:1px 4px;border-radius:2px">$1</code>')
    .replace(/^- (.+)$/gm, '<li style="margin:2px 0">$1</li>')
    .replace(/\n\n/g, '<br><br>')
}

export default function PreviewPanel({ latestOutput, onClose }: PreviewPanelProps) {
  const [mode, setMode] = useState<ViewMode>('output')
  const [htmlInput, setHtmlInput] = useState('')
  const [mdInput, setMdInput] = useState('')
  const iframeRef = useRef<HTMLIFrameElement>(null)

  const renderInIframe = useCallback((html: string) => {
    const doc = iframeRef.current?.contentDocument
    if (!doc) return
    doc.open()
    doc.write(`<!DOCTYPE html><html>
      <head><style>
        body{background:#040d18;color:#a8c4d4;font-family:'JetBrains Mono',monospace;padding:16px;font-size:13px;margin:0}
        a{color:#00d4ff} h1,h2,h3{color:#00d4ff} code{background:#0a1628;padding:2px 6px;border-radius:3px;color:#00d4ff}
        pre{background:#0a1628;padding:12px;border-radius:4px;overflow-x:auto;border:1px solid #0a2540}
        table{width:100%;border-collapse:collapse} td,th{border:1px solid #0a2540;padding:6px 10px;font-size:11px}
        th{background:#0a1628;color:#00d4ff}
      </style></head>
      <body>${html}</body></html>`)
    doc.close()
  }, [])

  const modes: { key: ViewMode; label: string }[] = [
    { key: 'output', label: 'AGENT OUTPUT' },
    { key: 'html', label: 'HTML PREVIEW' },
    { key: 'markdown', label: 'MARKDOWN' },
  ]

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex gap-1">
          {modes.map(m => (
            <button
              key={m.key}
              onClick={() => setMode(m.key)}
              className={`text-[9px] px-2 py-1 rounded tracking-widest transition-colors ${
                mode === m.key
                  ? 'bg-hud-cyan/20 text-hud-cyan border border-hud-cyan/40'
                  : 'text-hud-text/40 hover:text-hud-text/70 border border-transparent'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
        <button onClick={onClose} className="text-hud-text/40 hover:text-red-400 text-lg leading-none">✕</button>
      </div>

      {/* Agent Output mode */}
      {mode === 'output' && (
        <div className="flex-1 overflow-y-auto">
          {latestOutput ? (
            <div
              className="text-[11px] text-hud-text/80 leading-relaxed p-3 hud-panel"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(latestOutput) }}
            />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-hud-text/20 text-[10px] tracking-widest text-center">
              <div className="text-3xl mb-3">◈</div>
              <div>AWAITING AGENT OUTPUT</div>
              <div className="mt-2 text-[9px]">Agent responses will appear here</div>
            </div>
          )}
        </div>
      )}

      {/* HTML Preview mode */}
      {mode === 'html' && (
        <div className="flex-1 flex flex-col gap-2">
          <textarea
            value={htmlInput}
            onChange={e => setHtmlInput(e.target.value)}
            placeholder="Paste HTML here or let the agent generate it…"
            className="h-32 bg-hud-bg border border-hud-border rounded p-2 text-[10px] text-hud-text/80 font-mono resize-none focus:outline-none focus:border-hud-cyan/50 placeholder-hud-text/20"
          />
          <button
            onClick={() => renderInIframe(htmlInput)}
            className="text-[9px] px-3 py-1 border border-hud-cyan/40 text-hud-cyan rounded hover:bg-hud-cyan/10 self-start"
          >
            RENDER
          </button>
          <div className="flex-1 border border-hud-border rounded overflow-hidden min-h-0">
            <iframe
              ref={iframeRef}
              className="w-full h-full"
              sandbox="allow-scripts allow-same-origin"
              title="HTML Preview"
            />
          </div>
        </div>
      )}

      {/* Markdown mode */}
      {mode === 'markdown' && (
        <div className="flex-1 flex flex-col gap-2">
          <textarea
            value={mdInput}
            onChange={e => setMdInput(e.target.value)}
            placeholder="Paste markdown here…"
            className="h-32 bg-hud-bg border border-hud-border rounded p-2 text-[10px] text-hud-text/80 font-mono resize-none focus:outline-none focus:border-hud-cyan/50 placeholder-hud-text/20"
          />
          <div
            className="flex-1 overflow-y-auto hud-panel p-3 text-[11px] leading-relaxed"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(mdInput) || '<span style="color:#2a4a6a">Preview will appear here…</span>' }}
          />
        </div>
      )}
    </div>
  )
}