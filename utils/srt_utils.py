from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SubtitleCue:
    index: int
    start: float
    end: float
    text: str


_TIMECODE_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2},\d{3})"
)


def seconds_to_srt_timestamp(seconds: float) -> str:
    milliseconds_total = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(milliseconds_total, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def srt_timestamp_to_seconds(timestamp: str) -> float:
    hours, minutes, rest = timestamp.split(":")
    seconds, millis = rest.split(",")
    return (
        int(hours) * 3600
        + int(minutes) * 60
        + int(seconds)
        + int(millis) / 1000.0
    )


def clean_lyrics_lines(lyrics: str | None) -> list[str]:
    if not lyrics:
        return []
    lines: list[str] = []
    for raw_line in lyrics.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^\[.*\]$", line):
            continue
        lines.append(line)
    return lines


def generate_srt_from_lyrics(lyrics: str, duration: float) -> str:
    lines = clean_lyrics_lines(lyrics)
    if not lines:
        raise ValueError("Paste lyrics or upload an SRT file.")
    if duration <= 0:
        raise ValueError("Audio duration must be greater than zero.")

    cue_count = len(lines)
    raw_slot = duration / cue_count
    cue_length = min(5.0, max(2.0, raw_slot))
    gap = 0.08 if raw_slot > 2.1 else 0.0

    blocks: list[str] = []
    for index, line in enumerate(lines, start=1):
        start = min(duration, (index - 1) * raw_slot)
        end = min(duration, start + cue_length)
        if index == cue_count:
            end = duration
        if end <= start:
            end = min(duration, start + 0.5)

        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{seconds_to_srt_timestamp(start)} --> {seconds_to_srt_timestamp(max(start, end - gap))}",
                    line,
                ]
            )
        )

    return "\n\n".join(blocks) + "\n"


def parse_srt(srt_text: str) -> list[SubtitleCue]:
    normalized = srt_text.replace("\r\n", "\n").strip()
    if not normalized:
        raise ValueError("SRT content is empty.")

    cues: list[SubtitleCue] = []
    blocks = re.split(r"\n\s*\n", normalized)
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if len(lines) < 2:
            continue

        timing_line_index = 0
        if lines[0].isdigit() and len(lines) > 1:
            timing_line_index = 1

        match = _TIMECODE_RE.search(lines[timing_line_index])
        if not match:
            continue

        text = "\n".join(lines[timing_line_index + 1 :]).strip()
        if not text:
            continue

        start = srt_timestamp_to_seconds(match.group("start"))
        end = srt_timestamp_to_seconds(match.group("end"))
        if end <= start:
            continue
        cues.append(SubtitleCue(len(cues) + 1, start, end, text))

    if not cues:
        raise ValueError("No valid subtitle cues were found in the SRT file.")
    return cues


def read_srt_file(srt_path: str | None) -> str | None:
    if not srt_path:
        return None
    path = Path(srt_path)
    if path.suffix.lower() != ".srt":
        raise ValueError("Subtitle upload must be an .srt file.")
    return path.read_text(encoding="utf-8-sig")


def write_srt_file(srt_text: str, output_path: str) -> str:
    Path(output_path).write_text(srt_text, encoding="utf-8")
    return output_path
