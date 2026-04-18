'use client'
import { useEffect, useRef, useState, useCallback } from 'react'

// ---------------------------------------------------------------------------
// LiveVoicePanel — full-screen voice HUD. Takes over the chat area while on.
// Pipeline: greeting → listen (Web Speech interim transcript) → on final
//           → streamAgent → TTS (server, with fallback to browser) → loop.
// Barge-in: tap orb during SPEAKING to kill audio and re-open mic.
// ---------------------------------------------------------------------------

type VoiceState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'waiting'

interface Props {
  streamAgent: (msg: string) => Promise<string>
  onExit: () => void
}

// Minimal typing shim for Web Speech API (not in lib.dom until recently)
type SpeechRecognitionAlt = any

export default function LiveVoicePanel({ streamAgent, onExit }: Props) {
  const [state, setState] = useState<VoiceState>('idle')
  const [interim, setInterim] = useState('')
  const [lastUser, setLastUser] = useState('')
  const [lastAgent, setLastAgent] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [provider, setProvider] = useState<string>('')

  const recognizerRef = useRef<SpeechRecognitionAlt | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const activeRef = useRef(true)     // false after onExit — cancels the loop
  const finalRef = useRef('')         // accumulates finalized phrases this turn
  const awaitingTurnRef = useRef(false)

  // ------------------------------------------------------------------
  // TTS: try server (/api/agent-tts), fall back to window.speechSynthesis
  // Returns a promise that resolves when playback ends (or fails).
  // ------------------------------------------------------------------
  const speak = useCallback(async (text: string): Promise<void> => {
    if (!text.trim() || !activeRef.current) return
    setState('speaking')

    // Try server TTS first
    try {
      const res = await fetch('/api/agent-tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })
      if (res.ok) {
        setProvider(res.headers.get('X-TTS-Provider') || 'server')
        const ab = await res.arrayBuffer()
        const url = URL.createObjectURL(new Blob([ab], { type: 'audio/mpeg' }))
        if (audioRef.current) { try { audioRef.current.pause() } catch {} }
        const audio = new Audio(url)
        audioRef.current = audio
        await new Promise<void>((resolve) => {
          audio.onended = () => { URL.revokeObjectURL(url); resolve() }
          audio.onerror = () => { URL.revokeObjectURL(url); resolve() }
          audio.play().catch(() => resolve())
        })
        audioRef.current = null
        return
      }
    } catch {
      // fall through to browser
    }

    // Fallback: browser SpeechSynthesis
    setProvider('browser')
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      await new Promise<void>((resolve) => {
        const utter = new SpeechSynthesisUtterance(text)
        utter.onend = () => resolve()
        utter.onerror = () => resolve()
        window.speechSynthesis.speak(utter)
      })
    }
  }, [])

  const stopSpeaking = useCallback(() => {
    if (audioRef.current) { try { audioRef.current.pause() } catch {}; audioRef.current = null }
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      try { window.speechSynthesis.cancel() } catch {}
    }
  }, [])

  // ------------------------------------------------------------------
  // Listen via Web Speech API. Resolves to the finalized transcript,
  // or '' if cancelled / nothing recognised.
  // ------------------------------------------------------------------
  const listen = useCallback((): Promise<string> => {
    return new Promise((resolve) => {
      const W: any = typeof window !== 'undefined' ? window : {}
      const Ctor = W.SpeechRecognition || W.webkitSpeechRecognition
      if (!Ctor) {
        setError('Your browser does not support live speech recognition. Use Chrome or Edge.')
        resolve('')
        return
      }
      const rec: SpeechRecognitionAlt = new Ctor()
      // continuous=true keeps listening across short pauses; we stop manually
      // when we have a final result. This is more reliable than continuous=false
      // which ends immediately on the first silence window.
      rec.continuous = true
      rec.interimResults = true
      rec.lang = 'en-US'
      finalRef.current = ''
      setInterim('')
      setError(null)

      let sawAnyResult = false

      rec.onstart = () => {
        setState('listening')
        setError(null)
      }

      rec.onaudiostart = () => {
        // Confirms mic is actually capturing — clears any stale "nothing heard" msg
        setError(null)
      }

      rec.onresult = (ev: any) => {
        sawAnyResult = true
        let interimTxt = ''
        let finalTxt = finalRef.current
        for (let i = ev.resultIndex; i < ev.results.length; i++) {
          const r = ev.results[i]
          if (r.isFinal) finalTxt += r[0].transcript
          else interimTxt += r[0].transcript
        }
        finalRef.current = finalTxt
        setInterim(finalTxt + (interimTxt ? ' ' + interimTxt : ''))
        // Auto-stop once we've got a final and user has paused
        if (finalTxt.trim() && !interimTxt) {
          try { rec.stop() } catch {}
        }
      }

      rec.onerror = (ev: any) => {
        const err = ev?.error || 'unknown'
        if (err === 'not-allowed' || err === 'service-not-allowed') {
          setError('Microphone blocked — check browser permission (lock icon in address bar).')
        } else if (err === 'no-speech') {
          // Will retry in the main loop
        } else if (err === 'audio-capture') {
          setError('No microphone detected on this device.')
        } else if (err !== 'aborted') {
          setError(`Mic error: ${err}`)
        }
      }

      rec.onend = () => {
        recognizerRef.current = null
        if (!sawAnyResult && activeRef.current) {
          // Chrome sometimes ends silently on first start; surface that
          setState('waiting')
        }
        resolve(finalRef.current.trim())
      }

      recognizerRef.current = rec
      setState('listening')
      try {
        rec.start()
      } catch (e: any) {
        setError(e?.message || 'Could not start mic')
        resolve('')
      }
    })
  }, [])

  const stopListening = useCallback(() => {
    const rec = recognizerRef.current
    if (rec) { try { rec.stop() } catch {} }
  }, [])

  // ------------------------------------------------------------------
  // Main loop — greet, then listen→think→speak forever until onExit.
  // ------------------------------------------------------------------
  useEffect(() => {
    activeRef.current = true

    const run = async () => {
      // Greeting — let the agent produce a dynamic opener
      awaitingTurnRef.current = true
      setState('thinking')
      setInterim('')
      let greeting = ''
      try {
        greeting = await streamAgent(
          'The user just activated live voice mode. Greet them warmly in one short sentence and ask how you can help.'
        )
      } catch {
        greeting = "Hi, I'm listening — what can I help you with?"
      }
      awaitingTurnRef.current = false
      if (!greeting) greeting = "Hi, I'm listening — what can I help you with?"
      setLastAgent(greeting)
      await speak(greeting)

      let emptyInARow = 0
      while (activeRef.current) {
        setInterim('')
        const userText = await listen()
        if (!activeRef.current) break
        if (!userText) {
          emptyInARow++
          if (emptyInARow >= 2) {
            // Chrome ended silently twice — wait for explicit orb tap
            setState('waiting')
            await new Promise<void>((resolve) => { retryResolveRef.current = resolve })
            emptyInARow = 0
          }
          continue
        }
        emptyInARow = 0
        setLastUser(userText)
        setInterim('')
        setState('thinking')
        awaitingTurnRef.current = true
        let reply = ''
        try {
          reply = await streamAgent(userText)
        } catch (e: any) {
          reply = `Sorry, I hit an error: ${e?.message || e}`
        }
        awaitingTurnRef.current = false
        if (!activeRef.current) break
        setLastAgent(reply)
        await speak(reply)
      }
    }

    run()

    return () => {
      activeRef.current = false
      stopListening()
      stopSpeaking()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Tap orb: barge-in while speaking, OR manually retry listening when waiting
  const retryResolveRef = useRef<(() => void) | null>(null)
  const handleOrbTap = () => {
    if (state === 'speaking') {
      stopSpeaking()
    } else if (state === 'waiting' && retryResolveRef.current) {
      retryResolveRef.current()
      retryResolveRef.current = null
    }
  }

  const handleExit = () => {
    activeRef.current = false
    stopListening()
    stopSpeaking()
    onExit()
  }

  const stateColor = state === 'listening' ? '#00d4ff'
    : state === 'thinking' ? '#ff6b00'
    : state === 'speaking' ? '#00ff88'
    : state === 'waiting' ? '#ffcc00'
    : '#5a6b7a'

  const stateLabel = state === 'waiting' ? 'TAP ORB TO SPEAK' : state.toUpperCase()

  return (
    <div className="flex-1 flex flex-col items-center justify-center min-h-0 px-6 py-8 relative">
      {/* Orb */}
      <div
        onClick={handleOrbTap}
        className={`relative w-48 h-48 rounded-full cursor-pointer transition-all duration-300 ${state === 'listening' ? 'animate-pulse' : ''}`}
        style={{
          background: `radial-gradient(circle, ${stateColor}40 0%, ${stateColor}10 55%, transparent 80%)`,
          boxShadow: `0 0 80px ${stateColor}60, inset 0 0 40px ${stateColor}30`,
          border: `1.5px solid ${stateColor}80`,
        }}
        title={state === 'speaking' ? 'Tap to interrupt' : ''}
      >
        <div
          className="absolute inset-6 rounded-full"
          style={{
            background: `radial-gradient(circle, ${stateColor}30 0%, transparent 70%)`,
            animation: state === 'thinking' ? 'spin 2s linear infinite' : undefined,
          }}
        />
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-[10px] tracking-[0.3em]" style={{ color: stateColor }}>
            {stateLabel}
          </span>
        </div>
      </div>

      {/* Live transcript */}
      <div className="mt-8 max-w-xl w-full text-center min-h-[3rem]">
        {state === 'listening' && interim && (
          <div className="text-[15px] text-hud-cyan/90 leading-snug">
            <span className="opacity-60">"</span>{interim}<span className="opacity-60">"</span>
            <span className="inline-block w-[2px] h-[14px] bg-hud-cyan/70 ml-1 animate-pulse align-middle" />
          </div>
        )}
        {state === 'listening' && !interim && (
          <div className="text-[12px] text-hud-text/40 tracking-widest">SPEAK NOW…</div>
        )}
        {state === 'waiting' && (
          <div className="text-[12px] text-yellow-300/80 tracking-wider">
            Didn't hear anything. Tap the orb and speak.
          </div>
        )}
        {state === 'thinking' && (
          <div className="text-[12px] text-hud-amber/80 tracking-widest">AGENT IS THINKING…</div>
        )}
        {state === 'speaking' && lastAgent && (
          <div className="text-[13px] text-[#00ff88]/80 leading-snug max-h-32 overflow-y-auto">
            {lastAgent}
          </div>
        )}
      </div>

      {/* Last user line */}
      {lastUser && state !== 'listening' && (
        <div className="mt-6 text-[11px] text-hud-text/30 italic max-w-xl text-center">
          you said: “{lastUser}”
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-4 text-[11px] text-red-400 max-w-xl text-center">{error}</div>
      )}

      {/* Exit + provider */}
      <div className="absolute top-2 right-2 flex items-center gap-3">
        {provider && (
          <span className="text-[9px] text-hud-text/30 tracking-widest">TTS: {provider.toUpperCase()}</span>
        )}
        <button
          onClick={handleExit}
          className="px-3 py-1.5 text-[10px] border border-red-500/50 text-red-300 rounded tracking-widest font-medium hover:bg-red-500/10 transition-colors"
        >
          ■ END VOICE
        </button>
      </div>

      <div className="absolute bottom-3 text-[9px] text-hud-text/25 tracking-widest">
        TAP ORB TO INTERRUPT · CLICK END VOICE TO EXIT
      </div>
    </div>
  )
}
