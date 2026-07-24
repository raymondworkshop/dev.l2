# Echo

Personal **Echo Method** trainer (史嘉琳 回音法): bite → echo pause → imitate · ~10 min/day. Unknown words: in-app US pronunciation + gloss; 生词/错词本 for light review.

Method notes: [doc/echo.md](doc/echo.md) · Plan: [echo-plan.md](echo-plan.md)

## Run locally

```bash
make setup             # first time: venv + deps + .env + build UI
make service-install   # default: always-on LaunchAgent (login + KeepAlive)
```

Then open **http://127.0.0.1:5050** (Tailscale: `http://<tailscale-ip>:5050`) anytime — no need to `make run` each session.

```bash
make service-status    # running?
make service-restart   # after UI/code changes (rebuilds then restarts)
make service-stop / service-uninstall
make service-logs
```

Foreground one-shot (optional): `make run` or `make start` (build + run). Vite hot-reload: `make web`.

Other: `make help`, `make build`, `make synthesize`, `make install`.

```bash
# Manual equivalent of make setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r server/requirements.txt
cp .env.example .env
cd web && npm install && npm run build && cd ..
```

Open **http://127.0.0.1:5050** (Tailscale: `http://<tailscale-ip>:5050`) — one port serves UI + API.

Hot-reload UI while developing (optional):

```bash
.venv/bin/python server/app.py          # API
cd web && npm run dev                   # UI on :5173, proxies /api → 5050
```

After frontend changes for `:5050`, rebuild: `cd web && npm run build`.

Fixture / pasted transcripts get **Microsoft Edge neural US TTS** (`en-US-JennyNeural`) via `server/synthesize.py` — much more natural than browser novelty voices. Real YouTube/NPR audio (yt-dlp) is still better when available.

## Screens

| Route | Role |
|-------|------|
| `/` | Inbox — URL/transcript ingest + recent |
| `/prep/:id` | Prep — full play, tap word → US audio / IPA / gloss → 生词 |
| `/echo/:id` | Echo Session — Play → 听回音… → Loop / Next · 10:00 · 标错词 |
| `/bank` | Word — 全部/生词/错词 · 再听 · Delete · Open bite |

## Data

- `data/lexicon.json` — word bank
- `data/sources/<id>/` — `meta.json`, `transcript.json`, `bites.json`, optional `audio.*`

Ingest: paste transcript (neural TTS), or a **YouTube / media URL** via `yt-dlp` (audio + English captions). Install: `.venv/bin/pip install yt-dlp`. BBC article pages often have no extractable media — paste transcript or use a direct media / YouTube link.
