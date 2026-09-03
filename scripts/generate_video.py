#!/usr/bin/env python3
"""Generate a captioned digital-human video from a base video and script JSON."""
import argparse, copy, json, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from render_template import build_ass, build_shuangxiang_ass, build_siyue_ass, build_huangxing_ass, build_xiari_ass, build_xindong_ass, info_feed_ad_keyword_events, shuangxiang_geometry, siyue_geometry, split_sticker_text, huangxing_geometry, huangxing_lines, xiari_geometry, xiari_paragraph_geometry, xindong_geometry
import sticker_assets

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
    if template in ('social', 'redfruit', 'info_feed_ad', 'xindong', 'shuangxiang', 'siyue', 'xiari', 'huangxing') and data.get('title'):
        raise SystemExit(f'{template} template does not accept a title; use social_title for Social 奔现')
    title = str(data.get('title', '')).strip() if template == 'iqiyi' else ''
    title_mode = data.get('title_mode', 'two')
    if title_mode not in ('one', 'two'):
        raise SystemExit('title_mode must be "one" or "two"')
    cfg = json.loads((ROOT / 'rules' / f'{template}.json').read_text(encoding='utf-8'))
    social_variant = str(data.get('social_variant', 'standard')).strip() or 'standard'
    social_font = data.get('social_font')
    social_title = str(data.get('social_title', '')).strip()
    social_title_style = data.get('social_title_style')
    if template == 'social' and social_variant == '奔现':
        title_rule = cfg.setdefault('variants', {}).setdefault('奔现', {}).setdefault('title', {})
        fixed_size = data.get('social_title_font_size')
        if fixed_size is not None and float(fixed_size) != float(title_rule.get('font_size', 35)):
            raise SystemExit('social_title_font_size is fixed at 35px for 奔现')
        fixed_position = data.get('social_title_position')
        if fixed_position is not None and fixed_position != title_rule.get('position', {'x': 248, 'y': 50}):
            raise SystemExit('social_title_position is fixed at x=248, y=50 for 奔现')
    if template == 'social' and social_variant != 'standard':
        variant = cfg.get('variants', {}).get(social_variant)
        if variant is None:
            raise SystemExit(f'unknown social variant: {social_variant}')
        if social_font is not None and social_font not in variant.get('fonts', {}):
            raise SystemExit(f'unknown {social_variant} font: {social_font}')
        if social_variant == '奔现':
            title_styles = variant.get('title', {}).get('styles', {})
            if social_title_style is not None and social_title_style not in title_styles:
                raise SystemExit(f'unknown 奔现 title style: {social_title_style}')
            if social_title_style is not None and not social_title:
                raise SystemExit('social_title_style requires social_title')
            if social_title and not social_title_style:
                raise SystemExit('social_title requires social_title_style')
    elif social_title or social_title_style:
        raise SystemExit('social_title and social_title_style are only supported for Social 奔现')
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
    if (template == 'social' and social_variant == '奔现' and social_title and
            social_title_style in ('黄色星星', '心动时刻')):
        return render_social_benxian_styled_title(
            cfg, captions, input_path, output_path, ass_path, social_font,
            social_title, social_title_style)
    if template == 'xindong':
        return render_xindong(cfg, captions, input_path, output_path, ass_path)
    if template == 'shuangxiang':
        return render_shuangxiang(cfg, captions, input_path, output_path, ass_path)
    if template == 'siyue':
        return render_siyue(cfg, captions, input_path, output_path, ass_path)
    if template == 'xiari':
        return render_xiari(cfg, captions, input_path, output_path, ass_path)
    if template == 'huangxing':
        return render_huangxing(cfg, captions, input_path, output_path, ass_path)
    ass_path.write_text(
        build_ass(cfg, title, captions, title_mode, show_social_cta, social_variant, social_font,
                  social_title, social_title_style),
        encoding='utf-8'
    )
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


