import { NextResponse } from 'next/server'

// In development, default to the local backend so `npm run dev` works with
// the Python server running in the repository venv (e.g. http://127.0.0.1:10000).
const LOCAL_DEFAULT = 'http://127.0.0.1:10000'
const AGENT_URL = process.env.AGENT_API_URL || process.env.RENDER_AGENT_URL || (process.env.NODE_ENV !== 'production' ? LOCAL_DEFAULT : '')


export async function POST(req: Request) {
  if (!AGENT_URL) {
    return NextResponse.json({ error: 'AGENT_API_URL not configured' }, { status: 503 })
  }

  try {
    const { message, thread_id } = await req.json()
    if (!message?.trim()) {
      return NextResponse.json({ error: 'message required' }, { status: 400 })
    }

    const res = await fetch(`${AGENT_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message, thread_id: thread_id || 'dashboard-default', source: 'dashboard' }),
    })

    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: res.statusText }))
      return NextResponse.json(err, { status: res.status })
    }

    const data = await res.json()
    return NextResponse.json(data)
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}

export async function GET() {
  if (!AGENT_URL) return NextResponse.json({ status: 'AGENT_API_URL not set' })
  try {
    const res = await fetch(`${AGENT_URL}/health`, { next: { revalidate: 0 } })
    const data = await res.json()
    return NextResponse.json(data)
  } catch {
    return NextResponse.json({ status: 'unreachable' }, { status: 503 })
  }
}
