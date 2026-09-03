#!/usr/bin/env python3
"""Generate transparent PNG assets for the 心动时刻 sticker template (stdlib only).

Hearts are static assets cached under assets/images/. The sparkle overlay is a
transparent PNG sequence generated per render, timed to each sticker window.
"""
import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CANVAS_W, CANVAS_H = 496, 864

# Sparkle layout, tuned against the reference template on the 496x864 canvas.
# x offsets are fractions of the sticker half-width; y offsets are absolute px.
BURST = [
    # (x_frac, y_off, dx_frac, dy, size, delay, life, inner)
    (-0.46, -60, -0.19, -120, 22, 0.25, 0.60, 0.05),
    (-0.12, -67, -0.04, -140, 15, 0.28, 0.55, 0.16),
    (0.25, -70, 0.07, -150, 24, 0.23, 0.62, 0.05),
    (0.55, -62, 0.20, -115, 14, 0.30, 0.55, 0.16),
    (0.05, -77, 0.01, -160, 12, 0.35, 0.50, 0.16),
    (-0.29, 60, -0.14, 100, 18, 0.27, 0.58, 0.05),
    (0.01, 66, 0.00, 115, 13, 0.31, 0.55, 0.16),
    (0.35, 62, 0.15, 105, 19, 0.25, 0.60, 0.05),
    (0.59, 56, 0.24, 85, 11, 0.33, 0.52, 0.16),
]
AMBIENT = [
    # (x_frac, y_off, size, phase)
    (-0.66, -132, 11, 0.0),
    (0.69, -152, 9, 1.3),
    (1.09, -92, 12, 2.2),
    (-0.86, 128, 9, 0.7),
    (0.35, 158, 12, 1.8),
    (0.96, 128, 8, 2.8),
]
REFERENCE_HALF_WIDTH = 148.0  # half-width of a 4-char sticker at font size 74


def write_png(path, width, height, rgba):
    """rgba: bytearray of width*height*4."""
    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)
        raw += rgba[y * stride:(y + 1) * stride]
    def chunk(tag, data):
        c = tag + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    png = (b'\x89PNG\r\n\x1a\n'
           + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(bytes(raw), 6))
           + chunk(b'IEND', b''))
    Path(path).write_bytes(png)


def lerp(a, b, t):
    return a + (b - a) * t


def heart_polygon(n=240):
    """Classic parametric heart: x=16sin^3 t, y=13cos t-5cos2t-2cos3t-cos4t."""
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x, y))
    return pts


def point_in_poly(x, y, pts):
    inside = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def make_heart(size=125, tilt_deg=0.0):
    """Glossy pink heart, RGBA square image of `size` px (3x supersampled).

    tilt_deg > 0 rotates counterclockwise (bottom tip swings right).
    """
    img = bytearray(size * size * 4)
    pts = heart_polygon()
    sx = size / 36.0
    cx, cy = size / 2, size * 0.46
    tilt = math.radians(tilt_deg)
    ct, st = math.cos(tilt), math.sin(tilt)
    sub = 3
    for py in range(size):
        for px in range(size):
            cov = 0
            for sy in range(sub):
                for sxp in range(sub):
                    wx = (px + (sxp + 0.5) / sub - cx) / sx
                    wy = -(py + (sy + 0.5) / sub - cy) / sx
                    rx = ct * wx + st * wy
                    ry = -st * wx + ct * wy
                    if point_in_poly(rx, ry, pts):
                        cov += 1
            if cov == 0:
                continue
            alpha = cov / (sub * sub)
            x = (px - cx) / sx
            y = -(py - cy) / sx
            g = min(1.0, max(0.0, 0.55 - 0.030 * x + 0.035 * y))
            r = lerp(0xF4, 0xFD, g)
            gg = lerp(0x6B, 0xC9, g)
            b = lerp(0xA8, 0xDE, g)
            i = (py * size + px) * 4
            img[i] = int(r)
            img[i + 1] = int(gg)
            img[i + 2] = int(b)
            img[i + 3] = int(alpha * 255)
    return size, size, img


def ensure_heart_assets(left_path, right_path, size=125, tilt_deg=18.0):
    """Create the tilted heart PNGs once; reused by every 心动时刻 render."""
    for path, tilt in ((Path(left_path), tilt_deg), (Path(right_path), -tilt_deg)):
        if path.is_file():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        w, h, img = make_heart(size=size, tilt_deg=tilt)
        write_png(path, w, h, img)


