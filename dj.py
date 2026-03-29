#!/usr/bin/env python3
"""
kokoro-dj — A personal DJ that streams music from YouTube
with expressive voice intros between songs.

Usage:
    python dj.py --config examples/ilaiyaraja.yaml
    python dj.py --config examples/ilaiyaraja.yaml --request "Mouna Ragam SPB"
"""

import argparse
import os
import subprocess
import sys
import threading
import time
import yaml

from queue.youtube import SongQueue, _yt_search


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def play_song(url: str) -> subprocess.Popen:
    """Stream and play a song. Returns the process."""
    return subprocess.Popen(
        f'yt-dlp -q -o - "{url}" -f bestaudio | ffplay -nodisp -autoexit -i - 2>/dev/null',
        shell=True,
    )


def generate_intro(song: dict, config: dict) -> str:
    """Generate a DJ intro for a song using the configured TTS backend."""
    tts_cfg = config.get("tts", {})
    backend = tts_cfg.get("backend", "sarvam")
    language = tts_cfg.get("language", "ta-IN")
    speaker = tts_cfg.get("speaker", "anushka")
    artist = config.get("artist", "the artist")

    # Build intro text
    title = song.get("title", "this song")
    intro_style = config.get("intro_style", "informative")

    if language.startswith("ta"):
        intro = f"அடுத்த பாடல்... {title}. {artist} இசையில் ஒரு அற்புதமான தருணம்."
    else:
        intro = f"Up next — {title}. Enjoy!"

    if backend == "sarvam":
        from tts.sarvam import generate_expressive, speak_expressive

        # Split into natural chunks for expressiveness
        lines = intro.split(". ")
        chunks = []
        paces = [0.75, 0.80, 0.78, 0.82]
        for i, line in enumerate(lines):
            if line.strip():
                chunks.append((line.strip() + ("." if not line.endswith("!") else ""),
                               paces[i % len(paces)],
                               0.1 if i % 2 == 0 else 0.0))

        path = generate_expressive(chunks, language_code=language, speaker=speaker)
        return path

    elif backend == "kokoro":
        from tts.kokoro import generate
        voice = tts_cfg.get("voice", "bm_george")
        return generate(intro, voice=voice)

    return None


def play_intro(path: str):
    """Play a pre-generated intro WAV file."""
    if path and os.path.exists(path):
        subprocess.run(["afplay", path])
        os.unlink(path)


def run(config: dict, request: str = None):
    """Main DJ loop."""
    sources = config.get("sources", [])
    if not sources:
        print("No sources configured. Add search queries or playlist IDs to config.")
        sys.exit(1)

    print(f"🎙️ Starting kokoro-dj — {config.get('name', 'DJ')}")
    print(f"   Sources: {len(sources)} configured")
    print(f"   TTS: {config.get('tts', {}).get('backend', 'sarvam')}")
    print()

    queue = SongQueue(
        sources=sources,
        min_ahead=3,
        refill_interval=30,
        prefer_official=config.get("prefer_official", True),
    )

    # Inject request if provided
    if request:
        print(f"🔍 Finding: {request}")
        song = queue.request(request)
        if song:
            print(f"   Found: {song['title']}")

    # Wait for queue to populate
    print("⏳ Loading queue...")
    time.sleep(5)

    # Welcome message
    tts_cfg = config.get("tts", {})
    welcome = config.get("welcome_message")
    if welcome:
        if tts_cfg.get("backend") == "sarvam":
            from tts.sarvam import speak
            speak(welcome,
                  language_code=tts_cfg.get("language", "ta-IN"),
                  speaker=tts_cfg.get("speaker", "anushka"),
                  pace=0.80)
        elif tts_cfg.get("backend") == "kokoro":
            from tts.kokoro import speak
            speak(welcome, voice=tts_cfg.get("voice", "bm_george"))

    current_proc = None

    while True:
        song = queue.next()
        if not song:
            print("Queue empty — retrying in 10s...")
            time.sleep(10)
            continue

        print(f"\n🎵 Now playing: {song['title']}")
        print(f"   Channel: {song.get('channel', 'Unknown')}")

        # Generate intro in background while previous song winds down
        intro_path = generate_intro(song, config)

        # Play intro then song
        play_intro(intro_path)

        current_proc = play_song(song["url"])
        current_proc.wait()


def main():
    parser = argparse.ArgumentParser(description="kokoro-dj — YouTube DJ with voice intros")
    parser.add_argument("--config", required=True, help="Path to YAML config file")
    parser.add_argument("--request", help="Request a specific song to play next")
    args = parser.parse_args()

    config = load_config(args.config)
    run(config, request=args.request)


if __name__ == "__main__":
    main()
