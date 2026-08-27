# Digital Human Video Layouts

Fixed, no-UI rendering package for applying Social or iQiyi captions to a generated digital-human video. It accepts a finished 9:16 MP4 plus a timed user script and produces a caption-burned MP4 and its ASS source file.

## Requirements

- Python 3.9+
- FFmpeg built with `libass`
- 9:16 source MP4. Rules use a `496 x 864` reference canvas and are scaled proportionally by libass.

## Input Contract

1. The digital-human platform generates or receives a base video MP4.
2. The user enters the subtitle segments and, for iQiyi only, an optional front title.
3. Save the request as a UTF-8 JSON script.
4. Invoke `scripts/generate_video.py` with the selected template, base MP4, script JSON, and output path.

All timestamps are seconds. Captions must be sorted, non-overlapping, have `end > start`, and contain non-empty text. The video source is never modified.

### Social Script

`examples/social-script.json`:

```json
{
  "captions": [
    {"start": 0.00, "end": 2.55, "text": "王总，这是给你的礼物"}
  ]
}
```

Social does not accept a title.

### iQiyi Script

`examples/iqiyi-script.json`:

```json
{
  "title": "红果短剧开播了 快来红果短剧看",
  "title_mode": "two",
  "captions": [
    {"start": 0.00, "end": 2.55, "text": "王总，这是给你的礼物"}
  ]
}
```

For `title_mode: "two"`, the first whitespace splits the yellow first line and white/red second line. For `title_mode: "one"`, the title remains one centered line: text before the first whitespace is yellow/black; the remainder is white/red. If no whitespace is present, the full title is yellow/black.

## Render Command

```bash
python3 scripts/generate_video.py \
  --template iqiyi \
  --input /path/to/digital-human.mp4 \
  --script examples/iqiyi-script.json \
  --output /path/to/output/digital-human-iqiyi.mp4
```

An ASS file is emitted beside the output MP4. Specify `--ass /path/to/result.ass` to control its location.

## Fixed Layout Rules

Coordinates below use the 496 x 864 reference canvas. See `rules/social.json` and `rules/iqiyi.json` for integration-ready machine-readable values.

| Template | Element | Font | Size | Scale | Style | Position |
| --- | --- | --- | ---: | --- | --- | --- |
| Social | Subtitle | Microsoft YaHei Bold (`微软雅黑`) | 36px | 100% | White, 3px black outline, 1px shadow, max 2 lines | Center, `x=248 y=629` |
| iQiyi | Title | HanYi Variety Simplified (`HYZongYiJ`) | 30px | 100% | Line 1 yellow/3px black; line 2 white/3px red | Center, first line `y=82.5`; second line `y=120` |
| iQiyi | Subtitle | Source Han Sans Heavy (`思源黑体`) | 35px | 100% | White, 3px black outline, 1px shadow, max 2 lines | Center, `x=248 y=629` |

iQiyi two-line title has a net line gap of 7.5px, which is one quarter of its 30px title size.

## Packaged Fonts

- `assets/fonts/ZongYiTi.ttf`: HanYi Variety Simplified, used by the iQiyi title.
- `assets/fonts/msyhbd.ttc`: Microsoft YaHei Bold, used by the Social subtitle renderer to match the original confirmed test video.
- `assets/fonts/TeHeiTi.ttf`: Source Han Sans CN Heavy, used by the iQiyi subtitle renderer.

The fixed `render_font` fields in each rule identify the fonts available to the packaged FFmpeg renderer. Do not replace them with system font fallbacks in production.

## Reproducible Tests

The supplied test scripts use `/mnt/c/Users/EDY/Desktop/wf12026081819064440167851968514.mp4`:

```bash
bash scripts/test_social.sh
bash scripts/test_iqiyi.sh
python3 -m unittest discover -s tests -v
```

Results are separate:

- `outputs/social/wf12026081819064440167851968514.mp4`
- `outputs/iqiyi/wf12026081819064440167851968514.mp4`

## Output Contract

For each request, return:

1. A caption-burned MP4 at the requested `--output` path.
2. The generated ASS at `--ass` or beside the MP4, for traceability and platform debugging.

The renderer preserves the source audio stream with `-c:a copy`.