def blend_px(img, width, height, px, py, rgb, a):
    if px < 0 or py < 0 or px >= width or py >= height or a <= 0:
        return
    i = (py * width + px) * 4
    inv = 1.0 - a
    img[i] = int(rgb[0] * a + img[i] * inv)
    img[i + 1] = int(rgb[1] * a + img[i + 1] * inv)
    img[i + 2] = int(rgb[2] * a + img[i + 2] * inv)
    img[i + 3] = min(255, int(img[i + 3] + a * 255))


def in_rot_ellipse(px, py, cx, cy, rx, ry, rot_deg=0.0):
    """Point-in-rotated-ellipse test, returns coverage-ish value in [0,1]."""
    r = math.radians(rot_deg)
    c, s = math.cos(r), math.sin(r)
    dx, dy = px - cx, py - cy
    lx = (c * dx + s * dy) / rx
    ly = (-s * dx + c * dy) / ry
    return 1.0 - math.sqrt(lx * lx + ly * ly)


def make_brush(width=380, height=64):
    """Green brush: a hand-drawn oval loop on the left with a long thin tail right."""
    img = bytearray(width * height * 4)
    cx, cy = width * 0.17, height * 0.52
    rx, ry = width * 0.115, height * 0.36
    for py in range(height):
        for px in range(width):
            X, Y = px + 0.5, py + 0.5
            a = 0.0
            rgb = None
            # oval ring; stroke thicker at the lower-left, thinner at the top
            e = math.hypot((X - cx) / rx, (Y - cy) / ry)
            if 0.7 < e < 1.35:
                ang = math.atan2((Y - cy) / ry, (X - cx) / rx)
                sw = 2.2 + 3.4 * max(0.0, math.sin(ang + 0.6))  # heavier at the bottom
                ring_a = min(1.0, max(0.0, (sw / 2 - abs(e - 1.0) * ry) / 1.6))
                if ring_a > 0 and ang < 2.6:  # small gap where the tail exits
                    a = ring_a
                    sheen = min(1.0, max(0.0, -(e - 1.0) * 2.2))
                    rgb = (lerp(0x3F, 0xB9, sheen), lerp(0xA0, 0xE8, sheen), lerp(0x5C, 0xC4, sheen))
            # tail: exits the ring's lower right and sweeps right, thinning out
            if X > cx + rx * 0.35:
                t = min(1.0, (X - (cx + rx * 0.35)) / (width - cx - rx * 0.35))
                cyc = cy + ry * 0.55 + height * 0.10 * math.sin(math.pi * min(1.0, t * 1.15)) - height * 0.16 * t
                thick = 1.0 + 3.2 * math.exp(-3.2 * t)
                tail_a = min(1.0, max(0.0, (thick - abs(Y - cyc)) / 1.6)) * (1.0 - 0.45 * t)
                if tail_a > a:
                    a = tail_a
                    grey = min(1.0, t * 1.15)
                    rgb = (lerp(0x4A, 0x8A, grey), lerp(0xA6, 0xA8, grey), lerp(0x66, 0x90, grey))
            if a and rgb:
                blend_px(img, width, height, px, py, rgb, a)
    return width, height, img


def make_blossom(size=40):
    """Five-petal plum blossom, pink with a near-white rim and darker heart."""
    img = bytearray(size * size * 4)
    c = size / 2
    R = size / 2
    petal_r = R * 0.52
    for py in range(size):
        for px in range(size):
            best = 0.0
            for k in range(5):
                ang = math.radians(k * 72 - 90)
                pcx = c + math.cos(ang) * R * 0.42
                pcy = c + math.sin(ang) * R * 0.42
                best = max(best, in_rot_ellipse(px + 0.5, py + 0.5, pcx, pcy,
                                                R * 0.34, R * 0.24, k * 72 - 90))
            d_center = math.hypot(px + 0.5 - c, py + 0.5 - c)
            heart = max(0.0, 1.0 - d_center / (R * 0.22))
            cov = max(best, heart)
            if cov <= 0:
                continue
            a = min(1.0, cov * 3.0)
            rim = min(1.0, max(0.0, cov * 1.4))
            r = lerp(lerp(0xF2, 0xFC, rim), 0xEF, heart)
            g = lerp(lerp(0x9C, 0xE9, rim), 0x7E, heart)
            b = lerp(lerp(0xC4, 0xF4, rim), 0xAE, heart)
            blend_px(img, size, size, px, py, (r, g, b), a)
    return size, size, img


