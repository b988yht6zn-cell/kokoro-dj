#!/usr/bin/env python3
"""
kokoro-dj — A local DJ that streams music from YouTube
with AI-generated voice intros between songs.

Usage:
    # Start the DJ
    python dj.py --config examples/ilaiyaraja.yaml

    # Queue management (works while DJ is running)
    python dj.py --add '{"ytid":"abc123","title":"பாடல்","duration_mins":4}'
    python dj.py --interrupt '{"ytid":"abc123","title":"பாடல்"}'
    python dj.py --status
    python dj.py --stop

    # Volume control
    python dj.py --volume 20
    python dj.py --volume-up 10
    python dj.py --volume-down 10
"""

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from typing import Optional

import yaml

from songqueue.manager import (
    add as queue_add,
    interrupt as queue_interrupt,
    stop as queue_stop,
    status_str as queue_status_str,
    next_song,
    remaining_mins,
    _read as queue_read,
    _write as queue_write,
)
from songqueue.youtube import SongQueue
from utils.playback import play_command as _play_command
from utils.audio import (
    wake_on_lan,
    switch_airplay,
    get_volume,
    set_volume,
    adjust_volume,
)


# ── Audio playback ────────────────────────────────────────────────────────────

class AudioSession:
    """
    Manages a single yt-dlp → ffplay pipe.
    Allows clean kill without leaving zombie processes.
    """
    def __init__(self):
        self._yt: Optional[subprocess.Popen] = None
        self._ffplay: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    def play(self, url: str):
        """Start streaming. Blocks until song ends or kill() is called."""
        self.kill()  # ensure clean state

        with self._lock:
            self._yt = subprocess.Popen(
                ["yt-dlp", "-q", "-o", "-", url, "-f", "bestaudio"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
            self._ffplay = subprocess.Popen(
                ["ffplay", "-nodisp", "-autoexit", "-i", "-"],
                stdin=self._yt.stdout, stderr=subprocess.DEVNULL
            )
            self._yt.stdout.close()

        self._ffplay.wait()
        self._yt.wait()

    def kill(self):
        """Immediately stop playback."""
        with self._lock:
            for proc in [self._ffplay, self._yt]:
                if proc and proc.poll() is None:
                    try:
                        proc.terminate()
                        proc.wait(timeout=3)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass
            self._ffplay = None
            self._yt = None

    def is_playing(self) -> bool:
        with self._lock:
            return self._ffplay is not None and self._ffplay.poll() is None


def play_intro_wav(path: str):
    """Play a WAV file via afplay/aplay and clean up."""
    if path and os.path.exists(path):
        try:
            subprocess.run(_play_command(path), check=True)
        except Exception as e:
            print(f"[dj] Intro playback failed: {e}")
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass


# ── Intro preparation ─────────────────────────────────────────────────────────

def prepare_intro_wav(song: dict, prev_song: Optional[dict], config: dict) -> Optional[str]:
    """
    Generate intro WAV for a song. Returns path to WAV or None.
    Uses AI generator if llm config is present, else falls back to template.
    """
    tts_cfg = config.get("tts", {})
    llm_cfg = config.get("llm")

    try:
        if llm_cfg:
            from intro.generator import generate_intro
            chunks = generate_intro(song, prev_song, llm_cfg)
        else:
            # Simple template fallback (no LLM configured)
            title = song.get("title", "")
            artist = config.get("artist", "")
            chunks = [
                (f"{title}.", 0.80, 0.1),
                (f"{artist + ' இசையில்,' if artist else ''} கேட்டு மகிழுங்கள்.", 0.78, 0.0),
            ]

        from tts.sarvam import generate_expressive
        return generate_expressive(
            chunks,
            language_code=tts_cfg.get("language", "ta-IN"),
            speaker=tts_cfg.get("speaker", "anushka"),
            pause_between=tts_cfg.get("pause_between", 0.5),
        )
    except Exception as e:
        print(f"[dj] Intro generation failed: {e}")
        return None


# ── Main DJ loop ──────────────────────────────────────────────────────────────

def run(config: dict, request: str = None):
    """
    Main DJ loop.

    Flow per song:
      1. Pop song from queue (already has intro_wav_path if pre-generated)
      2. Play intro WAV
      3. Start song stream in AudioSession (blocks main thread)
      4. Meanwhile: background thread preps next song's intro
      5. Poll for interrupt flag every 2s while playing
         → if set: kill AudioSession immediately, handle interrupt
      6. Song ends → loop
    """
    # Audio setup
    audio_cfg = config.get("audio", {})
    if audio_cfg.get("wol_mac"):
        wake_on_lan(audio_cfg["wol_mac"], wait=audio_cfg.get("wol_wait", 8.0))
    if audio_cfg.get("airplay_device"):
        switch_airplay(audio_cfg["airplay_device"])
    if audio_cfg.get("volume") is not None:
        set_volume(audio_cfg["volume"])

    # Clear stale stop flag
    data = queue_read()
    data["stop"] = False
    queue_write(data)

    # Auto-queue fallback (when no file queue entries)
    sources = config.get("sources", [])
    # Only start auto-queue if file queue is empty — never run both simultaneously
    from songqueue.manager import remaining_mins as _remaining
    file_queue_active = _remaining() > 0

    auto_queue: Optional[SongQueue] = None
    if sources and not file_queue_active:
        print("⏳ Loading auto-queue from sources...")
        auto_queue = SongQueue(sources=sources, min_ahead=3, refill_interval=30)
        if request:
            print(f"🔍 Requesting: {request}")
            auto_queue.request(request)
    elif file_queue_active:
        print(f"[dj] File queue active ({_remaining()} mins) — skipping auto-queue")

    # Welcome message — only play if no file queue (avoids overlap at startup)
    welcome = config.get("welcome_message")
    if welcome and not file_queue_active:
        tts_cfg = config.get("tts", {})
        try:
            from tts.sarvam import speak
            speak(welcome,
                  language_code=tts_cfg.get("language", "ta-IN"),
                  speaker=tts_cfg.get("speaker", "anushka"),
                  pace=tts_cfg.get("pace", 0.80))
        except Exception as e:
            print(f"[dj] Welcome message failed: {e}")

    print(f"\n🎙️  {config.get('name', 'kokoro-dj')} — starting\n")

    session = AudioSession()
    prev_song: Optional[dict] = None
    next_intro_wav: Optional[str] = None  # pre-generated intro for next song
    next_song_peeked: Optional[dict] = None  # the song that next_intro_wav belongs to

    def _prep_next_intro(song: dict, prev: dict):
        """Background thread: generate intro WAV and attach to song dict."""
        nonlocal next_intro_wav, next_song_peeked
        wav = prepare_intro_wav(song, prev, config)
        next_intro_wav = wav
        next_song_peeked = song
        print(f"[dj] Intro ready for: {song.get('title', '')}")

    while True:
        # ── Get next song ──────────────────────────────────────────────────
        song = next_song()

        if song is None and auto_queue:
            song = auto_queue.next()

        if song is None:
            if queue_read().get("stop"):
                print("\n[dj] Stop signal received. Goodbye! 🎙️")
                break
            print("[dj] Queue empty — waiting 10s...")
            time.sleep(10)
            continue

        # Normalise to full song dict
        if "url" not in song:
            ytid = song.get("ytid", "")
            song["url"] = f"https://www.youtube.com/watch?v={ytid}"

        print(f"\n🎵 {song.get('title', 'Unknown')}")

        # ── Play intro ─────────────────────────────────────────────────────
        # Use pre-generated intro if it matches this song, else generate now
        if next_intro_wav and next_song_peeked and \
                next_song_peeked.get("ytid") == song.get("ytid"):
            intro_wav = next_intro_wav
            next_intro_wav = None
            next_song_peeked = None
        else:
            intro_wav = prepare_intro_wav(song, prev_song, config)

        play_intro_wav(intro_wav)

        # ── Start song + background intro prep + interrupt polling ─────────
        play_thread = threading.Thread(target=session.play, args=(song["url"],), daemon=True)
        play_thread.start()

        # Peek at next song and start prepping its intro in background
        prep_thread = None
        peeked = None
        try:
            from songqueue.manager import status
            q_data = status()
            queue_list = q_data.get("queue", [])
            interrupt_song = q_data.get("interrupt")
            peeked = interrupt_song if interrupt_song else (queue_list[0] if queue_list else None)
        except Exception:
            pass

        if peeked and peeked.get("ytid") != song.get("ytid"):
            prep_thread = threading.Thread(
                target=_prep_next_intro,
                args=(peeked, song),
                daemon=True
            )
            prep_thread.start()

        # Poll while song plays — check for interrupt
        interrupted = False
        while play_thread.is_alive():
            time.sleep(2)
            q_data = queue_read()
            if q_data.get("stop"):
                session.kill()
                interrupted = True
                break
            if q_data.get("interrupt"):
                print(f"\n[dj] ⚡ Interrupt received — stopping current song")
                session.kill()
                # Cancel pre-gen thread result (it'll finish but we'll ignore it)
                next_intro_wav = None
                next_song_peeked = None
                interrupted = True
                break

        play_thread.join(timeout=5)

        if not interrupted:
            prev_song = song

    if auto_queue:
        auto_queue.stop()
    session.kill()


# ── CLI ───────────────────────────────────────────────────────────────────────

def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(
        description="kokoro-dj — AI-powered YouTube DJ with Tamil voice intros",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument("--config", help="Path to YAML config file")
    parser.add_argument("--request", help="Search for and play a specific song next")

    # Queue management
    parser.add_argument("--add", metavar="JSON",
                        help='Add: \'{"ytid":"...","title":"...","duration_mins":4}\'')
    parser.add_argument("--interrupt", metavar="JSON",
                        help='Play next then resume: \'{"ytid":"...","title":"..."}\'')
    parser.add_argument("--stop", action="store_true", help="Stop the DJ")
    parser.add_argument("--status", action="store_true", help="Show queue status")

    # Volume
    parser.add_argument("--volume", type=int, metavar="N", help="Set volume (0–100)")
    parser.add_argument("--volume-up", type=int, metavar="N", help="Increase volume by N")
    parser.add_argument("--volume-down", type=int, metavar="N", help="Decrease volume by N")

    args = parser.parse_args()

    if args.add:
        queue_add(json.loads(args.add))
        print(queue_status_str())
        return

    if args.interrupt:
        queue_interrupt(json.loads(args.interrupt))
        print(f"[dj] Interrupt queued.")
        return

    if args.stop:
        queue_stop()
        print("[dj] Stop signal sent.")
        return

    if args.status:
        print(queue_status_str())
        return

    if args.volume is not None:
        set_volume(args.volume)
        return

    if args.volume_up:
        adjust_volume(+args.volume_up)
        return

    if args.volume_down:
        adjust_volume(-args.volume_down)
        return

    if not args.config:
        parser.print_help()
        sys.exit(1)

    config = load_config(args.config)
    run(config, request=args.request)


if __name__ == "__main__":
    main()
