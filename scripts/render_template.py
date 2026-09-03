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

def is_inside_protected_phrase(text, position, phrases):
    """Return whether a proposed split falls inside any protected phrase."""
    for phrase in phrases:
        if not phrase:
            continue
        start = text.find(phrase)
        while start >= 0:
            if start < position < start + len(phrase):
                return True
            start = text.find(phrase, start + 1)
    return False

def semantic_redfruit_chunks(part, max_chars, protected_phrases=()):
    """Split a punctuation-free sentence at likely Chinese phrase boundaries."""
    chunks = []
    while len(part) > max_chars:
        window = part[:max_chars]
        candidates = []
        for position in range(1, max_chars + 1):
            prefix = window[:position]
            suffix = part[position:]
            score = 0
            # Keep configured keyword phrases in one subtitle event so their
            # local color override is not lost across a line split.
            if is_inside_protected_phrase(part, position, protected_phrases):
                score -= 1000
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

def split_redfruit_text(text, max_chars=10, protected_phrases=()):
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
        chunks.extend(semantic_redfruit_chunks(part, max_chars, protected_phrases))
    return chunks

def split_benxian_text(text):
    """Split 奔现 copy into display lines while retaining inline spaces."""
    chunks = []
    current = []
    for char in text:
        if is_punctuation(char):
            if current:
                chunks.append(''.join(current).strip())
                current = []
        else:
            current.append(char)
    if current:
        chunks.append(''.join(current).strip())
    return [chunk for chunk in chunks if chunk]

def split_sticker_text(text):
    """Split sticker copy at punctuation into simultaneous display paragraphs."""
    chunks = []
    current = []
    for char in text:
        if is_punctuation(char):
            if ''.join(current).strip():
                chunks.append(''.join(current).strip())
                current = []
        else:
            current.append(char)
    if ''.join(current).strip():
        chunks.append(''.join(current).strip())
    return [chunk for chunk in chunks if chunk]

def sticker_paragraphs(captions):
    """Return caption timing paired with punctuation-separated paragraphs."""
    return [(start, end, split_sticker_text(text)) for start, end, text in captions]

def benxian_caption_events(captions, subtitle):
    """Render each caption as one simultaneous multi-line paragraph."""
    events = []
    for start, end, text in captions:
        lines = split_benxian_text(text)
        if lines:
            events.append((start, end, r'\N'.join(lines)))
    return events

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

def style_social_keywords(text, keywords, color, outline_color, base_color, base_outline_color):
    """Apply yellow fill and black outline only to configured social phrases."""
    phrases = sorted({phrase for phrase in keywords if phrase}, key=len, reverse=True)
    if not phrases:
        return esc(text)
    highlight = ass_color(color)
    highlight_outline = ass_color(outline_color)
    base = ass_color(base_color)
    base_outline = ass_color(base_outline_color)
    pieces = []
    cursor = 0
    while cursor < len(text):
        phrase = next((candidate for candidate in phrases if text.startswith(candidate, cursor)), None)
        if phrase is None:
            pieces.append(esc(text[cursor]))
            cursor += 1
            continue
        pieces.append(f"{{\\1c{highlight}&\\3c{highlight_outline}&}}{esc(phrase)}"
                     f"{{\\1c{base}&\\3c{base_outline}&}}")
        cursor += len(phrase)
    return ''.join(pieces)

def redfruit_caption_events(captions, subtitle):
    """Expand redfruit captions into non-overlapping, timed chunks."""
    max_chars = int(subtitle.get('max_chars_per_line', 10))
    events = []
    for start, end, text in captions:
        chunks = split_redfruit_text(text, max_chars, subtitle.get('highlight_keywords', ()))
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