def make_bird(size=64):
    """Flat-design pink bird with a tiny blossom on its head."""
    img = bytearray(size * size * 4)
    u = size / 64.0

    def ellipse(cx, cy, rx, ry, rot, rgb):
        x0, x1 = int(cx - rx - 2), int(cx + rx + 2)
        y0, y1 = int(cy - ry - 2), int(cy + ry + 2)
        for py in range(max(0, y0), min(size, y1)):
            for px in range(max(0, x0), min(size, x1)):
                v = in_rot_ellipse(px + 0.5, py + 0.5, cx, cy, rx, ry, rot)
                if v > 0:
                    blend_px(img, size, size, px, py, rgb, min(1.0, v * 3.0))

    def tri(pts, rgb):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        for py in range(max(0, int(min(ys))), min(size, int(max(ys)) + 1)):
            for px in range(max(0, int(min(xs))), min(size, int(max(xs)) + 1)):
                if point_in_poly(px + 0.5, py + 0.5, pts):
                    blend_px(img, size, size, px, py, rgb, 1.0)

    pink, dark, pale = (0xF4, 0xA9, 0xC9), (0xEA, 0x8F, 0xB6), (0xFC, 0xE4, 0xEF)
    # tail, body, belly, head, wing, beak, eye
    tri([(14 * u, 30 * u), (1 * u, 20 * u), (5 * u, 33 * u)], dark)
    tri([(14 * u, 36 * u), (3 * u, 40 * u), (10 * u, 41 * u)], dark)
    ellipse(30 * u, 33 * u, 17 * u, 12 * u, -10, pink)
    ellipse(32 * u, 37 * u, 12 * u, 8 * u, -8, pale)
    ellipse(44 * u, 20 * u, 10 * u, 10 * u, 0, pink)
    ellipse(27 * u, 31 * u, 9 * u, 6 * u, -25, dark)
    tri([(53 * u, 17 * u), (61 * u, 20 * u), (53 * u, 23 * u)], (0xF6, 0xC7, 0x6E))
    ellipse(47 * u, 19 * u, 1.8 * u, 1.8 * u, 0, (0x4A, 0x2C, 0x38))
    # tiny blossom on the head
    bw, bh, bimg = make_blossom(max(10, int(15 * u)))
    off_x, off_y = int(36 * u), int(2 * u)
    for py in range(bh):
        for px in range(bw):
            a = bimg[(py * bw + px) * 4 + 3] / 255
            if a:
                blend_px(img, size, size, off_x + px, off_y + py,
                         bimg[(py * bw + px) * 4:(py * bw + px) * 4 + 3], a)
    return size, size, img


def ensure_siyue_assets(brush_path, blossom_path, bird_path,
                        brush_size=(380, 64), blossom_size=60, bird_size=72):
    """Create the 人间四月天 brush/blossom/bird PNGs once; reused by every render."""
    if not Path(brush_path).is_file():
        Path(brush_path).parent.mkdir(parents=True, exist_ok=True)
        w, h, img = make_brush(*brush_size)
        write_png(brush_path, w, h, img)
    if not Path(blossom_path).is_file():
        Path(blossom_path).parent.mkdir(parents=True, exist_ok=True)
        w, h, img = make_blossom(blossom_size)
        write_png(blossom_path, w, h, img)
    if not Path(bird_path).is_file():
        Path(bird_path).parent.mkdir(parents=True, exist_ok=True)
        w, h, img = make_bird(bird_size)
        write_png(bird_path, w, h, img)


# Petal layout: (x_frac, phase, fall_speed, size, rot_speed). Petals drift down
# across the sticker area, swaying sideways, for the whole window.
PETALS = [
    (-0.85, 0.0, 60, 9, 40),
    (-0.45, 1.7, 75, 7, -30),
    (-0.05, 0.9, 55, 10, 25),
    (0.35, 2.6, 80, 7, -45),
    (0.70, 0.5, 65, 8, 35),
    (0.95, 2.1, 70, 6, -20),
    (-0.20, 3.1, 85, 6, 50),
]


def draw_petal(img, width, height, cx, cy, size, rot_deg, color=(247, 168, 196)):
    """One rotated ellipse petal with a pale edge."""
    R = size
    x0, x1 = int(cx - R - 2), int(cx + R + 2)
    y0, y1 = int(cy - R - 2), int(cy + R + 2)
    for py in range(max(0, y0), min(height, y1)):
        for px in range(max(0, x0), min(width, x1)):
            v = in_rot_ellipse(px + 0.5, py + 0.5, cx, cy, R, R * 0.55, rot_deg)
            if v <= 0:
                continue
            a = min(1.0, v * 3.0)
            rim = min(1.0, v * 1.3)
            blend_px(img, width, height, px, py,
                     (lerp(color[0], 252, rim), lerp(color[1], 226, rim), lerp(color[2], 238, rim)), a)


