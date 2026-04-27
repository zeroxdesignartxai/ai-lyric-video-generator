# AI Lyric Video Generator

A Hugging Face Spaces app that turns an uploaded song, artwork, and lyrics into a 1920x1080 MP4 lyric video with animated cinematic background effects.

## Features

- Upload audio as `mp3`, `wav`, or `m4a`
- Upload artwork as `jpg`, `jpeg`, `png`, or `webp`
- Upload an existing `.srt`, paste lyrics for automatic timing, or try optional Whisper transcription
- Generate a valid SRT subtitle file
- Render centered, top, or bottom lyric overlays with color and shadow controls
- Use the FFmpeg native render engine for faster free CPU Spaces rendering
- Animate the image with zoom, pan, dark, glitch, vignette, glow, grain, particles, and subtle pulse effects
- Download the final MP4, generated SRT, and processed 1920x1080 background image

## How It Works

1. Upload an audio file and image.
2. Choose a lyrics mode:
   - **Upload existing SRT** uses your provided subtitle timings.
   - **Paste lyrics and auto-time** splits lines evenly across the song duration.
   - **Use AI transcription if available** attempts OpenAI Whisper when it is installed and falls back to simple timing.
3. Pick style options.
4. Click **Generate Video**.

The generated video uses H.264 video and AAC audio. The default Hugging Face CPU profile renders 720p at 24 FPS for speed; balanced and full HD profiles are available in the UI.

Use **Draft Render** while tuning styles. It renders only the first 20 seconds at 854x480 and 15 FPS, which is much faster on free CPU. Use **Final Render** after the draft looks right.

## SRT Generation

`generate_srt_from_lyrics(lyrics, duration)` splits non-empty lyric lines and distributes them across the audio duration. Each subtitle cue targets 2 to 5 seconds when possible and is written in standard `.srt` format:

```srt
1
00:00:00,000 --> 00:00:03,000
First lyric line

2
00:00:03,000 --> 00:00:06,000
Second lyric line
```

## Deploy on Hugging Face Spaces

1. Create a new Space.
2. Select **Gradio** as the SDK.
3. Upload these files:
   - `app.py`
   - `requirements.txt`
   - `README.md`
   - `utils/`
4. The Space will run:

```bash
python app.py
```

The app uses `/tmp` for temporary uploads and generated files. User uploads are not stored permanently.

## Hardware Recommendation

Free CPU Spaces work best with the default **Fast HF CPU** profile and the **FFmpeg native** engine. GPU is recommended for Whisper transcription and faster full HD rendering.

Free CPU guardrails:

- Audio uploads should stay under 80 MB.
- Image uploads should stay under 25 MB.
- Final renders are capped at 8 minutes by default.
- Draft Render is the intended workflow for quick iteration.

Whisper is intentionally not installed by default because it pulls a large PyTorch dependency. To enable transcription on a larger Space, add this to `requirements.txt`:

```txt
openai-whisper
```

## Debugging

Use the **Debug** tab in the app before testing uploads on a new Space.

- **Refresh Diagnostics** checks Python, key dependencies, FFmpeg availability, Whisper availability, temp disk space, and process ID.
- **Run Render Self-Test** generates a tiny WAV, image, subtitles, and MP4 using the FFmpeg render path.
- If FFmpeg rendering fails during normal generation, the app falls back to MoviePy and prints the FFmpeg error in the status output.

## Privacy and Rights

Do not upload private or copyrighted material unless you have the rights to process and publish it. Temporary working files are cleaned after rendering, while downloadable outputs remain in `/tmp` for the active session.