def build_ass(cfg, title, captions, title_mode='two', show_social_cta=False,
              social_variant='standard', social_font=None, social_title='',
              social_title_style=None):
    s = cfg['subtitle']
    if cfg.get('template') == 'social' and social_variant != 'standard':
        variant = cfg.get('variants', {}).get(social_variant)
        if variant is None:
            raise ValueError(f'unknown social variant: {social_variant}')
        s = {**s, **variant}
        selected_font = social_font or variant.get('default_font')
        font_options = variant.get('fonts', {})
        if selected_font not in font_options:
            raise ValueError(f'unknown {social_variant} font: {selected_font}')
        s.update(font_options[selected_font])
    lines = [ass_header(cfg)]
    render_font = s.get('render_font', s['font'])
    lines.append(f"Style: Subtitle,{render_font},{s['font_size']},{ass_color(s['color'])},{ass_color(s['color'])},{ass_color(s['outline_color'])},&H00000000,-1,0,0,0,{s['scale_x']},{s['scale_y']},0,0,1,{s['outline']},{s['shadow']},{s.get('alignment', 2)},20,20,0,1\n")
    social_title_cfg = None
    if cfg.get('template') == 'social' and social_variant == '奔现' and social_title:
        title_cfg = cfg.get('variants', {}).get('奔现', {}).get('title', {})
        style_name = social_title_style or next(iter(title_cfg.get('styles', {})), None)
        social_title_cfg = title_cfg.get('styles', {}).get(style_name)
        if social_title_cfg is None:
            raise ValueError(f'unknown 奔现 title style: {style_name}')
        title_font = social_title_cfg.get('render_font', social_title_cfg['font'])
        bold = -1 if social_title_cfg.get('bold', False) else 0
        italic = -1 if social_title_cfg.get('italic', False) else 0
        lines.append(
            f"Style: SocialTitle,{title_font},{title_cfg.get('font_size', 40)},"
            f"{ass_color(social_title_cfg['color'])},{ass_color(social_title_cfg['color'])},"
            f"{ass_color(social_title_cfg['outline_color'])},&H00000000,{bold},{italic},0,0,"
            f"{social_title_cfg.get('scale_x', 100)},{social_title_cfg.get('scale_y', 100)},0,0,1,"
            f"{social_title_cfg.get('outline', 2.5)},{social_title_cfg.get('shadow', 1)},"
            f"{title_cfg.get('alignment', 8)},20,20,0,1\n"
        )
    if cfg['title']:
        t = cfg['title']
        lines.append(f"Style: TitleMain,{t['font']},{t['font_size']},{ass_color(t['line_1']['color'])},{ass_color(t['line_1']['color'])},{ass_color(t['line_1']['outline_color'])},&H00000000,-1,0,0,0,{t['scale_x']},{t['scale_y']},0,0,1,{t['line_1']['outline']},0,8,20,20,0,1\n")
        lines.append(f"Style: TitleSub,{t['font']},{t['font_size']},{ass_color(t['line_2']['color'])},{ass_color(t['line_2']['color'])},{ass_color(t['line_2']['outline_color'])},&H00000000,-1,0,0,0,{t['scale_x']},{t['scale_y']},0,0,1,{t['line_2']['outline']},0,8,20,20,0,1\n")
    lines.append("\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")
    if social_title_cfg is not None and captions:
        title_cfg = cfg['variants']['奔现']['title']
        title_start = min(start for start, _, _ in captions)
        title_end = max(end for _, end, _ in captions)
        title_position = title_cfg.get('position', {'x': 248, 'y': 50})
        x = title_position['x']
        # Font ascenders/descenders differ even at the same nominal size.  Keep
        # the configured top anchor stable while allowing per-style baseline
        # calibration to nudge the rendered glyph box by a few pixels.
        y = float(title_position['y']) + float(social_title_cfg.get('baseline_offset_y', 0))
        # A title may be supplied from the material library or as free text.
        # Treat the first whitespace as the optional two-line break and keep
        # the whole title in one centered ASS event.
        title_parts = re.split(r'\s+', social_title.strip(), maxsplit=1)
        title_body = r'\N'.join(esc(part) for part in title_parts)
        lines.append(
            f"Dialogue: 1,{ts(title_start)},{ts(title_end)},SocialTitle,,0,0,0,,"
            f"{{\\pos({x},{y:g})}}{title_body}\n"
        )
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
    if cfg.get('template') == 'social' and social_variant == '奔现':
        rendered_captions = benxian_caption_events(captions, s)
    elif s.get('punctuation_split'):
        rendered_captions = redfruit_caption_events(captions, s)
    for start, end, text in rendered_captions:
        body = esc(text)
        if cfg.get('template') == 'social' and social_variant == '奔现':
            # ASS uses a single backslash N as an in-event line break; keep it
            # intact while still escaping user-provided backslashes elsewhere.
            body = body.replace(r'\\N', r'\N')
        if cfg.get('template') in ('redfruit', 'info_feed_ad'):
            body = style_redfruit_keyword(text, s.get('keyword', ''), s.get('keyword_outline_color', '#ED1C2E'))
        elif cfg.get('template') == 'social' and social_variant == 'standard':
            body = style_social_keywords(
                text,
                s.get('highlight_keywords', ()),
                s.get('highlight_color', '#FFE500'),
                s.get('highlight_outline_color', s.get('outline_color', '#101010')),
                s.get('color', '#FFFFFF'),
                s.get('outline_color', '#101010'),
            )
        position = s['position']
        baseline_offset_y = float(s.get('baseline_offset_y', 0))
        if s.get('position_mode') == 'center_origin':
            x, y = standard_center_position(cfg, position)
            y += baseline_offset_y
            position_text = f'{x:g},{y:g}'
        else:
            y = float(position['y']) + baseline_offset_y
            position_text = f"{position['x']},{y:g}"
        lines.append(f"Dialogue: 0,{ts(start)},{ts(end)},Subtitle,,0,0,0,,{{\\pos({position_text})}}{body}\n")
    return ''.join(lines)

