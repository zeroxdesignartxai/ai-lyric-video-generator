from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import gradio as gr

from utils.audio_utils import copy_audio_to_tmp, format_duration, get_audio_duration, make_work_dir
from utils.diagnostics import collect_system_diagnostics, run_render_self_test
from utils.ffmpeg_renderer import render_lyric_video_ffmpeg
from utils.image_effects import validate_image_file
from utils.srt_utils import generate_srt_from_lyrics, read_srt_file, write_srt_file
from utils.video_renderer import render_lyric_video


APP_TITLE = "AI Lyric Video Generator"
MAX_FREE_CPU_DURATION_SECONDS = 8 * 60
DRAFT_DURATION_SECONDS = 20
MAX_AUDIO_UPLOAD_MB = 80
MAX_IMAGE_UPLOAD_MB = 25


def _file_size_mb(path: str | None) -> float:
    if not path:
        return 0.0
    return Path(path).stat().st_size / (1024 * 1024)


def _transcribe_with_whisper(audio_path: str) -> str | None:
    try:
        import whisper
    except Exception:
        return None

    try:
        model = whisper.load_model(os.getenv("WHISPER_MODEL", "base"))
        result = model.transcribe(audio_path, fp16=False)
    except Exception:
        return None

    lines = []
    for segment in result.get("segments", []):
        text = str(segment.get("text", "")).strip()
        if text:
            lines.append(text)
    return "\n".join(lines) if lines else None


def _build_srt(
    *,
    mode: str,
    audio_path: str,
    duration: float,
    lyrics: str | None,
    srt_path: str | None,
) -> tuple[str, str]:
    if mode == "Upload existing SRT":
        srt_text = read_srt_file(srt_path)
        if not srt_text:
            raise ValueError("Upload an SRT file or choose another lyrics mode.")
        return srt_text, "Using uploaded SRT."

    if mode == "Paste lyrics and auto-time":
        return generate_srt_from_lyrics(lyrics or "", duration), "Generated SRT from pasted lyrics."

    transcript = _transcribe_with_whisper(audio_path)
    if transcript:
        return generate_srt_from_lyrics(transcript, duration), "Generated SRT from Whisper transcription."

    fallback_text = lyrics or "Instrumental section"
    return (
        generate_srt_from_lyrics(fallback_text, duration),
        "Whisper was unavailable or failed, so a simple timed SRT was generated.",
    )


def inspect_audio(audio_path: str | None) -> str:
    if not audio_path:
        return "No audio uploaded."
    try:
        duration = get_audio_duration(audio_path)
        size_mb = _file_size_mb(audio_path)
    except Exception as exc:
        return f"Audio error: {exc}"
    warning = ""
    if size_mb > MAX_AUDIO_UPLOAD_MB:
        warning += f" File is {size_mb:.1f} MB; free CPU works best under {MAX_AUDIO_UPLOAD_MB} MB."
    if duration > MAX_FREE_CPU_DURATION_SECONDS:
        warning += " Longer tracks can be slow on free CPU; use Draft Render first."
    return f"Duration: {format_duration(duration)} ({duration:.2f} seconds). Size: {size_mb:.1f} MB.{warning}"


def _resolve_render_settings(render_profile: str, text_size: int, draft: bool) -> tuple[tuple[int, int], int, str, bool, int]:
    if draft:
        return (854, 480), 15, "ultrafast", True, max(24, int(text_size * 0.48))

    if render_profile.startswith("Fast"):
        return (1280, 720), 24, "ultrafast", True, max(32, int(text_size * 0.72))
    if render_profile.startswith("Balanced"):
        return (1920, 1080), 24, "veryfast", True, text_size
    return (1920, 1080), 30, "medium", False, text_size


