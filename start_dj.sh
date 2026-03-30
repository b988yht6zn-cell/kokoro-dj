#!/bin/bash
# Clean start script for kokoro-dj
# Kills ALL previous audio and DJ processes before starting fresh

echo "Stopping any existing DJ processes..."
pkill -f "dj.py" 2>/dev/null
pkill -f "ffplay" 2>/dev/null
pkill -f "yt-dlp" 2>/dev/null
pkill -f "afplay" 2>/dev/null
sleep 2

# Confirm silence
REMAINING=$(ps aux | grep -E "ffplay|yt-dlp|afplay|dj.py" | grep -v grep | wc -l)
if [ "$REMAINING" -gt 0 ]; then
    echo "Force killing remaining processes..."
    pkill -9 -f "ffplay" 2>/dev/null
    pkill -9 -f "yt-dlp" 2>/dev/null
    pkill -9 -f "afplay" 2>/dev/null
    pkill -9 -f "dj.py" 2>/dev/null
    sleep 1
fi

echo "All clear. Starting DJ..."
source /Users/paul/.hermes/.env
cd "$(dirname "$0")"
python3 -u dj.py --config examples/ilaiyaraja.yaml 2>&1