def ass_color_alpha(hex_color, alpha):
    """ASS color with an explicit alpha byte (00=opaque, FF=transparent)."""
    h = hex_color.lstrip('#')
    return '&H' + alpha.upper() + h[4:6] + h[2:4] + h[0:2]

def xindong_effective_len(text):
    """CJK glyphs count 1, others 0.55, for sticker width estimation."""
    return sum(1.0 if ord(char) > 0x2E7F else 0.55 for char in text)

def xindong_geometry(cfg, text):
    """Return font size and estimated half-width for one sticker line."""
    s = cfg['sticker']
    eff_len = max(xindong_effective_len(text), 1.0)
    font_size = min(s['font_size'], max(s['min_font_size'], int(s['max_width'] / eff_len)))
    return font_size, font_size * eff_len / 2

XINDONG_LAYER_ORDER = ('glow_out', 'glow', 'cyan', 'pink', 'face')

def build_xindong_ass(cfg, captions):
    """Render punctuation-separated paragraphs as a stacked layered sticker."""
    s = cfg['sticker']
    layers = s['layers']
    outline = ass_color(s['outline_color'])
    pos = s['position']
    pop = s['pop']
    scale_x = float(s.get('scale_x', 100))
    scale_y = float(s.get('scale_y', 100))
    lines = [ass_header(cfg)]
    for name in XINDONG_LAYER_ORDER:
        layer = layers[name]
        color = ass_color_alpha(layer['color'], layer['alpha'])
        outline_color = outline if layer['alpha'] == '00' else color
        lines.append(f"Style: Xindong-{name},{s['font']},{s['font_size']},{color},{color},{outline_color},&H00000000,0,0,0,0,{scale_x:g},{scale_y:g},0,0,1,{layer['outline']},0,5,0,0,0,1\n")
    lines.append("\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")
    pop_transform = (r"\fscx{0:g}\fscy{1:g}\t(0,{2:g},1.4,\fscx{3:g}\fscy{4:g})\t({2:g},{5:g},0.7,\fscx{6:g}\fscy{7:g})"
                     .format(scale_x * pop['scale_from'] / 100,
                             scale_y * pop['scale_from'] / 100,
                             pop['t1_ms'],
                             scale_x * pop['overshoot'] / 100,
                             scale_y * pop['overshoot'] / 100,
                             pop['t2_ms'], scale_x, scale_y))
    paragraph_gap = float(s.get('paragraph', {}).get('line_gap', 12))
    for start, end, text in captions:
        paragraphs = split_sticker_text(text) or [text.strip()]
        metrics = [xindong_geometry(cfg, paragraph) for paragraph in paragraphs]
        row_step = max((font_size for font_size, _ in metrics), default=s['font_size']) + paragraph_gap
        block_center = (len(paragraphs) - 1) / 2
        max_font_size = max((font_size for font_size, _ in metrics), default=s['font_size'])
        for row, (paragraph, (font_size, half_width)) in enumerate(zip(paragraphs, metrics)):
            k = font_size / s['font_size']
            row_y = pos['y'] - max_font_size / 2 - (len(paragraphs) - 1 - row) * row_step
            row_x = pos['x'] + half_width if s.get('position_mode') == 'left_bottom' else pos['x']
            for depth, name in enumerate(XINDONG_LAYER_ORDER):
                layer = layers[name]
                offset_x = layer.get('offset_x', layer['offset']) * k
                offset_y = layer.get('offset_y', layer['offset']) * k
                tags = (f"{{\\an5\\pos({row_x + offset_x:g},{row_y + offset_y:g})\\fs{font_size}"
                        f"\\bord{layer['outline'] * k:g}\\blur{layer['blur'] * k:g}{pop_transform}}}")
                lines.append(f"Dialogue: {depth},{ts(start)},{ts(end)},Xindong-{name},,0,0,0,,{tags}{esc(paragraph)}\n")
    return ''.join(lines)

