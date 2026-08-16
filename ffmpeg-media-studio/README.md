# 🎬 OmniMedia Studio — FFmpeg & yt-dlp All-In-One Media Suite for Ubuntu

OmniMedia Studio is a high-performance web-based media processing and video downloading suite powered by **FFmpeg** and **yt-dlp** on Ubuntu.

---

## ✨ Key Features

1. **📥 Universal URL Downloader**:
   - Downloads video and audio from 1000+ websites (YouTube, TikTok, Twitter/X, Instagram, Facebook, Reddit, Vimeo, Twitch, and direct m3u8/MP4 streams) via `yt-dlp`.
   - Quality presets: Best Video+Audio, 1080p FHD, 720p HD, 480p, and Audio-Only (MP3 320kbps, M4A, WAV).

2. **📂 Drag & Drop Media Workbench**:
   - Multi-file drag-and-drop upload with live progress bars.
   - Automatic `ffprobe` metadata inspection (duration, video/audio codecs, resolution, bitrate, FPS, audio channels, file size).

3. **🔀 Merge & Concatenate Engine**:
   - Merge multiple video or audio files in any custom order.
   - Automatic aspect ratio and resolution normalization (letterbox padding) for seamless merging of clips with different sizes.
   - Fast lossless stream concat mode for matching codecs.

4. **🔄 Format Converter**:
   - **Video**: MP4 (H.264 / H.265 / AV1), MKV, WebM (VP9 / AV1), AVI, MOV, TS.
   - **Audio**: MP3, WAV, AAC, FLAC, OGG, M4A, OPUS.
   - **Animated GIF / WebP**: High-fidelity 2-pass palette generation.
   - Fine-grained controls: CRF quality slider (0–51), CPU speed presets, video/audio bitrate limits.

5. **✂️ Trim, Cut & Segment**:
   - Interactive player with visual timeline scrubbing.
   - **📍 Set Current** buttons for 1-click start and end time capture.
   - Frame-accurate re-encode cut or ultra-fast lossless stream copy.

6. **🗜️ Compressor & Downscaler**:
   - Target file size calculator with 1-click presets: **Discord 8MB / 25MB**, **WhatsApp 50MB**, **Email 25MB**.
   - Resolution downscaling (4K -> 1080p -> 720p -> 480p -> 360p).

7. **🎵 Audio Track Studio**:
   - Extract audio tracks from video to MP3, WAV, AAC, or FLAC.
   - Replace video audio with a new voiceover or background music.
   - Mix background music with original video audio with independent volume controls.

8. **⚡ Speed & Video Transformations**:
   - Playback speed multiplier (0.25x to 4.0x) with audio pitch compensation (`atempo`).
   - Reverse video and audio.
   - 90° / 180° / 270° rotation, horizontal mirror flip, vertical flip.

9. **📦 Output Gallery & Batch ZIP**:
   - HTML5 video/audio player with seeking and media inspector.
   - 1-click individual downloads or **Download All as ZIP**.

---

## 🚀 Quick Start on Ubuntu

### Option 1: 1-Click Setup Script (Recommended for Ubuntu / Debian)

```bash
chmod +x setup.sh
./setup.sh
```

The script will automatically:
1. Install `ffmpeg`, `python3`, `python3-pip`, `curl`, and `jq`.
2. Create a virtual environment and install dependencies.
3. Update `yt-dlp` to the latest release.
4. Launch the Web UI at `http://localhost:7860`.

---

### Option 2: Docker / Docker Compose

```bash
# Build and start container
docker-compose up -d

# Check logs
docker-compose logs -f
```

Access the Web UI at: `http://localhost:7860`.

---

### Option 3: Manual Installation

```bash
# 1. Install FFmpeg and system tools
sudo apt update && sudo apt install -y ffmpeg python3 python3-pip

# 2. Install Python requirements
pip3 install -r requirements.txt

# 3. Start server
python3 app.py
```

---

## ⚙️ Configuration Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `PORT` | `7860` | Web server listening port |
| `HOST` | `0.0.0.0` | Binding host address |
| `OMNIMEDIA_DATA_DIR` | `./data` | Directory for uploads, outputs, and temporary files |