def generate_petal_sequence(out_dir, duration, windows, center, fps=30):
    """Transparent PNG sequence of falling petals, active inside each window."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cx, cy = center
    span = 400.0
    frames = int(math.ceil(duration * fps)) + 1
    for fi in range(frames):
        t = fi / fps
        img = bytearray(CANVAS_W * CANVAS_H * 4)
        for start, end, half_width in windows:
            if t < start or t > end:
                continue
            local = t - start
            for x_frac, phase, speed, size, rot_speed in PETALS:
                travel = (local * speed + phase * 90) % span
                y = cy - 200 + travel
                x = cx + x_frac * half_width + 14 * math.sin(local * 1.7 + phase)
                draw_petal(img, CANVAS_W, CANVAS_H, x, y, size, local * rot_speed + phase * 40)
        write_png(out_dir / f'f{fi:04d}.png', CANVAS_W, CANVAS_H, img)
    return frames


def make_bar(width=220, height=24, core=(255, 255, 255), edge=(244, 138, 200)):
    """Horizontal glowing pill: white core line, pink glow, ends fade out."""
    img = bytearray(width * height * 4)
    for py in range(height):
        for px in range(width):
            ny = abs((py + 0.5) / height * 2 - 1)
            nx = abs((px + 0.5) / width * 2 - 1)
            line = max(0.0, 1.0 - ny / 0.22)
            glow = max(0.0, 1.0 - ny) ** 2 * 0.75
            end_fade = min(1.0, (1.0 - nx) / 0.14)
            if end_fade <= 0:
                continue
            a = min(1.0, (line + glow) * end_fade)
            mix = min(1.0, line * 1.2)
            i = (py * width + px) * 4
            img[i] = int(lerp(edge[0], core[0], mix))
            img[i + 1] = int(lerp(edge[1], core[1], mix))
            img[i + 2] = int(lerp(edge[2], core[2], mix))
            img[i + 3] = int(a * 255)
    return width, height, img


def make_neon_star(size=48, color=(255, 182, 222)):
    """Pink 4-point sparkle with a soft halo and white-hot core."""
    img = bytearray(size * size * 4)
    c = size / 2
    R = size * 0.42
    for py in range(size):
        for px in range(size):
            dx, dy = px + 0.5 - c, py + 0.5 - c
            m = star_mask(dx, dy, R, inner=0.10, sharp=0.5)
            halo = max(0.0, 1.0 - math.hypot(dx, dy) / (R * 1.2)) ** 2 * 0.55
            a = min(1.0, m * 1.6 + halo)
            if a <= 0:
                continue
            mix = min(1.0, m * 1.5)
            i = (py * size + px) * 4
            img[i] = int(lerp(color[0], 255, mix))
            img[i + 1] = int(lerp(color[1], 255, mix))
            img[i + 2] = int(lerp(color[2], 255, mix))
            img[i + 3] = int(a * 255)
    return size, size, img


def ensure_shuangxiang_assets(bar_path, star_path, bar_size=(220, 24), star_size=48):
    """Create the 双向奔赴 bar/star PNGs once; reused by every render."""
    if not Path(bar_path).is_file():
        Path(bar_path).parent.mkdir(parents=True, exist_ok=True)
        w, h, img = make_bar(*bar_size)
        write_png(bar_path, w, h, img)
    if not Path(star_path).is_file():
        Path(star_path).parent.mkdir(parents=True, exist_ok=True)
        w, h, img = make_neon_star(size=star_size)
        write_png(star_path, w, h, img)


def star_mask(dx, dy, R, inner=0.16, sharp=0.65):
    """4-point sparkle mask value in [0,1]; points at cardinal directions."""
    d = math.hypot(dx, dy)
    if d > R:
        return 0.0
    theta = math.atan2(dy, dx)
    r_max = R * (inner + (1 - inner) * abs(math.cos(2 * theta)) ** sharp)
    if d >= r_max or r_max <= 0:
        return 0.0
    return 1.0 - d / r_max


def draw_sparkle(img, width, height, cx, cy, R, alpha, color=(255, 246, 216), inner=0.16):
    """Blend one sparkle into the frame buffer. alpha in [0,1]."""
    x0, x1 = int(cx - R - 2), int(cx + R + 2)
    y0, y1 = int(cy - R - 2), int(cy + R + 2)
    for py in range(max(0, y0), min(height, y1)):
        for px in range(max(0, x0), min(width, x1)):
            m = star_mask(px - cx, py - cy, R, inner)
            if m <= 0:
                continue
            a = alpha * min(1.0, m * 1.8)
            core = max(0.0, 1.0 - math.hypot(px - cx, py - cy) / (R * 0.45))
            r = lerp(color[0], 255, core)
            g = lerp(color[1], 255, core)
            b = lerp(color[2], 255, core)
            i = (py * width + px) * 4
            inv = 1.0 - a
            img[i] = int(r * a + img[i] * inv)
            img[i + 1] = int(g * a + img[i + 1] * inv)
            img[i + 2] = int(b * a + img[i + 2] * inv)
            img[i + 3] = min(255, int(img[i + 3] + a * 255))


def ease_out(t):
    return 1 - (1 - t) ** 2


def generate_sparkle_sequence(out_dir, duration, windows, center, fps=30):
    """Write a transparent PNG sequence covering [0, duration].

    windows: list of (start, end, half_width) sticker windows; burst sparkles
    fire near each window start, ambient stars twinkle until the window ends.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cx, cy = center
    frames = int(math.ceil(duration * fps)) + 1
    for fi in range(frames):
        t = fi / fps
        img = bytearray(CANVAS_W * CANVAS_H * 4)
        for start, end, half_width in windows:
            for x_frac, y_off, dx_frac, dy, size, delay, life, inner in BURST:
                t0 = start + delay
                if t < t0 or t > t0 + life:
                    continue
                k = (t - t0) / life
                e = ease_out(k)
                a = min(1.0, k / 0.15) * (1.0 - max(0.0, (k - 0.55) / 0.45))
                draw_sparkle(img, CANVAS_W, CANVAS_H,
                             cx + (x_frac + dx_frac * e) * half_width,
                             cy + y_off + dy * e, size * (0.6 + 0.4 * e), a,
                             inner=inner)
            if t >= start + 0.8 and t <= end:
                for x_frac, y_off, size, phase in AMBIENT:
                    tw = 0.5 + 0.5 * math.sin(t * 3.1 + phase)
                    drift = (t - (start + 0.8)) * 8
                    draw_sparkle(img, CANVAS_W, CANVAS_H,
                                 cx + x_frac * half_width,
                                 cy + y_off - drift, size, 0.25 + 0.75 * tw, inner=0.22)
        write_png(out_dir / f'f{fi:04d}.png', CANVAS_W, CANVAS_H, img)
    return frames


