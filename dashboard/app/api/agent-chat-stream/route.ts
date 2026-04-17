/**
 * SSE streaming proxy — connects the dashboard to the backend's /chat/stream
 * endpoint and pipes Server-Sent Events through to the browser.
 *
 * All messages go straight to the main agent (same as CLI).
 */

const LOCAL_DEFAULT = 'http://127.0.0.1:10000'
const AGENT_URL = process.env.AGENT_API_URL || process.env.RENDER_AGENT_URL || (process.env.NODE_ENV !== 'production' ? LOCAL_DEFAULT : '')

export const runtime = 'nodejs'

export async function POST(req: Request) {
  if (!AGENT_URL) {
    return new Response(JSON.stringify({ error: 'AGENT_API_URL not configured' }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  const { message, thread_id } = await req.json()
  if (!message?.trim()) {
    return new Response(JSON.stringify({ error: 'message required' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  // Call the backend SSE endpoint — straight to main agent
  const upstream = await fetch(`${AGENT_URL}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      thread_id: thread_id || 'dashboard-default',
      source: 'dashboard',
    }),
  })

  if (!upstream.ok) {
    const err = await upstream.text().catch(() => 'Backend error')
    return new Response(JSON.stringify({ error: err }), {
      status: upstream.status,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  // Pipe the SSE stream straight through to the browser
  return new Response(upstream.body, {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  })
}