def render_social_benxian_styled_title(cfg, captions, input_path, output_path,
                                       ass_path, social_font, social_title,
                                       social_title_style):
    """Render a replicated animated title, then overlay the fixed body copy."""
    style_templates = {
        '心动时刻': ('xindong', render_xindong),
        '双向奔赴': ('shuangxiang', render_shuangxiang),
        '人间四月天': ('siyue', render_siyue),
        '夏日限定美好': ('xiari', render_xiari),
        '黄色星星': ('huangxing', render_huangxing),
    }
    template_name, renderer = style_templates[social_title_style]
    style_cfg = json.loads((ROOT / 'rules' / f'{template_name}.json').read_text(encoding='utf-8'))
    title_cfg = copy.deepcopy(style_cfg)
    # Standalone sticker builders use different vertical anchors.  Normalize
    # their visible baseline to the same y=130 target used by 黄色星星.
    title_calibration = (cfg.get('variants', {}).get('奔现', {})
                         .get('title', {}).get('styles', {})
                         .get(social_title_style, {}))
    title_baseline_offset = float(title_calibration.get('baseline_offset_y', 0))
    visible_title_y = 130 + title_baseline_offset
    anchor_y = visible_title_y
    if style_templates[social_title_style][0] == 'xindong':
        # 心动时刻 computes rows upward from its anchor. Offset by half the
        # rendered block height so one- and two-line titles share the same
        # visual center as 黄色星星.
        title_size = float(cfg['variants']['奔现']['title']['font_size'])
        title_parts_count = min(2, len(social_title.split()))
        paragraph_gap = float(title_cfg['sticker'].get('paragraph', {}).get('line_gap', 12))
        row_step = title_size + paragraph_gap
        anchor_y += title_size / 2 + max(0, title_parts_count - 1) * row_step / 2
    title_cfg['sticker']['position'] = {'x': 248, 'y': anchor_y}
    title_cfg['sticker']['position_mode'] = 'canvas'
    title_cfg['sticker']['font_size'] = cfg['variants']['奔现']['title']['font_size']
    # Reuse the same per-style scale calibration for animated sticker layers.
    title_cfg['sticker']['scale_x'] = float(title_calibration.get('scale_x', 100))
    title_cfg['sticker']['scale_y'] = float(title_calibration.get('scale_y', 100))
    # Keep the configured title size invariant across copy lengths. The
    # standalone templates normally shrink long lines to fit their sticker;
    # a 奔现 title is a fixed-size UI field instead.
    if template_name == 'xindong':
        title_cfg['sticker']['max_width'] = 460
        # Social 奔现 titles are fixed-size UI text; do not shrink long lines.
        title_cfg['sticker']['min_font_size'] = title_cfg['sticker']['font_size']
    elif template_name == 'xiari':
        title_cfg['sticker']['paper']['max_width'] = 496
    elif template_name == 'huangxing':
        title_cfg['sticker']['max_width'] = 480
        title_cfg['sticker']['min_font_size'] = title_cfg['sticker']['font_size']
    # The standalone builders split on punctuation. Convert the user's first
    # whitespace into a disposable delimiter so the title keeps its two lines.
    title_text = social_title.strip()
    title_parts = title_text.split(None, 1)
    title_text = ('|'.join(title_parts) if template_name == 'huangxing'
                  else '，'.join(title_parts))
    title_captions = [(start, end, title_text) for start, end, _ in captions]
    title_base = output_path.with_name(output_path.stem + '.styled-base.mp4')
    title_ass = output_path.with_name(output_path.stem + '.styled-title.ass')
    body_ass = output_path.with_name(output_path.stem + '.body.ass')
    try:
        renderer(title_cfg, title_captions, input_path, title_base, title_ass)
        body_text = build_ass(
            cfg, '', captions, social_variant='奔现', social_font=social_font)
        body_ass.write_text(body_text, encoding='utf-8')
        subtitle_file = str(body_ass).replace('\\', '/').replace(':', r'\\:')
        fonts_dir = str(ROOT / 'assets' / 'fonts').replace('\\', '/').replace(':', r'\\:')
        subprocess.run([
            'ffmpeg', '-y', '-i', str(title_base), '-vf',
            f'subtitles={subtitle_file}:fontsdir={fonts_dir}', '-c:a', 'copy',
            str(output_path)
        ], check=True)
        # Keep one inspectable ASS containing both the animated title events
        # and the fixed body events.
        title_raw = title_ass.read_text(encoding='utf-8')
        body_raw = body_text
        title_header, title_events = title_raw.split('[Events]\n', 1)
        body_header, body_events = body_raw.split('[Events]\n', 1)
        body_styles = '\n'.join(line for line in body_header.splitlines()
                                 if line.startswith('Style: '))
        event_format = 'Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text'
        title_event_lines = title_events.splitlines()
        body_event_lines = body_events.splitlines()
        title_dialogues = '\n'.join(line for line in title_event_lines
                                     if line.startswith('Dialogue:'))
        body_dialogues = '\n'.join(line for line in body_event_lines
                                    if line.startswith('Dialogue:'))
        ass_path.write_text(
            title_header.rstrip() + '\n' + body_styles + '\n\n[Events]\n' +
            event_format + '\n' + title_dialogues + '\n' + body_dialogues + '\n',
            encoding='utf-8')
    finally:
        for path in (title_base, title_ass, body_ass):
            path.unlink(missing_ok=True)
    return output_path, ass_path

def probe_duration(input_path):
    probe = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'csv=p=0', str(input_path)],
        check=True, capture_output=True, text=True)
    return float(probe.stdout.strip())

