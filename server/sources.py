"""Sources: list, load, ingest (URL or pasted transcript)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from segment import segment_words, words_from_plain_text

ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = ROOT / "data" / "sources"
VENV_YT = ROOT / ".venv" / "bin" / "yt-dlp"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9\-]+", "-", s.strip().lower()).strip("-")
    return (s[:48] or "source") + "-" + uuid.uuid4().hex[:6]


def _yt_dlp() -> str | None:
    if VENV_YT.exists():
        return str(VENV_YT)
    return shutil.which("yt-dlp")


def list_sources() -> list[dict[str, Any]]:
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    out: list[dict[str, Any]] = []
    for d in sorted(SOURCES_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        meta_path = d / "meta.json"
        if not meta_path.exists():
            continue
        with meta_path.open(encoding="utf-8") as f:
            meta = json.load(f)
        meta["id"] = meta.get("id") or d.name
        # surface download status for Inbox
        meta["has_audio"] = bool(meta.get("has_audio")) or any(
            (d / name).exists() for name in ("audio.mp3", "audio.m4a", "audio.wav", "audio.webm")
        )
        tp = d / "transcript.json"
        if tp.exists():
            try:
                text = json.loads(tp.read_text(encoding="utf-8")).get("text", "")
                meta["has_transcript"] = bool(text) and not text.startswith("[Paste transcript")
            except json.JSONDecodeError:
                meta["has_transcript"] = False
        else:
            meta["has_transcript"] = False
        meta["labels"] = _normalize_labels(meta.get("labels"))
        out.append(meta)
    return out


def get_source(source_id: str) -> dict[str, Any] | None:
    d = SOURCES_DIR / source_id
    if not d.is_dir():
        return None
    meta_path = d / "meta.json"
    if not meta_path.exists():
        return None
    with meta_path.open(encoding="utf-8") as f:
        meta = json.load(f)
    meta["id"] = source_id

    transcript = {}
    tp = d / "transcript.json"
    if tp.exists():
        with tp.open(encoding="utf-8") as f:
            transcript = json.load(f)

    # Always resegment by sentence/pause so older 4–5-word bites refresh
    words = (transcript.get("words") if isinstance(transcript, dict) else None) or []
    if words:
        bite_list = segment_words(words)
        bp = d / "bites.json"
        with bp.open("w", encoding="utf-8") as f:
            json.dump({"bites": bite_list}, f, ensure_ascii=False, indent=2)
    else:
        bite_list = []
        bp = d / "bites.json"
        if bp.exists():
            with bp.open(encoding="utf-8") as f:
                bite_list = (json.load(f) or {}).get("bites", [])

    audio = None
    for name in ("audio.mp3", "audio.m4a", "audio.wav", "audio.webm"):
        if (d / name).exists():
            audio = f"/api/sources/{source_id}/audio"
            meta["has_audio"] = True
            break

    text = (transcript.get("text") or "") if isinstance(transcript, dict) else ""
    meta["has_transcript"] = bool(text) and not text.startswith("[Paste transcript")

    return {
        "meta": meta,
        "transcript": transcript,
        "bites": bite_list,
        "audio_url": audio,
    }


def _write_source(
    source_id: str,
    title: str,
    url: str,
    text: str,
    words: list[dict[str, Any]] | None = None,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    d = SOURCES_DIR / source_id
    d.mkdir(parents=True, exist_ok=True)
    if words is None:
        words = words_from_plain_text(text)
    bites = segment_words(words)
    duration = words[-1]["end"] if words else 0

    meta: dict[str, Any] = {
        "id": source_id,
        "title": title,
        "url": url,
        "duration_sec": round(duration),
        "accent": "US",
        "created": _now(),
        "has_audio": False,
        "has_transcript": bool(text) and not text.startswith("[Paste transcript"),
    }
    if extra_meta:
        meta.update(extra_meta)
    with (d / "meta.json").open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    with (d / "transcript.json").open("w", encoding="utf-8") as f:
        json.dump({"text": text, "words": words}, f, ensure_ascii=False, indent=2)
    with (d / "bites.json").open("w", encoding="utf-8") as f:
        json.dump({"bites": bites}, f, ensure_ascii=False, indent=2)
    return meta


def ingest_text(title: str, text: str, url: str = "", labels: list[str] | None = None) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise ValueError("transcript text required")
    title = (title or "Untitled clip").strip()
    source_id = _slug(title)
    extra = {"labels": _normalize_labels(labels or [])}
    meta = _write_source(source_id, title, url, text, extra_meta=extra)
    try:
        from synthesize import synthesize
        import asyncio

        asyncio.run(synthesize(source_id))
        refreshed = get_source(source_id)
        if refreshed:
            m = refreshed["meta"]
            m["ingest"] = {
                "ok": True,
                "audio": bool(refreshed.get("audio_url")),
                "transcript": True,
                "mode": "paste+tts",
                "warnings": [],
            }
            return m
    except Exception as e:
        meta["ingest"] = {
            "ok": True,
            "audio": False,
            "transcript": True,
            "mode": "paste",
            "warnings": [f"TTS synthesize skipped: {e}"],
        }
        return meta
    meta["ingest"] = {"ok": True, "audio": False, "transcript": True, "mode": "paste", "warnings": []}
    return meta


def delete_source(source_id: str) -> bool:
    """Remove a source directory. Returns False if missing / invalid id."""
    if not source_id or "/" in source_id or "\\" in source_id or source_id in (".", ".."):
        return False
    d = SOURCES_DIR / source_id
    if not d.is_dir() or not d.resolve().is_relative_to(SOURCES_DIR.resolve()):
        return False
    shutil.rmtree(d)
    return True


_LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9\-_]{0,31}$")


def _normalize_label(raw: str) -> str | None:
    s = (raw or "").strip().lower().replace(" ", "-")
    s = re.sub(r"[^a-z0-9\-_]", "", s)
    if not s or not _LABEL_RE.match(s):
        return None
    return s


def _normalize_labels(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        lab = _normalize_label(str(item))
        if lab and lab not in seen:
            seen.add(lab)
            out.append(lab)
    return out


def update_source_labels(source_id: str, labels: list[str] | None = None, *, add: str | None = None, remove: str | None = None) -> dict[str, Any] | None:
    """Set or toggle labels on a source. Returns updated meta or None."""
    if not source_id or "/" in source_id or "\\" in source_id:
        return None
    d = SOURCES_DIR / source_id
    meta_path = d / "meta.json"
    if not meta_path.exists():
        return None
    with meta_path.open(encoding="utf-8") as f:
        meta = json.load(f)
    current = _normalize_labels(meta.get("labels"))
    if labels is not None:
        current = _normalize_labels(labels)
    else:
        if add:
            lab = _normalize_label(add)
            if lab and lab not in current:
                current.append(lab)
        if remove:
            lab = _normalize_label(remove)
            if lab:
                current = [x for x in current if x != lab]
    meta["labels"] = current
    meta["id"] = meta.get("id") or source_id
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return meta


def _http_get(url: str, timeout: int = 60) -> Any:
    import requests

    return requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": "Mozilla/5.0 (compatible; EchoTrainer/1.0)"},
        allow_redirects=True,
    )


def _is_bbc_learning_english(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    path = urlparse(url).path.lower()
    return "bbc." in host and "learningenglish" in path


def _clean_bbc_transcript(text: str) -> str:
    lines = []
    skip_re = re.compile(
        r"^(BBC LEARNING ENGLISH|6 Minute English|Page \d+ of \d+|bbclearningenglish\.com|"
        r"This is not a word-for-word|©British Broadcasting|VOCABULARY|Vocabulary|"
        r"_{3,}|\d+$)",
        re.I,
    )
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line or skip_re.match(line):
            continue
        lines.append(line)
    # Join speaker labels with following dialogue when split oddly
    return " ".join(lines)


def ingest_bbc_learning_english(
    url: str, title: str = "", labels: list[str] | None = None
) -> dict[str, Any]:
    """BBC Learning English pages expose direct MP3 + transcript PDF — skip yt-dlp/ffmpeg."""
    warnings: list[str] = []
    try:
        page = _http_get(url, timeout=45)
        page.raise_for_status()
    except Exception as e:
        raise ValueError(f"Could not open BBC page: {e}") from e

    html = page.text
    og = re.search(r'property="og:title"\s+content="([^"]+)"', html, flags=re.I)
    resolved_title = title.strip()
    if not resolved_title and og:
        resolved_title = re.sub(r"^BBC Learning English\s*[-–—]\s*", "", og.group(1)).strip()[:120]
    if not resolved_title:
        resolved_title = "BBC Learning English"

    mp3s = re.findall(
        r'href="(https://downloads\.bbc\.co\.uk[^"]+\.mp3)"',
        html,
        flags=re.I,
    )
    pdfs = re.findall(
        r'href="(https://downloads\.bbc\.co\.uk[^"]*transcript[^"]*\.pdf)"',
        html,
        flags=re.I,
    )
    if not pdfs:
        pdfs = re.findall(
            r'href="(https://downloads\.bbc\.co\.uk[^"]+\.pdf)"',
            html,
            flags=re.I,
        )

    if not mp3s:
        raise ValueError(
            "No MP3 download link on this BBC Learning English page.\n"
            "Open the episode page that has “Download MP3”, or paste transcript + use another clip."
        )

    source_id = _slug(resolved_title or "bbc-6min")
    d = SOURCES_DIR / source_id
    d.mkdir(parents=True, exist_ok=True)

    audio_path = d / "audio.mp3"
    try:
        audio = _http_get(mp3s[0], timeout=120)
        audio.raise_for_status()
        if len(audio.content) < 1000:
            raise ValueError("MP3 too small")
        audio_path.write_bytes(audio.content)
    except Exception as e:
        raise ValueError(f"BBC MP3 download failed: {e}") from e

    transcript_text = ""
    if pdfs:
        try:
            from io import BytesIO

            from pypdf import PdfReader

            pdf = _http_get(pdfs[0], timeout=90)
            pdf.raise_for_status()
            reader = PdfReader(BytesIO(pdf.content))
            raw = "\n".join((page.extract_text() or "") for page in reader.pages)
            transcript_text = _clean_bbc_transcript(raw)
        except Exception as e:
            warnings.append(f"Transcript PDF failed: {e}")

    if not transcript_text:
        # Fallback: richtext paragraphs on the page
        paras = re.findall(r"<p[^>]*>(.*?)</p>", html, flags=re.S | re.I)
        bits = []
        for p in paras:
            t = re.sub(r"<[^>]+>", " ", p)
            t = re.sub(r"\s+", " ", t).strip()
            if len(t) > 40 and not t.startswith("_"):
                bits.append(t)
        transcript_text = " ".join(bits[:40])
        if transcript_text:
            warnings.append("Used on-page text (PDF transcript unavailable).")
        else:
            warnings.append("No transcript text — audio only. Paste transcript for Echo bites.")
            transcript_text = (
                f"[Audio saved for: {resolved_title}]\n"
                "Paste the episode transcript in Inbox to enable Prep / Echo text."
            )

    words = None if transcript_text.startswith("[") else words_from_plain_text(transcript_text)
    # Prefer shorter practice window: keep full audio but note duration
    meta = _write_source(
        source_id,
        resolved_title,
        url,
        transcript_text,
        words=words,
        extra_meta={
            "has_audio": True,
            "accent": "UK",
            "labels": _normalize_labels(labels or []),
            "ingest": {
                "ok": True,
                "audio": True,
                "transcript": bool(transcript_text) and not transcript_text.startswith("["),
                "mode": "bbc-direct",
                "warnings": warnings
                + [
                    "BBC 6 Minute English is UK English — fine for listen/comprehension; "
                    "prefer US clips the same day you shadow US."
                ],
                "mp3": mp3s[0],
            },
        },
    )
    return meta


def ingest_url(url: str, title: str = "", labels: list[str] | None = None) -> dict[str, Any]:
    """Download audio + captions. BBC Learning English uses direct MP3/PDF; else yt-dlp."""
    url = url.strip()
    if not url:
        raise ValueError("url required")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("url must be http(s)")

    if _is_bbc_learning_english(url):
        return ingest_bbc_learning_english(url, title=title, labels=labels)

    yt = _yt_dlp()
    if not yt:
        raise ValueError(
            "yt-dlp not installed. Run: .venv/bin/pip install yt-dlp\n"
            "Or paste the transcript text together with the URL."
        )

    source_id = _slug(title or parsed.netloc or "clip")
    d = SOURCES_DIR / source_id
    d.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    resolved_title = title.strip()
    transcript_text = ""
    words: list[dict[str, Any]] | None = None
    has_audio = False
    duration_hint = 0

    # --- title / duration ---
    try:
        meta_raw = subprocess.check_output(
            [yt, "--skip-download", "--print", "%(title)s\n%(duration)s", "--no-warnings", url],
            stderr=subprocess.STDOUT,
            timeout=90,
            text=True,
        ).strip()
        lines = [ln.strip() for ln in meta_raw.splitlines() if ln.strip()]
        if lines and not resolved_title:
            resolved_title = lines[0][:120]
        if len(lines) > 1 and lines[1].isdigit():
            duration_hint = int(lines[1])
    except subprocess.CalledProcessError as e:
        msg = (e.output or str(e))[-400:]
        warnings.append(f"Could not read media metadata: {msg}")
    except (OSError, TimeoutError) as e:
        warnings.append(f"Metadata fetch failed: {e}")

    if not resolved_title:
        resolved_title = parsed.path.rsplit("/", 1)[-1] or "Imported clip"

    # --- captions (manual then auto) ---
    sub_dir = d / "_subs"
    if sub_dir.exists():
        shutil.rmtree(sub_dir, ignore_errors=True)
    sub_dir.mkdir(exist_ok=True)
    for sub_flags in (
        ["--write-subs", "--sub-langs", "en.*,en", "--sub-format", "vtt/srt/best"],
        ["--write-auto-subs", "--sub-langs", "en.*,en", "--sub-format", "vtt/srt/best"],
    ):
        if transcript_text:
            break
        try:
            proc = subprocess.run(
                [
                    yt,
                    "--skip-download",
                    *sub_flags,
                    "-o",
                    str(sub_dir / "clip.%(ext)s"),
                    "--no-warnings",
                    "--socket-timeout",
                    "20",
                    url,
                ],
                check=False,
                timeout=90,
                capture_output=True,
                text=True,
            )
            vtts = sorted(sub_dir.rglob("*.vtt")) + sorted(sub_dir.rglob("*.srt"))
            if vtts:
                raw = vtts[0].read_text(encoding="utf-8", errors="ignore")
                transcript_text, words = _captions_to_words(raw)
            elif proc.returncode != 0:
                err = (proc.stderr or proc.stdout or "")[-200:]
                # Don't dump signed CDN URLs / ffmpeg noise into the UI
                if "timed out" in err.lower() or "timeout" in err.lower():
                    warnings.append("Captions timed out.")
                elif err.strip():
                    warnings.append("No captions available for this URL.")
        except (OSError, TimeoutError):
            warnings.append("Caption download timed out.")

    if not transcript_text:
        warnings.append(
            "No English captions found. Paste a transcript in Inbox, or pick a clip with CC."
        )

    # --- audio: prefer raw bestaudio (no ffmpeg remux) to avoid code 183 ---
    has_audio = _yt_download_audio(yt, url, d, warnings)

    if not transcript_text and not has_audio:
        raise ValueError(
            "Could not download audio or captions from this URL.\n"
            "Try a YouTube clip with CC, a BBC Learning English episode page, "
            "or paste the transcript in Inbox.\n"
            + "\n".join(w for w in warnings if "http" not in w.lower())[:500]
        )

    if not transcript_text:
        transcript_text = (
            f"[No captions for: {resolved_title}]\n"
            "Audio was saved — paste transcript text to enable Prep tap-to-lookup and Echo bites."
        )
        words = words_from_plain_text(transcript_text)

    meta = _write_source(
        source_id,
        resolved_title,
        url,
        transcript_text,
        words=words,
        extra_meta={
            "has_audio": has_audio,
            "source_duration_sec": duration_hint or None,
            "labels": _normalize_labels(labels or []),
            "ingest": {
                "ok": has_audio or bool(transcript_text and not transcript_text.startswith("[")),
                "audio": has_audio,
                "transcript": bool(transcript_text) and not transcript_text.startswith("["),
                "mode": "yt-dlp",
                "warnings": [w for w in warnings if "Key-Pair-Id" not in w][:6],
                "yt_dlp": yt,
            },
        },
    )
    if words and not transcript_text.startswith("["):
        meta["duration_sec"] = round(words[-1]["end"])
        with (d / "meta.json").open("w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    return meta


def _yt_download_audio(yt: str, url: str, d: Path, warnings: list[str]) -> bool:
    """Download audio without forcing ffmpeg mp3 conversion (avoids Invalid data / exit 183)."""
    attempts = [
        # Direct audio file, no remux
        [
            "-f",
            "bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio/best",
            "--download-sections",
            "*0-180",
            "-o",
            str(d / "audio.%(ext)s"),
            "--no-playlist",
            "--socket-timeout",
            "30",
        ],
        # Full short clip audio without section cut (some CDNs break on sections)
        [
            "-f",
            "bestaudio/best",
            "-o",
            str(d / "audio.%(ext)s"),
            "--no-playlist",
            "--socket-timeout",
            "30",
        ],
    ]
    for args in attempts:
        try:
            proc = subprocess.run(
                [yt, *args, "--no-warnings", url],
                check=False,
                timeout=180,
                capture_output=True,
                text=True,
            )
        except (OSError, TimeoutError) as e:
            warnings.append(f"Audio download failed: {e}")
            continue

        found = _find_audio_file(d)
        if found:
            return True
        err = (proc.stderr or proc.stdout or "").strip()
        if "ffmpeg exited" in err.lower():
            warnings.append("Audio remux failed (ffmpeg). Retrying another format…")
        elif "timed out" in err.lower():
            warnings.append("Audio download timed out.")
        elif proc.returncode != 0:
            warnings.append("Audio download failed for this URL.")
    return False


def _find_audio_file(d: Path) -> Path | None:
    for name in ("audio.mp3", "audio.m4a", "audio.webm", "audio.opus", "audio.wav"):
        p = d / name
        if p.exists() and p.stat().st_size > 1000:
            return p
    candidates = [
        p
        for p in d.iterdir()
        if p.is_file() and p.suffix.lower() in {".mp3", ".m4a", ".webm", ".opus", ".wav"}
    ]
    if not candidates:
        return None
    found = max(candidates, key=lambda p: p.stat().st_size)
    if found.stat().st_size <= 1000:
        return None
    dest = d / f"audio{found.suffix.lower()}"
    if found != dest:
        if dest.exists():
            dest.unlink()
        found.rename(dest)
        found = dest
    return found


_TIME_RE = re.compile(
    r"(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})[\.,](?P<ms>\d{3})"
)


def _ts_to_sec(stamp: str) -> float:
    m = _TIME_RE.search(stamp)
    if not m:
        return 0.0
    return (
        int(m.group("h")) * 3600
        + int(m.group("m")) * 60
        + int(m.group("s"))
        + int(m.group("ms")) / 1000.0
    )


_TAGGED_WORD_RE = re.compile(
    r"<(\d{2}:\d{2}:\d{2}[\.,]\d{3})><c>\s*([^<]+?)\s*</c>",
    re.IGNORECASE,
)
_NOISE_BRACKET_RE = re.compile(r"^\[.*\]$")


def _is_noise_token(tok: str) -> bool:
    t = tok.strip()
    if not t:
        return True
    low = t.lower()
    if low in {"foreign", ">>", "&gt;&gt;", "♪", "♫", "&nbsp;", "nbsp;"}:
        return True
    if _NOISE_BRACKET_RE.match(t):  # [Music], [Applause], …
        return True
    if "__" in t:
        return True
    return False


def _strip_cue_text(raw_body: str) -> str:
    text = re.sub(r"<[^>]+>", "", raw_body)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _new_suffix(prev: list[str], curr: list[str]) -> list[str]:
    """Rolling auto-caption: return tokens in curr that are new vs previous cue."""
    if not curr:
        return []
    if not prev:
        return curr
    prev_l = [p.lower() for p in prev]
    curr_l = [c.lower() for c in curr]
    # Hold / flash frame: curr is prefix of (or equal to) previous cue
    if len(curr_l) <= len(prev_l) and curr_l == prev_l[: len(curr_l)]:
        return []
    max_k = min(len(prev_l), len(curr_l))
    for k in range(max_k, 0, -1):
        if prev_l[-k:] == curr_l[:k]:
            return curr[k:]
    return curr


def _assign_word_ends(
    events: list[tuple[float, str]], cue_end: float
) -> list[tuple[float, float, str]]:
    if not events:
        return []
    out: list[tuple[float, float, str]] = []
    for i, (t, tok) in enumerate(events):
        te = events[i + 1][0] if i + 1 < len(events) else (cue_end or t + 0.25)
        if te <= t:
            te = t + 0.2
        out.append((t, te, tok))
    return out


def _parse_caption_cues(raw: str) -> list[tuple[float, float, str]]:
    """Return (start, end, raw_body) cues; body keeps <c> timing tags.

    Line-oriented: YouTube auto VTT often puts a whitespace-only line between the
    timing arrow and the cue text; blank-line splits would orphan that text.
    """
    cues: list[tuple[float, float, str]] = []
    start = end = 0.0
    in_cue = False
    text_lines: list[str] = []

    def flush() -> None:
        nonlocal in_cue, text_lines
        if not in_cue:
            return
        body = " ".join(ln for ln in text_lines if ln.strip()).strip()
        body = re.sub(r"\s+", " ", body).strip()
        if body:
            cues.append((start, end or start + 0.5, body))
        in_cue = False
        text_lines = []

    for ln in raw.splitlines():
        ln = ln.strip("\ufeff")
        if "-->" in ln:
            flush()
            left, _, right = ln.partition("-->")
            start = _ts_to_sec(left)
            end = _ts_to_sec(right.split()[0] if right.strip() else "")
            in_cue = True
            text_lines = []
            continue
        if not in_cue:
            continue
        if not ln.strip():
            # Only end the cue on a truly empty line after we've seen text;
            # whitespace-only placeholders before text are ignored.
            if any(t.strip() for t in text_lines):
                flush()
            continue
        text_lines.append(ln.strip())
    flush()
    return cues


def _captions_to_words(raw: str) -> tuple[str, list[dict[str, Any]]]:
    """Parse VTT/SRT into plain text + timed words.

    YouTube auto-captions use a rolling window and optional word-level <c> tags;
    we de-overlap those so Echo bites are real sentences, not triple-repeated spam.
    """
    cues = _parse_caption_cues(raw)
    timed: list[tuple[float, float, str]] = []
    emitted: list[str] = []

    has_tags = any("<c>" in b.lower() for _, _, b in cues)
    for start, end, body in cues:
        if has_tags and "<c>" not in body.lower():
            # Hold/display frame — ignore (would mark words seen without emitting)
            continue

        if "<c>" in body.lower():
            events: list[tuple[float, str]] = []
            lead = re.split(r"<\d{2}:", body, maxsplit=1)[0]
            lead = re.sub(r"<[^>]+>", "", lead).strip()
            lead_toks = [t for t in lead.split() if not _is_noise_token(t)]
            new_lead = _new_suffix(emitted, lead_toks)
            for tok in new_lead:
                events.append((start, tok))
            for m in _TAGGED_WORD_RE.finditer(body):
                tok = m.group(2).strip()
                if _is_noise_token(tok):
                    continue
                events.append((_ts_to_sec(m.group(1)), tok))
            chunk = _assign_word_ends(events, end)
            for _s, _e, tok in chunk:
                emitted.append(tok)
            timed.extend(chunk)
        else:
            plain = _strip_cue_text(body)
            toks = [t for t in plain.split() if not _is_noise_token(t)]
            new_toks = _new_suffix(emitted, toks)
            if not new_toks:
                continue
            span = max(end - start, 0.2)
            step = span / len(new_toks)
            for j, tok in enumerate(new_toks):
                ws = start + j * step
                timed.append((ws, ws + step, tok))
                emitted.append(tok)

    # Final near-duplicate cleanup (same token re-emitted almost immediately)
    cleaned: list[tuple[float, float, str]] = []
    for start, end, tok in timed:
        if cleaned:
            ps, pe, pt = cleaned[-1]
            if tok.lower() == pt.lower() and abs(start - ps) < 0.35:
                cleaned[-1] = (ps, max(pe, end), pt)
                continue
        cleaned.append((start, end, tok))

    words: list[dict[str, Any]] = []
    for i, (start, end, tok) in enumerate(cleaned):
        words.append({"i": i, "w": tok, "start": round(start, 3), "end": round(end, 3)})

    plain = " ".join(w["w"] for w in words)
    if not words:
        plain = _vtt_to_text(raw)
        words = words_from_plain_text(plain)
    return plain, words


def _vtt_to_text(vtt: str) -> str:
    """Fallback plain text from VTT with rolling-cue de-overlap."""
    cues = _parse_caption_cues(vtt)
    prev_toks: list[str] = []
    parts: list[str] = []
    for _, _, body in cues:
        plain = _strip_cue_text(body)
        toks = [t for t in plain.split() if not _is_noise_token(t)]
        new_toks = _new_suffix(prev_toks, toks)
        prev_toks = toks
        if new_toks:
            parts.append(" ".join(new_toks))
    return " ".join(parts)


def find_saved_captions(source_dir: Path) -> Path | None:
    """Prefer cleaned en.vtt over en-orig when both exist."""
    sub = source_dir / "_subs"
    if not sub.is_dir():
        return None
    vtts = sorted(sub.rglob("*.vtt")) + sorted(sub.rglob("*.srt"))
    if not vtts:
        return None
    # Prefer non-orig english track when available
    preferred = [p for p in vtts if "orig" not in p.name.lower()]
    return (preferred or vtts)[0]


def reparse_source_captions(source_id: str) -> dict[str, Any] | None:
    """Re-parse saved captions into transcript.json + bites.json."""
    d = SOURCES_DIR / source_id
    if not d.is_dir():
        return None
    cap = find_saved_captions(d)
    if not cap:
        return None
    raw = cap.read_text(encoding="utf-8", errors="ignore")
    text, words = _captions_to_words(raw)
    if not words:
        return None
    bites = segment_words(words)
    duration = words[-1]["end"] if words else 0
    with (d / "transcript.json").open("w", encoding="utf-8") as f:
        json.dump({"text": text, "words": words}, f, ensure_ascii=False, indent=2)
    with (d / "bites.json").open("w", encoding="utf-8") as f:
        json.dump({"bites": bites}, f, ensure_ascii=False, indent=2)
    meta_path = d / "meta.json"
    if meta_path.exists():
        with meta_path.open(encoding="utf-8") as f:
            meta = json.load(f)
        meta["has_transcript"] = True
        meta["duration_sec"] = round(duration)
        with meta_path.open("w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    return {"id": source_id, "words": len(words), "bites": len(bites), "captions": str(cap)}


if __name__ == "__main__":
    import sys

    ids = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not ids:
        ids = [
            d.name
            for d in sorted(SOURCES_DIR.iterdir())
            if d.is_dir() and find_saved_captions(d)
        ]
    for sid in ids:
        result = reparse_source_captions(sid)
        print(result or f"skip {sid}: no saved captions")
