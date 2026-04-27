from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from PIL import Image

from .image_effects import resize_crop_image
from .srt_utils import parse_srt


def _ffmpeg_executable() -> str:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError("ffmpeg is not available in PATH or imageio-ffmpeg.") from exc


def _escape_ass_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\r\n", "\\N")
        .replace("\n", "\\N")
    )


def _seconds_to_ass_time(seconds: float) -> str:
    centiseconds_total = max(0, int(round(seconds * 100)))
    hours, remainder = divmod(centiseconds_total, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    secs, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def _hex_to_ass_color(hex_color: str) -> str:
    value = (hex_color or "#FFFFFF").strip().lstrip("#")
    if len(value) != 6:
        value = "FFFFFF"
    red = value[0:2]
    green = value[2:4]
    blue = value[4:6]
    return f"&H00{blue}{green}{red}"


def _write_ass_subtitles(
    *,
    srt_text: str,
    output_path: str,
    video_size: tuple[int, int],
    text_size: int,
    text_position: str,
    subtitle_color: str,
    enable_shadow: bool,
) -> str:
    width, height = video_size
    alignment = {"top": 8, "center": 5, "bottom": 2}.get((text_position or "center").lower(), 5)
    margin_v = int(height * 0.11)
    outline = max(2, text_size // 18)
    shadow = 2 if enable_shadow else 0
    color = _hex_to_ass_color(subtitle_color)
    cues = parse_srt(srt_text)

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        (
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding"
        ),
        (
            f"Style: Default,DejaVu Sans,{text_size},{color},&H000000FF,"
            f"&HCC000000,&H99000000,-1,0,0,0,100,100,0,0,1,{outline},{shadow},"
            f"{alignment},120,120,{margin_v},1"
        ),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    for cue in cues:
        lines.append(
            "Dialogue: 0,"
            f"{_seconds_to_ass_time(cue.start)},{_seconds_to_ass_time(cue.end)},"
            f"Default,,0,0,0,,{_escape_ass_text(cue.text)}"
        )

    Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def _filter_for_effect(
    *,
    video_size: tuple[int, int],
    background_effect: str,
    dark_overlay: bool,
    processed_image_path: str,
    ass_path: str,
) -> str:
    width, height = video_size
    effect = (background_effect or "cinematic").lower()
    filters = [f"scale={width}:{height}:force_original_aspect_ratio=increase", f"crop={width}:{height}"]

    if effect in {"zoom", "cinematic"}:
        filters = [
            f"scale={int(width * 1.12)}:{int(height * 1.12)}:force_original_aspect_ratio=increase",
            (
                f"crop={width}:{height}:"
                f"x='(iw-ow)/2-(iw-ow)*0.08*sin(t/5)':"
                f"y='(ih-oh)/2-(ih-oh)*0.08*cos(t/6)'"
            ),
        ]
    elif effect == "pan":
        filters = [
            f"scale={int(width * 1.12)}:{int(height * 1.12)}:force_original_aspect_ratio=increase",
            f"crop={width}:{height}:x='(iw-ow)*(0.5+0.5*sin(t/8))':y='(ih-oh)/2'",
        ]
    elif effect == "glitch":
        filters.append("rgbashift=rh=2:bh=-2")

    filters.extend(["eq=contrast=1.06:saturation=1.08", "vignette=PI/5", "noise=alls=6:allf=t+u"])

    if dark_overlay or effect == "dark":
        filters.append("drawbox=x=0:y=0:w=iw:h=ih:color=black@0.28:t=fill")

    ass_filter_path = ass_path.replace("\\", "/").replace(":", "\\:")
    filters.append(f"ass='{ass_filter_path}'")
    filters.append("format=yuv420p")
    return ",".join(filters)


def render_lyric_video_ffmpeg(
    *,
    audio_path: str,
    image_path: str,
    srt_text: str,
    output_video_path: str,
    processed_image_path: str,
    duration: float,
    text_size: int,
    text_position: str,
    background_effect: str,
    subtitle_color: str,
    enable_shadow: bool,
    dark_overlay: bool,
    video_size: tuple[int, int],
    fps: int,
    codec_preset: str,
) -> tuple[str, str]:
    resize_crop_image(image_path, processed_image_path, size=video_size)
    ass_path = str(Path(output_video_path).with_suffix(".ass"))
    _write_ass_subtitles(
        srt_text=srt_text,
        output_path=ass_path,
        video_size=video_size,
        text_size=text_size,
        text_position=text_position,
        subtitle_color=subtitle_color,
        enable_shadow=enable_shadow,
    )

    vf = _filter_for_effect(
        video_size=video_size,
        background_effect=background_effect,
        dark_overlay=dark_overlay,
        processed_image_path=processed_image_path,
        ass_path=ass_path,
    )
    command = [
        _ffmpeg_executable(),
        "-y",
        "-loop",
        "1",
        "-framerate",
        str(fps),
        "-t",
        f"{duration:.3f}",
        "-i",
        processed_image_path,
        "-i",
        audio_path,
        "-vf",
        vf,
        "-r",
        str(fps),
        "-c:v",
        "libx264",
        "-preset",
        codec_preset,
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        output_video_path,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "ffmpeg render failed")[-1600:])

    # Ensure Pillow can read the processed background for Gradio download previews.
    with Image.open(processed_image_path) as image:
        image.verify()
    return output_video_path, processed_image_path