def generate_video(
    audio_file: str | None,
    image_file: str | None,
    mode: str,
    lyrics: str,
    srt_file: str | None,
    render_profile: str,
    render_engine: str,
    text_size: int,
    text_position: str,
    background_effect: str,
    subtitle_color: str,
    enable_shadow: bool,
    dark_overlay: bool,
    particles: bool,
    audio_pulse: bool,
    draft: bool = False,
    progress=gr.Progress(track_tqdm=False),
):
    progress(0, desc="Validating uploads")
    if not audio_file:
        raise gr.Error("Please upload an audio file.")
    if not image_file:
        raise gr.Error("Please upload an image.")

    try:
        validate_image_file(image_file)
        audio_size_mb = _file_size_mb(audio_file)
        image_size_mb = _file_size_mb(image_file)
        if audio_size_mb > MAX_AUDIO_UPLOAD_MB:
            raise ValueError(f"Audio file is too large for free CPU mode. Keep it under {MAX_AUDIO_UPLOAD_MB} MB.")
        if image_size_mb > MAX_IMAGE_UPLOAD_MB:
            raise ValueError(f"Image file is too large for free CPU mode. Keep it under {MAX_IMAGE_UPLOAD_MB} MB.")
        source_duration = get_audio_duration(audio_file)
    except Exception as exc:
        raise gr.Error(str(exc)) from exc

    duration = min(source_duration, DRAFT_DURATION_SECONDS) if draft else source_duration
    if not draft and source_duration > MAX_FREE_CPU_DURATION_SECONDS:
        raise gr.Error(
            "This track is longer than the free CPU guardrail. Use Draft Render first, "
            "or trim the audio before final rendering."
        )

    tmp_context = make_work_dir()
    keep_dir = None
    try:
        work_dir = tmp_context.name
        progress(0.08, desc="Preparing temporary files")
        safe_audio = copy_audio_to_tmp(audio_file, work_dir)
        safe_image = str(Path(work_dir) / f"source_image{Path(image_file).suffix.lower()}")
        shutil.copy2(image_file, safe_image)

        progress(0.16, desc="Creating subtitles")
        srt_text, srt_status = _build_srt(
            mode=mode,
            audio_path=safe_audio,
            duration=source_duration,
            lyrics=lyrics,
            srt_path=srt_file,
        )

        generated_srt = str(Path(work_dir) / "generated_subtitles.srt")
        processed_image = str(Path(work_dir) / "processed_background.jpg")
        output_video = str(Path(work_dir) / "ai_lyric_video.mp4")
        write_srt_file(srt_text, generated_srt)

        video_size, fps, codec_preset, fast_effects, adjusted_text_size = _resolve_render_settings(
            render_profile, text_size, draft
        )

        progress(0.24, desc="Rendering draft preview" if draft else "Rendering lyric video")
        engine_note = "FFmpeg"
        ffmpeg_error: Exception | None = None
        if render_engine.startswith("FFmpeg"):
            try:
                render_lyric_video_ffmpeg(
                    audio_path=safe_audio,
                    image_path=safe_image,
                    srt_text=srt_text,
                    output_video_path=output_video,
                    processed_image_path=processed_image,
                    duration=duration,
                    text_size=adjusted_text_size,
                    text_position=text_position,
                    background_effect=background_effect,
                    subtitle_color=subtitle_color,
                    enable_shadow=enable_shadow,
                    dark_overlay=dark_overlay,
                    video_size=video_size,
                    fps=fps,
                    codec_preset=codec_preset,
                )
            except Exception as exc:
                ffmpeg_error = exc
                engine_note = "MoviePy fallback"
                render_lyric_video(
                    audio_path=safe_audio,
                    image_path=safe_image,
                    srt_text=srt_text,
                    output_video_path=output_video,
                    processed_image_path=processed_image,
                    duration=duration,
                    text_size=adjusted_text_size,
                    text_position=text_position,
                    background_effect=background_effect,
                    subtitle_color=subtitle_color,
                    enable_shadow=enable_shadow,
                    dark_overlay=dark_overlay,
                    particles=particles,
                    audio_pulse=audio_pulse,
                    video_size=video_size,
                    fps=fps,
                    codec_preset=codec_preset,
                    fast_effects=fast_effects,
                    progress_callback=progress,
                )
        else:
            engine_note = "MoviePy"
            render_lyric_video(
                audio_path=safe_audio,
                image_path=safe_image,
                srt_text=srt_text,
                output_video_path=output_video,
                processed_image_path=processed_image,
                duration=duration,
                text_size=adjusted_text_size,
                text_position=text_position,
                background_effect=background_effect,
                subtitle_color=subtitle_color,
                enable_shadow=enable_shadow,
                dark_overlay=dark_overlay,
                particles=particles,
                audio_pulse=audio_pulse,
                video_size=video_size,
                fps=fps,
                codec_preset=codec_preset,
                fast_effects=fast_effects,
                progress_callback=progress,
            )

        progress(0.98, desc="Preparing downloads")
        keep_dir = Path(tempfile.gettempdir()) / f"lyric_video_output_{os.getpid()}"
        keep_dir.mkdir(parents=True, exist_ok=True)
        video_name = "draft_preview.mp4" if draft else "ai_lyric_video.mp4"
        final_video = str(keep_dir / video_name)
        final_srt = str(keep_dir / "generated_subtitles.srt")
        final_background = str(keep_dir / "processed_background.jpg")
        shutil.copy2(output_video, final_video)
        shutil.copy2(generated_srt, final_srt)
        shutil.copy2(processed_image, final_background)
        progress(1, desc="Done")
        render_label = "Draft preview" if draft else "Final video"
        status = (
            f"{srt_status} {render_label} rendered {format_duration(duration)} "
            f"of {format_duration(source_duration)} at "
            f"{video_size[0]}x{video_size[1]}, {fps} FPS using {engine_note} "
            f"with {codec_preset} preset."
        )
        if ffmpeg_error:
            status += f"\n\nFFmpeg fallback reason: `{ffmpeg_error}`"
        return final_video, final_video, final_srt, final_background, status
    except gr.Error:
        raise
    except Exception as exc:
        raise gr.Error(f"Video generation failed: {exc}") from exc
    finally:
        tmp_context.cleanup()


