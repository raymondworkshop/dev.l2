import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'

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
        {error ? (
          <p className="error" style={{ whiteSpace: 'pre-wrap' }}>
            {error}
          </p>
        ) : null}
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

      <h2 className="page-title" style={{ fontSize: '1.35rem', marginTop: '2rem' }}>
        Recent
      </h2>
      <ul className="list">
        {sources.map((s) => (
          <li key={s.id} className="list-item">
            <div>
              <h3>{s.title}</h3>
              <p>
                {s.duration_sec ? `~${s.duration_sec}s` : 'clip'} · {s.accent || 'US'}
                {s.has_audio ? ' · audio' : ' · no audio'}
                {s.has_transcript ? ' · transcript' : ' · no transcript'}
              </p>
            </div>
            <div className="actions">
              <Link className="btn btn-ghost" to={`/prep/${s.id}`}>
                Prep
              </Link>
              <Link className="btn btn-soft" to={`/echo/${s.id}`}>
                Echo
              </Link>
              <button
                type="button"
                className="btn btn-danger"
                onClick={() => removeSource(s.id, s.title)}
              >
                Delete
              </button>
            </div>
          </li>
        ))}
        {!sources.length ? <li className="muted">No clips yet.</li> : null}
      </ul>
    </div>
  )
}