def window_enable(windows):
    return '+'.join(f"between(t,{start:.2f},{end:.2f})" for start, end, *_ in windows)

def per_window_expr(windows, value_fn, default):
    expr = default
    for start, end, *rest in reversed(windows):
        expr = f"if(between(t,{start:.2f},{end:.2f}),{value_fn(start, *rest)},{expr})"
    return expr

def render_xindong(cfg, captions, input_path, output_path, ass_path):
    """Render 心动时刻 stickers: layered ASS text + beating hearts + sparkle track."""
    s = cfg['sticker']
    hearts = s['hearts']
    sparkles = s['sparkles']
    left_asset = ROOT / hearts['left']
    right_asset = ROOT / hearts['right']
    sticker_assets.ensure_heart_assets(left_asset, right_asset, hearts['size'], hearts['tilt_deg'])
    windows = []
    for start, end, text in captions:
        paragraphs = split_sticker_text(text) or [text.strip()]
        half_width = max(xindong_geometry(cfg, paragraph)[1] for paragraph in paragraphs)
        windows.append((start, end, half_width))
    duration = max(end for _, end, _ in windows) + float(sparkles['tail_seconds'])
    ass_path.write_text(build_xindong_ass(cfg, captions), encoding='utf-8')

    grow = float(hearts['grow_seconds'])
    amp = float(hearts['pulse_amp'])
    freq = float(hearts['pulse_freq'])
    peek = float(hearts['peek'])
    anchor_x = float(s['position']['x'])
    anchor_y = float(s['position']['y'])
    if s.get('position_mode') == 'left_bottom':
        row_gap = float(s.get('paragraph', {}).get('line_gap', 12))
        block_rows = max((len(split_sticker_text(text) or [text.strip()]) for _, _, text in captions), default=1)
        max_font = max((xindong_geometry(cfg, paragraph)[0]
                        for _, _, text in captions
                        for paragraph in (split_sticker_text(text) or [text.strip()])), default=s['font_size'])
        center_y = anchor_y - max_font / 2 - (block_rows - 1) * (max_font + row_gap) / 2
    else:
        center_y = anchor_y
    max_window_half = max((half_width for _, _, half_width in windows), default=0)
    center_x = anchor_x + max_window_half if s.get('position_mode') == 'left_bottom' else anchor_x

    scale_expr = per_window_expr(
        windows,
        lambda start, hw: (f"min(1,max(0.05,(t-{start:.2f})/{grow:g}))"
                           f"*(1+{amp:g}*pow(max(0,sin(2*PI*(t-{start:.2f})*{freq:g})),3))"),
        '1')
    if s.get('position_mode') == 'left_bottom':
        left_x_expr = per_window_expr(windows, lambda _, hw: f"{anchor_x - peek:g}-w/2", f"{anchor_x - peek:g}-w/2")
        right_x_expr = per_window_expr(windows, lambda _, hw: f"{anchor_x + 2 * hw + peek:g}-w/2", f"{anchor_x + 2 * max_window_half + peek:g}-w/2")
    else:
        left_x_expr = per_window_expr(windows, lambda _, hw: f"{center_x - hw - peek:g}-w/2", f"{center_x - peek:g}-w/2")
        right_x_expr = per_window_expr(windows, lambda _, hw: f"{center_x + hw + peek:g}-w/2", f"{center_x + peek:g}-w/2")
    enable = window_enable(windows)

    spark_dir = Path(tempfile.mkdtemp(prefix='xindong_spark_'))
    try:
        sticker_assets.generate_sparkle_sequence(
            spark_dir, duration, windows, (center_x, center_y), fps=int(sparkles['fps']))
        subtitle_file = str(ass_path).replace('\\', '/').replace(':', r'\\:')
        fonts_dir = str(ROOT / 'assets' / 'fonts').replace('\\', '/').replace(':', r'\\:')
        spark_input = str(spark_dir / 'f%04d.png').replace('\\', '/').replace(':', r'\\:')
        graph = (
            f"[1:v]format=rgba,scale=w='trunc(iw*{scale_expr}/2)*2':h=-2:eval=frame[hl];"
            f"[2:v]format=rgba,scale=w='trunc(iw*{scale_expr}/2)*2':h=-2:eval=frame[hr];"
            f"[0:v][hl]overlay=x='{left_x_expr}':y='{center_y:g}-h/2':enable='{enable}'[b1];"
            f"[b1][hr]overlay=x='{right_x_expr}':y='{center_y:g}-h/2':enable='{enable}'[b2];"
            f"[b2][3:v]overlay=0:0:shortest=0[b3];"
            f"[b3]subtitles={subtitle_file}:fontsdir={fonts_dir}[v]"
        )
        video_seconds = probe_duration(input_path)
        subprocess.run([
            'ffmpeg', '-y', '-i', str(input_path),
            '-loop', '1', '-i', str(left_asset),
            '-loop', '1', '-i', str(right_asset),
            '-framerate', str(sparkles['fps']), '-i', spark_input,
            '-filter_complex', graph, '-map', '[v]', '-map', '0:a?',
            '-c:v', 'libx264', '-c:a', 'copy',
            '-t', f'{video_seconds:.3f}', str(output_path)
        ], check=True)
    finally:
        shutil.rmtree(spark_dir, ignore_errors=True)
    return output_path, ass_path

