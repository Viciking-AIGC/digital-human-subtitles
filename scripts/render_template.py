#!/usr/bin/env python3
"""Render deterministic ASS captions for the social and iqiyi templates."""
import argparse, json, re, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def ass_color(hex_color):
    h = hex_color.lstrip('#')
    return '&H00' + h[4:6] + h[2:4] + h[0:2]

def ts(seconds):
    cs = int(round(seconds * 100))
    return f"{cs//360000}:{(cs//6000)%60:02d}:{(cs//100)%60:02d}.{cs%100:02d}"

def esc(text):
    return text.replace('\\', r'\\').replace('{', r'\\{').replace('}', r'\\}')

def ass_header(cfg):
    c = cfg['canvas']
    return f'''[Script Info]\nScriptType: v4.00+\nPlayResX: {c['width']}\nPlayResY: {c['height']}\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n'''

def build_ass(cfg, title, captions, title_mode='two'):
    s = cfg['subtitle']
    lines = [ass_header(cfg)]
    render_font = s.get('render_font', s['font'])
    lines.append(f"Style: Subtitle,{render_font},{s['font_size']},{ass_color(s['color'])},{ass_color(s['color'])},{ass_color(s['outline_color'])},&H00000000,-1,0,0,0,{s['scale_x']},{s['scale_y']},0,0,1,{s['outline']},{s['shadow']},2,20,20,0,1\n")
    if cfg['title']:
        t = cfg['title']
        lines.append(f"Style: TitleMain,{t['font']},{t['font_size']},{ass_color(t['line_1']['color'])},{ass_color(t['line_1']['color'])},{ass_color(t['line_1']['outline_color'])},&H00000000,-1,0,0,0,{t['scale_x']},{t['scale_y']},0,0,1,{t['line_1']['outline']},0,8,20,20,0,1\n")
        lines.append(f"Style: TitleSub,{t['font']},{t['font_size']},{ass_color(t['line_2']['color'])},{ass_color(t['line_2']['color'])},{ass_color(t['line_2']['outline_color'])},&H00000000,-1,0,0,0,{t['scale_x']},{t['scale_y']},0,0,1,{t['line_2']['outline']},0,8,20,20,0,1\n")
    lines.append("\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")
    if cfg['title'] and title:
        parts = re.split(r'\s+', title.strip(), maxsplit=1)
        t = cfg['title']; x, y = t['position']['x'], t['position']['y']
        if title_mode == 'one' and len(parts) > 1:
            first = ass_color(t['line_1']['color'])
            first_outline = ass_color(t['line_1']['outline_color'])
            second = ass_color(t['line_2']['color'])
            second_outline = ass_color(t['line_2']['outline_color'])
            combined = (f"{{\\pos({x},{y})\\c{first}\\3c{first_outline}}}{esc(parts[0])} "
                        f"{{\\c{second}\\3c{second_outline}}}{esc(parts[1])}")
            lines.append(f"Dialogue: 1,0:00:00.00,9:59:59.00,TitleMain,,0,0,0,,{combined}\n")
        else:
            lines.append(f"Dialogue: 1,0:00:00.00,9:59:59.00,TitleMain,,0,0,0,,{{\\pos({x},{y})}}{esc(parts[0])}\n")
        if title_mode != 'one' and len(parts) > 1:
            # ASS positions anchor each top-aligned title line. Add one font size plus the requested net gap.
            second_line_y = y + t['font_size'] + t['position']['line_gap']
            lines.append(f"Dialogue: 1,0:00:00.00,9:59:59.00,TitleSub,,0,0,0,,{{\\pos({x},{second_line_y:g})}}{esc(parts[1])}\n")
    for start, end, text in captions:
        lines.append(f"Dialogue: 0,{ts(start)},{ts(end)},Subtitle,,0,0,0,,{{\\pos({s['position']['x']},{s['position']['y']})}}{esc(text)}\n")
    return ''.join(lines)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--template', choices=['social', 'iqiyi'], required=True)
    ap.add_argument('--input', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--ass', required=True)
    ap.add_argument('--title', default='')
    ap.add_argument('--title-mode', choices=['one', 'two'], default='two')
    ap.add_argument('--captions-json', help='JSON array of {start, end, text} caption objects')
    args = ap.parse_args()
    cfg = json.loads((ROOT / 'rules' / f'{args.template}.json').read_text(encoding='utf-8'))
    captions = [(0, 2.55, '王总，这是给你的礼物'), (2.55, 4.10, '我不是王总'), (4.10, 5.20, '那谁是'), (5.20, 6.70, '这只猫')]
    if args.captions_json:
        raw = json.loads(Path(args.captions_json).read_text(encoding='utf-8'))
        captions = [(float(item['start']), float(item['end']), str(item['text'])) for item in raw]
    ass_path = Path(args.ass)
    output_path = Path(args.output)
    ass_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ass_path.write_text(build_ass(cfg, args.title, captions, args.title_mode), encoding='utf-8')
    subtitle_file = str(ass_path).replace('\\', '/').replace(':', r'\\:')
    fonts_dir = str(ROOT / 'assets' / 'fonts').replace('\\', '/').replace(':', r'\\:')
    subprocess.run(['ffmpeg', '-y', '-i', args.input, '-vf', f"subtitles={subtitle_file}:fontsdir={fonts_dir}", '-c:a', 'copy', str(output_path)], check=True)

if __name__ == '__main__': main()
