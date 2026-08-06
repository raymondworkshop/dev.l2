import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'

function displayUrl(raw) {
  try {
    const u = new URL(raw)
    const host = u.hostname.replace(/^www\./, '')
    const path = `${u.pathname}${u.search}`
    const short = path === '/' ? host : `${host}${path}`
    return short.length > 56 ? `${short.slice(0, 53)}…` : short
  } catch {
    return raw.length > 56 ? `${raw.slice(0, 53)}…` : raw
  }
}

export default function Inbox() {
  const navigate = useNavigate()
  const [sources, setSources] = useState([])
  const [url, setUrl] = useState('')
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [lastIngest, setLastIngest] = useState(null)
  /** Older months: user-opened; newest month is always expanded */
  const [openMonths, setOpenMonths] = useState(() => new Set())
  const [playingId, setPlayingId] = useState(null)
  const audioRef = useRef(null)

  async function refresh() {
    try {
      const list = await api.sources()
      setSources(list)
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current = null
      }
    }
  }, [])

  function stopListen() {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
      audioRef.current = null
    }
    setPlayingId(null)
  }

  function listenSource(id) {
    if (playingId === id) {
      stopListen()
      return
    }
    stopListen()
    const a = new Audio(`/api/sources/${id}/audio`)
    audioRef.current = a
    setPlayingId(id)
    a.onended = () => {
      audioRef.current = null
      setPlayingId(null)
    }
    a.onerror = () => {
      audioRef.current = null
      setPlayingId(null)
      setError('Audio failed to play.')
    }
    a.play().catch(() => {
      audioRef.current = null
      setPlayingId(null)
      setError('Audio failed to play.')
    })
  }

  function toggleMonth(key) {
    setOpenMonths((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const groups = useMemo(() => {
    const sorted = [...sources].sort((a, b) =>
      String(b.created || '').localeCompare(String(a.created || '')),
    )
    const buckets = new Map()
    for (const s of sorted) {
      const created = s.created || ''
      const key = created.length >= 7 ? created.slice(0, 7) : '未知'
      if (!buckets.has(key)) buckets.set(key, [])
      buckets.get(key).push(s)
    }
    const keys = [...buckets.keys()].sort((a, b) => {
      if (a === '未知') return 1
      if (b === '未知') return -1
      return b.localeCompare(a)
    })
    return keys.map((key) => {
      const [, y, m] = key.match(/^(\d{4})-(\d{2})$/) || []
      const label = y ? `${y}年${Number(m)}月` : key
      return { key, label, entries: buckets.get(key) }
    })
  }, [sources])

  async function startPrep(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    setLastIngest(null)
    try {
      let meta
      if (text.trim() || url.trim()) {
        setStatus(
          url.trim() && !text.trim()
            ? 'Downloading audio + captions (may take ~1 min)…'
            : 'Saving clip…',
        )
        meta = await api.ingest({
          url: url.trim(),
          title: title.trim(),
          text: text.trim(),
        })
        setLastIngest(meta)
        await refresh()
      } else if (sources[0]) {
        navigate(`/prep/${sources[0].id}`)
        return
      } else {
        setError('Paste a URL and/or transcript, or open a recent clip.')
        return
      }
      navigate(`/prep/${meta.id}`)
    } catch (err) {
      setError(err.message)
      setStatus('')
    } finally {
      setBusy(false)
      setStatus('')
    }
  }

  async function removeSource(id, title) {
    if (!window.confirm(`Delete “${title}”?`)) return
    try {
      if (playingId === id) stopListen()
      await api.deleteSource(id)
      await refresh()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div>
      <h1 className="page-title">Inbox</h1>
      <p className="lede">
        Paste a YouTube URL (audio + captions) or a BBC Learning English episode page (direct
        MP3 + transcript PDF). Or paste transcript text (US neural TTS).
      </p>

      <form className="panel" onSubmit={startPrep}>
        <div className="field">
          <label htmlFor="url">URL</label>
          <input
            id="url"
            placeholder="https://www.youtube.com/watch?v=…"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="title">Title (optional)</label>
          <input
            id="title"
            placeholder="Clip title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="text">Transcript (optional if the URL has captions)</label>
          <textarea
            id="text"
            placeholder="Paste short transcript if captions are missing…"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </div>
        {status ? <p className="muted">{status}</p> : null}
        {error ? <p className="error error-pre">{error}</p> : null}
        {lastIngest?.ingest ? (
          <p className="muted">
            Last ingest — audio: {lastIngest.ingest.audio ? 'yes' : 'no'} · transcript:{' '}
            {lastIngest.ingest.transcript ? 'yes' : 'no'}
            {lastIngest.ingest.warnings?.length
              ? ` · ${lastIngest.ingest.warnings[0]}`
              : ''}
          </p>
        ) : null}
        <div className="actions">
          <button type="submit" className="btn" disabled={busy}>
            {busy ? 'Working…' : 'Start prep'}
          </button>
        </div>
      </form>

      <div className="inbox-months">
        {!groups.length ? (
          <p className="muted">No clips yet.</p>
        ) : (
          groups.map((g, i) => {
            const expanded = i === 0 || openMonths.has(g.key)
            const titleNode = (
              <>
                {g.label} <span className="muted">{g.entries.length}</span>
              </>
            )
            return (
              <section
                key={g.key}
                className={`month-group${expanded ? '' : ' is-collapsed'}`}
              >
                <div className="month-head">
                  <h2>
                    {i === 0 ? (
                      titleNode
                    ) : (
                      <button
                        type="button"
                        className="month-toggle"
                        aria-expanded={expanded}
                        onClick={() => toggleMonth(g.key)}
                      >
                        <span className="month-chevron" aria-hidden>
                          {expanded ? '▾' : '▸'}
                        </span>
                        {titleNode}
                      </button>
                    )}
                  </h2>
                </div>
                {expanded ? (
                  <ul className="list">
                    {g.entries.map((s) => {
                      const isPlaying = playingId === s.id
                      return (
                        <li
                          key={s.id}
                          className={`list-item list-item-stack${isPlaying ? ' is-playing' : ''}`}
                        >
                          <div>
                            <h3>
                              <Link className="clip-title" to={`/prep/${s.id}`}>
                                {s.title}
                              </Link>
                            </h3>
                            <p>
                              {s.duration_sec ? `~${s.duration_sec}s` : 'clip'} ·{' '}
                              {s.accent || 'US'}
                              {s.has_audio ? ' · audio' : ' · no audio'}
                              {s.has_transcript ? ' · transcript' : ' · no transcript'}
                            </p>
                            {s.url ? (
                              <a
                                className="source-url"
                                href={s.url}
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                {displayUrl(s.url)}
                              </a>
                            ) : null}
                          </div>
                          <div className="item-actions">
                            <button
                              type="button"
                              className="btn"
                              disabled={!s.has_audio}
                              onClick={() => listenSource(s.id)}
                            >
                              {isPlaying ? 'Stop' : 'Listen'}
                            </button>
                            <Link className="text-link" to={`/echo/${s.id}`}>
                              Echo
                            </Link>
                            <button
                              type="button"
                              className="text-link text-link-danger"
                              onClick={() => removeSource(s.id, s.title)}
                            >
                              Delete
                            </button>
                          </div>
                        </li>
                      )
                    })}
                  </ul>
                ) : null}
              </section>
            )
          })
        )}
      </div>
    </div>
  )
}