def render_shuangxiang(cfg, captions, input_path, output_path, ass_path):
    """Render 双向奔赴 stickers: staggered neon glyphs + glowing bars + twinkling stars."""
    s = cfg['sticker']
    bars = s['bars']
    stars = s['stars']
    bar_asset = ROOT / bars['asset']
    star_asset = ROOT / stars['asset']
    sticker_assets.ensure_shuangxiang_assets(bar_asset, star_asset,
                                             bar_size=(bars['width'], 24), star_size=stars['size'])
    windows = []
    for start, end, text in captions:
        paragraphs = split_sticker_text(text) or [text.strip()]
        half_width = max(shuangxiang_geometry(cfg, paragraph)[2] for paragraph in paragraphs)
        windows.append((start, end, half_width))
    ass_path.write_text(build_shuangxiang_ass(cfg, captions), encoding='utf-8')

    anchor_x = float(s['position']['x'])
    anchor_y = float(s['position']['y'])
    max_window_half = max((half_width for _, _, half_width in windows), default=0)
    if s.get('position_mode') == 'left_bottom':
        row_gap = float(s.get('paragraph', {}).get('line_gap', 18))
        block_rows = max((len(split_sticker_text(text) or [text.strip()]) for _, _, text in captions), default=1)
        max_font = max((shuangxiang_geometry(cfg, paragraph)[0]
                        for _, _, text in captions
                        for paragraph in (split_sticker_text(text) or [text.strip()])), default=s['font_size'])
        center_y = anchor_y - max_font / 2 - (block_rows - 1) * (max_font + row_gap) / 2
        center_x = anchor_x + max_window_half
    else:
        center_x, center_y = anchor_x, anchor_y
    enable = window_enable(windows)
    first_start = windows[0][0]

    def bar_graph(input_index, spec, label):
        length_expr = per_window_expr(
            windows, lambda _, hw: f"trunc({bars['length_ratio']:g}*{hw:.2f}/2)*2",
            f"trunc({bars['length_ratio']:g}*195/2)*2")
        if s.get('position_mode') == 'left_bottom':
            x_expr = per_window_expr(
                windows, lambda _, hw: f"{anchor_x + (1 + spec['x_ratio']) * hw:g}-w/2",
                f"{anchor_x + (1 + spec['x_ratio']) * max_window_half:g}-w/2")
        else:
            x_expr = per_window_expr(
                windows, lambda _, hw: f"{center_x + spec['x_ratio'] * hw:g}-w/2",
                f"{center_x + spec['x_ratio'] * 195:g}-w/2")
        y = center_y + float(spec['y_off'])
        fade_start = first_start + float(bars['fade_delay'])
        return (
            f"[{input_index}:v]format=rgba,scale=w='{length_expr}':h=-2:eval=frame,"
            f"fade=t=in:st={fade_start:.2f}:d={bars['fade_seconds']:g}:alpha=1[{label}]",
            f"overlay=x='{x_expr}':y='{y:g}-h/2':enable='{enable}'")

    def star_graph(input_index, item, label):
        amp = float(stars['twinkle_amp'])
        freq = float(stars['twinkle_freq'])
        phase = float(item['phase'])
        scale_expr = per_window_expr(
            windows,
            lambda start, _: f"1+{amp:g}*sin(2*PI*{freq:g}*(t-{start:.2f})+{phase:g})",
            '1')
        if s.get('position_mode') == 'left_bottom':
            x_expr = per_window_expr(
                windows, lambda _, hw: f"{anchor_x + (1 + item['x_ratio']) * hw:g}-w/2",
                f"{anchor_x + (1 + item['x_ratio']) * max_window_half:g}-w/2")
        else:
            x_expr = per_window_expr(
                windows, lambda _, hw: f"{center_x + item['x_ratio'] * hw:g}-w/2",
                f"{center_x + item['x_ratio'] * 195:g}-w/2")
        y = center_y + float(item['y_off'])
        fade_start = first_start + float(stars['fade_delay'])
        return (
            f"[{input_index}:v]format=rgba,scale=w='trunc(iw*{scale_expr}/2)*2':h=-2:eval=frame,"
            f"fade=t=in:st={fade_start:.2f}:d={stars['fade_seconds']:g}:alpha=1[{label}]",
            f"overlay=x='{x_expr}':y='{y:g}-h/2':enable='{enable}'")

    chains = [
        bar_graph(1, bars['top'], 'bar_t'),
        bar_graph(2, bars['bottom'], 'bar_b'),
        star_graph(3, stars['items'][0], 'star_t'),
        star_graph(4, stars['items'][1], 'star_b'),
    ]
    subtitle_file = str(ass_path).replace('\\', '/').replace(':', r'\\:')
    fonts_dir = str(ROOT / 'assets' / 'fonts').replace('\\', '/').replace(':', r'\\:')
    graph_parts = [chain[0] for chain in chains]
    source = '[0:v]'
    for index, chain in enumerate(chains):
        target = f"[c{index}]"
        label = chain[0].rsplit('[', 1)[-1].rstrip(']')
        graph_parts.append(f"{source}[{label}]{chain[1]}{target}")
        source = target
    graph_parts.append(f"{source}subtitles={subtitle_file}:fontsdir={fonts_dir}[v]")
    graph = ';'.join(graph_parts)
    video_seconds = probe_duration(input_path)
    subprocess.run([
        'ffmpeg', '-y', '-i', str(input_path),
        '-loop', '1', '-i', str(bar_asset),
        '-loop', '1', '-i', str(bar_asset),
        '-loop', '1', '-i', str(star_asset),
        '-loop', '1', '-i', str(star_asset),
        '-filter_complex', graph, '-map', '[v]', '-map', '0:a?',
        '-c:v', 'libx264', '-c:a', 'copy',
        '-t', f'{video_seconds:.3f}', str(output_path)
    ], check=True)
    return output_path, ass_path