def shuangxiang_geometry(cfg, text):
    """Return (font_size, advance, half_width) for one staggered sticker line."""
    s = cfg['sticker']
    n = max(len(text), 1)
    base = s['font_size']
    if n > 1:
        fit = int(2 * s['max_half_width'] / (s['advance_ratio'] * (n - 1) + 1))
        font_size = min(base, max(s['min_font_size'], fit))
    else:
        font_size = base
    advance = s['advance_ratio'] * font_size
    half_width = ((n - 1) * advance + font_size) / 2
    return font_size, advance, half_width

SHUANGXIANG_LAYER_ORDER = ('glow_out', 'glow', 'face_top', 'face_bottom')
SHUANGXIANG_FACE_LAYERS = ('face_top', 'face_bottom')

def build_shuangxiang_ass(cfg, captions):
    """Render punctuation-separated paragraphs as stacked neon glyph rows.

    The pink-blue face is faked with two half-height clipped layers: pink on
    top, blue on bottom, both edge-blurred so the seam reads as a gradient.
    """
    s = cfg['sticker']
    layers = s['layers']
    pos = s['position']
    ent = s['entrance']
    scale_x = float(s.get('scale_x', 100))
    scale_y = float(s.get('scale_y', 100))
    italic = -1 if s.get('italic') else 0
    grow = float(ent['scale_from']) / 100
    lines = [ass_header(cfg)]
    for name in SHUANGXIANG_LAYER_ORDER:
        layer = layers[name]
        color = ass_color_alpha(layer['color'], layer['alpha'])
        lines.append(f"Style: Shuangxiang-{name},{s['font']},{s['font_size']},{color},{color},{color},&H00000000,0,{italic},0,0,{scale_x:g},{scale_y:g},0,0,1,{layer['outline']},0,5,0,0,0,1\n")
    lines.append("\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")
    paragraph_gap = float(s.get('paragraph', {}).get('line_gap', 18))
    for start, end, text in captions:
        paragraphs = split_sticker_text(text) or [text.strip()]
        metrics = [shuangxiang_geometry(cfg, paragraph) for paragraph in paragraphs]
        row_step = max((font_size for font_size, _, _ in metrics), default=s['font_size']) + paragraph_gap
        block_center = (len(paragraphs) - 1) / 2
        max_font_size = max((font_size for font_size, _, _ in metrics), default=s['font_size'])
        for row, (paragraph, (font_size, advance, half_width)) in enumerate(zip(paragraphs, metrics)):
            k = font_size / s['font_size']
            stagger = s['stagger'] * k
            n = len(paragraph)
            row_center_y = pos['y'] - max_font_size / 2 - (len(paragraphs) - 1 - row) * row_step
            row_center_x = pos['x'] + half_width if s.get('position_mode') == 'left_bottom' else pos['x']
            for index, char in enumerate(paragraph):
                char_x = row_center_x + (index - (n - 1) / 2) * advance
                char_y = row_center_y + (stagger if index % 2 else -stagger)
                for depth, name in enumerate(SHUANGXIANG_LAYER_ORDER):
                    layer = layers[name]
                    offset_x = layer.get('offset_x', layer['offset']) * k
                    offset_y = layer.get('offset_y', layer['offset']) * k
                    entrance = (f"\\fscx{scale_x * grow:g}\\fscy{scale_y * grow:g}\\blur{ent['blur_from']}"
                                f"\\t(0,{ent['duration_ms']},0.8,\\fscx{scale_x:g}\\fscy{scale_y:g}\\blur{layer['blur'] * k:g})")
                    clip = ''
                    if name in SHUANGXIANG_FACE_LAYERS:
                        half_box = font_size * 0.62
                        y_top = char_y - font_size * 0.75
                        y_bottom = char_y + font_size * 0.75
                        y_split = char_y + (font_size * 0.05 if name == 'face_top' else -font_size * 0.05)
                        y1, y2 = (y_top, y_split) if name == 'face_top' else (y_split, y_bottom)
                        clip = f"\\clip({char_x - half_box:g},{y1:g},{char_x + half_box:g},{y2:g})"
                    tags = (f"{{\\pos({char_x + offset_x:g},{char_y + offset_y:g})\\fs{font_size}"
                            f"\\bord{layer['outline'] * k:g}{clip}{entrance}}}")
                    lines.append(f"Dialogue: {depth},{ts(start)},{ts(end)},Shuangxiang-{name},,0,0,0,,{tags}{esc(char)}\n")
    return ''.join(lines)

