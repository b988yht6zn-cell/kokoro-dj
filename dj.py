#!/usr/bin/env python3
"""
kokoro-dj — A local DJ that streams music from YouTube
with expressive voice intros between songs.

Usage:
    # Start the DJ with a config (runs until stopped)
    python dj.py --config examples/ilaiyaraja.yaml

    # Queue management (works while DJ is running)
    python dj.py --add '{"ytid":"abc123","title":"பாடல்","duration_mins":4}'
    python dj.py --interrupt '{"ytid":"abc123","title":"பாடல்"}'
    python dj.py --status
    python dj.py --stop

    # Audio device control
    python dj.py --config examples/ilaiyaraja.yaml --volume 20
    python dj.py --volume-up 10
    python dj.py --volume-down 10

    # Legacy: request a song by search query
    python dj.py --config examples/ilaiyaraja.yaml --request "Mouna Ragam SPB"
"""

import argparse
import json
import os
import subprocess
import sys
import time

import yaml

from queue.manager import (
    add as queue_add,
    interrupt as queue_interrupt,
    stop as queue_stop,
    status_str as queue_status_str,
    next_song,
    clear as queue_clear,
    remaining_mins,
)
from queue.youtube import SongQueue
from utils.playback import play_command as _play_command
from utils.audio import (
    wake_on_lan,
    switch_airplay,
    get_volume,
    set_volume,
    adjust_volume,
)


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


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

    # Use per-song custom intro chunks if provided, else default template
    custom_chunks = song.get("intro_chunks")
    if custom_chunks:
        intro_chunks = [tuple(c) for c in custom_chunks]
    elif language.startswith("ta"):
        intro_chunks = [
            (f"{title}.", 0.80, 0.1),
            (f"{artist} இசையில், அற்புதமான குரலில்.", 0.78, 0.0),
            ("கேட்டு மகிழுங்கள்.", 0.80, 0.0),
        ]
    else:
        intro_chunks = [
            (f"Up next — {title}.", 0.80, 0.0),
            ("Enjoy!", 0.82, 0.1),
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
            try:
                os.unlink(path)
            except OSError:
                pass


def _song_from_queue_entry(entry: dict) -> dict:
    """Convert a queue manager entry to a dj song dict."""
    ytid = entry.get("ytid", "")
    return {
        "id": ytid,
        "title": entry.get("title", "Unknown"),
        "duration": entry.get("duration_mins", 4) * 60,
        "channel": entry.get("channel", ""),
        "url": f"https://www.youtube.com/watch?v={ytid}",
        "intro_chunks": entry.get("intro_chunks"),
    }


def run(config: dict, request: str = None):
    """Main DJ loop — plays songs sequentially with intros."""
    tts_cfg = config.get("tts", {})

    # Audio setup from config
    audio_cfg = config.get("audio", {})
    if audio_cfg.get("wol_mac"):
        wake_on_lan(audio_cfg["wol_mac"], wait=audio_cfg.get("wol_wait", 8.0))
    if audio_cfg.get("airplay_device"):
        switch_airplay(audio_cfg["airplay_device"])
    if audio_cfg.get("volume") is not None:
        set_volume(audio_cfg["volume"])

    # Clear any stale stop flag from previous session
    from queue.manager import _read, _write
    data = _read()
    data["stop"] = False
    _write(data)

    # Decide queue mode: file-based (--add was used) or auto (sources in config)
    sources = config.get("sources", [])
    use_file_queue = os.path.exists(os.environ.get("SONNA_QUEUE_FILE", "/tmp/sonna_queue.json"))
    auto_queue = None

    if sources and not use_file_queue:
        print(f"⏳ Loading initial queue from sources...")
        auto_queue = SongQueue(sources=sources, min_ahead=3, refill_interval=30)
        if request:
            print(f"🔍 Searching for: {request}")
            song = auto_queue.request(request)
            if song:
                print(f"   Queued: {song['title']}")

    # Welcome message
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

    print(f"\n🎙️  kokoro-dj — {config.get('name', 'DJ')} — starting\n")

    while True:
        # Check file queue first (supports --add / --interrupt / --stop)
        song = next_song()

        if song is None and auto_queue:
            # Fall back to auto queue
            song = auto_queue.next()

        if song is None:
            # Check stop flag
            from queue.manager import _read
            if _read().get("stop"):
                print("\n[dj] Stop signal received. Goodbye!")
                break
            print("[dj] Queue empty — waiting 10s...")
            time.sleep(10)
            continue

        # Normalise to song dict format
        if "url" not in song:
            song = _song_from_queue_entry(song)

        print(f"\n🎵 {song['title']}")
        if song.get("channel"):
            print(f"   {song['channel']}")

        intro_path = generate_intro(song, config)
        play_intro(intro_path)

        proc = play_song(song["url"])
        proc.wait()

    if auto_queue:
        auto_queue.stop()


def main():
    parser = argparse.ArgumentParser(
        description="kokoro-dj — YouTube DJ with voice intros",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Run modes
    parser.add_argument("--config", help="Path to YAML config file")
    parser.add_argument("--request", help="Search for and play a specific song next")

    # Queue management (no --config needed)
    parser.add_argument("--add", metavar="JSON",
                        help='Add a song: \'{"ytid":"...","title":"...","duration_mins":4}\'')
    parser.add_argument("--interrupt", metavar="JSON",
                        help='Play next then resume: \'{"ytid":"...","title":"..."}\'')
    parser.add_argument("--stop", action="store_true",
                        help="Stop the DJ after the current song")
    parser.add_argument("--status", action="store_true",
                        help="Show current queue status")

    # Volume control (no --config needed)
    parser.add_argument("--volume", type=int, metavar="N",
                        help="Set volume to N (0–100)")
    parser.add_argument("--volume-up", type=int, metavar="N",
                        help="Increase volume by N")
    parser.add_argument("--volume-down", type=int, metavar="N",
                        help="Decrease volume by N")

    args = parser.parse_args()

    # Queue management commands — no config needed
    if args.add:
        song = json.loads(args.add)
        queue_add(song)
        print(queue_status_str())
        return

    if args.interrupt:
        song = json.loads(args.interrupt)
        queue_interrupt(song)
        print(f"[dj] Interrupt set: {song['title']}")
        return

    if args.stop:
        queue_stop()
        print("[dj] Stop signal sent.")
        return

    if args.status:
        print(queue_status_str())
        return

    # Volume commands — no config needed
    if args.volume is not None:
        set_volume(args.volume)
        return

    if args.volume_up:
        adjust_volume(+args.volume_up)
        return

    if args.volume_down:
        adjust_volume(-args.volume_down)
        return

    # Start DJ — config required
    if not args.config:
        parser.print_help()
        sys.exit(1)

    config = load_config(args.config)
    run(config, request=args.request)


if __name__ == "__main__":
    main()
