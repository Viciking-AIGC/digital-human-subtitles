#!/usr/bin/env python3
"""Generate a captioned digital-human video from a base video and script JSON."""
import argparse, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from render_template import build_ass, info_feed_ad_keyword_events

def render_video(template, input_path, script_path, output_path, ass_path=None):
    """Render one validated template request and return its output/ASS paths."""
    input_path = Path(input_path)
    script_path = Path(script_path)
    output_path = Path(output_path)
    data = json.loads(script_path.read_text(encoding='utf-8'))
    captions = [(float(item['start']), float(item['end']), str(item['text'])) for item in data.get('captions', [])]
    if not captions:
        raise SystemExit('script.captions must contain at least one caption')
    previous_end = 0.0
    for start, end, text in captions:
        if start < 0 or end <= start or start < previous_end or not text.strip():
            raise SystemExit(f'invalid caption segment: {start}, {end}, {text!r}')
        previous_end = end
    if template in ('social', 'redfruit', 'info_feed_ad') and data.get('title'):
        raise SystemExit(f'{template} template does not accept a title')
    title = str(data.get('title', '')).strip() if template == 'iqiyi' else ''
    title_mode = data.get('title_mode', 'two')
    if title_mode not in ('one', 'two'):
        raise SystemExit('title_mode must be "one" or "two"')
    cfg = json.loads((ROOT / 'rules' / f'{template}.json').read_text(encoding='utf-8'))
    selected_products = data.get('selected_products', [])
    if template == 'social':
        if not isinstance(selected_products, list) or any(not isinstance(product, str) or not product.strip() for product in selected_products):
            raise SystemExit('social script.selected_products must be an array of non-empty product names')
        eligible_products = set(cfg.get('cta', {}).get('eligible_products', []))
        show_social_cta = bool(eligible_products.intersection(selected_products))
    else:
        show_social_cta = False
    ass_path = Path(ass_path) if ass_path else output_path.with_suffix('.ass')
    ass_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ass_path.write_text(build_ass(cfg, title, captions, title_mode, show_social_cta), encoding='utf-8')
    subtitle_file = str(ass_path).replace('\\', '/').replace(':', r'\\:')
    fonts_dir = str(ROOT / 'assets' / 'fonts').replace('\\', '/').replace(':', r'\\:')
    if template in ('redfruit', 'info_feed_ad'):
        subtitle_cfg = cfg['subtitle']
        logo_events = info_feed_ad_keyword_events(captions, subtitle_cfg)
    else:
        logo_events = []
    if logo_events:
        logo_cfg = cfg['subtitle']['logo']
        logo_path = ROOT / logo_cfg['file']
        if not logo_path.is_file():
            raise SystemExit(f'info-feed-ad logo file not found: {logo_path}')
        logo_width = logo_cfg['width']
        logo_x = round(float(logo_cfg['position']['x']) - logo_width / 2)
        logo_y = logo_cfg['position']['y']
        enable = '+'.join(f"between(t,{start:.2f},{end:.2f})" for start, end, _ in logo_events)
        graph = (
            f"[0:v]subtitles={subtitle_file}:fontsdir={fonts_dir}[sub];"
            f"[1:v]scale={logo_width}:-1[logo];"
            f"[sub][logo]overlay=x={logo_x}:y={logo_y}:enable='{enable}'[v]"
        )
        subprocess.run([
            'ffmpeg', '-y', '-i', str(input_path), '-loop', '1', '-i', str(logo_path),
            '-filter_complex', graph, '-map', '[v]', '-map', '0:a?', '-c:a', 'copy',
            '-shortest', str(output_path)
        ], check=True)
    else:
        subtitle_filter = f"subtitles={subtitle_file}:fontsdir={fonts_dir}"
        if show_social_cta and cfg.get('cta', {}).get('arrow_asset'):
            cta = cfg['cta']
            canvas = cfg['canvas']
            x = canvas['width'] / 2 + float(cta['position']['x']) * canvas['width'] / 1080 / 2
            y = canvas['height'] / 2 + float(cta['position']['y']) * canvas['height'] / 1920 / 2
            group_offset_y = float(cta.get('group_offset_y', 0))
            line_gap = float(cta.get('line_gap', cta['font_size']))
            arrow_gap = float(cta.get('arrow_gap', 6))
            arrow_height = float(cta.get('arrow_height', 140 * float(cta.get('arrow_width', cta['arrow_size'])) / 84))
            text_height = cta['font_size'] + (len(cta['text']) - 1) * line_gap
            group_top = y - (text_height + arrow_gap + arrow_height) / 2 + group_offset_y
            arrow_y = group_top + text_height + arrow_gap + arrow_height / 2
            arrow_path = str(ROOT / cta['arrow_asset']).replace('\\', '/').replace(':', r'\\:')
            arrow_width = int(cta.get('arrow_width', cta['arrow_size']))
            arrow_height = int(round(cta.get('arrow_height', 140 * arrow_width / 84)))
            overlay_x = round(x - arrow_width / 2)
            overlay_y = round(arrow_y - arrow_height / 2)
            filter_complex = (
                f"[0:v]{subtitle_filter}[captioned];"
                f"movie={arrow_path},format=rgba,scale={arrow_width}:{arrow_height}[cta_arrow];"
                f"[captioned][cta_arrow]overlay={overlay_x}:{overlay_y}:shortest=0[v]"
            )
            command = ['ffmpeg', '-y', '-i', str(input_path), '-filter_complex', filter_complex, '-map', '[v]', '-map', '0:a?', '-c:v', 'libx264', '-c:a', 'copy', str(output_path)]
        else:
            command = ['ffmpeg', '-y', '-i', str(input_path), '-vf', subtitle_filter, '-c:a', 'copy', str(output_path)]
        subprocess.run(command, check=True)
    return output_path, ass_path

def main():
    ap = argparse.ArgumentParser(description='Apply a fixed social, 信息流广告, or iQiyi layout to a digital-human video.')
    ap.add_argument('--template', choices=['social', 'redfruit', 'info_feed_ad', 'iqiyi'], required=True)
    ap.add_argument('--input', required=True, help='Uploaded/generated digital-human MP4')
    ap.add_argument('--script', required=True, help='JSON script containing captions and optional title')
    ap.add_argument('--output', required=True, help='Output MP4 path')
    ap.add_argument('--ass', help='Optional ASS path; defaults beside output')
    args = ap.parse_args()

    output_path, ass_path = render_video(args.template, args.input, args.script, args.output, args.ass)
    print(f'created video: {output_path}')
    print(f'created subtitles: {ass_path}')

if __name__ == '__main__':
    main()
