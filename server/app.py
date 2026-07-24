"""Echo MVP Flask API + static UI."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

import lexicon
import lookup as word_lookup
import sources

ROOT = Path(__file__).resolve().parent.parent
WEB_DIST = ROOT / "web" / "dist"
load_dotenv(ROOT / ".env")

app = Flask(__name__, static_folder=None)
CORS(app)


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "app": "echo"})


# --- Sources ---


@app.get("/api/sources")
def api_list_sources():
    return jsonify(sources.list_sources())


@app.get("/api/sources/<source_id>")
def api_get_source(source_id: str):
    data = sources.get_source(source_id)
    if not data:
        return jsonify({"error": "not found"}), 404
    return jsonify(data)


@app.get("/api/sources/<source_id>/audio")
def api_source_audio(source_id: str):
    d = sources.SOURCES_DIR / source_id
    for name in ("audio.mp3", "audio.m4a", "audio.wav", "audio.webm"):
        p = d / name
        if p.exists():
            return send_from_directory(d, name)
    return jsonify({"error": "no audio"}), 404


@app.delete("/api/sources/<source_id>")
def api_delete_source(source_id: str):
    if sources.delete_source(source_id):
        return jsonify({"ok": True})
    return jsonify({"error": "not found"}), 404


@app.post("/api/ingest")
def api_ingest():
    body = request.get_json(force=True, silent=True) or {}
    url = (body.get("url") or "").strip()
    text = (body.get("text") or "").strip()
    title = (body.get("title") or "").strip()
    try:
        if text:
            meta = sources.ingest_text(title=title or "Pasted clip", text=text, url=url)
        elif url:
            meta = sources.ingest_url(url=url, title=title)
        else:
            return jsonify({"error": "url or text required"}), 400
        return jsonify(meta), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


# --- Lexicon ---


@app.get("/api/lexicon")
def api_lexicon_list():
    kind = request.args.get("kind")
    return jsonify(lexicon.list_entries(kind))


@app.post("/api/lexicon")
def api_lexicon_add():
    body = request.get_json(force=True, silent=True) or {}
    try:
        entry = lexicon.upsert(
            surface=body.get("surface", ""),
            kind=body.get("kind", "unknown"),
            gloss_zh=body.get("gloss_zh", ""),
            ipa=body.get("ipa", ""),
            audio_url=body.get("audio_url", ""),
            context=body.get("context"),
        )
        return jsonify(entry), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.delete("/api/lexicon")
def api_lexicon_delete():
    body = request.get_json(force=True, silent=True) or {}
    surface = body.get("surface", "")
    kind = body.get("kind")
    ok = lexicon.remove(surface, kind)
    return jsonify({"ok": ok}), 200 if ok else 404


# --- Lookup ---


@app.get("/api/lookup")
def api_lookup():
    word = request.args.get("word", "")
    context = request.args.get("context", "")
    if not word.strip():
        return jsonify({"error": "word required"}), 400
    info = word_lookup.lookup(word, context=context)
    info["in_bank"] = lexicon.has(word, "unknown")
    info["in_hard"] = lexicon.has(word, "hard")
    return jsonify(info)


# --- UI (Vite build in web/dist) ---


@app.get("/")
def index():
    index_path = WEB_DIST / "index.html"
    if not index_path.exists():
        return (
            jsonify(
                {
                    "error": "UI not built",
                    "hint": "Run: cd web && npm run build",
                    "health": "/api/health",
                }
            ),
            503,
        )
    return send_from_directory(WEB_DIST, "index.html")


@app.get("/<path:path>")
def spa_or_static(path: str):
    if path.startswith("api/"):
        return jsonify({"error": "not found"}), 404
    candidate = WEB_DIST / path
    if candidate.is_file():
        return send_from_directory(WEB_DIST, path)
    index_path = WEB_DIST / "index.html"
    if index_path.exists():
        return send_from_directory(WEB_DIST, "index.html")
    return jsonify({"error": "not found"}), 404


if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "5050"))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    app.run(host=host, port=port, debug=debug)
