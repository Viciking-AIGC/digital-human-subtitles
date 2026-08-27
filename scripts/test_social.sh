#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
python3 "$ROOT/scripts/generate_video.py" \
  --template social \
  --input '/mnt/c/Users/EDY/Desktop/wf12026081819064440167851968514.mp4' \
  --script "$ROOT/examples/social-script.json" \
  --output "$ROOT/outputs/social/wf12026081819064440167851968514.mp4" \
  --ass "$ROOT/outputs/social/wf12026081819064440167851968514.ass"