def siyue_geometry(cfg, text):
    """Return (font_size, half_width) for one centered 人间四月天 line."""
    s = cfg['sticker']
    eff_len = max(xindong_effective_len(text), 1.0)
    font_size = min(s['font_size'], max(s['min_font_size'], int(s['max_width'] / eff_len)))
    return font_size, font_size * eff_len / 2

SIYUE_LAYER_ORDER = ('glow_out', 'glow', 'face')

def build_siyue_ass(cfg, captions):
    """Render punctuation-separated paragraphs as stacked serif lines."""
    s = cfg['sticker']
    layers = s['layers']
    pos = s['position']
    ent = s['entrance']
    scale_x = float(s.get('scale_x', 100))
    scale_y = float(s.get('scale_y', 100))
    lines = [ass_header(cfg)]
    for name in SIYUE_LAYER_ORDER:
        layer = layers[name]
        color = ass_color_alpha(layer['color'], layer['alpha'])
        outline_color = color if layer['alpha'] != '00' else ass_color(layers['glow']['color'])
        lines.append(f"Style: Siyue-{name},{s['font']},{s['font_size']},{color},{color},{outline_color},&H00000000,0,0,0,0,{scale_x:g},{scale_y:g},0,0,1,{layer['outline']},0,5,0,0,0,1\n")
    lines.append("\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")
    paragraph_gap = float(s.get('paragraph', {}).get('line_gap', 12))
    for start, end, text in captions:
        paragraphs = split_sticker_text(text) or [text.strip()]
        metrics = [siyue_geometry(cfg, paragraph) for paragraph in paragraphs]
        row_step = max((font_size for font_size, _ in metrics), default=s['font_size']) + paragraph_gap
        block_center = (len(paragraphs) - 1) / 2
        max_font_size = max((font_size for font_size, _ in metrics), default=s['font_size'])
        for row, (paragraph, (font_size, half_width)) in enumerate(zip(paragraphs, metrics)):
            k = font_size / s['font_size']
            row_y = pos['y'] - max_font_size / 2 - (len(paragraphs) - 1 - row) * row_step
            row_x = pos['x'] + half_width if s.get('position_mode') == 'left_bottom' else pos['x']
            for depth, name in enumerate(SIYUE_LAYER_ORDER):
                layer = layers[name]
                blur_rest = layer['blur'] * k
                entrance = (f"\\fscx{scale_x * ent['scale_from'] / 100:g}\\fscy{scale_y * ent['scale_from'] / 100:g}\\blur{blur_rest + ent['blur_from']:g}"
                            f"\\t(0,{ent['duration_ms']},0.8,\\fscx{scale_x:g}\\fscy{scale_y:g}\\blur{blur_rest:g})")
                tags = (f"{{\\an5\\pos({row_x:g},{row_y:g})\\fs{font_size}"
                        f"\\bord{layer['outline'] * k:g}{entrance}}}")
                lines.append(f"Dialogue: {depth},{ts(start)},{ts(end)},Siyue-{name},,0,0,0,,{tags}{esc(paragraph)}\n")
    return ''.join(lines)

