from __future__ import annotations

import importlib.util
import math
import os
import platform
import shutil
import struct
import tempfile
import time
import wave
from pathlib import Path

from PIL import Image

from .ffmpeg_renderer import _ffmpeg_executable, render_lyric_video_ffmpeg
from .srt_utils import generate_srt_from_lyrics


def _check_dependency(module_name: str, label: str | None = None) -> tuple[str, str]:
    name = label or module_name
    if importlib.util.find_spec(module_name):
        return "PASS", f"{name} is importable."
    return "FAIL", f"{name} is not installed."


def _format_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def collect_system_diagnostics() -> str:
    checks: list[tuple[str, str]] = []
    checks.append(("PASS", f"Python {platform.python_version()} on {platform.system()} {platform.release()}"))

    for module_name, label in [
        ("gradio", "Gradio"),
        ("moviepy", "MoviePy"),
        ("PIL", "Pillow"),
        ("numpy", "NumPy"),
        ("pydub", "pydub"),
        ("imageio_ffmpeg", "imageio-ffmpeg"),
    ]:
        checks.append(_check_dependency(module_name, label))

    whisper_status = "PASS" if importlib.util.find_spec("whisper") else "WARN"
    whisper_message = (
        "Whisper is installed."
        if whisper_status == "PASS"
        else "Whisper is not installed; AI transcription will use fallback timing."
    )
    checks.append((whisper_status, whisper_message))

    try:
        ffmpeg_path = _ffmpeg_executable()
        checks.append(("PASS", f"FFmpeg found: {ffmpeg_path}"))
    except Exception as exc:
        checks.append(("FAIL", f"FFmpeg unavailable: {exc}"))

    temp_root = Path(tempfile.gettempdir())
    try:
        usage = shutil.disk_usage(temp_root)
        status = "PASS" if usage.free > 500 * 1024 * 1024 else "WARN"
        checks.append((status, f"Temp free space at {temp_root}: {_format_bytes(usage.free)}"))
    except Exception as exc:
        checks.append(("WARN", f"Could not inspect temp disk space: {exc}"))

    checks.append(("PASS", f"Process ID: {os.getpid()}"))
    return "\n".join(f"- **{status}** {message}" for status, message in checks)


def run_render_self_test() -> str:
    start = time.perf_counter()
    work_dir = tempfile.mkdtemp(prefix="lyric_video_selftest_", dir=tempfile.gettempdir())
    try:
        audio_path = os.path.join(work_dir, "audio.wav")
        image_path = os.path.join(work_dir, "image.jpg")
        video_path = os.path.join(work_dir, "self_test.mp4")
        background_path = os.path.join(work_dir, "background.jpg")

        sample_rate = 8000
        seconds = 2
        with wave.open(audio_path, "w") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(sample_rate)
            for index in range(sample_rate * seconds):
                value = int(9000 * math.sin(2 * math.pi * 220 * index / sample_rate))
                audio.writeframes(struct.pack("<h", value))

        Image.new("RGB", (960, 540), (28, 46, 76)).save(image_path, quality=92)
        srt_text = generate_srt_from_lyrics("Self test lyric\nRenderer online", seconds)
        render_lyric_video_ffmpeg(
            audio_path=audio_path,
            image_path=image_path,
            srt_text=srt_text,
            output_video_path=video_path,
            processed_image_path=background_path,
            duration=seconds,
            text_size=34,
            text_position="center",
            background_effect="cinematic",
            subtitle_color="#FFFFFF",
            enable_shadow=True,
            dark_overlay=True,
            video_size=(640, 360),
            fps=12,
            codec_preset="ultrafast",
        )

        elapsed = time.perf_counter() - start
        size = Path(video_path).stat().st_size
        if size <= 0:
            return "- **FAIL** Render self-test created an empty video."
        return (
            "- **PASS** FFmpeg render self-test completed.\n"
            f"- **PASS** Output size: {_format_bytes(size)}\n"
            f"- **PASS** Elapsed time: {elapsed:.2f}s"
        )
    except Exception as exc:
        return f"- **FAIL** Render self-test failed: `{exc}`"
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
