"use client"

import React, { useEffect, useState } from 'react'

type SettingsResp = {
  agent_model?: string
  auto_approve?: boolean
  agent_api_url?: string
  ollama?: Record<string, unknown>
  langsmith?: Record<string, unknown>
  mcp_configs?: string[]
  skills?: { built_in?: string[]; project?: string[]; user?: string[] }
}

export default function SettingsPage() {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState<SettingsResp | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchSettings()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function fetchSettings() {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/settings')
      if (!res.ok) throw new Error(await res.text())
      const json = await res.json()
      setData(json)
    } catch (e: any) {
      setError(e.message || String(e))
    } finally {
      setLoading(false)
    }
  }

  async function update(partial: Record<string, unknown>) {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(partial),
      })
      if (!res.ok) throw new Error(await res.text())
      const json = await res.json()
      setData(json)
    } catch (e: any) {
      setError(e.message || String(e))
    } finally {
      setLoading(false)
    }
  }

  if (loading && !data) return <div className="p-4">Loading settings…</div>

  if (error) return <div className="p-4 text-red-600">Error: {error}</div>

  return (
    <div className="p-4">
      <h1 className="text-2xl font-semibold">Agent Settings</h1>
      <div className="mt-4 space-y-3">
        <div>
          <strong>Agent model:</strong> {data?.agent_model || '—'}
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={!!data?.auto_approve}
              onChange={(e) => update({ auto_approve: e.target.checked })}
            />
            Auto-approve saves
          </label>
        </div>
        <div>
          <button
            className="px-3 py-1 border rounded"
            onClick={() => update({ reload_env: true })}
          >
            Reload env
          </button>
          <button
            className="ml-3 px-3 py-1 border rounded"
            onClick={() => fetchSettings()}
          >
            Refresh
          </button>
        </div>

        <div className="mt-4">
          <h2 className="font-medium">Discovered Info</h2>
          <div className="mt-2">
            <strong>Agent API URL:</strong> {data?.agent_api_url || '—'}
          </div>
          <div className="mt-2">
            <strong>Ollama:</strong> {data?.ollama ? 'available' : 'not configured'}
          </div>
          <div className="mt-2">
            <strong>LangSmith:</strong> {data?.langsmith ? 'available' : 'not configured'}
          </div>
          <div className="mt-2">
            <strong>MCP configs:</strong>
            <ul className="list-disc ml-6">
              {(data?.mcp_configs || []).map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </div>
          <div className="mt-2">
            <strong>Skills:</strong>
            <div className="ml-4">
              <div>Built-in: {(data?.skills?.built_in || []).join(', ') || '—'}</div>
              <div>Project: {(data?.skills?.project || []).join(', ') || '—'}</div>
              <div>User: {(data?.skills?.user || []).join(', ') || '—'}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
