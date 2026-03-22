import { NextResponse } from 'next/server'

const RENDER_URL = process.env.RENDER_AGENT_URL || ''
const SECRET = process.env.DASHBOARD_SECRET || ''

export async function POST(req: Request) {
  if (!RENDER_URL) {
    return NextResponse.json({ error: 'RENDER_AGENT_URL not configured' }, { status: 503 })
  }

  try {
    const { message, thread_id } = await req.json()
    if (!message?.trim()) {
      return NextResponse.json({ error: 'message required' }, { status: 400 })
    }

    const res = await fetch(`${RENDER_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(SECRET ? { 'X-Dashboard-Secret': SECRET } : {}),
      },
      body: JSON.stringify({ message, thread_id: thread_id || 'dashboard-default' }),
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
  if (!RENDER_URL) return NextResponse.json({ status: 'RENDER_AGENT_URL not set' })
  try {
    const res = await fetch(`${RENDER_URL}/health`, { next: { revalidate: 0 } })
    const data = await res.json()
    return NextResponse.json(data)
  } catch {
    return NextResponse.json({ status: 'unreachable' }, { status: 503 })
  }
}