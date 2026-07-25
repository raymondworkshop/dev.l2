import { useEffect, useState } from 'react'
import { api, cambridgeUrl, youglishUrl } from '../api'
import PronRow from './PronRow'

export default function WordOverlay({ word, context, sourceId, onClose, onSaved }) {
  const [info, setInfo] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    api
      .lookup(word, context)
      .then((data) => {
        if (!cancelled) setInfo(data)
      })
      .catch((e) => {
        if (!cancelled) {
          setInfo({
            surface: word,
            ipa: '',
            audio_url: '',
            gloss_zh: '',
            in_bank: false,
          })
          setError(e.message)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [word, context])

  async function save(kind = 'unknown') {
    if (!info) return
    setSaving(true)
    try {
      const entry = await api.saveWord({
        surface: info.surface || word,
        kind,
        gloss_zh: info.gloss_zh || '',
        ipa: info.ipa_us || info.ipa || '',
        audio_url: info.audio_url_us || info.audio_url || '',
        context: {
          source_id: sourceId || '',
          clause: context || '',
        },
      })
      setInfo((prev) => ({
        ...prev,
        in_bank: kind === 'unknown' ? true : prev.in_bank,
        in_hard: kind === 'hard' ? true : prev.in_hard,
      }))
      onSaved?.(entry)
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const surface = info?.surface || word
  const text = info?.query || word

  return (
    <div className="overlay-backdrop" onClick={onClose} role="presentation">
      <div
        className="overlay-sheet"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label={`Word ${surface}`}
      >
        <h2>{surface}</h2>
        {loading ? (
          <p className="muted">Looking up…</p>
        ) : (
          <>
            <div className="pron-rows">
              <PronRow
                label="美音 US"
                ipa={info?.ipa_us || info?.ipa}
                audioUrl={info?.audio_url_us || info?.audio_url}
                text={text}
                accent="us"
              />
              <PronRow
                label="英音 UK"
                ipa={info?.ipa_uk}
                audioUrl={info?.audio_url_uk}
                text={text}
                accent="uk"
              />
            </div>
            {info?.gloss_zh ? <p className="gloss">{info.gloss_zh}</p> : null}
            {info?.gloss_en ? (
              <p className="gloss gloss-en">
                {info.pos ? <em>{info.pos}. </em> : null}
                {info.gloss_en}
              </p>
            ) : (
              <p className="muted">No English gloss found.</p>
            )}
            {error ? <p className="error">{error}</p> : null}
            <div className="actions">
              <button
                type="button"
                className="btn btn-soft"
                disabled={saving || info?.in_bank}
                onClick={() => save('unknown')}
              >
                {info?.in_bank ? '已收藏' : '加入生詞本'}
              </button>
            </div>
            <p className="secondary-links">
              <a href={cambridgeUrl(surface)} target="_blank" rel="noreferrer">
                Cambridge
              </a>
              {' · '}
              <a href={youglishUrl(surface)} target="_blank" rel="noreferrer">
                YouGlish
              </a>
            </p>
          </>
        )}
      </div>
    </div>
  )
}