def generate_draft_video(
    audio_file: str | None,
    image_file: str | None,
    mode: str,
    lyrics: str,
    srt_file: str | None,
    render_profile: str,
    render_engine: str,
    text_size: int,
    text_position: str,
    background_effect: str,
    subtitle_color: str,
    enable_shadow: bool,
    dark_overlay: bool,
    particles: bool,
    audio_pulse: bool,
    progress=gr.Progress(track_tqdm=False),
):
    return generate_video(
        audio_file,
        image_file,
        mode,
        lyrics,
        srt_file,
        render_profile,
        render_engine,
        text_size,
        text_position,
        background_effect,
        subtitle_color,
        enable_shadow,
        dark_overlay,
        particles,
        audio_pulse,
        draft=True,
        progress=progress,
    )


def generate_final_video(
    audio_file: str | None,
    image_file: str | None,
    mode: str,
    lyrics: str,
    srt_file: str | None,
    render_profile: str,
    render_engine: str,
    text_size: int,
    text_position: str,
    background_effect: str,
    subtitle_color: str,
    enable_shadow: bool,
    dark_overlay: bool,
    particles: bool,
    audio_pulse: bool,
    progress=gr.Progress(track_tqdm=False),
):
    return generate_video(
        audio_file,
        image_file,
        mode,
        lyrics,
        srt_file,
        render_profile,
        render_engine,
        text_size,
        text_position,
        background_effect,
        subtitle_color,
        enable_shadow,
        dark_overlay,
        particles,
        audio_pulse,
        draft=False,
        progress=progress,
    )


CSS = """
.warning-box {
  border-left: 4px solid #f59e0b;
  padding: 0.75rem 1rem;
  background: rgba(245, 158, 11, 0.08);
}
"""


