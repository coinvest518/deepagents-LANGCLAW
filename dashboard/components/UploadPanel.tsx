'use client'
import { useState, useCallback, useRef } from 'react'

interface DocFile { name: string; chunks: number; pages: number }
interface UploadState { status: 'idle' | 'uploading' | 'done' | 'error'; filename?: string; chunks?: number; words?: number; error?: string; progress?: number }

export default function UploadPanel() {
  const [drag, setDrag] = useState(false)
  const [upload, setUpload] = useState<UploadState>({ status: 'idle' })
  const [docs, setDocs] = useState<DocFile[]>([])
  const [docsLoaded, setDocsLoaded] = useState(false)
  const [search, setSearch] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [searching, setSearching] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const loadDocs = useCallback(async () => {
    const r = await fetch('/api/knowledge?type=list')
    const data = await r.json()
    if (!data.error) { setDocs(data.files ?? []); setDocsLoaded(true) }
  }, [])

  const uploadFile = useCallback(async (file: File) => {
    setUpload({ status: 'uploading', filename: file.name, progress: 0 })
    const form = new FormData()
    form.append('file', file)
    try {
      const r = await fetch('/api/upload', { method: 'POST', body: form })
      const data = await r.json()
      if (data.error) {
        setUpload({ status: 'error', error: data.error })
      } else {
        setUpload({ status: 'done', filename: data.filename, chunks: data.chunks, words: data.words })
        setDocsLoaded(false) // refresh list
      }
    } catch (e: any) {
      setUpload({ status: 'error', error: e.message })
    }
  }, [])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDrag(false)
    const file = e.dataTransfer.files[0]
    if (file) uploadFile(file)
  }, [uploadFile])

  const doSearch = useCallback(async () => {
    if (!search.trim()) return
    setSearching(true)
    const r = await fetch(`/api/knowledge?type=search&q=${encodeURIComponent(search)}`)
    const data = await r.json()
    setSearchResults(data.results ?? [])
    setSearching(false)
  }, [search])

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
        onClick={() => fileRef.current?.click()}
        className={`border-2 border-dashed rounded p-6 text-center cursor-pointer transition-all ${
          drag ? 'border-hud-cyan bg-hud-cyan/10' : 'border-hud-border hover:border-hud-cyan/50'
        }`}
      >
        <input
          ref={fileRef}
          type="file"
          className="hidden"
          accept=".pdf,.txt,.md,.rst,.csv,.json"
          onChange={e => { const f = e.target.files?.[0]; if (f) uploadFile(f) }}
        />
        <div className="text-hud-cyan text-2xl mb-2">⬆</div>
        <div className="text-[11px] text-hud-text/70">Drop PDF, TXT, MD, CSV here</div>
        <div className="text-[9px] text-hud-text/40 mt-1">or click to browse</div>
      </div>

      {/* Upload status */}
      {upload.status === 'uploading' && (
        <div className="hud-panel p-3">
          <div className="flex items-center gap-2 text-[10px] text-hud-cyan">
            <span className="animate-spin">⟳</span>
            <span>Ingesting <span className="font-bold">{upload.filename}</span>…</span>
          </div>
          <div className="mt-2 h-1 bg-hud-border rounded overflow-hidden">
            <div className="h-full bg-hud-cyan animate-pulse w-3/4" />
          </div>
        </div>
      )}
      {upload.status === 'done' && (
        <div className="hud-panel p-3 border-hud-green/40">
          <div className="text-[10px] text-hud-green">
            ✓ <span className="font-bold">{upload.filename}</span> ingested
          </div>
          <div className="text-[9px] text-hud-text/50 mt-1">
            {upload.chunks} chunks · {upload.words?.toLocaleString()} words stored in knowledge base
          </div>
        </div>
      )}
      {upload.status === 'error' && (
        <div className="hud-panel p-3 border-red-500/30">
          <div className="text-[10px] text-red-400">✗ {upload.error}</div>
        </div>
      )}

      {/* Search */}
      <div className="flex gap-2">
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && doSearch()}
          placeholder="Search knowledge base…"
          className="flex-1 bg-hud-bg border border-hud-border rounded px-3 py-1.5 text-[11px] text-hud-text placeholder-hud-text/30 focus:outline-none focus:border-hud-cyan/50"
        />
        <button
          onClick={doSearch}
          className="px-3 py-1.5 text-[10px] border border-hud-cyan/40 text-hud-cyan rounded hover:bg-hud-cyan/10 transition-colors"
        >
          {searching ? '…' : 'SEARCH'}
        </button>
      </div>

      {/* Search results */}
      {searchResults.length > 0 && (
        <div className="space-y-2 max-h-48 overflow-y-auto">
          {searchResults.map((r, i) => (
            <div key={i} className="hud-panel p-2">
              <div className="flex justify-between text-[9px] text-hud-text/50 mb-1">
                <span>{r.filename} · chunk {r.chunk}</span>
                <span className="text-hud-cyan">{(r.score * 100).toFixed(0)}%</span>
              </div>
              <div className="text-[10px] text-hud-text/80 line-clamp-3">{r.text?.slice(0, 200)}</div>
            </div>
          ))}
        </div>
      )}

      {/* Stored docs list */}
      <div>
        <button
          onClick={() => { if (!docsLoaded) loadDocs(); else setDocsLoaded(false) }}
          className="text-[9px] text-hud-cyan/60 hover:text-hud-cyan tracking-widest uppercase"
        >
          {docsLoaded ? '▾ STORED DOCUMENTS' : '▸ VIEW STORED DOCUMENTS'}
        </button>
        {docsLoaded && (
          <div className="mt-2 space-y-1">
            {docs.length === 0 ? (
              <div className="text-[10px] text-hud-text/30">No documents ingested yet</div>
            ) : docs.map((d, i) => (
              <div key={i} className="flex justify-between text-[10px] text-hud-text/70 py-0.5 border-b border-hud-border/30">
                <span className="truncate max-w-[60%]">{d.name}</span>
                <span className="text-hud-text/40">{d.chunks} chunks · {d.pages}p</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}