# Lyric SRT Engine Design

## Goal

Build the first production-ready lyric SRT engine for the AI Lyric Video Generator so a user can upload song audio, paste lyrics or request transcription, and receive a cleaner, validated `.srt` file than the current even-spacing implementation.

## User Outcome

The user can generate lyric-video-ready subtitles from music audio with two modes:

- Pasted lyrics: the app creates readable timed subtitle cues from the supplied lyric lines.
- Direct transcription: when Whisper is installed, the app uses timestamped transcription segments to create subtitle cues instead of flattening the transcript across the whole song.

The output must always be valid SRT with non-overlapping, monotonic cue timings.

## Existing Context

Project: `E:\.codex\ai-lyric-video-generator`

Current app:

- Gradio app in `app.py`
- SRT utilities in `utils/srt_utils.py`
- Audio duration helpers in `utils/audio_utils.py`
- Optional Whisper transcription path in `app.py`
- Existing SRT generation distributes lyric lines evenly across duration

Current dependencies:

- `gradio`
- `moviepy==1.0.3`
- `pillow`
- `numpy`
- `pydub`
- `ffmpeg-python`
- `imageio-ffmpeg`

No new required dependency should be added for the first engine pass.

## Scope

### In Scope

- Add a dedicated lyric SRT engine module.
- Parse and normalize pasted lyrics into clean cue text.
- Use better heuristic timing for pasted lyrics than even distribution.
- Use Whisper segment timestamps when transcription is available.
- Validate and repair generated SRT cues.
- Keep the existing Gradio workflow intact.
- Preserve the existing fallback behavior when Whisper is unavailable.
- Add focused tests or self-test helpers for cue generation and validation where practical.

### Out of Scope

- Full neural forced alignment.
- Vocal separation or stem extraction.
- Word-level karaoke highlighting.
- ASS style export.
- Burned-in lyric video improvements.
- Desktop Tauri packaging.
- Cloud transcription providers.

These are future upgrades after the local SRT engine is stable.

## Architecture

Add `utils/lyric_srt_engine.py` as the engine boundary. It should expose small, testable functions and a single high-level API for app integration.

Primary data model:

```python
@dataclass
class SubtitleCue:
    index: int
    start: float
    end: float
    text: str
```

Primary API:

```python
def generate_lyric_srt(
    audio_duration: float,
    lyrics: str | None = None,
    transcript_segments: list[dict] | None = None,
) -> str:
    ...
```

Behavior:

- If `transcript_segments` are present, build cues from those timestamps.
- Else if `lyrics` are present, build cues from cleaned lyric lines using heuristic timing.
- Else generate a single instrumental cue.
- Always pass cues through validation and repair before formatting as SRT.

## Pasted Lyrics Timing

Pasted lyrics should be split into non-empty lyric lines while dropping obvious metadata such as section headers:

- `[Verse]`
- `[Chorus]`
- `(Intro)`

Timing should be proportional rather than purely even. Each line receives a weight based on word count and character count. Longer lines receive more time, short repeated hooks receive less time, and all timings are scaled to fit the audio duration.

Rules:

- Minimum cue duration: 1.2 seconds
- Preferred maximum cue duration: 6.0 seconds
- Gap between cues: 0.08 seconds where possible
- First cue starts at 0.0 seconds for v1
- Last cue must end no later than audio duration

This is still heuristic alignment, not true forced alignment, but it is a direct upgrade over even line spacing.

## Transcription Mode

When Whisper is installed, use `result["segments"]` from Whisper instead of only `result["text"]`.

Rules:

- Convert each segment into one or more readable lyric cues.
- Preserve segment start/end timestamps.
- Split long text into shorter lyric lines.
- Repair overlaps and invalid durations.
- Fall back to the pasted lyrics path or simple instrumental cue if Whisper fails.

The engine should not require Whisper directly. `app.py` remains responsible for calling Whisper and passing transcript segments into the engine.

## Validation And Repair

Every generated cue list must be normalized before formatting:

- Remove empty cues.
- Clamp negative start times to zero.
- Ensure `end > start`.
- Ensure cue start times are monotonic.
- Prevent overlaps by shifting starts forward or shortening previous cues.
- Clamp the final cue to `audio_duration`.
- Reindex cues from 1.

If a cue cannot satisfy timing constraints because the audio is too short, preserve validity over ideal readability.

## App Integration

Update `_transcribe_with_whisper` in `app.py` to return transcript text and timestamped segments.

Update `_build_srt`:

- `Upload existing SRT`: unchanged.
- `Paste lyrics and auto-time`: call `generate_lyric_srt(audio_duration, lyrics=lyrics)`.
- `Use AI transcription if available`: call Whisper, then pass segments into `generate_lyric_srt`.
- Whisper unavailable: call `generate_lyric_srt(audio_duration, lyrics=lyrics or "Instrumental section")`.

User-facing mode names can stay unchanged for this pass.

## Error Handling

- Invalid or missing duration raises a clear `ValueError`.
- Empty lyrics produce a valid fallback cue instead of crashing.
- Whisper import or runtime failures return a fallback status message.
- Existing app-level exception handling remains responsible for displaying errors in Gradio.

## Testing

Minimum verification:

- Pasted multi-line lyrics generate valid SRT with monotonic cue indexes.
- Long lyric lines are split or timed without overlap.
- Empty lyrics generate a valid fallback cue.
- Whisper-like timestamped segments generate SRT using segment timings.
- Cues never exceed audio duration.

Because the project currently has no formal test runner configured, add tests only if they can run with the existing Python environment. Otherwise add deterministic helper coverage through a small script or documented self-test.

## Future Upgrade Path

After v1:

1. Add optional vocal separation before transcription.
2. Add real forced alignment for pasted lyrics.
3. Add word-level timestamps.
4. Add `.ass` export with font, stroke, shadow, position, and karaoke effects.
5. Move the engine into a desktop Tauri app sidecar when building Vibe Lyrics Studio.

