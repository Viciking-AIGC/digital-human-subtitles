#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
python3 "$ROOT/scripts/generate_video.py" \
  --template redfruit \
  --input '/mnt/c/Users/EDY/Desktop/wf12026081819064440167851968514.mp4' \
  --script "$ROOT/examples/redfruit-script.json" \
  --output "$ROOT/outputs/redfruit/wf12026081819064440167851968514.mp4" \
  --ass "$ROOT/outputs/redfruit/wf12026081819064440167851968514.ass"
