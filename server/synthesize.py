"""Synthesize natural US audio for a source with Microsoft Edge neural TTS.

Usage:
  .venv/bin/python server/synthesize.py fixture-npr-climate
  .venv/bin/python server/synthesize.py <source_id> [--voice en-US-JennyNeural]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "data" / "sources"

DEFAULT_VOICE = "en-US-JennyNeural"


def _clean(tok: str) -> str:
    return re.sub(r"^[^A-Za-z0-9']+|[^A-Za-z0-9']+$", "", tok).lower()


async def synthesize(source_id: str, voice: str = DEFAULT_VOICE) -> Path:
    import edge_tts

    from segment import segment_words

    d = SOURCES / source_id
    tp = d / "transcript.json"
    if not tp.exists():
        raise SystemExit(f"missing {tp}")

    with tp.open(encoding="utf-8") as f:
        transcript = json.load(f)
    text = (transcript.get("text") or "").strip()
    if not text:
        raise SystemExit("empty transcript")

    audio_path = d / "audio.mp3"
    communicate = edge_tts.Communicate(text, voice=voice, rate="-5%")

    # Collect word boundaries (offset/duration in 100-nanosecond units)
    boundaries: list[dict] = []
    with audio_path.open("wb") as out:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                out.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                boundaries.append(
                    {
                        "text": chunk["text"],
                        "offset": chunk["offset"] / 10_000_000,
                        "duration": chunk["duration"] / 10_000_000,
                    }
                )

    # Map boundaries onto transcript tokens
    tokens = text.split()
    words: list[dict] = []
    bi = 0
    for i, tok in enumerate(tokens):
        clean = _clean(tok)
        start = end = None
        if bi < len(boundaries) and clean and _clean(boundaries[bi]["text"]) == clean:
            start = boundaries[bi]["offset"]
            end = start + boundaries[bi]["duration"]
            bi += 1
        elif bi < len(boundaries):
            # soft match: advance boundary cursor if needed
            matched = False
            for j in range(bi, min(bi + 3, len(boundaries))):
                if clean and _clean(boundaries[j]["text"]) == clean:
                    start = boundaries[j]["offset"]
                    end = start + boundaries[j]["duration"]
                    bi = j + 1
                    matched = True
                    break
            if not matched and bi < len(boundaries):
                start = boundaries[bi]["offset"]
                end = start + max(boundaries[bi]["duration"], 0.2)
        if start is None:
            prev_end = words[-1]["end"] if words else 0.0
            start = prev_end
            end = start + 0.35
        words.append({"i": i, "w": tok, "start": round(start, 3), "end": round(end, 3)})

    bites = segment_words(words)
    duration = words[-1]["end"] if words else 0.0

    with tp.open("w", encoding="utf-8") as f:
        json.dump({"text": text, "words": words}, f, ensure_ascii=False, indent=2)
    with (d / "bites.json").open("w", encoding="utf-8") as f:
        json.dump({"bites": bites}, f, ensure_ascii=False, indent=2)

    meta_path = d / "meta.json"
    meta = {}
    if meta_path.exists():
        with meta_path.open(encoding="utf-8") as f:
            meta = json.load(f)
    meta["has_audio"] = True
    meta["audio_voice"] = voice
    meta["duration_sec"] = round(duration)
    meta["note"] = f"US neural TTS ({voice}) — replace with real clip when available."
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"wrote {audio_path} ({audio_path.stat().st_size} bytes), {len(words)} words, {len(bites)} bites, ~{duration:.1f}s")
    return audio_path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("source_id")
    p.add_argument("--voice", default=DEFAULT_VOICE)
    args = p.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    asyncio.run(synthesize(args.source_id, voice=args.voice))


if __name__ == "__main__":
    main()
