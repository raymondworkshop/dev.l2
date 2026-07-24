"""Lexicon (生词/错词本) persistence."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LEXICON_PATH = ROOT / "data" / "lexicon.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load() -> list[dict[str, Any]]:
    if not LEXICON_PATH.exists():
        return []
    with LEXICON_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def save(entries: list[dict[str, Any]]) -> None:
    LEXICON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LEXICON_PATH.open("w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def list_entries(kind: str | None = None) -> list[dict[str, Any]]:
    entries = load()
    if kind in ("unknown", "hard"):
        return [e for e in entries if e.get("kind") == kind]
    return entries


def upsert(
    surface: str,
    kind: str = "unknown",
    gloss_zh: str = "",
    ipa: str = "",
    audio_url: str = "",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    surface = surface.strip()
    if not surface:
        raise ValueError("surface required")
    if kind not in ("unknown", "hard"):
        raise ValueError("kind must be unknown or hard")

    entries = load()
    key = surface.lower()
    for e in entries:
        if e.get("surface", "").lower() == key and e.get("kind") == kind:
            e["count"] = int(e.get("count", 1)) + 1
            e["updated"] = _now()
            if gloss_zh:
                e["gloss_zh"] = gloss_zh
            if ipa:
                e["ipa"] = ipa
            if audio_url:
                e["audio_url"] = audio_url
            if context:
                e["context"] = context
            save(entries)
            return e

    entry = {
        "surface": surface,
        "kind": kind,
        "gloss_zh": gloss_zh,
        "ipa": ipa,
        "audio_url": audio_url,
        "context": context or {},
        "count": 1,
        "updated": _now(),
    }
    entries.append(entry)
    save(entries)
    return entry


def remove(surface: str, kind: str | None = None) -> bool:
    entries = load()
    key = surface.strip().lower()
    before = len(entries)
    if kind:
        entries = [e for e in entries if not (e.get("surface", "").lower() == key and e.get("kind") == kind)]
    else:
        entries = [e for e in entries if e.get("surface", "").lower() != key]
    if len(entries) == before:
        return False
    save(entries)
    return True


def has(surface: str, kind: str = "unknown") -> bool:
    key = surface.strip().lower()
    return any(e.get("surface", "").lower() == key and e.get("kind") == kind for e in load())
