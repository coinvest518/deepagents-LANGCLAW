import { NextResponse } from 'next/server'

export const runtime = 'nodejs'
export const maxDuration = 60

const MEM0_KEY = process.env.MEM0_API_KEY || ''
const MEM0_BASE = 'https://api.mem0.ai/v2'

function chunkText(text: string, size = 500, overlap = 60): string[] {
  const words = text.split(/\s+/).filter(Boolean)
  const chunks: string[] = []
  let start = 0
  while (start < words.length) {
    chunks.push(words.slice(start, start + size).join(' '))
    start += size - overlap
  }
  return chunks.filter(c => c.trim().length > 0)
}

async function storeMem0(content: string, meta: object): Promise<boolean> {
  if (!MEM0_KEY) return false
  try {
    const r = await fetch(`${MEM0_BASE}/memories/`, {
      method: 'POST',
      headers: { Authorization: `Token ${MEM0_KEY}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: [{ role: 'user', content }],
        user_id: 'knowledge_base',
        metadata: meta,
      }),
    })
    return r.ok
  } catch {
    return false
  }
}

export async function POST(req: Request) {
  try {
    const form = await req.formData()
    const file = form.get('file') as File | null
    if (!file) return NextResponse.json({ error: 'No file provided' }, { status: 400 })

    const filename = file.name
    const ext = filename.split('.').pop()?.toLowerCase() ?? ''
    const allowed = ['pdf', 'txt', 'md', 'rst', 'csv', 'json']
    if (!allowed.includes(ext)) {
      return NextResponse.json({ error: `Unsupported file type: .${ext}` }, { status: 400 })
    }

    const buf = Buffer.from(await file.arrayBuffer())
    let text = ''
    let pages = 1

    if (ext === 'pdf') {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const pdfParse = require('pdf-parse')
      const data = await pdfParse(buf)
      text = data.text
      pages = data.numpages
    } else {
      text = buf.toString('utf-8')
    }

    if (!text.trim()) {
      return NextResponse.json({ error: 'Could not extract text from file' }, { status: 422 })
    }

    const chunks = chunkText(text)
    let stored = 0
    const errors: string[] = []

    for (let i = 0; i < chunks.length; i++) {
      const content = `[${filename} | page ~${Math.floor((i / chunks.length) * pages) + 1} | chunk ${i + 1}/${chunks.length}]\n\n${chunks[i]}`
      const ok = await storeMem0(content, {
        filename,
        chunk: i + 1,
        total_chunks: chunks.length,
        pages,
        ext,
      })
      if (ok) stored++
      else errors.push(`chunk ${i + 1}`)
    }

    return NextResponse.json({
      success: true,
      filename,
      pages,
      chunks: stored,
      total_chunks: chunks.length,
      words: text.split(/\s+/).filter(Boolean).length,
      errors: errors.length ? errors : undefined,
    })
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}
