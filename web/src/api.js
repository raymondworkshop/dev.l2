const BASE = ''

async function req(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || res.statusText)
  return data
}

export const api = {
  sources: () => req('/api/sources'),
  source: (id) => req(`/api/sources/${id}`),
  deleteSource: (id) => req(`/api/sources/${id}`, { method: 'DELETE' }),
  ingest: (body) => req('/api/ingest', { method: 'POST', body: JSON.stringify(body) }),
  lexicon: (kind) => req(kind ? `/api/lexicon?kind=${kind}` : '/api/lexicon'),
  saveWord: (body) => req('/api/lexicon', { method: 'POST', body: JSON.stringify(body) }),
  removeWord: (body) =>
    req('/api/lexicon', { method: 'DELETE', body: JSON.stringify(body) }),
  lookup: (word, context = '') =>
    req(`/api/lookup?word=${encodeURIComponent(word)}&context=${encodeURIComponent(context)}`),
}

const NOVELTY =
  /albert|bad news|bahh|bells|boing|bubbles|cellos|wobble|zarvox|trinoids|whisper|good news|jester|organ|superstar|kathy \(premium\)/i

const PREFERRED = [
  /jenny/i,
  /aria/i,
  /ava/i,
  /samantha/i,
  /siri.*american/i,
  /google us english/i,
  /microsoft (aria|jenny|guy|davis|nancy)/i,
  /natural/i,
  /enhanced/i,
  /premium/i,
  /nicky/i,
  /aaron/i,
  /susan/i,
]

function pickVoice(langPrefix) {
  const voices = window.speechSynthesis?.getVoices?.() || []
  const matched = voices.filter(
    (v) => new RegExp(langPrefix, 'i').test(v.lang) && !NOVELTY.test(v.name),
  )
  if (!matched.length) return null
  if (/en-US|en_US/i.test(langPrefix)) {
    for (const re of PREFERRED) {
      const hit = matched.find((v) => re.test(v.name))
      if (hit) return hit
    }
  }
  const local = matched.find((v) => v.localService)
  return local || matched[0]
}

function pickUsVoice() {
  return pickVoice('en-US|en_US')
}

/** Ensure voice list is loaded (Chrome loads async). */
export function warmVoices() {
  if (!window.speechSynthesis) return
  window.speechSynthesis.getVoices()
  window.speechSynthesis.onvoiceschanged = () => {
    window.speechSynthesis.getVoices()
  }
}

let currentAudio = null
let finishPlay = null

function finishCurrent(result) {
  const fn = finishPlay
  finishPlay = null
  currentAudio = null
  if (fn) fn(result)
}

/** Stop dictionary audio / TTS; resolves any in-flight play promise with `'stopped'`. */
export function stopAllAudio() {
  if (currentAudio) {
    currentAudio.onended = null
    currentAudio.onerror = null
    try {
      currentAudio.pause()
      currentAudio.removeAttribute('src')
      currentAudio.load()
    } catch {
      /* ignore */
    }
    currentAudio = null
  }
  window.speechSynthesis?.cancel()
  finishCurrent('stopped')
}

/** Play dictionary audio URL, else TTS for lang (en-US / en-GB). */
export function playAccentAudio(audioUrl, text, lang = 'en-US') {
  return new Promise((resolve) => {
    stopAllAudio()
    finishPlay = resolve
    if (audioUrl) {
      const a = new Audio(audioUrl)
      currentAudio = a
      a.onended = () => finishCurrent('audio')
      a.onerror = () => {
        currentAudio = null
        speakTts(text, lang).then((r) => finishCurrent(r))
      }
      a.play().catch(() => {
        currentAudio = null
        speakTts(text, lang).then((r) => finishCurrent(r))
      })
      return
    }
    speakTts(text, lang).then((r) => finishCurrent(r))
  })
}

/** Play dictionary US audio, else browser TTS with a natural en-US voice. */
export function playUsAudio(audioUrl, text) {
  return playAccentAudio(audioUrl, text, 'en-US')
}

function speakTts(text, lang = 'en-US') {
  return new Promise((resolve) => {
    if (!window.speechSynthesis || !text) {
      resolve('none')
      return
    }
    window.speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text)
    u.lang = lang.startsWith('en-GB') || lang.startsWith('en-UK') ? 'en-GB' : 'en-US'
    u.rate = 0.95
    u.pitch = 1
    const voice = pickVoice(u.lang === 'en-GB' ? 'en-GB|en_GB|en-UK' : 'en-US|en_US')
    if (voice) u.voice = voice
    u.onend = () => resolve('tts')
    u.onerror = () => resolve('tts-error')
    if (!voice && window.speechSynthesis.getVoices().length === 0) {
      const once = () => {
        window.speechSynthesis.onvoiceschanged = null
        const v = pickVoice(u.lang === 'en-GB' ? 'en-GB|en_GB|en-UK' : 'en-US|en_US')
        if (v) u.voice = v
        window.speechSynthesis.speak(u)
      }
      window.speechSynthesis.onvoiceschanged = once
      window.speechSynthesis.getVoices()
      setTimeout(() => {
        if (!window.speechSynthesis.speaking && !window.speechSynthesis.pending) {
          once()
        }
      }, 250)
      return
    }
    window.speechSynthesis.speak(u)
  })
}

export function cambridgeUrl(word) {
  const q = word.replace(/[^a-zA-Z'\-\s]/g, '').trim()
  return `https://dictionary.cambridge.org/dictionary/english/${encodeURIComponent(q)}`
}

export function youglishUrl(word) {
  const q = word.replace(/[^a-zA-Z'\-\s]/g, '').trim()
  return `https://youglish.com/pronounce/${encodeURIComponent(q)}/english/us`
}
