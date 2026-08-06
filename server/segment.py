"""Segment transcript into Echo bites — one sentence / utterance per bite."""
from __future__ import annotations

import re
from typing import Any


def _clean_token(w: str) -> str:
    return re.sub(r"^[^A-Za-z0-9']+|[^A-Za-z0-9']+$", "", w)


_END_PUNCT = re.compile(r'[.!?…]+["\')\]]*$')
_SOFT_PUNCT = re.compile(r'[,;:]+["\')\]]*$')

# Safety only: runaway caption runs with no .!? / pause
_MAX_WORDS = 35
_MAX_DUR_SEC = 10.0
_INTERNAL_GAP = 0.38  # near pause_sec — ignore tiny word-tag jitter


def segment_words(
    words: list[dict[str, Any]],
    target: int | None = None,  # kept for call-site compat; ignored
    pause_sec: float = 0.4,
) -> list[dict[str, Any]]:
    """One bite ≈ one sentence: split on .!? or a silence gap between words.

    Does not chop to 4–5 words. Soft-splits / internal gaps only when a run is
    already long (safety against no-punct auto-captions).
    """
    del target  # unused — sentence/pause mode
    if not words:
        return []

    bites: list[dict[str, Any]] = []
    chunk: list[dict[str, Any]] = []
    bid = 0

    def make_bite(parts: list[dict[str, Any]]) -> None:
        nonlocal bid
        if not parts:
            return
        text = " ".join(w.get("w", "") for w in parts).strip()
        if not text:
            return
        start = parts[0].get("start", 0.0)
        end = parts[-1].get("end", start)
        bites.append(
            {
                "id": bid,
                "text": text,
                "start": start,
                "end": end,
                "word_from": parts[0].get("i", 0),
                "word_to": parts[-1].get("i", 0),
                "tokens": [w.get("w", "") for w in parts],
            }
        )
        bid += 1

    def flush() -> None:
        nonlocal chunk
        make_bite(chunk)
        chunk = []

    def chunk_dur() -> float:
        if not chunk:
            return 0.0
        return float(chunk[-1].get("end", 0)) - float(chunk[0].get("start", 0))

    def safety_split() -> bool:
        """If chunk is runaway, flush at best internal gap or soft punct."""
        nonlocal chunk
        if len(chunk) < 16 and chunk_dur() < 5.5:
            return False
        if len(chunk) < _MAX_WORDS and chunk_dur() < _MAX_DUR_SEC:
            return False
        # Prefer last soft punct in the latter half
        for j in range(len(chunk) - 1, max(3, len(chunk) // 3) - 1, -1):
            if _SOFT_PUNCT.search(chunk[j].get("w", "")):
                make_bite(chunk[: j + 1])
                chunk = chunk[j + 1 :]
                return True
        # Else largest internal gap in the latter half (must be pause-like)
        best_j = None
        best_gap = _INTERNAL_GAP
        for j in range(max(4, len(chunk) // 3), len(chunk)):
            gap = float(chunk[j].get("start", 0)) - float(chunk[j - 1].get("end", 0))
            if gap >= best_gap:
                best_gap = gap
                best_j = j
        if best_j is not None:
            make_bite(chunk[:best_j])
            chunk = chunk[best_j:]
            return True
        # Last resort only for extreme runaways
        if len(chunk) >= _MAX_WORDS + 10:
            mid = len(chunk) // 2
            make_bite(chunk[:mid])
            chunk = chunk[mid:]
            return True
        return False

    for idx, w in enumerate(words):
        chunk.append(w)
        token = w.get("w", "")
        # Sentence-final punctuation
        if _END_PUNCT.search(token):
            flush()
            continue
        # Pause before next word → utterance boundary
        if idx + 1 < len(words):
            gap = float(words[idx + 1].get("start", 0)) - float(w.get("end", 0))
            if gap >= pause_sec:
                flush()
                continue
        # Soft punctuation when already a decent-length clause
        long = len(chunk) >= 12 or chunk_dur() >= 4.0
        if long and _SOFT_PUNCT.search(token):
            flush()
            continue
        safety_split()

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
