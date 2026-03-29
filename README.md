# kokoro-dj 🎙️

A local DJ that streams music from YouTube with expressive voice intros between songs. Pick any artist, configure your sources, choose a voice — and let it run.

Built on a Sunday morning with Ilaiyaraja playing on a Bose Soundbar 700. 🎵

## Features

- **Live queue** — auto-refills from YouTube playlists and search queries. Never runs dry.
- **Voice intros** — natural, expressive DJ announcements between every song
- **Two TTS backends** — Sarvam AI for Indian languages (Tamil, Hindi, etc.) or Kokoro for English
- **Expressive speech** — chunked TTS with variable pace, pitch, and pauses for a human feel
- **Song requests** — inject a specific song at the front of the queue anytime
- **HD quality** — prefers official artist channels and high-quality audio sources
- **Bluetooth ready** — works with any system audio output (use `switchaudio-osx` to route to Bluetooth)

## Quick Start

### 1. Install dependencies

```bash
# System tools
brew install ffmpeg sox yt-dlp switchaudio-osx   # macOS (switchaudio-osx installs the SwitchAudioSource binary)
# apt install ffmpeg sox && pip install yt-dlp   # Linux

# Python
pip install -r requirements.txt

# TTS backend — pick one or both
pip install kokoro soundfile espeak-ng            # English (Kokoro)
# Sarvam is API-based — free key at dashboard.sarvam.ai
```

### 2. Configure

Copy and edit an example config:

```bash
cp examples/ilaiyaraja.yaml my-dj.yaml
# Edit my-dj.yaml — set your artist, sources, TTS voice
```

### 3. Set API key (Sarvam only)

```bash
export SARVAM_API_KEY=your_key_here
```

### 4. Run

```bash
python dj.py --config my-dj.yaml

# Request a specific song
python dj.py --config my-dj.yaml --request "Bohemian Rhapsody Queen"

# Route audio to Bluetooth speaker first
SwitchAudioSource -s "Bose Soundbar 700"
python dj.py --config my-dj.yaml
```

## Project Structure

```
kokoro-dj/
├── dj.py                  # Main entry point — DJ loop, queue management, intro playback
├── utils.py               # Shared utilities (cross-platform audio playback command)
├── queue/
│   └── youtube.py         # Live auto-refilling song queue via yt-dlp
├── tts/
│   ├── sarvam.py          # Sarvam AI TTS (Tamil + Indian languages)
│   └── kokoro.py          # Kokoro TTS (English, fully local)
├── examples/
│   └── ilaiyaraja.yaml    # Example config — Ilaiyaraja Tamil DJ
├── requirements.txt
└── README.md
```

## Configuration

See `examples/ilaiyaraja.yaml` for a full annotated example.

| Key | Description |
|-----|-------------|
| `sources` | YouTube playlist IDs (PL...) or search queries |
| `tts.backend` | `sarvam` or `kokoro` |
| `tts.language` | `ta-IN`, `en-IN`, `hi-IN` etc (Sarvam) or `a`/`b` (Kokoro) |
| `tts.speaker` | Sarvam: `anushka`, `manisha`, `vidya`, `arya` — Kokoro: `bm_george`, `af_heart` etc |
| `tts.pace` | Speech speed: 0.6 (slow) to 1.2 (fast). Default 0.80 |
| `prefer_official` | Prefer official artist channel uploads |
| `welcome_message` | Played at startup |

## TTS Backends

### Sarvam AI (recommended for Indian languages)
- Supports Tamil, Hindi, Telugu, Kannada, Malayalam + Indian English
- Free tier available at [dashboard.sarvam.ai](https://dashboard.sarvam.ai)
- Voices: `anushka`, `manisha`, `vidya`, `arya` (female) + male options
- Set `SARVAM_API_KEY` environment variable

### Kokoro (English, fully local)
- 82M parameter model, runs fast on Apple Silicon
- No API key needed, fully offline
- 30+ voices including `bm_george` (British male), `af_heart` (American female)
- Install: `pip install kokoro soundfile && brew install espeak-ng`

## Hardware

Tested on macOS with Bluetooth speaker output. Should work on any macOS or Linux machine with ffmpeg and Python 3.10+.

**Linux note:** `afplay` is macOS-only. On Linux the code automatically falls back to `aplay` (alsa-utils) or `paplay` (pulseaudio-utils). Install one of these if you're on Linux.

## Bluetooth Setup (macOS)

```bash
# List available audio devices
SwitchAudioSource -a

# Switch to Bluetooth speaker
SwitchAudioSource -s "Bose Soundbar 700"

# Switch back to built-in speakers
SwitchAudioSource -s "Mac mini Speakers"
```

## License

MIT
