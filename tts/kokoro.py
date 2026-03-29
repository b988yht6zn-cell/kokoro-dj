"""
Kokoro TTS backend for kokoro-dj.
English-language TTS using the Kokoro-82M model.
Use for English DJ intros or as a fallback when Sarvam is unavailable.

Note: _pipeline is a module-level singleton — not thread-safe.
For single-threaded DJ use this is fine.

Install:
  pip install kokoro soundfile
  brew install espeak-ng  (macOS)
  apt install espeak-ng   (Linux)
"""

import os
import subprocess
import tempfile
import numpy as np

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

try:
    from kokoro import KPipeline
    import soundfile as sf
    _KOKORO_AVAILABLE = True
except ImportError:
    _KOKORO_AVAILABLE = False


# Module-level singleton pipeline (not thread-safe — single-threaded use only)
_pipeline = None


def _get_pipeline(lang_code: str = "a"):
    global _pipeline
    if _pipeline is None:
        if not _KOKORO_AVAILABLE:
            raise ImportError(
                "kokoro not installed. Run: pip install kokoro soundfile"
            )
        _pipeline = KPipeline(lang_code=lang_code)
    return _pipeline


from utils import play_command as _play_command


def generate(
    text: str,
    voice: str = "bm_george",
    lang_code: str = "a",
    output_path: str = None,
) -> str:
    """Generate speech and return path to WAV file."""
    pipeline = _get_pipeline(lang_code)
    chunks = []
    for _, _, audio in pipeline(text.strip(), voice=voice):
        chunks.append(audio)
    final = np.concatenate(chunks)

    if output_path is None:
        output_path = tempfile.mktemp(suffix=".wav")

    sf.write(output_path, final, 24000)
    return output_path


def speak(text: str, voice: str = "bm_george", lang_code: str = "a"):
    """Generate and immediately play speech."""
    path = generate(text, voice, lang_code)
    try:
        subprocess.run(_play_command(path), check=True)
    finally:
        if os.path.exists(path):
            os.unlink(path)
