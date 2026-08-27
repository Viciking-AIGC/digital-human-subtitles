#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
python3 "$ROOT/scripts/generate_video.py" \
  --template iqiyi \
  --input '/mnt/c/Users/EDY/Desktop/wf12026081819064440167851968514.mp4' \
  --script "$ROOT/examples/iqiyi-script.json" \
  --output "$ROOT/outputs/iqiyi/wf12026081819064440167851968514.mp4" \
  --ass "$ROOT/outputs/iqiyi/wf12026081819064440167851968514.ass"
