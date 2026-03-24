import { NextResponse } from 'next/server'

const LS_KEY = process.env.LANGSMITH_API_KEY || ''
const LS_PROJECT = process.env.LANGSMITH_PROJECT || 'deeperagents'
const BASE = 'https://api.smith.langchain.com/api/v1'

// Cache the session UUID so we only look it up once per process.
let _sessionId: string | null = null

async function getSessionId(): Promise<string | null> {
  if (_sessionId) return _sessionId
  const res = await fetch(`${BASE}/sessions?name=${encodeURIComponent(LS_PROJECT)}`, {
    headers: { 'x-api-key': LS_KEY },
    next: { revalidate: 0 },
  })
  if (!res.ok) {
    console.error('LangSmith sessions lookup failed', res.status, await res.text().catch(() => ''))
    return null
  }
  const sessions = await res.json()
  // API returns an array; find exact name match
  const match = Array.isArray(sessions)
    ? sessions.find((s: any) => s.name === LS_PROJECT)
    : null
  _sessionId = match?.id ?? null
  return _sessionId
}

async function ls(path: string, body?: object) {
  const res = await fetch(`${BASE}${path}`, {
    method: body ? 'POST' : 'GET',
    headers: { 'x-api-key': LS_KEY, 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
    next: { revalidate: 0 },
  })
  if (!res.ok) {
    console.error('LangSmith error', res.status, await res.text().catch(() => ''))
    return null
  }
  return res.json()
}

/** Extract model name from the run's metadata / inputs */
function extractModel(r: any): string {
  return (
    r.extra?.metadata?.ls_model_name ||
    r.extra?.metadata?.model_name ||
    r.extra?.invocation_params?.model ||
    r.inputs?.model_name ||
    r.inputs?.model ||
    ''
  )
}

/** Latency in seconds from start_time / end_time strings */
function latency(r: any): number {
  if (!r.start_time || !r.end_time) return 0
  return Math.round((new Date(r.end_time).getTime() - new Date(r.start_time).getTime()) / 100) / 10
}

function mapRun(r: any) {
  return {
    id: r.id,
    name: r.name,
    run_type: r.run_type,
    status: r.status,
    start_time: r.start_time,
    end_time: r.end_time,
    latency_s: latency(r),
    model: extractModel(r),
    total_tokens: r.total_tokens || 0,
    prompt_tokens: r.prompt_tokens || 0,
    completion_tokens: r.completion_tokens || 0,
    error: r.error || null,
    parent_run_id: r.parent_run_id || null,
    // short previews for the activity stream
    inputs_preview: extractInputText(r.inputs),
    outputs_preview: extractOutputText(r.outputs),
  }
}

function extractInputText(inputs: any): string {
  if (!inputs) return ''
  // LangGraph passes messages array
  const msgs = inputs.messages || inputs.input?.messages
  if (Array.isArray(msgs) && msgs.length > 0) {
    const last = msgs[msgs.length - 1]
    const txt = typeof last === 'string' ? last : last?.content
    return String(txt || '').slice(0, 120)
  }
  return JSON.stringify(inputs).slice(0, 120)
}

function extractOutputText(outputs: any): string {
  if (!outputs) return ''
  const msgs = outputs.messages || outputs.output?.messages
  if (Array.isArray(msgs) && msgs.length > 0) {
    const last = msgs[msgs.length - 1]
    const txt = typeof last === 'string' ? last : last?.content
    return String(txt || '').slice(0, 120)
  }
  if (outputs.output) return String(outputs.output).slice(0, 120)
  return JSON.stringify(outputs).slice(0, 120)
}

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url)
  const type = searchParams.get('type') || 'runs'

  if (!LS_KEY) {
    return NextResponse.json({ error: 'LANGSMITH_API_KEY not configured' }, { status: 503 })
  }

  try {
    // Resolve project name → session UUID (cached after first call)
    const sessionId = await getSessionId()
    if (!sessionId) {
      return NextResponse.json(
        { error: `LangSmith project '${LS_PROJECT}' not found. Check LANGSMITH_PROJECT env var.` },
        { status: 404 }
      )
    }

    if (type === 'runs') {
      const data = await ls('/runs/query', {
        session: [sessionId],
        filter: 'eq(is_root, true)',
        limit: 25,
      })
      const runs = (data?.runs || []).map(mapRun)
      return NextResponse.json({ runs, _raw_count: data?.runs?.length ?? 0 })
    }

    if (type === 'stats') {
      const data = await ls('/runs/query', {
        session: [sessionId],
        filter: 'eq(is_root, true)',
        limit: 100,
      })
      const runs: any[] = data?.runs || []
      const totalTokens = runs.reduce((s, r) => s + (r.total_tokens || 0), 0)
      const totalRuns = runs.length
      const errors = runs.filter(r => r.error).length
      const avgTokens = totalRuns ? Math.round(totalTokens / totalRuns) : 0
      const avgLatency = totalRuns
        ? Math.round(runs.reduce((s, r) => s + latency(r), 0) / totalRuns * 10) / 10
        : 0

      // Daily token usage
      const daily: Record<string, number> = {}
      runs.forEach(r => {
        const day = r.start_time?.slice(0, 10)
        if (day) daily[day] = (daily[day] || 0) + (r.total_tokens || 0)
      })
      const chart = Object.entries(daily)
        .sort(([a], [b]) => a.localeCompare(b))
        .slice(-7)
        .map(([date, tokens]) => ({ date: date.slice(5), tokens }))

      // Model usage breakdown
      const modelCounts: Record<string, number> = {}
      runs.forEach(r => {
        const m = extractModel(r)
        if (m) modelCounts[m] = (modelCounts[m] || 0) + 1
      })

      return NextResponse.json({ totalTokens, totalRuns, errors, avgTokens, avgLatency, chart, modelCounts })
    }

    if (type === 'trace') {
      const traceId = searchParams.get('id')
      if (!traceId) return NextResponse.json({ error: 'id required' }, { status: 400 })
      const data = await ls('/runs/query', {
        session: [sessionId],
        filter: `eq(trace_id, "${traceId}")`,
        limit: 100,
      })
      const spans = (data?.runs || []).map(mapRun)
      spans.sort((a: any, b: any) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime())
      return NextResponse.json({ spans, trace_id: traceId })
    }

    if (type === 'status') {
      return NextResponse.json({ connected: true, project: LS_PROJECT, session_id: sessionId })
    }

    return NextResponse.json({ error: 'Unknown type' }, { status: 400 })
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}