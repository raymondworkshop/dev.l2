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


@app.patch("/api/sources/<source_id>")
def api_patch_source(source_id: str):
    body = request.get_json(force=True, silent=True) or {}
    labels = body.get("labels")
    add = body.get("add_label")
    remove = body.get("remove_label")
    if labels is None and not add and not remove:
        return jsonify({"error": "labels, add_label, or remove_label required"}), 400
    if labels is not None and not isinstance(labels, list):
        return jsonify({"error": "labels must be a list"}), 400
    meta = sources.update_source_labels(
        source_id,
        labels=labels if isinstance(labels, list) else None,
        add=str(add) if add else None,
        remove=str(remove) if remove else None,
    )
    if not meta:
        return jsonify({"error": "not found"}), 404
    return jsonify(meta)


@app.post("/api/ingest")
def api_ingest():
    body = request.get_json(force=True, silent=True) or {}
    url = (body.get("url") or "").strip()
    text = (body.get("text") or "").strip()
    title = (body.get("title") or "").strip()
    raw_labels = body.get("labels")
    if isinstance(raw_labels, str):
        labels = [p.strip() for p in raw_labels.replace(",", " ").split() if p.strip()]
    elif isinstance(raw_labels, list):
        labels = raw_labels
    else:
        labels = []
    try:
        if text:
            meta = sources.ingest_text(
                title=title or "Pasted clip", text=text, url=url, labels=labels
            )
        elif url:
            meta = sources.ingest_url(url=url, title=title, labels=labels)
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
        surface = body.get("surface", "")
        gloss_zh = (body.get("gloss_zh") or "").strip()
        ipa = (body.get("ipa") or "").strip()
        audio_url = (body.get("audio_url") or "").strip()
        context = body.get("context")

        # Enrich from dictionary when client omitted IPA / gloss (e.g. Echo 標錯詞)
        if surface and (not gloss_zh or not ipa or not audio_url):
            clause = ""
            if isinstance(context, dict):
                clause = str(context.get("clause") or "")
            info = word_lookup.lookup(surface, context=clause)
            gloss_zh = gloss_zh or (info.get("gloss_zh") or "")
            ipa = ipa or (info.get("ipa_us") or info.get("ipa") or "")
            audio_url = audio_url or (info.get("audio_url_us") or info.get("audio_url") or "")

        entry = lexicon.upsert(
            surface=surface,
            kind=body.get("kind", "unknown"),
            gloss_zh=gloss_zh,
            ipa=ipa,
            audio_url=audio_url,
            context=context,
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
