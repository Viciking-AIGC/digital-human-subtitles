#!/usr/bin/env python3
"""Render deterministic ASS captions for the social, 信息流广告, and iQiyi templates."""
import argparse, json, re, string, subprocess, unicodedata
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

def is_punctuation(char):
    return char in string.punctuation or unicodedata.category(char).startswith('P')

RED_FRUIT_BOUNDARY_END = set('了的是吗呢吧啊呀着过看来到上下里中人')
RED_FRUIT_BOUNDARY_START = (
    '我', '你', '他', '她', '它', '这', '那', '快', '请', '看', '后', '再',
    '但', '而', '因', '所', '如', '然', '其', '根本', '真的', '现在', '然后',
)
RED_FRUIT_BOUNDARY_PHRASES = ('红果短剧', '后续内容', '精彩内容', '认错人了')

def semantic_redfruit_chunks(part, max_chars):
    """Split a punctuation-free sentence at likely Chinese phrase boundaries."""
    chunks = []
    while len(part) > max_chars:
        window = part[:max_chars]
        candidates = []
        for position in range(1, max_chars + 1):
            prefix = window[:position]
            suffix = part[position:]
            score = 0
            if prefix[-1:] in RED_FRUIT_BOUNDARY_END:
                score += 35
            if any(suffix.startswith(marker) for marker in RED_FRUIT_BOUNDARY_START):
                score += 35
            if any(prefix.endswith(phrase) for phrase in RED_FRUIT_BOUNDARY_PHRASES):
                score += 70
            # Prefer readable phrase lengths when several boundaries are equivalent.
            if 4 <= position <= 8:
                score += 8
            score -= abs(7 - position)
            candidates.append((score, position))
        _, position = max(candidates)
        chunks.append(part[:position])
        part = part[position:]
    if part:
        chunks.append(part)
    return chunks

def split_redfruit_text(text, max_chars=10):
    """Drop punctuation, split there first, then use semantic boundaries under 10 chars."""
    punctuation_parts = []
    current = []
    for char in text:
        if is_punctuation(char) or char.isspace():
            if ''.join(current).strip():
                punctuation_parts.append(''.join(current).strip())
            current = []
        else:
            current.append(char)
    if ''.join(current).strip():
        punctuation_parts.append(''.join(current).strip())

    chunks = []
    for part in punctuation_parts:
        chunks.extend(semantic_redfruit_chunks(part, max_chars))
    return chunks

def style_redfruit_keyword(text, keyword, outline_color):
    """Apply a red outline only to keyword occurrences; the base style remains black."""
    if not keyword or keyword not in text:
        return esc(text)
    red = ass_color(outline_color)
    black = ass_color('#101010')
    pieces = []
    cursor = 0
    while True:
        match = text.find(keyword, cursor)
        if match < 0:
            pieces.append(esc(text[cursor:]))
            break
        pieces.append(esc(text[cursor:match]))
        # Set both channels explicitly so the keyword remains white-filled in every libass build.
        pieces.append(f"{{\\1c&H00FFFFFF&\\3c{red}&}}{esc(keyword)}{{\\1c&H00FFFFFF&\\3c{black}&}}")
        cursor = match + len(keyword)
    return ''.join(pieces)

def redfruit_caption_events(captions, subtitle):
    """Expand redfruit captions into non-overlapping, timed chunks."""
    max_chars = int(subtitle.get('max_chars_per_line', 10))
    events = []
    for start, end, text in captions:
        chunks = split_redfruit_text(text, max_chars)
        if not chunks:
            continue
        weights = [max(1, len(chunk.replace(' ', ''))) for chunk in chunks]
        total_weight = sum(weights)
        cursor = start
        for index, (chunk, weight) in enumerate(zip(chunks, weights)):
            next_cursor = end if index == len(chunks) - 1 else cursor + (end - start) * weight / total_weight
            events.append((cursor, next_cursor, chunk))
            cursor = next_cursor
    return events

def redfruit_keyword_events(captions, subtitle):
    """Return only the first timed chunk containing the keyword for Logo overlay."""
    keyword = subtitle.get('keyword', '')
    if not keyword:
        return []
    for event in redfruit_caption_events(captions, subtitle):
        if keyword in event[2]:
            return [event]
    return []

# Compatibility name for callers that still use the former business-line slug.
info_feed_ad_keyword_events = redfruit_keyword_events

