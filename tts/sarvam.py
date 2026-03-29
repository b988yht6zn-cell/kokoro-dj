"""
Sarvam AI TTS backend for kokoro-dj.
Supports Tamil and Indian English via Sarvam's bulbul:v2 model.
Generates expressive speech by splitting text into chunks with varying pace/pitch,
then stitching together with sox.
"""

import os
import subprocess
import tempfile
import base64
import json
from typing import List, Tuple

try:
    import requests
except ImportError:
    raise ImportError("requests is required: pip install requests")


SARVAM_API_URL = "https://api.sarvam.ai/text-to-speech"


def _get_api_key() -> str:
    key = os.environ.get("SARVAM_API_KEY", "")
    if not key:
        raise EnvironmentError("SARVAM_API_KEY not set in environment.")
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
    data = resp.json()
    if "audios" not in data:
        raise RuntimeError(f"Sarvam API error: {data}")

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
    pause_between: silence in seconds between chunks
    Returns path to final stitched WAV file.
    """
    tmp_dir = tempfile.mkdtemp()
    wav_files = []

    for i, (text, pace, pitch) in enumerate(chunks):
        out = os.path.join(tmp_dir, f"chunk_{i}.wav")
        raw = generate_chunk(text, language_code, speaker, pace, pitch, out)

        # Normalise to pcm_s16le 22050Hz mono for sox compatibility
        fixed = os.path.join(tmp_dir, f"chunk_{i}_fixed.wav")
        subprocess.run(
            ["ffmpeg", "-i", raw, "-ar", "22050", "-ac", "1",
             "-acodec", "pcm_s16le", fixed, "-y"],
            capture_output=True,
        )
        wav_files.append(fixed)

    # Generate silence file
    silence_path = os.path.join(tmp_dir, "silence.wav")
    subprocess.run(
        ["sox", "-n", "-r", "22050", "-c", "1", silence_path,
         "trim", "0.0", str(pause_between)],
        capture_output=True,
    )

    # Interleave chunks with silence
    sox_args = ["sox"]
    for wav in wav_files:
        sox_args.append(wav)
        sox_args.append(silence_path)
    sox_args.pop()  # remove trailing silence

    if output_path is None:
        output_path = tempfile.mktemp(suffix=".wav")

    sox_args.append(output_path)
    subprocess.run(sox_args, capture_output=True)

    return output_path


def speak(text: str, language_code: str = "ta-IN", speaker: str = "anushka",
          pace: float = 0.80, pitch: float = 0.0):
    """Generate and immediately play a TTS clip."""
    path = generate_chunk(text, language_code, speaker, pace, pitch)
    subprocess.run(["afplay", path])
    os.unlink(path)


def speak_expressive(chunks: List[Tuple[str, float, float]],
                     language_code: str = "ta-IN", speaker: str = "anushka",
                     pause_between: float = 0.5):
    """Generate and immediately play an expressive stitched TTS clip."""
    path = generate_expressive(chunks, language_code, speaker, pause_between)
    subprocess.run(["afplay", path])
    os.unlink(path)
