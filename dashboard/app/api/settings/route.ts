import { NextResponse } from 'next/server'

// In development, default to the local backend so `npm run dev` works with
// the Python server running in the repository venv (port 10000).
const LOCAL_DEFAULT = 'http://127.0.0.1:10000'
const AGENT_URL = process.env.AGENT_API_URL || process.env.RENDER_AGENT_URL || (process.env.NODE_ENV !== 'production' ? LOCAL_DEFAULT : '')

export async function GET() {
  if (!AGENT_URL) {
    return NextResponse.json({ error: 'AGENT_API_URL not configured' }, { status: 503 })
  }

  try {
    const res = await fetch(`${AGENT_URL}/settings`, { next: { revalidate: 0 } })
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

export async function POST(req: Request) {
  if (!AGENT_URL) {
    return NextResponse.json({ error: 'AGENT_API_URL not configured' }, { status: 503 })
  }

  try {
    const body = await req.json()
    const res = await fetch(`${AGENT_URL}/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
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