def make_paper(width=400, height=150, seed=11):
    """Cream torn-paper strip: jagged top/bottom edges, subtle paper noise."""
    img = bytearray(width * height * 4)
    tear = 7.0
    phases = [((seed * (i + 3)) % 7 + 1, ((seed * (i + 5)) % 11) * 0.7) for i in range(4)]

    def edge(x):
        v = 0.0
        for k, (freq, ph) in enumerate(phases):
            v += math.sin(x / width * math.pi * 2 * freq + ph) * (tear / (k + 1)) * 0.5
        # fine fibrous jitter so the edge reads as torn, not wavy
        v += math.sin(x * 1.7 + ph) * 0.8 + math.sin(x * 3.9) * 0.5
        return v

    for py in range(height):
        for px in range(width):
            top = tear + edge(px)
            bottom = height - tear + edge(px * 1.13 + 37)
            y = py + 0.5
            a_top = min(1.0, max(0.0, y - top))
            a_bottom = min(1.0, max(0.0, bottom - y))
            a = min(a_top, a_bottom)
            if a <= 0:
                continue
            noise = (((px * 31 + py * 17 + seed) * 2654435761) % 1024) / 1024 - 0.5
            tone = noise * 7
            blend_px(img, width, height, px, py,
                     (0xF1 + tone, 0xF4 + tone, 0xDC + tone), a)
    return width, height, img


