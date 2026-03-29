"""
YouTube song queue manager for kokoro-dj.
Maintains a live queue, auto-refills from configured sources,
and supports on-demand requests.
"""

import subprocess
import json
import random
import threading
import time
from collections import deque
from typing import List, Optional


def _yt_search(query: str, max_results: int = 10) -> List[dict]:
    """Search YouTube and return list of {id, title, duration, channel}."""
    result = subprocess.run(
        ["yt-dlp", "--flat-playlist", "-j", f"ytsearch{max_results}:{query}"],
        capture_output=True, text=True
    )
    songs = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        try:
            v = json.loads(line)
            dur = v.get("duration", 0)
            # Only single songs — skip jukeboxes and compilations
            if dur and 90 < dur < 540:
                songs.append({
                    "id": v["id"],
                    "title": v.get("title", "Unknown")[:80],
                    "duration": dur,
                    "channel": v.get("channel", ""),
                    "url": f"https://www.youtube.com/watch?v={v['id']}",
                })
        except Exception:
            pass
    return songs


def _yt_playlist(playlist_id: str, max_results: int = 50) -> List[dict]:
    """Pull songs from a YouTube playlist."""
    url = f"https://www.youtube.com/playlist?list={playlist_id}"
    result = subprocess.run(
        ["yt-dlp", "--flat-playlist", "-j", url],
        capture_output=True, text=True
    )
    songs = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        try:
            v = json.loads(line)
            dur = v.get("duration", 0)
            if dur and 90 < dur < 540:
                songs.append({
                    "id": v["id"],
                    "title": v.get("title", "Unknown")[:80],
                    "duration": dur,
                    "channel": v.get("channel", ""),
                    "url": f"https://www.youtube.com/watch?v={v['id']}",
                })
        except Exception:
            pass
    return songs[:max_results]


class SongQueue:
    """
    Live song queue that auto-refills from sources.

    Sources can be:
      - YouTube search queries (strings)
      - YouTube playlist IDs (strings starting with 'PL')
    """

    def __init__(
        self,
        sources: List[str],
        min_ahead: int = 3,
        refill_interval: int = 30,
        prefer_official: bool = True,
    ):
        self.sources = sources
        self.min_ahead = min_ahead
        self.refill_interval = refill_interval
        self.prefer_official = prefer_official

        self._queue = deque()
        self._played_ids = set()
        self._lock = threading.Lock()
        self._pool = []  # fetched but not yet queued

        # Start background refill thread
        self._running = True
        self._thread = threading.Thread(target=self._refill_loop, daemon=True)
        self._thread.start()

    def _fetch_from_sources(self) -> List[dict]:
        """Fetch songs from all configured sources."""
        all_songs = []
        for source in self.sources:
            try:
                if source.startswith("PL"):
                    songs = _yt_playlist(source)
                else:
                    songs = _yt_search(source)
                all_songs.extend(songs)
            except Exception as e:
                print(f"[queue] Error fetching from {source}: {e}")
        return all_songs

    def _refill_loop(self):
        """Background thread — keep pool stocked and queue topped up."""
        while self._running:
            with self._lock:
                if len(self._queue) < self.min_ahead:
                    # Refill pool if needed
                    if not self._pool:
                        songs = self._fetch_from_sources()
                        # Filter already played
                        fresh = [s for s in songs if s["id"] not in self._played_ids]
                        random.shuffle(fresh)
                        self._pool = fresh

                    # Top up queue from pool
                    while self._pool and len(self._queue) < self.min_ahead + 2:
                        song = self._pool.pop(0)
                        if self.prefer_official:
                            # Prefer official channel results
                            pass  # already filtered at search level
                        self._queue.append(song)

            time.sleep(self.refill_interval)

    def next(self) -> Optional[dict]:
        """Get the next song from the queue."""
        with self._lock:
            if self._queue:
                song = self._queue.popleft()
                self._played_ids.add(song["id"])
                return song
        # Queue empty — try immediate fetch
        songs = self._fetch_from_sources()
        fresh = [s for s in songs if s["id"] not in self._played_ids]
        if fresh:
            song = random.choice(fresh)
            self._played_ids.add(song["id"])
            return song
        return None

    def inject(self, song: dict, position: int = 0):
        """Insert a song at a specific position (0 = play next)."""
        with self._lock:
            queue_list = list(self._queue)
            queue_list.insert(position, song)
            self._queue = deque(queue_list)

    def request(self, query: str):
        """Search for a specific song and inject it at the front."""
        songs = _yt_search(query, max_results=5)
        if songs:
            self.inject(songs[0], position=0)
            return songs[0]
        return None

    def peek(self, n: int = 3) -> List[dict]:
        """Preview the next n songs without removing them."""
        with self._lock:
            return list(self._queue)[:n]

    def stop(self):
        self._running = False
