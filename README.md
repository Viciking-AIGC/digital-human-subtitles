# Digital Human Video Layouts

Fixed, no-UI rendering package for applying Social, 信息流广告, or iQiyi captions to a generated digital-human video. It accepts a finished 9:16 MP4 plus a timed user script and produces a caption-burned MP4 and its ASS source file.

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
  "selected_products": ["爱聊唯西"],
  "captions": [
    {"start": 0.00, "end": 2.55, "text": "王总，这是给你的礼物"}
  ]
}
```

Social does not accept a title. `selected_products` is the product array from the upstream checkbox selection. The fixed left-side CTA (`点击下方立即使用` and arrow) is added only when this array includes at least one of `爱聊唯西`, `爱聊新远方`, or `会会新远方`. This rule applies identically to both generated digital-human videos and empty-shot videos; the renderer does not branch on video type. Omit the field or pass an empty array for the subtitle-only layout; see `examples/social-subtitle-only-script.json`. Other product names remain subtitle-only.

### 信息流广告 Script

信息流广告是独立于社交和爱奇艺的业务线。三条管线都在各自规则文件中单独启用去标点、标点优先切分、常见中文语义切分和每段最多 10 个字；这些公共字幕规则不会合并业务配置。信息流广告脚本只包含字幕，不接受标题，并额外处理 `红果短剧`：首次出现时四字为白字红边并在正上方显示 Logo，后续出现仍为白字红边但不再显示 Logo。使用 `examples/info-feed-ad-script.json`。

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

### 信息流广告固定入口

The information-feed ad line has a dedicated command with fixed behavior. It accepts only the input video, the UTF-8 JSON script, and the output MP4 path:

```bash
python3 scripts/generate_info_feed_ad.py \
  /path/to/input.mp4 \
  examples/info-feed-ad-script.json \
  /path/to/output.mp4
```

The command always uses the 信息流广告 rules and emits a traceable `.ass` file beside the output video. The former `redfruit` template slug remains available only as a compatibility alias.

## Fixed Layout Rules

Coordinates below use the 496 x 864 reference canvas. See the individual rule files for integration-ready machine-readable values.

| Template | Element | Font | Size | Scale | Style | Position |
| --- | --- | --- | ---: | --- | --- | --- |
| Social | Subtitle | Microsoft YaHei Bold (`微软雅黑`) | 36px | 100% | White, 1.5px black outline, 1px shadow, max 2 lines | Center, `x=248 y=629` |
| Social | Conditional CTA | Microsoft YaHei Bold (`微软雅黑`) | 28px | 100% | Vertical black text, 2.5px white outline, supplied red arrow image `24x40px` | Added to both digital-human and empty-shot videos only for `爱聊唯西` / `爱聊新远方` / `会会新远方`; center-origin `X=-900 Y=0`, group offset `-20px` |
| 信息流广告 | Subtitle | DouyinSans Bold (`抖音美好体`) | 36px | 100% | White, 1.5px black outline, 1px shadow, max 2 lines | Center, `x=248 y=629` |
| iQiyi | Title | HanYi Variety Simplified (`HYZongYiJ`) | 30px | 100% | Line 1 yellow/3px black; line 2 white/3px red | Center, first line `y=82.5`; second line `y=120` |
| iQiyi | Subtitle | Source Han Sans Heavy (`思源黑体`) | 35px | 100% | White, 1.5px black outline, 1px shadow, max 2 lines | Center, `x=248 y=629` |

iQiyi two-line title has a net line gap of 7.5px, which is one quarter of its 30px title size.

## Packaged Fonts

- `assets/fonts/ZongYiTi.ttf`: HanYi Variety Simplified, used by the iQiyi title.
- `assets/fonts/msyhbd.ttc`: Microsoft YaHei Bold, used by the Social subtitle renderer.
- `assets/fonts/DouyinSansBold.ttf`: DouyinSans Bold (`抖音美好体`), used by the 信息流广告 subtitle renderer.
- `assets/images/info-feed-ad-logo.png`: transparent Redfruit App Logo, overlaid above the first subtitle occurrence of `红果短剧` only.
- `assets/fonts/TeHeiTi.ttf`: Source Han Sans CN Heavy, used by the iQiyi subtitle renderer.

The fixed `render_font` fields in each rule identify the fonts available to the packaged FFmpeg renderer. Do not replace them with system font fallbacks in production.

## Reproducible Tests

The supplied test scripts use `/mnt/c/Users/EDY/Desktop/wf12026081819064440167851968514.mp4`:

```bash
bash scripts/test_social.sh
bash scripts/test_info_feed_ad.sh
bash scripts/test_iqiyi.sh
python3 -m unittest discover -s tests -v
```

Results are separate:

- `outputs/social/wf12026081819064440167851968514.mp4`
- `outputs/info_feed_ad/wf12026081819064440167851968514.mp4`
- `outputs/iqiyi/wf12026081819064440167851968514.mp4`

## Output Contract

For each request, return:

1. A caption-burned MP4 at the requested `--output` path.
2. The generated ASS at `--ass` or beside the MP4, for traceability and platform debugging.

The renderer preserves the source audio stream with `-c:a copy`.