def make_quote(size=60):
    """Yellow-green double quotation mark, flat style with a soft sheen."""
    img = bytearray(size * size * 4)
    u = size / 60.0
    for mark_cx in (17.0, 40.0):
        for py in range(size):
            for px in range(size):
                X, Y = (px + 0.5) / u, (py + 0.5) / u
                # round bulb
                bulb = max(0.0, 1.0 - math.hypot(X - mark_cx, Y - 44.0) / 13.5)
                # thick curved tail sweeping up-right from the bulb
                tail = max(0.0, in_rot_ellipse(X, Y, mark_cx + 5.5, 27.0,
                                               13.5, 7.0, -40))
                cov = max(bulb, tail)
                if cov <= 0:
                    continue
                a = min(1.0, cov * 2.5)
                sheen = min(1.0, max(0.0, (30.0 - Y) / 30.0))
                blend_px(img, size, size, px, py,
                         (lerp(0x8C, 0xC0, sheen), lerp(0xBE, 0xE0, sheen), lerp(0x2A, 0x4A, sheen)), a)
    return size, size, img


def make_daisy(size=96):
    """White daisy with yellow heart; stem and two leaves trail to the left."""
    img = bytearray(size * size * 4)
    u = size / 96.0
    fx, fy = 64.0 * u, 42.0 * u  # flower center
    for py in range(size):
        for px in range(size):
            X, Y = px + 0.5, py + 0.5
            # stem from the flower down-left
            sx, sy = 14.0 * u, 78.0 * u
            dx, dy = fx - sx, fy - sy
            seg = math.hypot(dx, dy)
            tproj = min(1.0, max(0.0, ((X - sx) * dx + (Y - sy) * dy) / (seg * seg)))
            d_stem = math.hypot(X - (sx + tproj * dx), Y - (sy + tproj * dy))
            stem_a = min(1.0, max(0.0, (2.2 * u - d_stem) / 1.2))
            if stem_a > 0:
                blend_px(img, size, size, px, py, (0x7A, 0x94, 0x18), stem_a)
            # two leaves along the stem
            for lx, ly, rot in ((26.0, 62.0, -35), (40.0, 72.0, 15)):
                v = in_rot_ellipse(X, Y, lx * u, ly * u, 11.0 * u, 4.6 * u, rot)
                if v > 0:
                    a = min(1.0, v * 2.5)
                    sheen = min(1.0, max(0.0, v))
                    blend_px(img, size, size, px, py,
                             (lerp(0x8A, 0xB8, sheen), lerp(0xA4, 0xCC, sheen), lerp(0x14, 0x30, sheen)), a)
            # 8 white petals
            best = 0.0
            for k in range(8):
                ang = k * 45 + 10
                rad = math.radians(ang)
                pcx = fx + math.cos(rad) * 16.5 * u
                pcy = fy + math.sin(rad) * 16.5 * u
                best = max(best, in_rot_ellipse(X, Y, pcx, pcy, 15.5 * u, 8.6 * u, ang))
            if best > 0:
                a = min(1.0, best * 2.5)
                shade = min(1.0, max(0.0, 1.0 - best)) * 0.7
                blend_px(img, size, size, px, py,
                         (lerp(255, 0xF0, shade), lerp(255, 0xF4, shade), lerp(255, 0xF6, shade)), a)
            # yellow center
            d = math.hypot(X - fx, Y - fy)
            c_a = min(1.0, max(0.0, (8.5 * u - d) / 1.4))
            if c_a > 0:
                core = min(1.0, max(0.0, 1.0 - d / (8.5 * u)))
                blend_px(img, size, size, px, py,
                         (lerp(0xF0, 0xF8, core), lerp(0xD8, 0xEA, core), lerp(0x11, 0x30, core)), c_a)
    return size, size, img


def ensure_xiari_assets(paper_path, quote_path, daisy_path,
                        paper_size=(400, 150), quote_size=60, daisy_size=96):
    """Create the 夏日限定美好 paper/quote/daisy PNGs once; reused by every render."""
    if not Path(paper_path).is_file():
        Path(paper_path).parent.mkdir(parents=True, exist_ok=True)
        w, h, img = make_paper(*paper_size)
        write_png(paper_path, w, h, img)
    if not Path(quote_path).is_file():
        Path(quote_path).parent.mkdir(parents=True, exist_ok=True)
        w, h, img = make_quote(quote_size)
        write_png(quote_path, w, h, img)
    if not Path(daisy_path).is_file():
        Path(daisy_path).parent.mkdir(parents=True, exist_ok=True)
        w, h, img = make_daisy(daisy_size)
        write_png(daisy_path, w, h, img)


def ensure_huangxing_assets(star_path, star_size=44, color=(252, 233, 184)):
    """Create the 黄色星星 gold twinkle star once; reused by every render."""
    if not Path(star_path).is_file():
        Path(star_path).parent.mkdir(parents=True, exist_ok=True)
        w, h, img = make_neon_star(size=star_size, color=color)
        write_png(star_path, w, h, img)
