"""
AI intro generator for kokoro-dj.

Flow:
1. Fetch song metadata from YouTube description (free, no API needed)
2. Optional: web search for a quick interesting fact
3. Call LLM to generate Tamil/English intro text
4. Split into TTS chunks with pace/pitch hints
5. Return chunks ready for tts.sarvam.generate_expressive()

Supported LLM providers (configured in yaml):
  anthropic  — claude-haiku-4-5 (default, fast + cheap)
  openai     — gpt-4o-mini
  openrouter — any model via openrouter.ai
"""

import os
import re
import subprocess
import json
from typing import Optional

from intro.prompts import SYSTEM_PROMPT, choose_prompt


# ── Metadata fetching ─────────────────────────────────────────────────────────

def fetch_youtube_metadata(ytid: str) -> dict:
    """
    Pull title, description, channel from yt-dlp — free, no API key.
    Extracts singer, composer, film, year from description if present.
    """
    result = subprocess.run(
        ["yt-dlp", "--skip-download", "-j", f"https://www.youtube.com/watch?v={ytid}"],
        capture_output=True, text=True, timeout=20
    )
    if result.returncode != 0:
        return {}

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}

    description = data.get("description", "")
    meta = {
        "yt_title": data.get("title", ""),
        "channel": data.get("channel", ""),
        "description": description[:500],  # first 500 chars usually has the good stuff
    }

    # Try to extract structured fields from description
    # Tamil music descriptions often have: Singer:, Music:, Film:, Year: etc.
    for field, keys in [
        ("singer", ["singer", "vocals", "playback", "voice"]),
        ("composer", ["music", "composer", "music by", "composed by", "musical"]),
        ("film", ["film", "movie", "picture", "from"]),
        ("year", ["year", "released"]),
    ]:
        for key in keys:
            match = re.search(
                rf"{key}\s*[:\-]\s*([^\n\|,]+)",
                description, re.IGNORECASE
            )
            if match:
                meta[field] = match.group(1).strip()
                break

    return meta


def web_search_context(title: str, singer: str, composer: str) -> str:
    """
    Quick web search for an interesting fact about the song.
    Uses yt-dlp search description as a lightweight proxy — no external search API needed.
    Falls back gracefully if nothing useful found.
    """
    query = f"{title} {singer} {composer} Tamil song history"
    result = subprocess.run(
        ["yt-dlp", "--flat-playlist", "-j", f"ytsearch3:{query}"],
        capture_output=True, text=True, timeout=15
    )

    snippets = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        try:
            v = json.loads(line)
            desc = v.get("description", "") or ""
            if desc and len(desc) > 30:
                snippets.append(desc[:200])
        except Exception:
            pass

    if snippets:
        return " | ".join(snippets[:2])
    return ""


# ── LLM call ──────────────────────────────────────────────────────────────────

def call_llm(prompt: str, config: dict) -> str:
    """
    Call the configured LLM provider and return the generated text.
    Supports: anthropic, openai, openrouter.
    """
    provider = config.get("provider", "anthropic")
    model = config.get("model", "claude-haiku-4-5")
    api_key_env = config.get("api_key_env", "ANTHROPIC_API_KEY")
    api_key = os.environ.get(api_key_env, "")

    if not api_key:
        raise EnvironmentError(
            f"LLM API key not set. Set {api_key_env} environment variable."
        )

    if provider == "anthropic":
        return _call_anthropic(prompt, model, api_key)
    elif provider == "openai":
        return _call_openai(prompt, model, api_key,
                            base_url="https://api.openai.com/v1")
    elif provider == "openrouter":
        return _call_openai(prompt, model, api_key,
                            base_url="https://openrouter.ai/api/v1")
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def _call_anthropic(prompt: str, model: str, api_key: str) -> str:
    try:
        import anthropic
    except ImportError:
        raise ImportError("anthropic SDK not installed. Run: pip install anthropic")

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text.strip()


def _call_openai(prompt: str, model: str, api_key: str, base_url: str) -> str:
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("openai SDK not installed. Run: pip install openai")

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        max_tokens=512,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
    )
    return response.choices[0].message.content.strip()


# ── Text → TTS chunks ─────────────────────────────────────────────────────────

def text_to_chunks(text: str) -> list:
    """
    Split LLM-generated text into (text, pace, pitch) chunks for Sarvam TTS.

    Strategy:
    - Split on sentence boundaries (. ! ? —)
    - First chunk slightly slower (sets the mood)
    - Last chunk slightly slower with pitch drop (natural sentence-end feel)
    - Middle chunks at normal pace
    """
    # Split on sentence-ending punctuation, keep delimiter
    sentences = re.split(r'(?<=[.!?—])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return [(text, 0.80, 0.0)]

    chunks = []
    for i, sentence in enumerate(sentences):
        if i == 0:
            pace, pitch = 0.78, 0.05   # opening — slightly slower, warm
        elif i == len(sentences) - 1:
            pace, pitch = 0.78, 0.0    # closing — slower, natural drop
        else:
            pace, pitch = 0.81, 0.05   # middle — natural pace

        chunks.append((sentence, pace, pitch))

    return chunks


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_intro(
    song: dict,
    prev_song: Optional[dict],
    llm_config: dict,
    do_web_search: bool = True,
) -> list:
    """
    Full pipeline: fetch metadata → web search → LLM → TTS chunks.

    Returns list of (text, pace, pitch) tuples ready for tts.sarvam.generate_expressive().
    Falls back to a simple template if anything fails.

    song dict should have at minimum: ytid, title
    Enriched in place with: singer, composer, film, year, web_context
    """
    ytid = song.get("ytid", "")

    # Step 1: Fetch YouTube metadata
    if ytid and not song.get("singer"):
        try:
            meta = fetch_youtube_metadata(ytid)
            song.setdefault("singer", meta.get("singer", ""))
            song.setdefault("composer", meta.get("composer", ""))
            song.setdefault("film", meta.get("film", ""))
            song.setdefault("year", meta.get("year", ""))
            song.setdefault("yt_description", meta.get("description", ""))
        except Exception as e:
            print(f"[intro] Metadata fetch failed: {e}")

    # Step 2: Web search for context (only for rich intros)
    if do_web_search and not song.get("web_context"):
        same_as_prev = (
            prev_song and
            song.get("singer") and
            song.get("singer", "").lower() == prev_song.get("singer", "").lower() and
            song.get("composer", "").lower() == prev_song.get("composer", "").lower()
        )
        if not same_as_prev:
            try:
                ctx = web_search_context(
                    song.get("title", ""),
                    song.get("singer", ""),
                    song.get("composer", ""),
                )
                song["web_context"] = ctx
            except Exception as e:
                print(f"[intro] Web search failed: {e}")

    # Step 3: Build prompt
    prompt = choose_prompt(song, prev_song)

    # Step 4: Call LLM
    try:
        intro_text = call_llm(prompt, llm_config)
        print(f"[intro] Generated: {intro_text[:80]}...")
    except Exception as e:
        print(f"[intro] LLM failed: {e} — using fallback")
        title = song.get("title", "")
        singer = song.get("singer", "")
        intro_text = f"{title}. {singer + ' குரலில்,' if singer else ''} கேட்டு மகிழுங்கள்."

    # Step 5: Split into TTS chunks
    return text_to_chunks(intro_text)
