import { NextResponse } from 'next/server'

const MEM0_KEY = process.env.MEM0_API_KEY || ''
const MEM0_BASE = 'https://api.mem0.ai/v1'

async function mem0Get(path: string, body?: object) {
  const r = await fetch(`${MEM0_BASE}${path}`, {
    method: body ? 'POST' : 'GET',
    headers: { Authorization: `Token ${MEM0_KEY}`, 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
    next: { revalidate: 0 },
  })
  if (!r.ok) return null
  return r.json()
}

export async function GET(req: Request) {
  if (!MEM0_KEY) return NextResponse.json({ error: 'MEM0_API_KEY not set' }, { status: 500 })
  const { searchParams } = new URL(req.url)
  const type = searchParams.get('type') || 'list'
  const query = searchParams.get('q') || ''

  try {
    if (type === 'list') {
      const data = await mem0Get('/memories/?user_id=knowledge_base&limit=200')
      const memories = data?.results ?? data ?? []
      // Group by filename
      const files: Record<string, { chunks: number; pages: number }> = {}
      for (const m of memories) {
        const fn = m.metadata?.filename ?? m.memory?.match(/\[([^\]]+) \|/)?.[1] ?? 'unknown'
        if (!files[fn]) files[fn] = { chunks: 0, pages: m.metadata?.pages ?? 0 }
        files[fn].chunks++
      }
      return NextResponse.json({
        total_chunks: memories.length,
        files: Object.entries(files).map(([name, info]) => ({ name, ...info })),
      })
    }

    if (type === 'search') {
      if (!query) return NextResponse.json({ results: [] })
      const data = await mem0Get('/memories/search/', {
        query,
        user_id: 'knowledge_base',
        limit: 8,
      })
      const results = (data?.results ?? data ?? []).map((m: any) => ({
        text: m.memory ?? m.text ?? '',
        score: m.score ?? 0,
        filename: m.metadata?.filename ?? '?',
        chunk: m.metadata?.chunk ?? '?',
      }))
      return NextResponse.json({ results })
    }

    return NextResponse.json({ error: 'Unknown type' }, { status: 400 })
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}