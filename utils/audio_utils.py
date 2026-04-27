from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a"}


def validate_audio_file(audio_path: str | None) -> Path:
    if not audio_path:
        raise ValueError("Please upload an audio file.")

    path = Path(audio_path)
    if not path.exists():
        raise ValueError("Uploaded audio file could not be found.")

    if path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        raise ValueError("Unsupported audio type. Upload an mp3, wav, or m4a file.")

    return path


def copy_audio_to_tmp(audio_path: str, work_dir: str) -> str:
    source = validate_audio_file(audio_path)
    safe_name = f"audio{source.suffix.lower()}"
    destination = Path(work_dir) / safe_name
    shutil.copy2(source, destination)
    return str(destination)


def get_audio_duration(audio_path: str) -> float:
    path = validate_audio_file(audio_path)
    try:
        from moviepy.editor import AudioFileClip

        clip = AudioFileClip(str(path))
        try:
            duration = float(clip.duration or 0)
        finally:
            clip.close()
    except Exception:
        duration = _get_audio_duration_with_pydub(path)

    if duration <= 0:
        raise ValueError("Audio duration must be greater than zero.")
    return duration


def _get_audio_duration_with_pydub(path: Path) -> float:
    try:
        from pydub import AudioSegment

        segment = AudioSegment.from_file(path)
    except Exception as exc:  # pydub surfaces ffmpeg failures as generic exceptions.
        raise ValueError(
            "Could not read the audio file. Make sure it is valid and ffmpeg is available."
        ) from exc

    return len(segment) / 1000.0


def format_duration(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def make_work_dir() -> tempfile.TemporaryDirectory[str]:
    return tempfile.TemporaryDirectory(prefix="lyric_video_", dir=tempfile.gettempdir())
