const MENU_ID = 'save-to-word'
const DEFAULT_API = 'http://127.0.0.1:5050'

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: MENU_ID,
      title: 'Save to Word',
      contexts: ['selection'],
    })
  })
})

function normalizeSurface(raw) {
  let s = String(raw || '').trim()
  s = s.replace(/^[\s"'“”‘’(\[{<«]+/, '').replace(/[\s"'“”‘’)\]}>».,;:!?…]+$/, '')
  s = s.trim()
  if (s.length > 80) s = s.slice(0, 80).trim()
  return s
}

async function getApiBase() {
  const { apiBase } = await chrome.storage.sync.get({ apiBase: DEFAULT_API })
  return String(apiBase || DEFAULT_API).replace(/\/$/, '')
}

function notify(title, message) {
  chrome.notifications.create({
    type: 'basic',
    iconUrl: 'icon.png',
    title,
    message,
    priority: 1,
  })
}

async function saveWord(surface, pageUrl) {
  const base = await getApiBase()
  const res = await fetch(`${base}/api/lexicon`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      surface,
      kind: 'unknown',
      context: {
        source_id: '',
        clause: 'extension',
        page_url: pageUrl || '',
      },
    }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || res.statusText || `HTTP ${res.status}`)
  return data
}

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== MENU_ID) return
  const surface = normalizeSurface(info.selectionText)
  if (!surface) {
    notify('Save to Word', 'No text selected.')
    return
  }
  try {
    await saveWord(surface, tab?.url || '')
    notify('Saved to Word', `“${surface}”`)
  } catch (e) {
    const base = await getApiBase()
    notify(
      'Save failed',
      `${e.message || e}. Is Echo API running at ${base}?`,
    )
  }
})
