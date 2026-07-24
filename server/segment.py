"""Segment transcript into Echo bites by sentence / pause — not fixed word count."""
from __future__ import annotations

import re
from typing import Any


def _clean_token(w: str) -> str:
    return re.sub(r"^[^A-Za-z0-9']+|[^A-Za-z0-9']+$", "", w)


_END_PUNCT = re.compile(r'[.!?…]+["\')\]]*$')


def segment_words(
    words: list[dict[str, Any]],
    target: int | None = None,  # kept for call-site compat; ignored
    pause_sec: float = 0.55,
) -> list[dict[str, Any]]:
    """One bite ≈ one utterance: split on .!? or a silence gap between words."""
    del target  # unused — sentence/pause mode
    if not words:
        return []

    bites: list[dict[str, Any]] = []
    chunk: list[dict[str, Any]] = []
    bid = 0

    def flush() -> None:
        nonlocal bid, chunk
        if not chunk:
            return
        text = " ".join(w.get("w", "") for w in chunk).strip()
        if not text:
            chunk = []
            return
        start = chunk[0].get("start", 0.0)
        end = chunk[-1].get("end", start)
        bites.append(
            {
                "id": bid,
                "text": text,
                "start": start,
                "end": end,
                "word_from": chunk[0].get("i", 0),
                "word_to": chunk[-1].get("i", 0),
                "tokens": [w.get("w", "") for w in chunk],
            }
        )
        bid += 1
        chunk = []

    for idx, w in enumerate(words):
        chunk.append(w)
        token = w.get("w", "")
        # Sentence-final punctuation
        if _END_PUNCT.search(token):
            flush()
            continue
        # Pause before next word
        if idx + 1 < len(words):
            gap = float(words[idx + 1].get("start", 0)) - float(w.get("end", 0))
            if gap >= pause_sec:
                flush()

    flush()
    return bites


def words_from_plain_text(text: str, words_per_sec: float = 2.4) -> list[dict[str, Any]]:
    """Build synthetic timed words from plain transcript text."""
    del words_per_sec
    tokens = text.split()
    words: list[dict[str, Any]] = []
    t = 0.0
    for i, tok in enumerate(tokens):
        dur = max(0.28, len(_clean_token(tok)) * 0.07 + 0.15)
        words.append({"i": i, "w": tok, "start": round(t, 3), "end": round(t + dur, 3)})
        t += dur
        if _END_PUNCT.search(tok):
            t += 0.6  # sentence pause for resegment
        elif tok.endswith((",", ";", ":")):
            t += 0.2
    return words
