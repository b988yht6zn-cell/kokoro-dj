"""
Shared utilities for kokoro-dj.
"""

import platform
import subprocess

# Cached at first call — avoids repeated `which` subprocess calls on every playback
_cached_play_cmd = None


def play_command(path: str):
    """
    Return the correct audio playback command for this OS.
    macOS: afplay
    Linux: aplay (alsa-utils) or paplay (pulseaudio-utils)
    Result is cached after the first call.
    """
    global _cached_play_cmd
    if _cached_play_cmd is None:
        if platform.system() == "Darwin":
            _cached_play_cmd = "afplay"
        else:
            for cmd in ["aplay", "paplay"]:
                if subprocess.run(["which", cmd], capture_output=True).returncode == 0:
                    _cached_play_cmd = cmd
                    break
            else:
                raise EnvironmentError(
                    "No audio playback command found. "
                    "Install aplay (alsa-utils) or paplay (pulseaudio-utils)."
                )
    return [_cached_play_cmd, path]
