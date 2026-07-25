"""Word lookup: US/UK IPA + audio, English gloss, Chinese gloss."""
from __future__ import annotations

import os
import re
from typing import Any

import requests

DICT_API = os.getenv("DICTIONARY_API", "https://api.dictionaryapi.dev/api/v2/entries/en")
YOUDAO_VOICE = "https://dict.youdao.com/dictvoice"


def _strip_punct(word: str) -> str:
    return re.sub(r"^[^A-Za-z']+|[^A-Za-z']+$", "", word).lower()


def _youdao_voice(word: str, accent: str) -> str:
    # type=2 US, type=1 UK
    t = "2" if accent == "us" else "1"
    return f"{YOUDAO_VOICE}?audio={word}&type={t}"


def fetch_youdao(word: str) -> dict[str, Any]:
    """IPA + Chinese gloss + speech URLs from Youdao."""
    clean = _strip_punct(word)
    out: dict[str, Any] = {
        "ipa_us": "",
        "ipa_uk": "",
        "audio_url_us": "",
        "audio_url_uk": "",
        "gloss_zh": "",
        "gloss_en": "",
        "pos": "",
    }
    if not clean:
        return out

    try:
        r = requests.get(
            "https://dict.youdao.com/jsonapi",
            params={"q": clean},
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0 (compatible; EchoTrainer/1.0)"},
        )
        if r.status_code != 200:
            return out
        data = r.json() or {}
        simple_words = ((data.get("simple") or {}).get("word")) or []
        if simple_words:
            w0 = simple_words[0] or {}
            us = (w0.get("usphone") or "").strip()
            uk = (w0.get("ukphone") or "").strip()
            if us:
                out["ipa_us"] = us if us.startswith("/") else f"/{us}/"
            if uk:
                out["ipa_uk"] = uk if uk.startswith("/") else f"/{uk}/"
            if w0.get("usspeech") or us:
                out["audio_url_us"] = _youdao_voice(clean, "us")
            if w0.get("ukspeech") or uk:
                out["audio_url_uk"] = _youdao_voice(clean, "uk")

        # Chinese gloss from ec / explain
        ec_words = ((data.get("ec") or {}).get("word")) or []
        if ec_words:
            trs = (((ec_words[0] or {}).get("trs")) or [])
            parts = []
            for tr in trs[:4]:
                for item in (tr.get("tr") or []):
                    for l in (item.get("l") or {}).get("i") or []:
                        if isinstance(l, str) and l.strip():
                            parts.append(l.strip())
                # newer shape: tr["tran"]
                tran = tr.get("tran")
                if isinstance(tran, str) and tran.strip():
                    parts.append(tran.strip())
            if parts:
                out["gloss_zh"] = "；".join(parts)[:180]

        if not out["gloss_zh"]:
            # suggest-style fallback already used elsewhere; try web_trans
            web = (((data.get("web_trans") or {}).get("web-translation")) or [])
            if web:
                values = (((web[0] or {}).get("trans")) or [])
                vals = [v.get("value") for v in values if isinstance(v, dict) and v.get("value")]
                if vals:
                    out["gloss_zh"] = "；".join(vals[:3])[:160]
    except (requests.RequestException, ValueError, TypeError, KeyError):
        pass
    return out


