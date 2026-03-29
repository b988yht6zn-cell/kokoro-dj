#!/usr/bin/env python3
"""
kokoro-dj — A local DJ that streams music from YouTube
with expressive voice intros between songs.

Usage:
    python dj.py --config examples/ilaiyaraja.yaml
    python dj.py --config examples/ilaiyaraja.yaml --request "Mouna Ragam SPB"
"""

import argparse
import os
import platform
import subprocess
import sys
import time

import yaml

from queue.youtube import SongQueue


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _play_command(path: str):
    """Return the right audio playback command for this OS."""
    if platform.system() == "Darwin":
        return ["afplay", path]
    for cmd in ["aplay", "paplay"]:
        if subprocess.run(["which", cmd], capture_output=True).returncode == 0:
            return [cmd, path]
    raise EnvironmentError("No audio playback command found. Install aplay or paplay.")


def play_song(url: str) -> subprocess.Popen:
    """
    Stream and play a song via yt-dlp + ffplay.
    URL is passed as a list argument to avoid shell injection.
    """
    yt = subprocess.Popen(
        ["yt-dlp", "-q", "-o", "-", url, "-f", "bestaudio"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    ffplay = subprocess.Popen(
        ["ffplay", "-nodisp", "-autoexit", "-i", "-"],
        stdin=yt.stdout, stderr=subprocess.DEVNULL
    )
    yt.stdout.close()
    return ffplay


def generate_intro(song: dict, config: dict) -> str:
    """Generate a DJ intro for a song. Returns path to WAV or None."""
    tts_cfg = config.get("tts", {})
    backend = tts_cfg.get("backend", "sarvam")
    language = tts_cfg.get("language", "ta-IN")
    speaker = tts_cfg.get("speaker", "anushka")
    artist = config.get("artist", "the artist")
    title = song.get("title", "this song")

    if language.startswith("ta"):
        intro_chunks = [
            (f"அடுத்த பாடல்...", 0.75, 0.0),
            (f"{title}.", 0.82, 0.1),
            (f"{artist} இசையில் ஒரு அற்புதமான தருணம்.", 0.78, 0.0),
        ]
    else:
        intro_chunks = [
            (f"Up next — {title}.", 0.80, 0.0),
            (f"Enjoy!", 0.82, 0.1),
        ]

    try:
        if backend == "sarvam":
            from tts.sarvam import generate_expressive
            return generate_expressive(
                intro_chunks,
                language_code=language,
                speaker=speaker,
                pause_between=tts_cfg.get("pause_between", 0.5),
            )
        elif backend == "kokoro":
            from tts.kokoro import generate
            voice = tts_cfg.get("voice", "bm_george")
            text = " ".join(c[0] for c in intro_chunks)
            return generate(text, voice=voice)
        else:
            print(f"[dj] Warning: unknown TTS backend '{backend}' — skipping intro")
            return None
    except Exception as e:
        print(f"[dj] Warning: intro generation failed: {e}")
        return None


def play_intro(path: str):
    """Play a pre-generated intro WAV file and clean up."""
    if path and os.path.exists(path):
        try:
            subprocess.run(_play_command(path), check=True)
        except Exception as e:
            print(f"[dj] Warning: intro playback failed: {e}")
        finally:
            os.unlink(path)


def run(config: dict, request: str = None):
    """Main DJ loop."""
    sources = config.get("sources", [])
    if not sources:
        print("No sources configured. Add search queries or playlist IDs to config.")
        sys.exit(1)

    print(f"🎙️  kokoro-dj starting — {config.get('name', 'DJ')}")
    print(f"    Sources : {len(sources)} configured")
    print(f"    TTS     : {config.get('tts', {}).get('backend', 'sarvam')}")
    print()
    print("⏳ Loading initial queue (this may take a moment)...")

    queue = SongQueue(
        sources=sources,
        min_ahead=3,
        refill_interval=30,
    )

    if request:
        print(f"🔍 Searching for: {request}")
        song = queue.request(request)
        if song:
            print(f"   Queued: {song['title']}")
        else:
            print("   Song not found — continuing with auto queue")

    # Welcome message
    tts_cfg = config.get("tts", {})
    welcome = config.get("welcome_message")
    if welcome:
        print("🔊 Playing welcome message...")
        try:
            if tts_cfg.get("backend") == "sarvam":
                from tts.sarvam import speak
                speak(welcome,
                      language_code=tts_cfg.get("language", "ta-IN"),
                      speaker=tts_cfg.get("speaker", "anushka"),
                      pace=tts_cfg.get("pace", 0.80))
            elif tts_cfg.get("backend") == "kokoro":
                from tts.kokoro import speak
                speak(welcome, voice=tts_cfg.get("voice", "bm_george"))
        except Exception as e:
            print(f"[dj] Warning: welcome message failed: {e}")

    while True:
        song = queue.next()
        if not song:
            print("Queue empty — retrying in 10s...")
            time.sleep(10)
            continue

        print(f"\n🎵 Now playing : {song['title']}")
        print(f"   Channel     : {song.get('channel', 'Unknown')}")
        print(f"   Duration    : {int(song.get('duration', 0) // 60)}:{int(song.get('duration', 0) % 60):02d}")

        intro_path = generate_intro(song, config)
        play_intro(intro_path)

        proc = play_song(song["url"])
        proc.wait()


def main():
    parser = argparse.ArgumentParser(
        description="kokoro-dj — YouTube DJ with voice intros"
    )
    parser.add_argument("--config", required=True, help="Path to YAML config file")
    parser.add_argument("--request", help="Request a specific song to play next")
    args = parser.parse_args()

    config = load_config(args.config)
    run(config, request=args.request)


if __name__ == "__main__":
    main()