def render_siyue(cfg, captions, input_path, output_path, ass_path):
    """Render 人间四月天 stickers: glowing serif line + brush wipe + blossoms + bird + petals."""
    s = cfg['sticker']
    brush = s['brush']
    blossoms = s['blossoms']
    bird = s['bird']
    petals = s['petals']
    brush_asset = ROOT / brush['asset']
    blossom_asset = ROOT / blossoms['asset']
    bird_asset = ROOT / bird['asset']
    sticker_assets.ensure_siyue_assets(
        brush_asset, blossom_asset, bird_asset,
        brush_size=(brush['width'], brush['height']),
        blossom_size=max(item['size'] for item in blossoms['items']),
        bird_size=bird['size'])
    windows = []
    for start, end, text in captions:
        paragraphs = split_sticker_text(text) or [text.strip()]
        half_width = max(siyue_geometry(cfg, paragraph)[1] for paragraph in paragraphs)
        windows.append((start, end, half_width))
    duration = max(end for _, end, _ in windows) + float(petals['tail_seconds'])
    ass_path.write_text(build_siyue_ass(cfg, captions), encoding='utf-8')

    anchor_x = float(s['position']['x'])
    anchor_y = float(s['position']['y'])
    max_window_half = max((half_width for _, _, half_width in windows), default=0)
    if s.get('position_mode') == 'left_bottom':
        row_gap = float(s.get('paragraph', {}).get('line_gap', 12))
        block_rows = max((len(split_sticker_text(text) or [text.strip()]) for _, _, text in captions), default=1)
        max_font = max((siyue_geometry(cfg, paragraph)[0]
                        for _, _, text in captions
                        for paragraph in (split_sticker_text(text) or [text.strip()])), default=s['font_size'])
        center_y = anchor_y - max_font / 2 - (block_rows - 1) * (max_font + row_gap) / 2
        center_x = anchor_x + max_window_half
    else:
        center_x, center_y = anchor_x, anchor_y
    enable = window_enable(windows)

    # Brush: width grows left-to-right inside each window (wipe), left edge anchored.
    wipe = float(brush['wipe_seconds'])
    ratio = float(brush['length_ratio'])
    brush_len = per_window_expr(
        windows,
        lambda start, hw: (f"max(16,trunc({ratio:g}*{hw:.2f}*min(1,max(0.02,(t-{start:.2f})/{wipe:g}))/2)*2)"),
        f"{brush['width']}")
    if s.get('position_mode') == 'left_bottom':
        brush_x = per_window_expr(
            windows, lambda _, hw: f"{anchor_x + (1 + float(brush['x_ratio'])) * hw - ratio * hw / 2:g}", '0')
    else:
        brush_x = per_window_expr(
            windows, lambda _, hw: f"{center_x + float(brush['x_ratio']) * hw - ratio * hw / 2:g}", '0')
    brush_y = center_y + float(brush['y_off'])
    chains = [(
        f"[1:v]format=rgba,scale=w='{brush_len}':h=-2:eval=frame[brush]",
        f"overlay=x='{brush_x}':y='{brush_y:g}-h/2':enable='{enable}'",
        'brush')]

    # Blossoms: delayed bloom (scale up) with a gentle sway, one input per item.
    bloom_from = float(blossoms['bloom_from'])
    bloom_seconds = float(blossoms['bloom_seconds'])
    sway_amp = float(blossoms['sway_amp'])
    sway_freq = float(blossoms['sway_freq'])
    for index, item in enumerate(blossoms['items']):
        delay = float(item['delay'])
        size = float(item['size'])
        scale_expr = per_window_expr(
            windows,
            lambda start, _, d=delay, sz=size: (
                f"{sz:g}*({bloom_from:g}+{1 - bloom_from:g}*min(1,max(0,(t-{start:.2f}-{d:g})/{bloom_seconds:g})))"
                f"*(1+{sway_amp:g}*sin(2*PI*{sway_freq:g}*(t-{start:.2f})))"),
            f"{size:g}")
        if s.get('position_mode') == 'left_bottom':
            x_expr = per_window_expr(
                windows, lambda _, hw, xr=float(item['x_ratio']): f"{anchor_x:g}+{1 + xr:g}*{hw:.2f}-w/2", '0')
        else:
            x_expr = per_window_expr(
                windows, lambda _, hw, xr=float(item['x_ratio']): f"{center_x:g}+{xr:g}*{hw:.2f}-w/2", '0')
        y = center_y + float(item['y_off'])
        label = f'blossom{index}'
        chains.append((
            f"[{2 + index}:v]format=rgba,scale=w='trunc({scale_expr}/2)*2':h=-2:eval=frame[{label}]",
            f"overlay=x='{x_expr}':y='{y:g}-h/2':enable='{enable}'",
            label))

    # Bird: pop-in then a slow vertical bob.
    pop_from = float(bird['pop_from'])
    pop_seconds = float(bird['pop_seconds'])
    bird_delay = float(bird['delay'])
    bob_amp = float(bird['bob_amp'])
    bob_freq = float(bird['bob_freq'])
    bird_scale = per_window_expr(
        windows,
        lambda start, _: (f"{bird['size']}*({pop_from:g}+{1 - pop_from:g}"
                          f"*min(1,max(0,(t-{start:.2f}-{bird_delay:g})/{pop_seconds:g})))"),
        f"{bird['size']}")
    if s.get('position_mode') == 'left_bottom':
        bird_x = per_window_expr(
            windows, lambda _, hw: f"{anchor_x:g}+{1 + float(bird['x_ratio']):g}*{hw:.2f}-w/2", '0')
    else:
        bird_x = per_window_expr(
            windows, lambda _, hw: f"{center_x:g}+{float(bird['x_ratio']):g}*{hw:.2f}-w/2", '0')
    bird_y = per_window_expr(
        windows,
        lambda start, _: (f"{center_y + float(bird['y_off']):g}-h/2"
                          f"+{bob_amp:g}*sin(2*PI*{bob_freq:g}*(t-{start:.2f}))"),
        f"{center_y + float(bird['y_off']):g}-h/2")
    bird_input = 2 + len(blossoms['items'])
    chains.append((
        f"[{bird_input}:v]format=rgba,scale=w='trunc({bird_scale}/2)*2':h=-2:eval=frame[bird]",
        f"overlay=x='{bird_x}':y='{bird_y}':enable='{enable}'",
        'bird'))

    petal_dir = Path(tempfile.mkdtemp(prefix='siyue_petal_'))
    try:
        sticker_assets.generate_petal_sequence(
            petal_dir, duration, windows, (center_x, center_y), fps=int(petals['fps']))
        subtitle_file = str(ass_path).replace('\\', '/').replace(':', r'\\:')
        fonts_dir = str(ROOT / 'assets' / 'fonts').replace('\\', '/').replace(':', r'\\:')
        petal_input = str(petal_dir / 'f%04d.png').replace('\\', '/').replace(':', r'\\:')
        graph_parts = [chain[0] for chain in chains]
        source = '[0:v]'
        for index, chain in enumerate(chains):
            target = f"[c{index}]"
            graph_parts.append(f"{source}[{chain[2]}]{chain[1]}{target}")
            source = target
        petal_index = bird_input + 1
        graph_parts.append(f"{source}[{petal_index}:v]overlay=0:0:shortest=0[p]")
        graph_parts.append(f"[p]subtitles={subtitle_file}:fontsdir={fonts_dir}[v]")
        graph = ';'.join(graph_parts)
        video_seconds = probe_duration(input_path)
        command = ['ffmpeg', '-y', '-i', str(input_path), '-loop', '1', '-i', str(brush_asset)]
        for _ in blossoms['items']:
            command += ['-loop', '1', '-i', str(blossom_asset)]
        command += [
            '-loop', '1', '-i', str(bird_asset),
            '-framerate', str(petals['fps']), '-i', petal_input,
            '-filter_complex', graph, '-map', '[v]', '-map', '0:a?',
            '-c:v', 'libx264', '-c:a', 'copy',
            '-t', f'{video_seconds:.3f}', str(output_path)
        ]
        subprocess.run(command, check=True)
    finally:
        shutil.rmtree(petal_dir, ignore_errors=True)
    return output_path, ass_path

