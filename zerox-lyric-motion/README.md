---
title: ZeroX Lyric Motion
emoji: 🎵
colorFrom: purple
colorTo: blue
sdk: static
app_file: index.html
license: mit
pinned: false
---
# ZeroX Lyric Motion — free browser studio
Upload audio → automatic word timing → music-reactive lyrics video → download.

This folder is a complete Hugging Face **Static Space**, with no build step, server, paid inference API, watermark, account token in frontend code, or GPU subscription. Transcription downloads the Apache-2.0 Whisper base model and runs on the visitor's device using Transformers.js. Video export uses browser MediaRecorder: MP4 where supported, otherwise WebM. Recognition and export speed depend on the device. Export takes approximately the song duration after recognition.

## Special effects studio
- Drifting stars, neon rain, embers, soft glitch lines, film grain.
- Effect intensity and speed controls.
- Animated GIF or still PNG/JPEG/WebP overlay upload, with size, opacity, placement, and blend controls.
- Actual GIF frame decoding, loop timing, transparency/disposal compositing. GIFs animate in the canvas captured by video export.
- Generate a 2-second 480×270 animated effect GIF (24 frames), with a black matte for Screen blending.
- Live visual effect preview. Overlays render beneath the lyric text so captions stay readable.
- Limits: GIF/image input 8 MB; GIF max 120 frames / 1024px dimensions / 12 million decoded logical pixels; still images max 4096px dimensions.

## Use
Run `python -m http.server 8000` from this folder and open http://localhost:8000, or upload this folder's files to a Hugging Face Static Space. Use HTTPS or localhost, not file://. No Python packages are needed for this browser app. Try the included synthetic spoken demo, or use instrumental mode to skip speech-model downloads.

## GitHub → Hugging Face
The repository workflow `.github/workflows/zerox-lyric-motion-hf.yml` syncs only this folder to `Zeroxdesignart/zerox-lyric-motion-free` as a Static Space. It uses the official `huggingface/hub-sync` action. Add a repository Actions secret named `HF_TOKEN` containing a Hugging Face token permitted to create/write that Space. Never commit it or put it in browser code. The workflow clearly skips publication when the secret is absent. Its validation still runs. No paid hardware is requested. `delete_removed: false` avoids deleting unrelated Hub files.

Static hosting is free under the provider's current policy; service policies can change. This public GitHub repository uses standard ubuntu-latest runners; GitHub's runner policy applies. The app has no billing integration. No Hugging Face deployment is claimed until the workflow succeeds and the Space is verified.

## Privacy and rights
Audio and overlays stay on the visitor's device; the model and executable dependencies download from Hugging Face/jsDelivr. Audio, GIFs and video output are not saved to the host. Download the result before leaving. Settings/timing text are saved in localStorage. Use audio and images you own or are permitted to use.

Automatic transcription of singing can be inaccurate. Cinematic diffusion footage and studio-quality vocal separation are not part of this version. WebP overlays are treated as still images. GIF is the supported animated overlay format. Long/high-resolution exports on older tablets may exhaust memory. See TEST_REPORT.md for passed checks and browser verification limits.

## Licenses
App and original procedural effects: MIT. Bundled gifuct-js, js-binary-schema-parser and gifenc: MIT (full notices in vendor/LICENSES.txt). Transformers.js and the ONNX Whisper base model: Apache-2.0. Upstream ONNX Runtime: MIT. See THIRD_PARTY.md. There are no paid asset feeds.
