import { playAccentAudio, playUsAudio } from '../api'

/** Compact speaker control after IPA. */
export default function PronRow({ label, ipa, audioUrl, text, accent = 'us' }) {
  const shown = ipa || '—'
  async function play() {
    if (accent === 'uk') {
      await playAccentAudio(audioUrl, text, 'en-GB')
    } else {
      await playUsAudio(audioUrl, text)
    }
  }

  return (
    <p className="ipa pron-row">
      <span className="pron-label">{label}</span>
      <span className="pron-ipa">{shown}</span>
      <button
        type="button"
        className="pron-speak"
        onClick={play}
        title={accent === 'uk' ? 'Play UK' : 'Play US'}
        aria-label={accent === 'uk' ? 'Play UK pronunciation' : 'Play US pronunciation'}
      >
        <SpeakerIcon />
      </button>
    </p>
  )
}

function SpeakerIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" fill="none">
      <path
        d="M4 9v6h3.5L12 19V5L7.5 9H4z"
        fill="currentColor"
      />
      <path
        d="M15.5 8.5a4.5 4.5 0 010 7"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <path
        d="M18 6a8 8 0 010 12"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  )
}
