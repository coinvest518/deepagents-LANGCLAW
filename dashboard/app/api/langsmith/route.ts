import { NextResponse } from 'next/server'

const LS_KEY = process.env.LANGSMITH_API_KEY || ''
const LS_PROJECT = process.env.LANGSMITH_PROJECT || 'deeperagents'
const BASE = 'https://api.smith.langchain.com/api/v1'

async function ls(path: string, body?: object) {
  const res = await fetch(`${BASE}${path}`, {
    method: body ? 'POST' : 'GET',
    headers: { 'x-api-key': LS_KEY, 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
    next: { revalidate: 0 },
  })
  if (!res.ok) return null
  return res.json()
}

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url)
  const type = searchParams.get('type') || 'runs'

  try {
    if (type === 'runs') {
      const data = await ls('/runs/query', {
        session_name: LS_PROJECT,
        limit: 20,
        order: 'desc',
      })
      const runs = (data?.runs || []).map((r: any) => ({
        id: r.id,
        name: r.name,
        run_type: r.run_type,
        status: r.status,
        start_time: r.start_time,
        end_time: r.end_time,
        total_tokens: r.total_tokens || 0,
        prompt_tokens: r.prompt_tokens || 0,
        completion_tokens: r.completion_tokens || 0,
        error: r.error,
        parent_run_id: r.parent_run_id,
        inputs_preview: JSON.stringify(r.inputs)?.slice(0, 120),
        outputs_preview: JSON.stringify(r.outputs)?.slice(0, 120),
      }))
      return NextResponse.json({ runs })
    }

    if (type === 'stats') {
      // Aggregate token usage over last 7 days
      const data = await ls('/runs/query', {
        session_name: LS_PROJECT,
        limit: 100,
        order: 'desc',
      })
      const runs = data?.runs || []
      const totalTokens = runs.reduce((s: number, r: any) => s + (r.total_tokens || 0), 0)
      const totalRuns = runs.length
      const errors = runs.filter((r: any) => r.error).length
      const avgTokens = totalRuns ? Math.round(totalTokens / totalRuns) : 0

      // Daily token usage (last 7 days)
      const daily: Record<string, number> = {}
      runs.forEach((r: any) => {
        const day = r.start_time?.slice(0, 10)
        if (day) daily[day] = (daily[day] || 0) + (r.total_tokens || 0)
      })
      const chart = Object.entries(daily)
        .sort(([a], [b]) => a.localeCompare(b))
        .slice(-7)
        .map(([date, tokens]) => ({ date: date.slice(5), tokens }))

      return NextResponse.json({ totalTokens, totalRuns, errors, avgTokens, chart })
    }

    if (type === 'active') {
      const data = await ls('/runs/query', {
        session_name: LS_PROJECT,
        limit: 5,
        filter: 'and(eq(status, "running"))',
      })
      return NextResponse.json({ runs: data?.runs || [] })
    }

    return NextResponse.json({ error: 'Unknown type' }, { status: 400 })
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}
