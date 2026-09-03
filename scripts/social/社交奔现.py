#!/usr/bin/env python3
"""Render the standalone Social 奔现 entry.

The title/copy strings may come from the material library or be entered by
the user; this script deliberately keeps both as independent arguments.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from generate_video import render_video

BODY_FONTS = ('标题圆', '抖音体', '新青年体', '美玲体', '江户招牌', '仓耳丰黑')
TITLE_STYLES = ('黄色星星', '心动时刻')
FIXED_TITLE_FONT_SIZE = 35
FIXED_TITLE_POSITION = {'x': 248, 'y': 50}


def main():
    parser = argparse.ArgumentParser(
        description='Render the Social 奔现 title and synchronized body copy (fixed 35px title).'
    )
    parser.add_argument('input', help='source 9:16 MP4')
    parser.add_argument('output', help='output MP4')
    parser.add_argument('--title', required=True, help='selected or user-entered title text')
    parser.add_argument('--title-style', choices=TITLE_STYLES, required=True,
                        help='黄色星星 or 心动时刻')
    parser.add_argument('--text', required=True,
                        help='selected or user-entered body copy; punctuation creates simultaneous lines')
    parser.add_argument('--font', choices=BODY_FONTS, required=True,
                        help='body copy font')
    parser.add_argument('--start', type=float, default=1.0,
                        help='in-video start time in seconds')
    parser.add_argument('--end', type=float, default=8.0,
                        help='in-video end time in seconds')
    parser.add_argument('--ass', help='optional output ASS path')
    args = parser.parse_args()

    if args.end <= args.start:
        parser.error('--end must be greater than --start')
    if not args.title.strip():
        parser.error('--title must not be empty')
    if not args.text.strip():
        parser.error('--text must not be empty')

    payload = {
        'selected_products': [],
        'social_variant': '奔现',
        'social_title': args.title,
        'social_title_style': args.title_style,
        'social_title_font_size': FIXED_TITLE_FONT_SIZE,
        'social_title_position': FIXED_TITLE_POSITION,
        'social_font': args.font,
        'captions': [{'start': args.start, 'end': args.end, 'text': args.text}],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', suffix='.json', delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        script_path = Path(handle.name)
    try:
        render_video('social', Path(args.input), script_path, output, args.ass)
    finally:
        script_path.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
