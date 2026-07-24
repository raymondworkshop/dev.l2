import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, playUsAudio, warmVoices } from '../api'
import WordOverlay from '../components/WordOverlay'

function cleanSurface(w) {
  return w.replace(/^[^A-Za-z']+|[^A-Za-z']+$/g, '')
}

export default function Prep() {
  const { sourceId } = useParams()
  const [data, setData] = useState(null)
  const [bank, setBank] = useState([])
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)
  const [playing, setPlaying] = useState(false)
  const audioRef = useRef(null)

  const bankSet = useMemo(
    () => new Set(bank.filter((e) => e.kind === 'unknown').map((e) => e.surface.toLowerCase())),
    [bank],
  )

  async function load() {
    try {
      const [src, lex] = await Promise.all([api.source(sourceId), api.lexicon()])
      setData(src)
      setBank(lex)
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => {
    warmVoices()
    load()
    return () => {
      window.speechSynthesis?.cancel()
      if (audioRef.current) {
        audioRef.current.pause()
      }
    }
  }, [sourceId])

  const tokens = useMemo(() => {
    const words = data?.transcript?.words
    if (words?.length) return words.map((w) => w.w)
    const text = data?.transcript?.text || ''
    return text.split(/\s+/).filter(Boolean)
  }, [data])

  function stopFull() {
    setPlaying(false)
    window.speechSynthesis?.cancel()
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
    }
  }

  async function playFull() {
    if (playing) {
      stopFull()
      return
    }
    const text = data?.transcript?.text || tokens.join(' ')
    if (data?.audio_url) {
      const a = new Audio(data.audio_url)
      audioRef.current = a
      setPlaying(true)
      a.onended = () => setPlaying(false)
      a.play().catch(() => setPlaying(false))
      return
    }
    setPlaying(true)
    await playUsAudio('', text)
    setPlaying(false)
  }

  if (error) {
    return (
      <div>
        <p className="error">{error}</p>
        <Link to="/">Back to Inbox</Link>
      </div>
    )
  }

  if (!data) {
    return <p className="muted">Loading prep…</p>
  }

  const title = data.meta?.title || 'Prep'

  return (
    <div>
      <h1 className="page-title">{title}</h1>
      <p className="lede">
        Read until the meaning is clear. Tap a word for in-app US audio, IPA, and a Chinese gloss —
        then save 生词. Begin Echo when ready.
      </p>
      <p className="muted" style={{ marginTop: '-1rem', marginBottom: '1.25rem' }}>
        {data.audio_url ? 'Audio ready' : 'No audio file'} ·{' '}
        {data.meta?.has_transcript ? 'Transcript ready' : 'Transcript missing / placeholder'}
        {data.meta?.ingest?.warnings?.length ? ` · ${data.meta.ingest.warnings[0]}` : ''}
      </p>

      <div className="actions" style={{ marginBottom: '1.25rem' }}>
        <button type="button" className="btn" onClick={playFull}>
          {playing ? 'Stop' : 'Play full'}
        </button>
        <Link className="btn btn-soft" to={`/echo/${sourceId}`}>
          Begin Echo
        </Link>
        <Link className="btn btn-ghost" to="/">
          Inbox
        </Link>
      </div>

      <div className="panel transcript">
        {tokens.map((tok, i) => {
          const surface = cleanSurface(tok)
          const inBank = surface && bankSet.has(surface.toLowerCase())
          return (
            <span key={`${i}-${tok}`}>
              <button
                type="button"
                className={`word-token${inBank ? ' in-bank' : ''}${
                  selected?.word === tok && selected?.i === i ? ' active' : ''
                }`}
                onClick={() => surface && setSelected({ word: surface, i, raw: tok })}
                style={{
                  background: 'none',
                  border: 'none',
                  font: 'inherit',
                  color: 'inherit',
                  padding: '0.05em 0.08em',
                }}
              >
                {tok}
              </button>{' '}
            </span>
          )
        })}
      </div>

      {selected ? (
        <WordOverlay
          word={selected.word}
          context={data.transcript?.text?.slice(0, 200) || ''}
          sourceId={sourceId}
          onClose={() => setSelected(null)}
          onSaved={() => load()}
        />
      ) : null}
    </div>
  )
}