def ass_header(cfg):
    c = cfg['canvas']
    return f'''[Script Info]\nScriptType: v4.00+\nPlayResX: {c['width']}\nPlayResY: {c['height']}\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n'''

def standard_center_position(cfg, position):
    canvas = cfg['canvas']
    return (
        canvas['width'] / 2 + float(position['x']) * canvas['width'] / 1080 / 2,
        canvas['height'] / 2 + float(position['y']) * canvas['height'] / 1920 / 2,
    )

def build_ass(cfg, title, captions, title_mode='two', show_social_cta=False):
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
    if cfg.get('template') == 'social' and show_social_cta and cfg.get('cta'):
        cta = cfg['cta']
        x, y = standard_center_position(cfg, cta['position'])
        # Place each glyph explicitly so the vertical line gap remains deterministic.
        line_gap = float(cta.get('line_gap', cta['font_size']))
        arrow_gap = float(cta.get('arrow_gap', 6))
        arrow_height = float(cta.get('arrow_height', 140 * float(cta.get('arrow_width', cta['arrow_size'])) / 84))
        text_height = cta['font_size'] + (len(cta['text']) - 1) * line_gap
        group_height = text_height + arrow_gap + arrow_height
        group_top = y - group_height / 2 + float(cta.get('group_offset_y', 0))
        style_end = chr(10)
        lines.insert(2, f"Style: SocialCTA,{cta.get('render_font', cta['font'])},{cta['font_size']},{ass_color(cta['color'])},{ass_color(cta['color'])},{ass_color(cta['outline_color'])},&H00000000,-1,0,0,0,100,100,0,0,1,{cta['outline']},1,5,0,0,0,1{style_end}")
        if not cta.get('arrow_asset'):
            lines.insert(3, f"Style: SocialCTAArrow,{cta.get('render_font', cta['font'])},{cta['arrow_size']},{ass_color(cta['arrow_color'])},{ass_color(cta['arrow_color'])},{ass_color(cta['outline_color'])},&H00000000,-1,0,0,0,100,100,0,0,1,{cta.get('arrow_outline', 0)},{cta.get('arrow_shadow', 0)},5,0,0,1{style_end}")
        for index, char in enumerate(cta['text']):
            glyph_y = group_top + cta['font_size'] / 2 + index * line_gap
            lines.append(f"Dialogue: 2,0:00:00.00,9:59:59.00,SocialCTA,,0,0,0,,{{\\pos({x:.2f},{glyph_y:.2f})}}{esc(char)}" + chr(10))
        arrow_y = group_top + text_height + arrow_gap + arrow_height / 2
        if cta.get('arrow_asset'):
            arrow_body = None
        elif cta.get('arrow_vector'):
            arrow_shape = 'm -5 -30 l 5 -30 l 5 8 l 18 8 l 0 10 l -18 0 l 0 12 l -10 0 l 0 -12 l -18 0 l 0 -10 l 18 0 l 0 -8 l -5 0 z'
            arrow_body = f"{{\\pos({x:.2f},{arrow_y:.2f})\\c{ass_color(cta['arrow_color'])}\\p1}}{arrow_shape}{{\\p0}}"
        else:
            arrow_body = f"{{\\pos({x:.2f},{arrow_y:.2f})}}{esc(cta['arrow'])}"
        if arrow_body is not None:
            lines.append(f"Dialogue: 2,0:00:00.00,9:59:59.00,SocialCTAArrow,,0,0,0,,{arrow_body}" + chr(10))
    rendered_captions = captions
    if cfg.get('template') in ('redfruit', 'info_feed_ad') and s.get('punctuation_split'):
        rendered_captions = redfruit_caption_events(captions, s)
    for start, end, text in rendered_captions:
        body = esc(text)
        if cfg.get('template') in ('redfruit', 'info_feed_ad'):
            body = style_redfruit_keyword(text, s.get('keyword', ''), s.get('keyword_outline_color', '#ED1C2E'))
        lines.append(f"Dialogue: 0,{ts(start)},{ts(end)},Subtitle,,0,0,0,,{{\\pos({s['position']['x']},{s['position']['y']})}}{body}\n")
    return ''.join(lines)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--template', choices=['social', 'redfruit', 'info_feed_ad', 'iqiyi'], required=True)
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
