import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, cambridgeUrl, playUsAudio, stopAllAudio, warmVoices, youglishUrl } from '../api'
import PronRow from '../components/PronRow'
import WordOverlay from '../components/WordOverlay'

const PLAYLIST_GAP_MS = 550

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

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
  /** Older months: user-opened; newest month is always expanded */
  const [openMonths, setOpenMonths] = useState(() => new Set())
  const [playingMonth, setPlayingMonth] = useState(null)
  const [playingSurface, setPlayingSurface] = useState(null)
  const playGenRef = useRef(0)

  function toggleMonth(key) {
    setOpenMonths((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  function stopMonthPlay() {
    playGenRef.current += 1
    stopAllAudio()
    setPlayingMonth(null)
    setPlayingSurface(null)
  }

  async function playMonth(key, monthEntries) {
    stopMonthPlay()
    const gen = playGenRef.current
    setPlayingMonth(key)
    for (const entry of monthEntries) {
      if (playGenRef.current !== gen) return
      setPlayingSurface(entry.surface)
      const wordKey = `${key}:${entry.surface}`
      const row = [...document.querySelectorAll('[data-word-key]')].find(
        (el) => el.getAttribute('data-word-key') === wordKey,
      )
      row?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
      const result = await playUsAudio(entry.audio_url, entry.surface)
      if (playGenRef.current !== gen || result === 'stopped') return
      await sleep(PLAYLIST_GAP_MS)
      if (playGenRef.current !== gen) return
    }
    if (playGenRef.current === gen) {
      setPlayingMonth(null)
      setPlayingSurface(null)
    }
  }

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
    return () => {
      playGenRef.current += 1
      stopAllAudio()
    }
  }, [])

  useEffect(() => {
    stopMonthPlay()
  }, [filter])

  const groups = useMemo(() => {
    const list = filter === 'all' ? entries : entries.filter((e) => e.kind === filter)
    const sorted = [...list].sort((a, b) =>
      String(b.updated || '').localeCompare(String(a.updated || '')),
    )
    const buckets = new Map()
    for (const e of sorted) {
      const updated = e.updated || ''
      const key = updated.length >= 7 ? updated.slice(0, 7) : '未知'
      if (!buckets.has(key)) buckets.set(key, [])
      buckets.get(key).push(e)
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
  }, [entries, filter])

  async function replay(entry) {
    stopMonthPlay()
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
        手工查詞，或複習生詞 / 錯詞。點「聽列表」可連播本月美音。
      </p>

      <form className="panel lookup-form" onSubmit={onLookup}>
        <div className="field lookup-field">
          <label htmlFor="manual-word">手工輸入單詞</label>
          <div className="actions lookup-row">
            <input
              id="manual-word"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="e.g. vulnerability"
              autoComplete="off"
            />
            <button type="submit" className="btn" disabled={looking || !draft.trim()}>
              {looking ? '查詞…' : '查詞'}
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
              <strong>中</strong> {lookup.gloss_zh || '（暫無中文釋義）'}
            </p>
            <p className="gloss gloss-en">
              <strong>EN</strong>{' '}
              {lookup.pos ? <em>{lookup.pos}. </em> : null}
              {lookup.gloss_en || '（暫無英文釋義）'}
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
                {lookup.in_bank ? '已收藏' : '加入生詞本'}
              </button>
              <button
                type="button"
                className="btn btn-danger"
                disabled={saving || lookup.in_hard}
                onClick={() => saveLookup('hard')}
              >
                {lookup.in_hard ? '已標錯詞' : '標為錯詞'}
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
          ['unknown', '生詞'],
          ['hard', '錯詞'],
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
        {groups[0] ? (
          <button
            type="button"
            className={`chip chip-play${playingMonth === groups[0].key ? ' active' : ''}`}
            onClick={() =>
              playingMonth === groups[0].key
                ? stopMonthPlay()
                : playMonth(groups[0].key, groups[0].entries)
            }
          >
            {playingMonth === groups[0].key ? '停止連播' : '聽列表'}
          </button>
        ) : null}
      </div>

      {error ? <p className="error">{error}</p> : null}

      {!groups.length ? (
        <p className="muted">Empty — 上方手工查詞，或從 Prep / Echo 收藏。</p>
      ) : (
        groups.map((g, i) => {
          const expanded = i === 0 || openMonths.has(g.key)
          const title = (
            <>
              {g.label} <span className="muted">{g.entries.length} words</span>
            </>
          )
          const isPlayingMonth = playingMonth === g.key
          return (
          <section
            key={g.key}
            className={`month-group${expanded ? '' : ' is-collapsed'}`}
          >
            <div className="month-head">
              <h2>
                {i === 0 ? (
                  title
                ) : (
                  <button
                    type="button"
                    className="month-toggle"
                    aria-expanded={expanded}
                    onClick={() => {
                      if (isPlayingMonth && expanded) stopMonthPlay()
                      toggleMonth(g.key)
                    }}
                  >
                    <span className="month-chevron" aria-hidden>
                      {expanded ? '▾' : '▸'}
                    </span>
                    {title}
                  </button>
                )}
              </h2>
              {expanded ? (
                <button
                  type="button"
                  className="btn month-play"
                  aria-pressed={isPlayingMonth}
                  onClick={() =>
                    isPlayingMonth ? stopMonthPlay() : playMonth(g.key, g.entries)
                  }
                >
                  {isPlayingMonth ? '停止' : '聽列表'}
                </button>
              ) : null}
            </div>
            {expanded ? (
            <ul className="list">
              {g.entries.map((e) => {
                const biteId = e.context?.bite_id
                const sourceId = e.context?.source_id
                const active = isPlayingMonth && playingSurface === e.surface
                return (
                  <li
                    key={`${e.kind}-${e.surface}-${e.updated}`}
                    className={`list-item${active ? ' is-playing' : ''}`}
                    data-word-key={`${g.key}:${e.surface}`}
                  >
                    <div>
                      <h3>
                        <button
                          type="button"
                          className="word-link"
                          onClick={() => setSelected(e.surface)}
                        >
                          {e.surface}
                        </button>
                      </h3>
                      <p>
                        {e.kind === 'hard' ? '錯詞' : '生詞'}
                        {e.ipa ? ` · ${e.ipa}` : ''}
                        {e.gloss_zh ? ` · ${e.gloss_zh}` : ''}
                      </p>
                    </div>
                    <div className="actions">
                      <button type="button" className="btn btn-soft" onClick={() => replay(e)}>
                        Listen
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
                      <button
                        type="button"
                        className="btn btn-danger"
                        onClick={() => removeEntry(e)}
                      >
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
                      <a
                        className="muted"
                        href={youglishUrl(e.surface)}
                        target="_blank"
                        rel="noreferrer"
                      >
                        YouGlish
                      </a>
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