def xiari_geometry(cfg, text):
    """Return (font_size, center_x, paper_half_width) for one 夏日限定美好 line.

    The paper strip width follows the text: text width plus a fixed margin on
    each side, capped at paper.max_width (the font shrinks to respect the cap).
    """
    s = cfg['sticker']
    paper = s['paper']
    margin = float(paper['margin'])
    max_text = float(paper['max_width']) - 2 * margin
    eff_len = max(xindong_effective_len(text), 1.0)
    font_size = min(s['font_size'], max(s['min_font_size'], int(max_text / eff_len)))
    paper_half = min(float(paper['max_width']) / 2, font_size * eff_len / 2 + margin)
    return font_size, float(s['position']['x']), paper_half

def xiari_paragraph_geometry(cfg, paragraphs):
    """Return shared font/strip geometry for a stacked punctuation-split block."""
    s = cfg['sticker']
    paper = s['paper']
    margin = float(paper['margin'])
    max_text = float(paper['max_width']) - 2 * margin
    effective_lengths = [max(xindong_effective_len(paragraph), 1.0) for paragraph in paragraphs]
    longest = max(effective_lengths, default=1.0)
    font_size = min(s['font_size'], max(s['min_font_size'], int(max_text / longest)))
    paper_half = min(float(paper['max_width']) / 2, font_size * longest / 2 + margin)
    line_gap = float(s.get('paragraph', {}).get('line_gap', 8))
    row_step = font_size + line_gap
    paper_height = max(float(paper['height']), len(paragraphs) * font_size + max(0, len(paragraphs) - 1) * line_gap + 20)
    return font_size, float(s['position']['x']), paper_half, row_step, paper_height

def build_xiari_ass(cfg, captions):
    """Render punctuation-separated paragraphs as typewriter lines on one strip.

    One Dialogue event per prefix: event i shows text[:i+1] from its reveal
    time until the caption ends, so characters appear one by one while the
    partial line stays centered on the strip.
    """
    s = cfg['sticker']
    pos = s['position']
    tw = s['typewriter']
    color = ass_color_alpha(s['color'], '00')
    lines = [ass_header(cfg)]
    lines.append(f"Style: Xiari,{s['font']},{s['font_size']},{color},{color},{color},&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1\n")
    lines.append("\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")
    for start, end, text in captions:
        paragraphs = split_sticker_text(text) or [text.strip()]
        font_size, center_x, _, row_step, paper_height = xiari_paragraph_geometry(cfg, paragraphs)
        block_center = (len(paragraphs) - 1) / 2
        block_center_y = pos['y'] - paper_height / 2 if s.get('position_mode') == 'left_bottom' else pos['y']
        for row, paragraph in enumerate(paragraphs):
            row_y = block_center_y + (row - block_center) * row_step
            text_half_width = font_size * max(xindong_effective_len(paragraph), 1.0) / 2
            row_x = center_x + text_half_width if s.get('position_mode') == 'left_bottom' else center_x
            reveals = [start + float(tw['delay']) + index * float(tw['char_seconds'])
                       for index in range(len(paragraph))]
            reveals = [reveal for reveal in reveals if reveal < end]
            for index, reveal in enumerate(reveals):
                # each prefix is replaced by the next one, so events never overlap
                prefix_end = reveals[index + 1] if index + 1 < len(reveals) else end
                tags = f"{{\\an5\\pos({row_x:g},{row_y:g})\\fs{font_size}}}"
                lines.append(f"Dialogue: 0,{ts(reveal)},{ts(prefix_end)},Xiari,,0,0,0,,{tags}{esc(paragraph[:index + 1])}\n")
    return ''.join(lines)

