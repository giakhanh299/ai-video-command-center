"""Presentation-only Wuby hybrid: frame an already processed Wuby V4 MP4.

This does not run OCR, translation, voice cloning, Telegram, or a queue worker.
It never changes Telegram Configurations 2/3/4 or adds a second subtitle track.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .config import DEFAULT, THEMES, merge, validate


def reviewed_crop(value: str | None) -> list[float] | None:
    """Parse an explicit, normalized source crop; never infer one from dark frames."""
    if value is None:
        return None
    try:
        rect = [float(part.strip()) for part in value.split(',')]
    except ValueError as exc:
        raise ValueError('Crop must be x,y,w,h with normalized numbers') from exc
    if (len(rect) != 4 or not all(math.isfinite(v) for v in rect) or
            rect[0] < 0 or rect[1] < 0 or rect[2] <= 0 or rect[3] <= 0 or
            rect[0] + rect[2] > 1 or rect[1] + rect[3] > 1):
        raise ValueError('Crop must fit inside the source frame')
    return rect


def hybrid_config(theme: str = 'peach', crop: str | None = None,
                  source_aspect: float = 9 / 16) -> dict:
    """Keep most of the processed picture visible inside the V7 theme."""
    if theme not in THEMES:
        raise ValueError(f'Unknown Wuby theme: {theme}')
    if not math.isfinite(source_aspect) or not 0.35 <= source_aspect <= 1.1:
        raise ValueError('Wuby hybrid needs portrait/square content; review landscape separately')
    # Fit the *visible* source into a maximum 86%-wide / 80%-high region.
    # A square cartoon no longer sits inside a tall, mostly empty white card.
    pixel_w = min(0.86 * 1080, 0.80 * 1920 * source_aspect)
    pixel_h = pixel_w / source_aspect
    video_rect = [(1080 - pixel_w) / 2160,
                  0.15 + (0.80 * 1920 - pixel_h) / 3840,
                  pixel_w / 1080, pixel_h / 1920]
    return validate(merge(DEFAULT, {
        'theme': theme,
        'fps': 'source',
        'title': {'enabled': True, 'font_ratio': 0.047, 'max_lines': 2},
        'subtitle': {'enabled': False},
        'logo': {'enabled': False},
        'motion': {'zoom': 1.0},
        'layout': {
            'title': [0.075, 0.035, 0.85, 0.10],
            'video': video_rect,
            'subtitle': [0.07, 0.955, 0.86, 0.015],
            'logo': [0.39, 0.975, 0.22, 0.015],
        },
        'cleanup': {'mode': 'none', 'input_already_rendered': True,
                    'crop': reviewed_crop(crop), 'masks': [], 'reviewed': False},
        'audio': {'mode': 'preserve', 'background_path': ''},
        'quality': {'require_visual_review': True},
    }))


def render_hybrid(processed_video: str | Path, output: str | Path,
                  title: str, theme: str = 'peach', crop: str | None = None,
                  write_review_artifacts: bool = True) -> str:
    source = Path(processed_video)
    if not source.is_file():
        raise FileNotFoundError(f'Processed video not found: {source}')
    if not title.strip():
        raise ValueError('A title is required for the V7 frame')
    from .media import probe
    dims = probe(source)['video']
    rect = reviewed_crop(crop)
    aspect = (int(dims['width']) * (rect[2] if rect else 1) /
              (int(dims['height']) * (rect[3] if rect else 1)))
    # Empty cues + disabled subtitles: preserve the Vietnamese text already
    # burned into the Wuby V4 video without creating a duplicate layer.
    from .renderer import render
    return render(source, output, [], title, hybrid_config(theme, crop, aspect),
                  write_review_artifacts=write_review_artifacts)


def frame_finished_wuby(processed_video: str | Path, title: str,
                        channel_cfg: dict) -> Path:
    """Frame only a completed Configuration 1 output; never re-run OCR or TTS."""
    source = Path(processed_video)
    if channel_cfg.get('workflow') != 'wuby':
        return source
    studio = channel_cfg.get('wuby_studio') or {}
    frame = studio.get('hybrid_frame') or {}
    if not isinstance(frame, dict) or not frame.get('enabled', False):
        return source
    if not source.is_file():
        raise FileNotFoundError(f'Completed Wuby video not found: {source}')
    output = source.with_name(source.stem + '_hybrid.mp4')
    # Bot workspace outputs are temporary. Do not leave a visual packet pointing
    # to an upstream source which the bot removes after Drive delivery.
    render_hybrid(source, output, title, frame.get('theme', 'peach'),
                  frame.get('crop'), write_review_artifacts=False)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Wuby hybrid frame preview (no OCR/TTS)')
    parser.add_argument('--processed-video', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--title', required=True)
    parser.add_argument('--theme', choices=tuple(THEMES), default='peach')
    parser.add_argument('--crop', help='reviewed normalized source crop x,y,w,h; never automatic')
    parser.add_argument('--render', action='store_true', help='actually render; default is dry-run')
    args = parser.parse_args(argv)
    if args.processed_video.is_file():
        from .media import probe
        dims = probe(args.processed_video)['video']
        rect = reviewed_crop(args.crop)
        aspect = (int(dims['width']) * (rect[2] if rect else 1) /
                  (int(dims['height']) * (rect[3] if rect else 1)))
    else:
        aspect = 9 / 16
    cfg = hybrid_config(args.theme, args.crop, aspect)
    if not args.render:
        print(json.dumps({'mode': 'dry_run', 'source': str(args.processed_video),
                          'output': str(args.output), 'title': args.title,
                          'theme': args.theme, 'subtitle_enabled': cfg['subtitle']['enabled'],
                          'audio_mode': cfg['audio']['mode'],
                          'cleanup_mode': cfg['cleanup']['mode'],
                          'source_aspect': aspect if args.processed_video.is_file() else 'not_probed',
                          'crop': cfg['cleanup']['crop'],
                          'video_region': cfg['layout']['video']}, ensure_ascii=True, indent=2))
        return 0
    print(render_hybrid(args.processed_video, args.output, args.title, args.theme, args.crop))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
