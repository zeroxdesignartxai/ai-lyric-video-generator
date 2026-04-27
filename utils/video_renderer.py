from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from moviepy.editor import AudioFileClip, VideoClip

from .image_effects import VIDEO_SIZE, add_dark_overlay, add_grain, add_soft_glow, add_vignette, resize_crop_image
from .srt_utils import SubtitleCue, parse_srt


FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for font_path in FONT_CANDIDATES:
        if os.path.exists(font_path):
            return ImageFont.truetype(font_path, size=size)
    return ImageFont.load_default()


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = (value or "#FFFFFF").strip().lstrip("#")
    if len(value) != 6:
        return (255, 255, 255)
    try:
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (255, 255, 255)


def _wrap_text(text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    wrapped: list[str] = []
    for paragraph in text.splitlines():
        words = paragraph.split()
        if not words:
            wrapped.append("")
            continue
        line = words[0]
        for word in words[1:]:
            candidate = f"{line} {word}"
            bbox = font.getbbox(candidate)
            if bbox[2] - bbox[0] <= max_width:
                line = candidate
            else:
                wrapped.append(line)
                line = word
        wrapped.append(line)
    return wrapped


def _active_cue(cues: list[SubtitleCue], t: float) -> SubtitleCue | None:
    for cue in cues:
        if cue.start <= t <= cue.end:
            return cue
    return None


def _make_background_frame(
    base: Image.Image,
    t: float,
    duration: float,
    effect: str,
    dark_overlay: bool,
    particles: bool,
    audio_pulse: bool,
    video_size: tuple[int, int],
    fast_effects: bool,
) -> np.ndarray:
    width, height = video_size
    progress = 0 if duration <= 0 else min(1.0, max(0.0, t / duration))
    effect_key = (effect or "cinematic").lower()

    zoom = 1.0
    offset_x = 0
    offset_y = 0
    if effect_key in {"zoom", "cinematic", "dark", "glitch"}:
        zoom = 1.0 + 0.09 * progress
    if effect_key in {"pan", "cinematic"}:
        zoom = max(zoom, 1.08)
        travel_x = int(width * 0.045)
        offset_x = int((progress - 0.5) * travel_x * 2)
    if audio_pulse:
        zoom += 0.006 * (0.5 + 0.5 * math.sin(t * math.pi * 2.0))

    scaled = base.resize((int(width * zoom), int(height * zoom)), Image.Resampling.LANCZOS)
    left = (scaled.width - width) // 2 + offset_x
    top = (scaled.height - height) // 2 + offset_y
    left = min(max(0, left), max(0, scaled.width - width))
    top = min(max(0, top), max(0, scaled.height - height))
    frame = np.array(scaled.crop((left, top, left + width, top + height)))

    if effect_key == "glitch":
        shift = int(5 * math.sin(t * 18))
        frame[:, :, 0] = np.roll(frame[:, :, 0], shift, axis=1)
        frame[:, :, 2] = np.roll(frame[:, :, 2], -shift, axis=1)

    if not fast_effects:
        frame = add_soft_glow(frame)
        frame = add_grain(frame, seed=int(t * 30))
    frame = add_vignette(frame)

    if particles and not fast_effects:
        rng = np.random.default_rng(int(t * 12) + 17)
        draw_image = Image.fromarray(frame)
        draw = ImageDraw.Draw(draw_image, "RGBA")
        for _ in range(42):
            x = int(rng.integers(0, width))
            y = int((rng.integers(0, height) + t * 18) % height)
            alpha = int(rng.integers(24, 74))
            radius = int(rng.integers(1, 4))
            draw.ellipse((x, y, x + radius, y + radius), fill=(255, 255, 255, alpha))
        frame = np.array(draw_image)

    if dark_overlay or effect_key == "dark":
        frame = add_dark_overlay(frame)

    return frame


def _draw_subtitle(
    frame: np.ndarray,
    cue: SubtitleCue | None,
    text_size: int,
    position: str,
    color: str,
    shadow: bool,
    video_size: tuple[int, int],
) -> np.ndarray:
    if cue is None:
        return frame

    image = Image.fromarray(frame).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _load_font(text_size)
    width, height = video_size
    lines = _wrap_text(cue.text, font, int(width * 0.78))
    line_spacing = int(text_size * 0.26)
    line_boxes = [font.getbbox(line) for line in lines]
    line_heights = [box[3] - box[1] for box in line_boxes]
    block_height = sum(line_heights) + line_spacing * max(0, len(lines) - 1)

    position_key = (position or "center").lower()
    if position_key == "top":
        y = int(height * 0.16)
    elif position_key == "bottom":
        y = int(height * 0.72)
    else:
        y = int((height - block_height) / 2)

    fill = _hex_to_rgb(color)
    for index, line in enumerate(lines):
        bbox = font.getbbox(line)
        text_width = bbox[2] - bbox[0]
        x = int((width - text_width) / 2)
        current_y = y + sum(line_heights[:index]) + line_spacing * index
        if shadow:
            draw.text((x + 5, current_y + 6), line, font=font, fill=(0, 0, 0, 190))
        draw.text(
            (x, current_y),
            line,
            font=font,
            fill=(*fill, 255),
            stroke_width=max(2, text_size // 18),
            stroke_fill=(0, 0, 0, 230),
        )

    combined = Image.alpha_composite(image, overlay).convert("RGB")
    return np.array(combined)


def render_lyric_video(
    *,
    audio_path: str,
    image_path: str,
    srt_text: str,
    output_video_path: str,
    processed_image_path: str,
    duration: float,
    text_size: int = 72,
    text_position: str = "center",
    background_effect: str = "cinematic",
    subtitle_color: str = "#FFFFFF",
    enable_shadow: bool = True,
    dark_overlay: bool = True,
    particles: bool = False,
    audio_pulse: bool = False,
    video_size: tuple[int, int] = VIDEO_SIZE,
    fps: int = 30,
    codec_preset: str = "medium",
    fast_effects: bool = False,
    progress_callback=None,
) -> tuple[str, str]:
    cues = parse_srt(srt_text)
    resize_crop_image(image_path, processed_image_path, size=video_size)
    base_image = Image.open(processed_image_path).convert("RGB")

    def make_frame(t: float) -> np.ndarray:
        if progress_callback and int(t * 10) % 30 == 0:
            progress_callback(min(0.95, t / max(duration, 1)), desc="Rendering frames")
        frame = _make_background_frame(
            base_image,
            t,
            duration,
            background_effect,
            dark_overlay,
            particles,
            audio_pulse,
            video_size,
            fast_effects,
        )
        return _draw_subtitle(
            frame,
            _active_cue(cues, t),
            int(text_size),
            text_position,
            subtitle_color,
            enable_shadow,
            video_size,
        )

    audio_clip = AudioFileClip(audio_path)
    video_clip = VideoClip(make_frame, duration=duration).set_audio(audio_clip)
    try:
        video_clip.write_videofile(
            output_video_path,
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            preset=codec_preset,
            bitrate="6000k",
            threads=2,
            logger=None,
        )
    finally:
        video_clip.close()
        audio_clip.close()
        base_image.close()

    return output_video_path, processed_image_path
