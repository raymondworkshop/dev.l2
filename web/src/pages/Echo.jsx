import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api, playUsAudio, warmVoices } from '../api'

const SESSION_MS = 10 * 60 * 1000
const ECHO_PAUSE_MS = 1400

function formatTime(ms) {
  const s = Math.max(0, Math.ceil(ms / 1000))
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${m}:${String(r).padStart(2, '0')}`
}

function cleanToken(w) {
  return (w || '').replace(/^[^A-Za-z']+|[^A-Za-z']+$/g, '')
}

export default function Echo() {
  const { sourceId } = useParams()
  const [search] = useSearchParams()
  const navigate = useNavigate()
  const startBite = Number(search.get('bite') || 0)

  const [data, setData] = useState(null)
  const [biteIndex, setBiteIndex] = useState(startBite)
  const [phase, setPhase] = useState('idle') // idle | play | echo | speak
  const [remaining, setRemaining] = useState(SESSION_MS)
  const [error, setError] = useState('')
  const [hardMsg, setHardMsg] = useState('')
  /** Selected token indexes within the current bite (for 标错词). */
  const [selected, setSelected] = useState([])

  const endAt = useRef(Date.now() + SESSION_MS)
  const timers = useRef([])
  const audioRef = useRef(null)

  const bites = data?.bites || []
  const bite = bites[biteIndex]
  const tokens = useMemo(() => {
    if (bite?.tokens?.length) return bite.tokens
    return (bite?.text || '').split(/\s+/).filter(Boolean)
  }, [bite])

  const clearTimers = () => {
    timers.current.forEach((t) => clearTimeout(t))
    timers.current = []
    window.speechSynthesis?.cancel()
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
  }

  useEffect(() => {
    warmVoices()
    api
      .source(sourceId)
      .then((src) => {
        setData(src)
        const idx = Math.min(Math.max(0, startBite), Math.max(0, (src.bites?.length || 1) - 1))
        setBiteIndex(idx)
      })
      .catch((e) => setError(e.message))
  }, [sourceId, startBite])

  useEffect(() => {
    setSelected([])
    setHardMsg('')
  }, [biteIndex])

  useEffect(() => {
    endAt.current = Date.now() + SESSION_MS
    const id = setInterval(() => {
      const left = endAt.current - Date.now()
      setRemaining(left)
      if (left <= 0) {
        clearInterval(id)
        clearTimers()
        setPhase('done')
      }
    }, 250)
    return () => {
      clearInterval(id)
      clearTimers()
    }
  }, [])

  const playBiteAudio = useCallback(
    (text, start, end) =>
      new Promise((resolve) => {
        if (data?.audio_url && typeof start === 'number' && typeof end === 'number') {
          const a = new Audio(data.audio_url)
          audioRef.current = a
          a.currentTime = Math.max(0, start)
          const onTime = () => {
            if (a.currentTime >= end) {
              a.pause()
              a.removeEventListener('timeupdate', onTime)
              resolve('audio')
            }
          }
          a.addEventListener('timeupdate', onTime)
          a.onended = () => resolve('audio')
          a.play().catch(() => {
            playUsAudio('', text).then(resolve)
          })
          timers.current.push(
            setTimeout(() => {
              a.pause()
              resolve('audio')
            }, Math.max(800, (end - start) * 1000 + 400)),
          )
          return
        }
        playUsAudio('', text).then(resolve)
      }),
    [data],
  )

  const runCycle = useCallback(async () => {
    if (!bite || remaining <= 0) return
    clearTimers()
    setPhase('play')
    await playBiteAudio(bite.text, bite.start, bite.end)
    if (endAt.current - Date.now() <= 0) {
      setPhase('done')
      return
    }
    setPhase('echo')
    await new Promise((r) => {
      timers.current.push(setTimeout(r, ECHO_PAUSE_MS))
    })
    if (endAt.current - Date.now() <= 0) {
      setPhase('done')
      return
    }
    setPhase('speak')
  }, [bite, playBiteAudio, remaining])

  function phaseLabel() {
    switch (phase) {
      case 'play':
        return 'Playing…'
      case 'echo':
        return '听回音…'
      case 'speak':
        return 'Speak — imitate the echo'
      case 'done':
        return 'Time’s up — nice work'
      default:
        return 'Ready — tap words to mark 错词'
    }
  }

  function toggleToken(i) {
    setHardMsg('')
    setSelected((prev) => {
      if (prev.includes(i)) return prev.filter((x) => x !== i)
      // Keep selection as a contiguous span when possible
      if (!prev.length) return [i]
      const sorted = [...prev].sort((a, b) => a - b)
      const lo = sorted[0]
      const hi = sorted[sorted.length - 1]
      if (i === lo - 1 || i === hi + 1) return [...prev, i]
      // Jump: start a new selection
      return [i]
    })
  }

  const selectedSurface = useMemo(() => {
    if (!selected.length) return ''
    const sorted = [...selected].sort((a, b) => a - b)
    return sorted
      .map((i) => cleanToken(tokens[i]))
      .filter(Boolean)
      .join(' ')
  }, [selected, tokens])

  async function markHard() {
    if (!bite) return
    setHardMsg('')
    if (!selectedSurface) {
      setHardMsg('先点选句中的词（可连点组成短语），再标错词')
      return
    }
    try {
      await api.saveWord({
        surface: selectedSurface,
        kind: 'hard',
        gloss_zh: '',
        context: {
          source_id: sourceId,
          bite_id: bite.id,
          timestamp: bite.start,
          clause: bite.text,
        },
      })
      setHardMsg(`已标错词：${selectedSurface}`)
      setSelected([])
    } catch (e) {
      setHardMsg(e.message)
    }
  }

  function nextBite() {
    clearTimers()
    setHardMsg('')
    setBiteIndex((i) => Math.min(i + 1, bites.length - 1))
    setPhase('idle')
  }

  function prevBite() {
    clearTimers()
    setHardMsg('')
    setBiteIndex((i) => Math.max(i - 1, 0))
    setPhase('idle')
  }

  function stopCycle() {
    clearTimers()
    setPhase('idle')
  }

  const canPrev = biteIndex > 0
  const canNext = biteIndex < bites.length - 1
  const busy = phase === 'play' || phase === 'echo'

  if (error) {
    return (
      <div>
        <p className="error">{error}</p>
        <Link to="/">Inbox</Link>
      </div>
    )
  }

  if (!data) return <p className="muted">Loading session…</p>

  return (
    <div>
      <div className="actions" style={{ justifyContent: 'space-between', marginBottom: '0.5rem' }}>
        <Link className="btn btn-ghost" to={`/prep/${sourceId}`}>
          Prep
        </Link>
        <span className="timer" aria-live="polite">
          {phase === 'done' ? '0:00' : formatTime(remaining)}
        </span>
      </div>

      <h1 className="page-title" style={{ fontSize: '1.4rem' }}>
        {data.meta?.title || 'Echo'}
      </h1>
      <p className="muted" style={{ marginTop: 0 }}>
        Sentence {bites.length ? biteIndex + 1 : 0} / {bites.length} · 按停顿/句号切分 · 点词再标错词
      </p>

      <div className="panel echo-stage">
        <p className="echo-bite echo-bite-tokens">
          {tokens.map((tok, i) => (
            <button
              key={`${i}-${tok}`}
              type="button"
              className={`echo-token${selected.includes(i) ? ' is-selected' : ''}`}
              onClick={() => toggleToken(i)}
            >
              {tok}
            </button>
          ))}
        </p>
        <p className={`echo-phase${phase === 'echo' ? ' is-echo' : ''}`}>{phaseLabel()}</p>
        {selectedSurface ? (
          <p className="muted">
            将标为错词：<strong>{selectedSurface}</strong>
          </p>
        ) : null}

        {phase === 'done' ? (
          <div className="actions">
            <button type="button" className="btn" onClick={() => navigate('/bank')}>
              Word
            </button>
            <Link className="btn btn-ghost" to="/">
              Inbox
            </Link>
          </div>
        ) : (
          <div className="actions" style={{ justifyContent: 'center' }}>
            {busy ? (
              <button type="button" className="btn btn-ghost" onClick={stopCycle}>
                Stop
              </button>
            ) : (
              <>
                <button type="button" className="btn" onClick={runCycle}>
                  Play
                </button>
                <button type="button" className="btn btn-ghost" onClick={runCycle}>
                  Loop
                </button>
              </>
            )}
            <button type="button" className="btn btn-ghost" disabled={!canPrev} onClick={prevBite}>
              Prev
            </button>
            <button type="button" className="btn btn-soft" disabled={!canNext} onClick={nextBite}>
              Next
            </button>
            <button type="button" className="btn btn-danger" onClick={markHard}>
              标错词
            </button>
          </div>
        )}
        {hardMsg ? <p className="muted">{hardMsg}</p> : null}
      </div>
    </div>
  )
}
