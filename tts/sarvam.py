"""
Sarvam AI TTS backend for kokoro-dj.
Supports Tamil and Indian English via Sarvam's bulbul:v2 model.
Generates expressive speech by splitting text into chunks with varying pace/pitch,
then stitching with sox.

Requires:
  - SARVAM_API_KEY environment variable (free at dashboard.sarvam.ai)
  - pip install requests
  - brew install ffmpeg sox  (macOS) / apt install ffmpeg sox (Linux)
"""

import os
import subprocess
import tempfile
import base64
from typing import List, Tuple

try:
    import requests
except ImportError:
    raise ImportError("requests is required: pip install requests")

SARVAM_API_URL = "https://api.sarvam.ai/text-to-speech"

from utils import play_command as _play_command


def _get_api_key() -> str:
    key = os.environ.get("SARVAM_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "SARVAM_API_KEY not set. Get a free key at dashboard.sarvam.ai"
        )
    return key


def generate_chunk(
    text: str,
    language_code: str = "ta-IN",
    speaker: str = "anushka",
    pace: float = 0.80,
    pitch: float = 0.0,
    output_path: str = None,
) -> str:
    """
    Generate a single TTS audio chunk via Sarvam API.
    Returns path to the WAV file.
    Raises requests.HTTPError on API failure.
    """
    api_key = _get_api_key()

    resp = requests.post(
        SARVAM_API_URL,
        headers={"api-subscription-key": api_key, "Content-Type": "application/json"},
        json={
            "inputs": [text],
            "target_language_code": language_code,
            "speaker": speaker,
            "model": "bulbul:v2",
            "pace": pace,
            "pitch": pitch,
        },
    )
    resp.raise_for_status()

    data = resp.json()
    if "audios" not in data:
        raise RuntimeError(f"Sarvam API unexpected response: {data}")

    if output_path is None:
        output_path = tempfile.mktemp(suffix=".wav")

    with open(output_path, "wb") as f:
        f.write(base64.b64decode(data["audios"][0]))

    return output_path


def generate_expressive(
    chunks: List[Tuple[str, float, float]],
    language_code: str = "ta-IN",
    speaker: str = "anushka",
    pause_between: float = 0.5,
    output_path: str = None,
) -> str:
    """
    Generate expressive speech by stitching multiple chunks with pauses.

    chunks: list of (text, pace, pitch) tuples
      - pace: 0.6 (slow) to 1.0 (normal). Keep pitch variation subtle (0.0–0.1).
      - pitch: -1.0 to 1.0. Large jumps sound like a different voice — avoid.
    pause_between: silence in seconds between chunks
    Returns path to final stitched WAV file.

    Requires ffmpeg and sox on PATH.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        wav_files = []

        for i, (text, pace, pitch) in enumerate(chunks):
            raw = os.path.join(tmp_dir, f"chunk_{i}_raw.wav")
            generate_chunk(text, language_code, speaker, pace, pitch, raw)

            # Normalise to pcm_s16le 22050Hz mono for sox compatibility
            fixed = os.path.join(tmp_dir, f"chunk_{i}.wav")
            result = subprocess.run(
                ["ffmpeg", "-i", raw, "-ar", "22050", "-ac", "1",
                 "-acodec", "pcm_s16le", fixed, "-y"],
                capture_output=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg failed on chunk {i}: {result.stderr.decode()}")
            wav_files.append(fixed)

        # Generate silence file
        silence_path = os.path.join(tmp_dir, "silence.wav")
        subprocess.run(
            ["sox", "-n", "-r", "22050", "-c", "1", silence_path,
             "trim", "0.0", str(pause_between)],
            capture_output=True, check=True,
        )

        # Generate tail silence (longer than between-chunk pause — prevents abrupt cut-off)
        tail_path = os.path.join(tmp_dir, "tail.wav")
        subprocess.run(
            ["sox", "-n", "-r", "22050", "-c", "1", tail_path,
             "trim", "0.0", "1.2"],
            capture_output=True, check=True,
        )

        # Interleave chunks with silence, then append tail
        sox_args = ["sox"]
        for wav in wav_files:
            sox_args.extend([wav, silence_path])
        sox_args.append(tail_path)  # trailing silence so last word doesn't cut abruptly

        if output_path is None:
            # Use a path outside tmp_dir so it survives context exit
            output_path = tempfile.mktemp(suffix=".wav")

        sox_args.append(output_path)
        subprocess.run(sox_args, capture_output=True, check=True)

    return output_path


def speak(
    text: str,
    language_code: str = "ta-IN",
    speaker: str = "anushka",
    pace: float = 0.80,
    pitch: float = 0.0,
):
    """Generate and immediately play a TTS clip."""
    path = generate_chunk(text, language_code, speaker, pace, pitch)
    try:
        subprocess.run(_play_command(path), check=True)
    finally:
        os.unlink(path)


def speak_expressive(
    chunks: List[Tuple[str, float, float]],
    language_code: str = "ta-IN",
    speaker: str = "anushka",
    pause_between: float = 0.5,
):
    """Generate and immediately play an expressive stitched TTS clip."""
    path = generate_expressive(chunks, language_code, speaker, pause_between)
    try:
        subprocess.run(_play_command(path), check=True)
    finally:
        if os.path.exists(path):
            os.unlink(path)
