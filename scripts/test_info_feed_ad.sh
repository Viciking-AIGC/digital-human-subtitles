#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
python3 "$ROOT/scripts/generate_info_feed_ad.py" \
  '/mnt/c/Users/EDY/Desktop/wf12026081819064440167851968514.mp4' \
  "$ROOT/examples/info-feed-ad-script.json" \
  "$ROOT/outputs/info_feed_ad/wf12026081819064440167851968514.mp4"
