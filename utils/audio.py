"""
Audio device utilities for kokoro-dj.

Handles Wake-on-LAN, AirPlay routing, and system volume control on macOS.
On Linux these functions are no-ops with a warning.
"""

import platform
import subprocess
import time


def _is_macos() -> bool:
    return platform.system() == "Darwin"


def wake_on_lan(mac_address: str, wait: float = 8.0):
    """
    Send a Wake-on-LAN magic packet to a device and wait for it to come up.

    mac_address: e.g. "4c:87:5d:b2:62:8e"
    wait: seconds to wait after sending WOL before returning

    Requires: brew install wakeonlan
    """
    if not _is_macos():
        print(f"[audio] WOL not supported on this platform — skipping")
        return

    result = subprocess.run(["wakeonlan", mac_address], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[audio] WOL failed: {result.stderr.strip()}")
        return

    print(f"[audio] WOL sent to {mac_address}, waiting {wait}s...")
    time.sleep(wait)


def switch_airplay(device_name: str = "AirPlay") -> bool:
    """
    Switch macOS audio output to an AirPlay device.

    device_name: the CoreAudio name of the device.
      - Bose Soundbar 700 registers as "AirPlay" (not "Bose Soundbar 700")
      - Check available devices with: SwitchAudioSource -a -t output

    Returns True if successful.

    Requires: brew install switchaudio-osx
    """
    if not _is_macos():
        print(f"[audio] SwitchAudioSource not available on this platform — skipping")
        return False

    result = subprocess.run(
        ["SwitchAudioSource", "-s", device_name, "-t", "output"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"[audio] Audio output → {device_name}")
        return True
    else:
        print(f"[audio] Could not switch to '{device_name}': {result.stderr.strip()}")
        print(f"[audio] Available devices:")
        avail = subprocess.run(
            ["SwitchAudioSource", "-a", "-t", "output"],
            capture_output=True, text=True
        )
        for line in avail.stdout.strip().split("\n"):
            print(f"         {line}")
        return False


def get_volume() -> int:
    """Get current system output volume (0–100). macOS only."""
    if not _is_macos():
        return -1
    result = subprocess.run(
        ["osascript", "-e", "get output volume of (get volume settings)"],
        capture_output=True, text=True
    )
    try:
        return int(result.stdout.strip())
    except ValueError:
        return -1


def set_volume(level: int):
    """
    Set system output volume (0–100). macOS only.
    Affects all audio output including AirPlay.
    """
    if not _is_macos():
        print(f"[audio] Volume control not supported on this platform — skipping")
        return
    level = max(0, min(100, level))
    subprocess.run(
        ["osascript", "-e", f"set volume output volume {level}"],
        capture_output=True
    )
    print(f"[audio] Volume → {level}")


def adjust_volume(delta: int):
    """
    Adjust volume by a relative amount (e.g. +10 or -10).
    Clamps to 0–100.
    """
    current = get_volume()
    if current < 0:
        print("[audio] Could not read current volume")
        return
    set_volume(current + delta)