with gr.Blocks(title=APP_TITLE, css=CSS) as demo:
    gr.Markdown(
        f"# {APP_TITLE}\n"
        "Upload an audio track and artwork to create a downloadable lyric video. "
        "Only upload media you own or have rights to use."
    )

    with gr.Tabs():
        with gr.Tab("Generator"):
            with gr.Row():
                with gr.Column(scale=1):
                    audio = gr.Audio(
                        label="Upload Audio",
                        sources=["upload"],
                        type="filepath",
                        format="mp3",
                    )
                    audio_status = gr.Markdown("No audio uploaded.")
                    image = gr.Image(
                        label="Upload Image",
                        sources=["upload"],
                        type="filepath",
                        image_mode="RGB",
                    )

                    mode = gr.Radio(
                        choices=[
                            "Upload existing SRT",
                            "Paste lyrics and auto-time",
                            "Use AI transcription if available",
                        ],
                        value="Paste lyrics and auto-time",
                        label="Lyrics Mode",
                    )
                    lyrics = gr.Textbox(
                        label="Lyrics Text",
                        lines=9,
                        placeholder="Paste lyrics here. Leave empty only when uploading SRT or trying AI transcription.",
                    )
                    srt = gr.File(
                        label="Upload SRT",
                        file_types=[".srt"],
                        type="filepath",
                    )

                with gr.Column(scale=1):
                    gr.Markdown("## Style Options")
                    render_profile = gr.Dropdown(
                        choices=[
                            "Fast HF CPU (720p, 24 FPS)",
                            "Balanced (1080p, 24 FPS)",
                            "Full HD final (1080p, 30 FPS)",
                        ],
                        value="Fast HF CPU (720p, 24 FPS)",
                        label="Render profile",
                    )
                    render_engine = gr.Dropdown(
                        choices=[
                            "FFmpeg native (fastest CPU)",
                            "MoviePy fallback (slower)",
                        ],
                        value="FFmpeg native (fastest CPU)",
                        label="Render engine",
                    )
                    text_size = gr.Slider(42, 110, value=72, step=2, label="Text size")
                    text_position = gr.Dropdown(
                        choices=["center", "bottom", "top"],
                        value="center",
                        label="Text position",
                    )
                    background_effect = gr.Dropdown(
                        choices=["cinematic", "zoom", "pan", "dark", "glitch"],
                        value="cinematic",
                        label="Background effect",
                    )
                    subtitle_color = gr.ColorPicker(value="#FFFFFF", label="Subtitle color")
                    enable_shadow = gr.Checkbox(value=True, label="Enable text shadow")
                    dark_overlay = gr.Checkbox(value=True, label="Dark overlay for readable lyrics")
                    particles = gr.Checkbox(value=False, label="Light particles")
                    audio_pulse = gr.Checkbox(value=False, label="Subtle pulse")
                    with gr.Row():
                        draft_generate = gr.Button("Draft Render", variant="secondary")
                        generate = gr.Button("Final Render", variant="primary")

            with gr.Row():
                video_preview = gr.Video(label="Video preview", format="mp4")
                with gr.Column():
                    status = gr.Markdown("Ready.")
                    video_download = gr.File(label="Download final MP4")
                    srt_download = gr.File(label="Download generated SRT")
                    background_download = gr.File(label="Download processed background")

        with gr.Tab("Debug"):
            gr.Markdown("## System Diagnostics")
            diagnostics_output = gr.Markdown(value=collect_system_diagnostics())
            with gr.Row():
                refresh_diagnostics = gr.Button("Refresh Diagnostics")
                run_self_test = gr.Button("Run Render Self-Test", variant="secondary")
            self_test_output = gr.Markdown("Self-test has not been run.")

    audio.change(fn=inspect_audio, inputs=audio, outputs=audio_status)
    refresh_diagnostics.click(fn=collect_system_diagnostics, outputs=diagnostics_output)
    run_self_test.click(fn=run_render_self_test, outputs=self_test_output, show_progress="full")
    draft_generate.click(
        fn=generate_draft_video,
        inputs=[
            audio,
            image,
            mode,
            lyrics,
            srt,
            render_profile,
            render_engine,
            text_size,
            text_position,
            background_effect,
            subtitle_color,
            enable_shadow,
            dark_overlay,
            particles,
            audio_pulse,
        ],
        outputs=[video_preview, video_download, srt_download, background_download, status],
        show_progress="full",
        concurrency_limit=1,
    )
    generate.click(
        fn=generate_final_video,
        inputs=[
            audio,
            image,
            mode,
            lyrics,
            srt,
            render_profile,
            render_engine,
            text_size,
            text_position,
            background_effect,
            subtitle_color,
            enable_shadow,
            dark_overlay,
            particles,
            audio_pulse,
        ],
        outputs=[video_preview, video_download, srt_download, background_download, status],
        show_progress="full",
        concurrency_limit=1,
    )


if __name__ == "__main__":
    demo.launch()