def render_xiari(cfg, captions, input_path, output_path, ass_path):
    """Render 夏日限定美好 stickers: torn-paper strip + green quote + daisy + typewriter text."""
    s = cfg['sticker']
    paper = s['paper']
    quote = s['quote']
    daisy = s['daisy']
    ent = s['entrance']
    paper_asset = ROOT / paper['asset']
    quote_asset = ROOT / quote['asset']
    daisy_asset = ROOT / daisy['asset']
    sticker_assets.ensure_xiari_assets(
        paper_asset, quote_asset, daisy_asset,
        paper_size=(paper['max_width'], paper['height']),
        quote_size=quote['size'], daisy_size=daisy['size'])
    windows = []
    block_heights = []
    for start, end, text in captions:
        paragraphs = split_sticker_text(text) or [text.strip()]
        _, _, half_width, _, block_height = xiari_paragraph_geometry(cfg, paragraphs)
        windows.append((start, end, half_width))
        block_heights.append(block_height)
    ass_path.write_text(build_xiari_ass(cfg, captions), encoding='utf-8')

    anchor_x = float(s['position']['x'])
    anchor_y = float(s['position']['y'])
    enable = window_enable(windows)
    grow = float(ent['scale_from']) / 100
    duration = float(ent['duration_ms']) / 1000
    pop_expr = per_window_expr(
        windows,
        lambda start, _: f"{grow:g}+{1 - grow:g}*min(1,(t-{start:.2f})/{duration:g})",
        '1')

    # Paper width follows each caption's widest paragraph; height expands for
    # punctuation-separated rows while retaining the original paper artwork.
    paper_height = max(block_heights, default=float(paper['height']))
    max_window_half = max((half_width for _, _, half_width in windows), default=0)
    if s.get('position_mode') == 'left_bottom':
        center_x = anchor_x + max_window_half
        center_y = anchor_y - paper_height / 2
    else:
        center_x, center_y = anchor_x, anchor_y
    def paper_w_fn(start, half):
        pop = f"{grow:g}+{1 - grow:g}*min(1,(t-{start:.2f})/{duration:g})"
        return f"trunc(({pop})*{2 * half:.2f}/2)*2"
    paper_w = per_window_expr(windows, paper_w_fn, f"{paper['max_width']}")
    if s.get('position_mode') == 'left_bottom':
        paper_x = per_window_expr(
            windows, lambda _, half: f"{anchor_x + half:g}-w/2", f"{anchor_x + max_window_half:g}-w/2")
        quote_x = per_window_expr(
            windows, lambda _, half: f"{anchor_x + float(quote['inset']):g}-w/2", f"{anchor_x + float(quote['inset']):g}-w/2")
        daisy_x = per_window_expr(
            windows, lambda _, half: f"{anchor_x + 2 * half - float(daisy['inset']):g}-w/2", f"{anchor_x + 2 * max_window_half - float(daisy['inset']):g}-w/2")
    else:
        paper_x = f'{center_x:g}-w/2'
        quote_x = per_window_expr(
            windows, lambda _, half: f"{center_x:g}-{half:.2f}+{float(quote['inset']):g}-w/2", '0')
        daisy_x = per_window_expr(
            windows, lambda _, half: f"{center_x:g}+{half:.2f}-{float(daisy['inset']):g}-w/2", '0')

    def chain(input_index, x_expr, y_expr, label, w_expr=None, h_fixed=None):
        if w_expr is None:
            scale = f"scale=w='trunc(iw*{pop_expr}/2)*2':h=-2:eval=frame"
        else:
            scale = f"scale=w='{w_expr}':h={h_fixed}:eval=frame"
        return (
            f"[{input_index}:v]format=rgba,{scale}[{label}]",
            f"overlay=x='{x_expr}':y='{y_expr}':enable='{enable}'",
            label)

    quote_y = center_y - paper_height / 2 - (float(quote['size']) / 2 - 8)
    daisy_y = center_y + paper_height / 2 - (float(daisy['size']) / 2 - 8)
    chains = [
        chain(1, paper_x, f'{center_y:g}-h/2', 'paper',
              w_expr=paper_w, h_fixed=round(paper_height)),
        chain(2, quote_x, f'{quote_y:g}-h/2', 'quote'),
        chain(3, daisy_x, f'{daisy_y:g}-h/2', 'daisy'),
    ]
    subtitle_file = str(ass_path).replace('\\', '/').replace(':', r'\\:')
    fonts_dir = str(ROOT / 'assets' / 'fonts').replace('\\', '/').replace(':', r'\\:')
    graph_parts = [c[0] for c in chains]
    source = '[0:v]'
    for index, c in enumerate(chains):
        target = f"[c{index}]"
        graph_parts.append(f"{source}[{c[2]}]{c[1]}{target}")
        source = target
    graph_parts.append(f"{source}subtitles={subtitle_file}:fontsdir={fonts_dir}[v]")
    graph = ';'.join(graph_parts)
    video_seconds = probe_duration(input_path)
    subprocess.run([
        'ffmpeg', '-y', '-i', str(input_path),
        '-loop', '1', '-i', str(paper_asset),
        '-loop', '1', '-i', str(quote_asset),
        '-loop', '1', '-i', str(daisy_asset),
        '-filter_complex', graph, '-map', '[v]', '-map', '0:a?',
        '-c:v', 'libx264', '-c:a', 'copy',
        '-t', f'{video_seconds:.3f}', str(output_path)
    ], check=True)
    return output_path, ass_path

