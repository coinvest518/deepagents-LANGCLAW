import { NextResponse } from 'next/server'

const AGENT_URL = process.env.AGENT_API_URL || ''
const SECRET = process.env.DASHBOARD_SECRET || ''

export async function GET(req: Request) {
  if (!AGENT_URL) return NextResponse.json({ messages: [] })

  const { searchParams } = new URL(req.url)
  const threadId = searchParams.get('thread_id')
  if (!threadId) return NextResponse.json({ messages: [], error: 'thread_id required' })

  try {
    const res = await fetch(`${AGENT_URL}/history/${encodeURIComponent(threadId)}`, {
      headers: { ...(SECRET ? { 'X-Dashboard-Secret': SECRET } : {}) },
      next: { revalidate: 0 },
    })
    if (!res.ok) return NextResponse.json({ messages: [] })
    const data = await res.json()
    return NextResponse.json(data)
  } catch {
    return NextResponse.json({ messages: [] })
  }
}