def fetch_dictionary(word: str) -> dict[str, Any]:
    """Free Dictionary API: EN glosses + any US/UK audio/IPA."""
    clean = _strip_punct(word)
    out: dict[str, Any] = {
        "surface": word.strip(),
        "query": clean,
        "ipa": "",
        "ipa_us": "",
        "ipa_uk": "",
        "audio_url": "",
        "audio_url_us": "",
        "audio_url_uk": "",
        "gloss_en": "",
        "glosses_en": [],
        "gloss_zh": "",
        "pos": "",
    }
    if not clean:
        return out

    try:
        r = requests.get(f"{DICT_API}/{clean}", timeout=8)
        if r.status_code != 200:
            return out
        data = r.json()
        if not isinstance(data, list) or not data:
            return out
        entry = data[0]
        phonetics = entry.get("phonetics") or []
        us_audio = uk_audio = any_audio = ""
        us_ipa = uk_ipa = ""
        ipa = entry.get("phonetic") or ""

        for p in phonetics:
            audio = (p.get("audio") or "").strip()
            text = (p.get("text") or "").strip()
            if text and not ipa:
                ipa = text
            low = audio.lower() if audio else ""
            if audio:
                any_audio = any_audio or audio
            if "-us." in low or low.endswith("-us.mp3") or "/us/" in low:
                us_audio = audio or us_audio
                if text:
                    us_ipa = text
            elif "-uk." in low or "-gb." in low or low.endswith("-uk.mp3"):
                uk_audio = audio or uk_audio
                if text:
                    uk_ipa = text
            elif "-au." in low:
                if text and not ipa:
                    ipa = text
            elif text:
                if "ɹ" in text or "oʊ" in text or "æ" in text:
                    us_ipa = us_ipa or text
                elif "əʊ" in text or "ɒ" in text or "ɑː" in text:
                    uk_ipa = uk_ipa or text
                elif not us_ipa:
                    us_ipa = text
                elif not uk_ipa and text != us_ipa:
                    uk_ipa = text

        out["ipa_us"] = us_ipa or ipa
        out["ipa_uk"] = uk_ipa
        out["ipa"] = out["ipa_us"] or out["ipa_uk"] or ipa
        out["audio_url_us"] = us_audio
        out["audio_url_uk"] = uk_audio
        out["audio_url"] = us_audio or any_audio or uk_audio

        glosses: list[dict[str, str]] = []
        for meaning in entry.get("meanings") or []:
            pos = meaning.get("partOfSpeech") or ""
            for d in (meaning.get("definitions") or [])[:2]:
                definition = (d.get("definition") or "").strip()
                if not definition:
                    continue
                glosses.append({"pos": pos, "definition": definition[:200]})
            if len(glosses) >= 4:
                break
        out["glosses_en"] = glosses
        if glosses:
            out["gloss_en"] = glosses[0]["definition"]
            out["pos"] = glosses[0].get("pos") or ""
    except requests.RequestException:
        pass
    return out


def gloss_zh_youdao_suggest(word: str) -> str:
    clean = _strip_punct(word)
    if not clean:
        return ""
    try:
        r = requests.get(
            "https://dict.youdao.com/suggest",
            params={"q": clean, "num": 3, "doctype": "json", "le": "en"},
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0 (compatible; EchoTrainer/1.0)"},
        )
        if r.status_code != 200:
            return ""
        data = r.json()
        entries = (((data or {}).get("data") or {}).get("entries")) or []
        exact = next((e for e in entries if (e.get("entry") or "").lower() == clean), None)
        pick = exact or (entries[0] if entries else None)
        if not pick:
            return ""
        return (pick.get("explain") or "").strip()[:160]
    except (requests.RequestException, ValueError, TypeError):
        return ""


def gloss_zh_llm(word: str, context: str = "") -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return ""
    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    prompt = (
        f"用一句簡短繁體中文解釋英語詞「{word}」"
        + (f"，語境：{context[:120]}" if context else "")
        + "。只返回那一句繁體中文，不要引號。"
    )
    try:
        r = requests.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 80,
            },
            timeout=12,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip().strip("「」\"'")
    except (requests.RequestException, KeyError, IndexError):
        pass
    return ""


def lookup(word: str, context: str = "") -> dict[str, Any]:
    info = fetch_dictionary(word)
    yd = fetch_youdao(word)

    # Prefer Free Dictionary audio when present; fill IPA/audio gaps from Youdao
    if yd.get("ipa_us") and not info.get("ipa_us"):
        info["ipa_us"] = yd["ipa_us"]
    if yd.get("ipa_uk") and not info.get("ipa_uk"):
        info["ipa_uk"] = yd["ipa_uk"]
    # Youdao IPA often better/complete — prefer when Free Dict missing either
    if yd.get("ipa_us"):
        info["ipa_us"] = info["ipa_us"] or yd["ipa_us"]
    if yd.get("ipa_uk"):
        info["ipa_uk"] = info["ipa_uk"] or yd["ipa_uk"]

    if not info.get("audio_url_us") and yd.get("audio_url_us"):
        info["audio_url_us"] = yd["audio_url_us"]
    if not info.get("audio_url_uk") and yd.get("audio_url_uk"):
        info["audio_url_uk"] = yd["audio_url_uk"]

    info["ipa"] = info.get("ipa_us") or info.get("ipa_uk") or info.get("ipa") or ""
    info["audio_url"] = info.get("audio_url_us") or info.get("audio_url") or info.get("audio_url_uk") or ""

    zh = yd.get("gloss_zh") or gloss_zh_youdao_suggest(word) or gloss_zh_llm(word, context=context)
    info["gloss_zh"] = zh
    return info