HUANGXING_LAYER_ORDER = ('glow_out', 'glow', 'outline', 'face')

def huangxing_lines(text):
    """Split a caption into main/sub lines on '|'; a single line stays one."""
    parts = [part.strip() for part in text.split('|') if part.strip()]
    return parts[:2] if parts else ['']

def huangxing_geometry(cfg, text):
    """Return (font_size, block_half_width) for the 黄色星星 sticker.

    Both lines share one size, shrunk together so the longest line fits.
    """
    s = cfg['sticker']
    lengths = [max(xindong_effective_len(line), 1.0) for line in huangxing_lines(text)]
    longest = max(lengths, default=1.0)
    size = min(s['font_size'], max(s['min_font_size'], int(s['max_width'] / longest)))
    return size, size * longest / 2

def build_huangxing_ass(cfg, captions):
    """Render each caption as one or two centered italic lines with a warm glow.

    Layers per line: soft outer glow, glow, hard warm outline, cream face.
    Entrance: 85% scale + blur easing to sharp over the configured duration.
    """
    s = cfg['sticker']
    layers = s['layers']
    pos = s['position']
    ent = s['entrance']
    italic = -1 if s.get('italic') else 0
    scale_x = float(s.get('scale_x', 100))
    scale_y = float(s.get('scale_y', 100))
    lines = [ass_header(cfg)]
    for name in HUANGXING_LAYER_ORDER:
        layer = layers[name]
        color = ass_color_alpha(layer['color'], layer['alpha'])
        outline_color = color if layer['alpha'] != '00' else ass_color(layer['color'])
        lines.append(f"Style: Huangxing-{name},{s['font']},{s['font_size']},{color},{color},{outline_color},&H00000000,0,{italic},0,0,{scale_x:g},{scale_y:g},0,0,1,{layer['outline']},0,5,0,0,0,1\n")
    lines.append("\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")
    for start, end, text in captions:
        size, _ = huangxing_geometry(cfg, text)
        text_lines = huangxing_lines(text)
        gap = float(s['line_gap'])
        if len(text_lines) == 1:
            ys = [float(pos['y'])]
        else:
            ys = [pos['y'] - gap / 2, pos['y'] + gap / 2]
        for line, y in zip(text_lines, ys):
            k = size / s['font_size']
            for depth, name in enumerate(HUANGXING_LAYER_ORDER):
                layer = layers[name]
                blur_rest = layer['blur'] * k
                entrance = (f"\\fscx{scale_x * ent['scale_from'] / 100:g}\\fscy{scale_y * ent['scale_from'] / 100:g}\\blur{blur_rest + ent['blur_from']:g}"
                            f"\\t(0,{ent['duration_ms']},0.8,\\fscx{scale_x:g}\\fscy{scale_y:g}\\blur{blur_rest:g})")
                tags = (f"{{\\an5\\pos({pos['x']},{y:g})\\fs{size}"
                        f"\\bord{layer['outline'] * k:g}{entrance}}}")
                lines.append(f"Dialogue: {depth},{ts(start)},{ts(end)},Huangxing-{name},,0,0,0,,{tags}{esc(line)}\n")
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
