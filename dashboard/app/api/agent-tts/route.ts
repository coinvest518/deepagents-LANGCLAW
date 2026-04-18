export const runtime = 'nodejs'

const LOCAL_DEFAULT = 'http://127.0.0.1:10000'
const AGENT_URL = process.env.AGENT_API_URL || process.env.RENDER_AGENT_URL || (process.env.NODE_ENV !== 'production' ? LOCAL_DEFAULT : '')

export async function POST(req: Request) {
  if (!AGENT_URL) {
    return new Response(JSON.stringify({ error: 'AGENT_API_URL not configured' }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  let body: { text?: string }
  try {
    body = await req.json()
  } catch (error: any) {
    return new Response(JSON.stringify({ error: 'Invalid JSON' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  const text = body.text?.trim()
  if (!text) {
    return new Response(JSON.stringify({ error: 'text required' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  const upstream = await fetch(`${AGENT_URL}/tts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })

  if (!upstream.ok) {
    const err = await upstream.json().catch(() => ({ error: upstream.statusText }))
    return new Response(JSON.stringify(err), {
      status: upstream.status,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  const buffer = await upstream.arrayBuffer()
  const provider = upstream.headers.get('x-tts-provider') || 'unknown'
  return new Response(buffer, {
    status: 200,
    headers: {
      'Content-Type': 'audio/mpeg',
      'X-TTS-Provider': provider,
    },
  })
}
