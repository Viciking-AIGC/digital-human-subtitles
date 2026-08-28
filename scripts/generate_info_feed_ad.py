#!/usr/bin/env python3
"""Fixed information-feed ad renderer: video + script -> captioned video."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from generate_video import render_video


def main():
    parser = argparse.ArgumentParser(
        description='Render the fixed 信息流广告 layout from a video and caption script.'
    )
    parser.add_argument('video', help='input 9:16 video')
    parser.add_argument('script', help='UTF-8 JSON caption script')
    parser.add_argument('output', help='output captioned MP4')
    args = parser.parse_args()
    output, ass = render_video('info_feed_ad', args.video, args.script, args.output)
    print(f'created video: {output}')
    print(f'created subtitles: {ass}')


if __name__ == '__main__':
    main()
