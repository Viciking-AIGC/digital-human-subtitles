#!/usr/bin/env python3
"""Generate a captioned digital-human video from a base video and script JSON."""
import argparse, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from render_template import build_ass

def main():
    ap = argparse.ArgumentParser(description='Apply the fixed social or iQiyi layout to a digital-human video.')
    ap.add_argument('--template', choices=['social', 'iqiyi'], required=True)
    ap.add_argument('--input', required=True, help='Uploaded/generated digital-human MP4')
    ap.add_argument('--script', required=True, help='JSON script containing captions and optional title')
    ap.add_argument('--output', required=True, help='Output MP4 path')
    ap.add_argument('--ass', help='Optional ASS path; defaults beside output')
    args = ap.parse_args()

    input_path = Path(args.input)
    script_path = Path(args.script)
    output_path = Path(args.output)
    data = json.loads(script_path.read_text(encoding='utf-8'))
    captions = [(float(item['start']), float(item['end']), str(item['text'])) for item in data.get('captions', [])]
    if not captions:
        raise SystemExit('script.captions must contain at least one caption')
    previous_end = 0.0
    for start, end, text in captions:
        if start < 0 or end <= start or start < previous_end or not text.strip():
            raise SystemExit(f'invalid caption segment: {start}, {end}, {text!r}')
        previous_end = end
    if args.template == 'social' and data.get('title'):
        raise SystemExit('social template does not accept a title')
    title = str(data.get('title', '')).strip() if args.template == 'iqiyi' else ''
    title_mode = data.get('title_mode', 'two')
    if title_mode not in ('one', 'two'):
        raise SystemExit('title_mode must be "one" or "two"')
    cfg = json.loads((ROOT / 'rules' / f'{args.template}.json').read_text(encoding='utf-8'))
    ass_path = Path(args.ass) if args.ass else output_path.with_suffix('.ass')
    ass_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ass_path.write_text(build_ass(cfg, title, captions, title_mode), encoding='utf-8')
    subtitle_file = str(ass_path).replace('\\', '/').replace(':', r'\\:')
    fonts_dir = str(ROOT / 'assets' / 'fonts').replace('\\', '/').replace(':', r'\\:')
    subprocess.run(['ffmpeg', '-y', '-i', str(input_path), '-vf', f"subtitles={subtitle_file}:fontsdir={fonts_dir}", '-c:a', 'copy', str(output_path)], check=True)
    print(f'created video: {output_path}')
    print(f'created subtitles: {ass_path}')

if __name__ == '__main__':
    main()
