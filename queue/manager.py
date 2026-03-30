"""
File-based DJ queue manager for kokoro-dj.

Maintains a persistent JSON queue at QUEUE_FILE so that external processes
(cron jobs, other scripts) can add songs, set interrupts, and check status
without needing to talk to the running DJ process directly.

Queue file format:
{
  "queue": [
    {"ytid": "abc123", "title": "பாடல் பெயர்", "duration_mins": 4},
    ...
  ],
  "interrupt": {"ytid": "xyz", "title": "..."} | null,
  "stop": false
}
"""

import json
import os
import subprocess
from typing import Optional

QUEUE_FILE = os.environ.get("SONNA_QUEUE_FILE", "/tmp/sonna_queue.json")


def _read() -> dict:
    if not os.path.exists(QUEUE_FILE):
        return {"queue": [], "interrupt": None, "stop": False}
    with open(QUEUE_FILE) as f:
        return json.load(f)


def _write(data: dict):
    with open(QUEUE_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Public API ────────────────────────────────────────────────────────────────

def add(song: dict):
    """Add a song to the end of the queue."""
    data = _read()
    data["queue"].append(song)
    _write(data)


def interrupt(song: dict):
    """Set a song to play next, then resume the queue."""
    data = _read()
    data["interrupt"] = song
    _write(data)


def stop():
    """Signal the DJ loop to stop after the current song."""
    data = _read()
    data["stop"] = True
    _write(data)
    # Kill audio processes immediately
    for proc in ["ffplay", "yt-dlp", "afplay"]:
        subprocess.run(["pkill", "-f", proc], capture_output=True)


def status() -> dict:
    """Return current queue state."""
    return _read()


def status_str() -> str:
    """Human-readable queue status."""
    data = _read()
    lines = [f"Queue ({len(data['queue'])} songs):"]
    for i, s in enumerate(data["queue"]):
        lines.append(f"  {i+1}. {s['title']} (~{s.get('duration_mins', '?')} min)")
    if data.get("interrupt"):
        lines.append(f"  [NEXT — interrupt]: {data['interrupt']['title']}")
    total = sum(s.get("duration_mins", 4) for s in data["queue"])
    lines.append(f"  Total: ~{total} mins queued")
    return "\n".join(lines)


def remaining_mins() -> int:
    """Total estimated minutes left in queue."""
    data = _read()
    return sum(s.get("duration_mins", 4) for s in data["queue"])


def next_song() -> Optional[dict]:
    """
    Pop and return the next song to play.
    Interrupt takes priority over the regular queue.
    Returns None if queue is empty and no interrupt is set.
    """
    data = _read()

    if data.get("stop"):
        return None

    if data.get("interrupt"):
        song = data["interrupt"]
        data["interrupt"] = None
        _write(data)
        return song

    if data["queue"]:
        song = data["queue"].pop(0)
        _write(data)
        return song

    return None


def clear():
    """Clear the queue file entirely."""
    if os.path.exists(QUEUE_FILE):
        os.unlink(QUEUE_FILE)
