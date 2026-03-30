# kokoro-dj 🎙️

A local DJ that streams music from YouTube with expressive voice intros between songs. Pick any artist, configure your sources, choose a voice — and let it run.

Built on a Sunday morning with Ilaiyaraja playing on a Bose Soundbar 700. 🎵

## Features

- **Live queue** — auto-refills from YouTube playlists and search queries. Never runs dry.
- **File-based queue** — add songs, interrupt with one-offs, and stop cleanly from any process
- **Voice intros** — natural, expressive DJ announcements between every song
- **Two TTS backends** — Sarvam AI for Indian languages (Tamil, Hindi, etc.) or Kokoro for English
- **Expressive speech** — chunked TTS with variable pace, pitch, and pauses for a human feel
- **Song requests** — inject a specific song at the front of the queue anytime
- **Volume control** — set, increase or decrease system volume from the CLI
- **AirPlay / Bluetooth** — route audio to any output device via SwitchAudioSource
- **Wake-on-LAN** — wake a sleeping speaker before starting playback

## Quick Start

### 1. Install dependencies

```bash
# System tools
brew install ffmpeg sox yt-dlp switchaudio-osx wakeonlan   # macOS
# apt install ffmpeg sox && pip install yt-dlp              # Linux

# Python
pip install -r requirements.txt

# TTS backend — pick one or both
pip install kokoro soundfile espeak-ng   # English (Kokoro, fully local)
# Sarvam is API-based — free key at dashboard.sarvam.ai
```

### 2. Configure

```bash
cp examples/ilaiyaraja.yaml my-dj.yaml
# Edit — set artist, sources, TTS voice, audio device
```

### 3. Set API key (Sarvam only)

```bash
export SARVAM_API_KEY=your_key_here
```

### 4. Run

```bash
python dj.py --config my-dj.yaml
```

---

## Queue Management

The DJ uses a file-based queue (`/tmp/sonna_queue.json`) that can be controlled while the DJ is running:

```bash
# Add a song
python dj.py --add '{"ytid":"Xk9Ug_g_hck","title":"தென்றல் உறங்கிய போதும்","duration_mins":4}'

# Play a one-off next, then resume queue
python dj.py --interrupt '{"ytid":"HVRP92Mu92E","title":"வாராயோ வெண்ணிலாவே"}'

# Check queue status
python dj.py --status

# Stop
python dj.py --stop
```

**Important:** always add **individual song IDs**, not playlist IDs — each song gets its own voice intro.

---

## Volume Control

```bash
python dj.py --volume 20        # set to 20
python dj.py --volume-up 10     # increase by 10
python dj.py --volume-down 10   # decrease by 10
```

---

## AirPlay Setup (macOS — Bose Soundbar 700)

### One-time setup
Select the device once in **System Settings → Sound → Output**. macOS stores the pairing — after this it works automatically.

### Wake-on-LAN
The Bose sleeps when idle. Add to your config:
```yaml
audio:
  wol_mac: "4c:87:5d:b2:62:8e"
  wol_wait: 8.0
  airplay_device: "AirPlay"
```

### ⚠️ Device name gotcha
macOS registers the Bose Soundbar 700 as **`"AirPlay"`** in CoreAudio — **not** `"Bose Soundbar 700"`.
```bash
SwitchAudioSource -a -t output   # check your actual device names
```

### DJ session lifecycle
```bash
# Start
python dj.py --config my-dj.yaml &   # or run in a background process manager

# Top up queue every ~15 mins while playing
python dj.py --status
python dj.py --add '{"ytid":"...","title":"...","duration_mins":4}'

# Stop cleanly
python dj.py --stop
```

---

## Project Structure

```
kokoro-dj/
├── dj.py                    # Main entry point — DJ loop, queue, intro playback
├── queue/
│   ├── manager.py           # File-based queue (add/interrupt/stop/status)
│   └── youtube.py           # Auto-refilling queue via yt-dlp
├── tts/
│   ├── sarvam.py            # Sarvam AI TTS (Tamil + Indian languages)
│   └── kokoro.py            # Kokoro TTS (English, fully local)
├── utils/
│   ├── audio.py             # WOL, AirPlay switching, volume control
│   └── playback.py          # Cross-platform audio playback command
├── examples/
│   └── ilaiyaraja.yaml      # Example config — Ilaiyaraja Tamil DJ
├── requirements.txt
└── README.md
```

---

## Configuration Reference

See `examples/ilaiyaraja.yaml` for a full annotated example.

| Key | Description |
|-----|-------------|
| `sources` | YouTube playlist IDs (`PL...`) or search queries for auto-queue |
| `audio.wol_mac` | MAC address for Wake-on-LAN (macOS only) |
| `audio.wol_wait` | Seconds to wait after WOL |
| `audio.airplay_device` | CoreAudio device name (check with `SwitchAudioSource -a`) |
| `audio.volume` | Startup volume (0–100) |
| `tts.backend` | `sarvam` or `kokoro` |
| `tts.language` | `ta-IN`, `en-IN`, `hi-IN` etc (Sarvam) |
| `tts.speaker` | Sarvam: `anushka`, `manisha`, `vidya`, `arya` — Kokoro: `bm_george` etc |
| `tts.pace` | Speech speed: 0.6 (slow) to 1.0 (normal). Default 0.80 |
| `welcome_message` | Played at startup |

---

## TTS Backends

### Sarvam AI (recommended for Indian languages)
- Supports Tamil, Hindi, Telugu, Kannada, Malayalam + Indian English
- Free tier at [dashboard.sarvam.ai](https://dashboard.sarvam.ai)
- Voices: `anushka`, `manisha`, `vidya`, `arya` (female) + male options
- Set `SARVAM_API_KEY` environment variable

### Kokoro (English, fully local)
- 82M parameter model, runs fast on Apple Silicon
- No API key needed, fully offline
- 30+ voices including `bm_george` (British male), `af_heart` (American female)
- Install: `pip install kokoro soundfile && brew install espeak-ng`

---

## Hardware

Tested on macOS (Apple Silicon) with Bose Soundbar 700 via AirPlay. Should work on any macOS or Linux machine with ffmpeg and Python 3.10+.

**Linux note:** `afplay` is macOS-only. The code automatically falls back to `aplay` (alsa-utils) or `paplay` (pulseaudio-utils). WOL and AirPlay switching are macOS-only — they no-op gracefully on Linux.

---

## License

MIT
