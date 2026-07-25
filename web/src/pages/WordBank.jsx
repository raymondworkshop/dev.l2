import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, cambridgeUrl, playUsAudio, warmVoices, youglishUrl } from '../api'
import PronRow from '../components/PronRow'
import WordOverlay from '../components/WordOverlay'

export default function WordBank() {
  const [entries, setEntries] = useState([])
  const [filter, setFilter] = useState('all') // all | unknown | hard
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)

  const [draft, setDraft] = useState('')
  const [lookup, setLookup] = useState(null)
  const [looking, setLooking] = useState(false)
  const [saving, setSaving] = useState(false)
  const [lookupError, setLookupError] = useState('')

  async function load() {
    try {
      const list = await api.lexicon()
      setEntries(list)
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => {
    warmVoices()
    load()
  }, [])

  const shown = useMemo(() => {
    if (filter === 'all') return entries
    return entries.filter((e) => e.kind === filter)
  }, [entries, filter])

  async function replay(entry) {
    await playUsAudio(entry.audio_url, entry.surface)
  }

  async function removeEntry(entry) {
    if (!window.confirm(`Delete “${entry.surface}”?`)) return
    try {
      await api.removeWord({ surface: entry.surface, kind: entry.kind })
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  async function onLookup(e) {
    e?.preventDefault?.()
    const word = draft.trim()
    if (!word) return
    setLooking(true)
    setLookupError('')
    setLookup(null)
    try {
      const info = await api.lookup(word)
      setLookup(info)
    } catch (err) {
      setLookupError(err.message)
    } finally {
      setLooking(false)
    }
  }

  async function saveLookup(kind = 'unknown') {
    if (!lookup) return
    setSaving(true)
    try {
      await api.saveWord({
        surface: lookup.surface || draft.trim(),
        kind,
        gloss_zh: lookup.gloss_zh || '',
        ipa: lookup.ipa_us || lookup.ipa || '',
        audio_url: lookup.audio_url_us || lookup.audio_url || '',
        context: { source_id: '', clause: 'manual' },
      })
      setLookup((prev) =>
        prev
          ? {
              ...prev,
              in_bank: kind === 'unknown' ? true : prev.in_bank,
              in_hard: kind === 'hard' ? true : prev.in_hard,
            }
          : prev,
      )
      await load()
    } catch (err) {
      setLookupError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <h1 className="page-title">Word</h1>
      <p className="lede">
        手工查词，或复习生词 / 错词：听美音与英音，看中英文释义。
      </p>

      <form className="panel lookup-form" onSubmit={onLookup}>
        <div className="field lookup-field">
          <label htmlFor="manual-word">手工输入单词</label>
          <div className="actions lookup-row">
            <input
              id="manual-word"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="e.g. vulnerability"
              autoComplete="off"
            />
            <button type="submit" className="btn" disabled={looking || !draft.trim()}>
              {looking ? '查词…' : '查词'}
            </button>
          </div>
        </div>

        {lookupError ? <p className="error">{lookupError}</p> : null}

        {lookup ? (
          <div className="lookup-card">
            <h2 className="lookup-word">{lookup.surface || draft}</h2>
            <div className="pron-rows">
              <PronRow
                label="美音 US"
                ipa={lookup.ipa_us || lookup.ipa}
                audioUrl={lookup.audio_url_us || lookup.audio_url}
                text={lookup.query || draft}
                accent="us"
              />
              <PronRow
                label="英音 UK"
                ipa={lookup.ipa_uk}
                audioUrl={lookup.audio_url_uk}
                text={lookup.query || draft}
                accent="uk"
              />
            </div>
            <p className="gloss">
              <strong>中</strong> {lookup.gloss_zh || '（暂无中文释义）'}
            </p>
            <p className="gloss gloss-en">
              <strong>EN</strong>{' '}
              {lookup.pos ? <em>{lookup.pos}. </em> : null}
              {lookup.gloss_en || '（暂无英文释义）'}
            </p>
            {(lookup.glosses_en || []).slice(1, 3).map((g, i) => (
              <p key={i} className="gloss gloss-en muted">
                {g.pos ? <em>{g.pos}. </em> : null}
                {g.definition}
              </p>
            ))}
            <div className="actions lookup-actions">
              <button
                type="button"
                className="btn btn-soft"
                disabled={saving || lookup.in_bank}
                onClick={() => saveLookup('unknown')}
              >
                {lookup.in_bank ? '已收藏' : '加入生词本'}
              </button>
              <button
                type="button"
                className="btn btn-danger"
                disabled={saving || lookup.in_hard}
                onClick={() => saveLookup('hard')}
              >
                {lookup.in_hard ? '已标错词' : '标为错词'}
              </button>
            </div>
            <p className="secondary-links">
              <a href={cambridgeUrl(lookup.surface || draft)} target="_blank" rel="noreferrer">
                Cambridge
              </a>
              {' · '}
              <a href={youglishUrl(lookup.surface || draft)} target="_blank" rel="noreferrer">
                YouGlish
              </a>
            </p>
          </div>
        ) : null}
      </form>

      <div className="filters">
        {[
          ['all', '全部'],
          ['unknown', '生词'],
          ['hard', '错词'],
        ].map(([k, label]) => (
          <button
            key={k}
            type="button"
            className={`chip${filter === k ? ' active' : ''}`}
            onClick={() => setFilter(k)}
          >
            {label}
          </button>
        ))}
      </div>

      {error ? <p className="error">{error}</p> : null}

      <ul className="list">
        {shown.map((e) => {
          const biteId = e.context?.bite_id
          const sourceId = e.context?.source_id
          return (
            <li key={`${e.kind}-${e.surface}-${e.updated}`} className="list-item">
              <div>
                <h3>
                  <button type="button" className="word-link" onClick={() => setSelected(e.surface)}>
                    {e.surface}
                  </button>
                </h3>
                <p>
                  {e.kind === 'hard' ? '错词' : '生词'}
                  {e.ipa ? ` · ${e.ipa}` : ''}
                  {e.gloss_zh ? ` · ${e.gloss_zh}` : ''}
                </p>
              </div>
              <div className="actions">
                <button type="button" className="btn btn-soft" onClick={() => replay(e)}>
                  再听
                </button>
                {sourceId != null && sourceId !== '' ? (
                  <Link
                    className="btn btn-ghost"
                    to={
                      biteId != null
                        ? `/echo/${sourceId}?bite=${biteId}`
                        : `/prep/${sourceId}`
                    }
                  >
                    Open bite
                  </Link>
                ) : null}
                <button type="button" className="btn btn-danger" onClick={() => removeEntry(e)}>
                  Delete
                </button>
                <a
                  className="muted"
                  href={cambridgeUrl(e.surface)}
                  target="_blank"
                  rel="noreferrer"
                >
                  Cambridge
                </a>
                <a className="muted" href={youglishUrl(e.surface)} target="_blank" rel="noreferrer">
                  YouGlish
                </a>
              </div>
            </li>
          )
        })}
        {!shown.length ? (
          <li className="muted">Empty — 上方手工查词，或从 Prep / Echo 收藏。</li>
        ) : null}
      </ul>

      {selected ? (
        <WordOverlay
          word={selected}
          context=""
          sourceId=""
          onClose={() => setSelected(null)}
          onSaved={() => load()}
        />
      ) : null}
    </div>
  )
}