def render_huangxing(cfg, captions, input_path, output_path, ass_path):
    """Render 黄色星星 stickers: two-line warm-glow italic text + twinkling gold stars."""
    s = cfg['sticker']
    stars = s['stars']
    ent = s['entrance']
    star_asset = ROOT / stars['asset']
    sticker_assets.ensure_huangxing_assets(star_asset, star_size=stars['size'])
    pos = s['position']
    gap = float(s['line_gap'])
    windows = []
    for start, end, text in captions:
        _, half = huangxing_geometry(cfg, text)
        star_y = float(pos['y']) if len(huangxing_lines(text)) == 1 else float(pos['y']) + gap / 2
        windows.append((start, end, half, star_y))
    ass_path.write_text(build_huangxing_ass(cfg, captions), encoding='utf-8')

    center_x = float(pos['x'])
    enable = window_enable(windows)
    amp = float(stars['twinkle_amp'])
    freq = float(stars['twinkle_freq'])
    duration = float(ent['duration_ms']) / 1000
    grow = float(ent['scale_from']) / 100

    def star_graph(input_index, side, phase, label):
        scale_expr = per_window_expr(
            windows,
            lambda start, half, y, ph=phase: (
                f"({grow:g}+{1 - grow:g}*min(1,(t-{start:.2f})/{duration:g}))"
                f"*(1+{amp:g}*sin(2*PI*{freq:g}*(t-{start:.2f})+{ph:g}))"),
            '1')
        x_expr = per_window_expr(
            windows,
            lambda _, half, y, sd=side: f"{center_x:g}+{sd}*({half:.2f}+{float(stars['x_gap']):g})-w/2",
            '0')
        y_expr = per_window_expr(windows, lambda _, half, y: f"{y:g}-h/2", '0')
        return (
            f"[{input_index}:v]format=rgba,scale=w='trunc(iw*{scale_expr}/2)*2':h=-2:eval=frame[{label}]",
            f"overlay=x='{x_expr}':y='{y_expr}':enable='{enable}'",
            label)

    chains = [
        star_graph(1, '-1', 0.0, 'star_l'),
        star_graph(2, '1', 3.14, 'star_r'),
    ]
    subtitle_file = str(ass_path).replace('\\', '/').replace(':', r'\\:')
    fonts_dir = str(ROOT / 'assets' / 'fonts').replace('\\', '/').replace(':', r'\\:')
    graph_parts = [c[0] for c in chains]
    source = '[0:v]'
    for index, c in enumerate(chains):
        target = f"[c{index}]"
        graph_parts.append(f"{source}[{c[2]}]{c[1]}{target}")
        source = target
    graph_parts.append(f"{source}subtitles={subtitle_file}:fontsdir={fonts_dir}[v]")
    graph = ';'.join(graph_parts)
    video_seconds = probe_duration(input_path)
    subprocess.run([
        'ffmpeg', '-y', '-i', str(input_path),
        '-loop', '1', '-i', str(star_asset),
        '-loop', '1', '-i', str(star_asset),
        '-filter_complex', graph, '-map', '[v]', '-map', '0:a?',
        '-c:v', 'libx264', '-c:a', 'copy',
        '-t', f'{video_seconds:.3f}', str(output_path)
    ], check=True)
    return output_path, ass_path

def main():
    ap = argparse.ArgumentParser(description='Apply a fixed social, 信息流广告, iQiyi, or 心动时刻 layout to a digital-human video.')
    ap.add_argument('--template', choices=['social', 'redfruit', 'info_feed_ad', 'iqiyi', 'xindong', 'shuangxiang', 'siyue', 'xiari', 'huangxing'], required=True)
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
