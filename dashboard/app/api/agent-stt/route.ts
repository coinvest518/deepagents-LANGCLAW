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

  let formData: FormData
  try {
    formData = await req.formData()
  } catch {
    return new Response(JSON.stringify({ error: 'Invalid form data' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  const audio = formData.get('audio')
  if (!(audio instanceof Blob)) {
    return new Response(JSON.stringify({ error: 'audio file required' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  const upstream = await fetch(`${AGENT_URL}/stt`, {
    method: 'POST',
    body: formData,
  })

  if (!upstream.ok) {
    const err = await upstream.json().catch(() => ({ error: upstream.statusText }))
    return new Response(JSON.stringify(err), {
      status: upstream.status,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  const data = await upstream.json()
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}
