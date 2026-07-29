# Save to Word (Chrome / Edge)

Select text on any page → right-click → **Save to Word**. Saves to the local Echo 生詞本 (`POST /api/lexicon`).

## Setup

1. Start the Echo API (port **5050**):

   ```bash
   # from repo root
   npm run dev:api
   # or: .venv/bin/python server/app.py
   ```

2. Open Chrome (or Edge) → `chrome://extensions` (or `edge://extensions`).

3. Enable **Developer mode** → **Load unpacked** → choose this `extension/` folder.

4. On a webpage: select a word → right-click → **Save to Word**.

5. Open the app Word page (`/bank`) and refresh — the word should appear.

## Notes

- Default API: `http://127.0.0.1:5050`. To change, in DevTools console for the extension service worker:

  ```js
  chrome.storage.sync.set({ apiBase: 'http://127.0.0.1:5050' })
  ```

- Kind is always `unknown` (生詞). Gloss / IPA are filled by the server lookup.

- Does not work inside native apps (e.g. Apple Books) — only in the browser.
