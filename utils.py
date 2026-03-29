"""
Shared utilities for kokoro-dj.
"""

import platform
import subprocess


def play_command(path: str):
    """
    Return the correct audio playback command for this OS.
    macOS: afplay
    Linux: aplay (alsa-utils) or paplay (pulseaudio-utils)
    """
    if platform.system() == "Darwin":
        return ["afplay", path]
    for cmd in ["aplay", "paplay"]:
        if subprocess.run(["which", cmd], capture_output=True).returncode == 0:
            return [cmd, path]
    raise EnvironmentError(
        "No audio playback command found. Install aplay (alsa-utils) or paplay (pulseaudio-utils)."
    )
