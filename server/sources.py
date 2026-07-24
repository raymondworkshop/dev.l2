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


def ingest_text(title: str, text: str, url: str = "") -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise ValueError("transcript text required")
    title = (title or "Untitled clip").strip()
    source_id = _slug(title)
    meta = _write_source(source_id, title, url, text)
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


def ingest_bbc_learning_english(url: str, title: str = "") -> dict[str, Any]:
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


def ingest_url(url: str, title: str = "") -> dict[str, Any]:
    """Download audio + captions. BBC Learning English uses direct MP3/PDF; else yt-dlp."""
    url = url.strip()
    if not url:
        raise ValueError("url required")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("url must be http(s)")

    if _is_bbc_learning_english(url):
        return ingest_bbc_learning_english(url, title=title)

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


def _captions_to_words(raw: str) -> tuple[str, list[dict[str, Any]]]:
    """Parse VTT/SRT into plain text + timed words (cue-level timing spread across tokens)."""
    # Strip header / NOTE blocks lightly
    cues: list[tuple[float, float, str]] = []
    blocks = re.split(r"\n\s*\n", raw.strip())
    for block in blocks:
        lines = [ln.strip("\ufeff ") for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        # find timing line
        t_idx = next((i for i, ln in enumerate(lines) if "-->" in ln), None)
        if t_idx is None:
            continue
        left, _, right = lines[t_idx].partition("-->")
        start = _ts_to_sec(left)
        end = _ts_to_sec(right.split()[0] if right.strip() else "")
        text_lines = lines[t_idx + 1 :]
        text = " ".join(text_lines)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            cues.append((start, end or start + 0.5, text))

    # Dedupe overlapping auto-caption spam (keep first occurrence of identical text)
    deduped: list[tuple[float, float, str]] = []
    seen: set[str] = set()
    for start, end, text in cues:
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append((start, end, text))

    words: list[dict[str, Any]] = []
    i = 0
    parts: list[str] = []
    for start, end, text in deduped:
        toks = text.split()
        if not toks:
            continue
        parts.append(text)
        span = max(end - start, 0.2)
        step = span / len(toks)
        for j, tok in enumerate(toks):
            ws = start + j * step
            we = ws + step
            words.append({"i": i, "w": tok, "start": round(ws, 3), "end": round(we, 3)})
            i += 1

    plain = " ".join(parts)
    if not words:
        plain = _vtt_to_text(raw)
        words = words_from_plain_text(plain)
    return plain, words


def _vtt_to_text(vtt: str) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for line in vtt.splitlines():
        line = line.strip()
        if not line or line.startswith("WEBVTT") or "-->" in line or line.isdigit():
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if line and line not in seen:
            seen.add(line)
            lines.append(line)
    return " ".join(lines)
