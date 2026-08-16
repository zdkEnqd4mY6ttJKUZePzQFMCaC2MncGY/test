#!/usr/bin/env python3
"""
OmniMedia & Audio Studio - FFmpeg & yt-dlp All-In-One Processing Suite
Features 5MB Chunked Uploads (100% Cloudflare 100MB Limit Proof) and
a comprehensive Audio & Video Processing Engine for Ubuntu.
"""

import os
import sys
import re
import time
import json
import uuid
import shutil
import asyncio
import zipfile
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, BackgroundTasks, Request
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("omnimeda-audio-studio")

# Environment & Directory Setup
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("OMNIMEDIA_DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
TEMP_DIR = DATA_DIR / "temp"
CHUNK_DIR = TEMP_DIR / "chunks"

for directory in [UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR, CHUNK_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Application state for job tracking and chunk uploads
JOBS: Dict[str, Dict[str, Any]] = {}
PROCESSES: Dict[str, asyncio.subprocess.Process] = {}
ACTIVE_UPLOADS: Dict[str, Dict[str, Any]] = {}

app = FastAPI(
    title="OmniMedia & Audio Studio",
    description="High-Performance FFmpeg Audio/Video Suite with 5MB Chunked Uploads",
    version="2.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security Headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "media-src 'self' blob: data:; "
        "img-src 'self' blob: data:; "
        "connect-src 'self';"
    )
    return response

# ==============================================================================
# Helper Functions & Safe Path Utilities
# ==============================================================================

def sanitize_filename(filename: str) -> str:
    """Sanitizes filename and prevents directory traversal sequences."""
    base = os.path.basename(filename)
    sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', base)
    if not sanitized or sanitized.startswith('.'):
        sanitized = f"audio_{int(time.time())}_{sanitized.lstrip('.')}"
    return sanitized

def get_safe_path(category: str, filename: str) -> Path:
    """Resolves and validates that path stays strictly within category directory."""
    clean_name = sanitize_filename(filename)
    if category == "uploads":
        target_dir = UPLOAD_DIR
    elif category == "outputs":
        target_dir = OUTPUT_DIR
    else:
        raise HTTPException(status_code=400, detail="Invalid file category")
    
    target_path = (target_dir / clean_name).resolve()
    try:
        target_path.relative_to(target_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied: path traversal attempt")
    
    return target_path

def parse_time_str(time_val: Any) -> float:
    """Converts seconds float or HH:MM:SS / MM:SS string to seconds."""
    if isinstance(time_val, (int, float)):
        return float(time_val)
    if not time_val:
        return 0.0
    val = str(time_val).strip()
    if ":" in val:
        parts = val.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return float(h) * 3600 + float(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return float(m) * 60 + float(s)
    try:
        return float(val)
    except ValueError:
        return 0.0

def format_duration(seconds: float) -> str:
    """Formats seconds into readable HH:MM:SS or MM:SS."""
    if not seconds or seconds < 0:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

async def probe_media_file(file_path: Path) -> Dict[str, Any]:
    """Runs ffprobe on a file to extract audio/video streams, tags, and metadata."""
    if not file_path.exists():
        return {"error": "File not found"}
    
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(file_path)
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            return {"error": "Failed to probe file", "raw": stderr.decode(errors="ignore")}
        
        info = json.loads(stdout.decode("utf-8", errors="ignore"))
        format_info = info.get("format", {})
        streams = info.get("streams", [])
        tags = format_info.get("tags", {})
        
        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        
        duration = float(format_info.get("duration", 0) or 0)
        size_bytes = int(format_info.get("size", 0) or file_path.stat().st_size)
        bit_rate = int(format_info.get("bit_rate", 0) or 0)
        
        result = {
            "filename": file_path.name,
            "size_bytes": size_bytes,
            "size_formatted": f"{size_bytes / (1024 * 1024):.2f} MB" if size_bytes >= 1024*1024 else f"{size_bytes / 1024:.1f} KB",
            "duration": duration,
            "duration_formatted": format_duration(duration),
            "format_name": format_info.get("format_long_name", format_info.get("format_name", "Unknown")),
            "bitrate_kbps": round(bit_rate / 1000) if bit_rate else 0,
            "has_video": len(video_streams) > 0,
            "has_audio": len(audio_streams) > 0,
            "tags": {
                "title": tags.get("title", tags.get("TITLE", "")),
                "artist": tags.get("artist", tags.get("ARTIST", "")),
                "album": tags.get("album", tags.get("ALBUM", "")),
                "genre": tags.get("genre", tags.get("GENRE", "")),
                "date": tags.get("date", tags.get("DATE", tags.get("year", "")))
            },
            "audio_streams": [],
            "video_streams": []
        }
        
        for a in audio_streams:
            result["audio_streams"].append({
                "codec_name": a.get("codec_name", "unknown"),
                "codec_long_name": a.get("codec_long_name", ""),
                "sample_rate": a.get("sample_rate", "44100"),
                "channels": a.get("channels", 2),
                "channel_layout": a.get("channel_layout", "stereo"),
                "bitrate_kbps": round(int(a.get("bit_rate", 0)) / 1000) if a.get("bit_rate") else 0
            })
            
        for v in video_streams:
            r_fps = v.get("r_frame_rate", "0/1")
            fps = 0.0
            if "/" in r_fps:
                num, den = r_fps.split("/")
                fps = round(float(num) / float(den), 2) if float(den) != 0 else 0.0
            result["video_streams"].append({
                "codec_name": v.get("codec_name", "unknown"),
                "resolution": f"{v.get('width', 0)}x{v.get('height', 0)}" if v.get("width") else "N/A",
                "fps": fps
            })
            
        return result
    except Exception as e:
        logger.error(f"Error probing media file {file_path}: {e}")
        return {"error": str(e), "filename": file_path.name}

# ==============================================================================
# 5MB Chunked Sliced Upload Engine (Cloudflare 100MB Limit Proof)
# ==============================================================================

class InitChunkUploadRequest(BaseModel):
    filename: str
    total_chunks: int
    total_size: int

@app.post("/api/upload/init")
async def init_chunk_upload(req: InitChunkUploadRequest):
    """Initializes a 5MB chunked upload session for files of any size."""
    upload_id = str(uuid.uuid4())[:12]
    safe_name = sanitize_filename(req.filename)
    
    upload_chunk_dir = CHUNK_DIR / upload_id
    upload_chunk_dir.mkdir(parents=True, exist_ok=True)
    
    ACTIVE_UPLOADS[upload_id] = {
        "upload_id": upload_id,
        "filename": safe_name,
        "total_chunks": req.total_chunks,
        "total_size": req.total_size,
        "received_chunks": set(),
        "chunk_dir": str(upload_chunk_dir),
        "created_at": time.time()
    }
    
    logger.info(f"Initialized chunked upload [{upload_id}] for {safe_name} ({req.total_chunks} chunks, {req.total_size} bytes)")
    return {"upload_id": upload_id, "chunk_size": 5 * 1024 * 1024}

@app.post("/api/upload/chunk")
async def upload_chunk(
    upload_id: str = Form(...),
    chunk_index: int = Form(...),
    chunk: UploadFile = File(...)
):
    """Receives a single 5MB chunk and saves it safely to the staging area."""
    session = ACTIVE_UPLOADS.get(upload_id)
    if not session:
        raise HTTPException(status_code=404, detail="Upload session not found or expired")
    
    chunk_dir = Path(session["chunk_dir"])
    chunk_file = chunk_dir / f"chunk_{chunk_index:06d}.part"
    
    try:
        with chunk_file.open("wb") as f:
            while data := await chunk.read(1024 * 512):
                f.write(data)
                
        session["received_chunks"].add(chunk_index)
        progress_pct = round((len(session["received_chunks"]) / session["total_chunks"]) * 100)
        return {
            "success": True,
            "upload_id": upload_id,
            "chunk_index": chunk_index,
            "received_count": len(session["received_chunks"]),
            "total_chunks": session["total_chunks"],
            "progress_percent": progress_pct
        }
    except Exception as e:
        logger.error(f"Error saving chunk {chunk_index} for {upload_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class CompleteChunkUploadRequest(BaseModel):
    upload_id: str

@app.post("/api/upload/complete")
async def complete_chunk_upload(req: CompleteChunkUploadRequest):
    """Stitches all 5MB chunks together into the final media file."""
    session = ACTIVE_UPLOADS.get(req.upload_id)
    if not session:
        raise HTTPException(status_code=404, detail="Upload session not found")
        
    chunk_dir = Path(session["chunk_dir"])
    total_chunks = session["total_chunks"]
    received_count = len(session["received_chunks"])
    
    if received_count < total_chunks:
        raise HTTPException(status_code=400, detail=f"Incomplete chunks: received {received_count}/{total_chunks}")
        
    safe_name = session["filename"]
    target_path = UPLOAD_DIR / safe_name
    
    # Avoid duplicate name collisions
    counter = 1
    stem = target_path.stem
    suffix = target_path.suffix
    while target_path.exists():
        safe_name = f"{stem}_{counter}{suffix}"
        target_path = UPLOAD_DIR / safe_name
        counter += 1
        
    logger.info(f"Stitching {total_chunks} chunks for [{req.upload_id}] -> {target_path.name}...")
    
    try:
        with target_path.open("wb") as outfile:
            for idx in range(total_chunks):
                chunk_file = chunk_dir / f"chunk_{idx:06d}.part"
                if not chunk_file.exists():
                    raise HTTPException(status_code=500, detail=f"Missing chunk index {idx}")
                with chunk_file.open("rb") as infile:
                    shutil.copyfileobj(infile, outfile)
                    
        # Clean up chunks
        shutil.rmtree(chunk_dir, ignore_errors=True)
        del ACTIVE_UPLOADS[req.upload_id]
        
        probe = await probe_media_file(target_path)
        logger.info(f"Successfully assembled: {target_path.name} ({target_path.stat().st_size} bytes)")
        return {
            "success": True,
            "filename": safe_name,
            "url": f"/api/media/uploads/{safe_name}",
            "metadata": probe
        }
    except Exception as e:
        logger.exception(f"Failed to assemble chunks for [{req.upload_id}]")
        raise HTTPException(status_code=500, detail=f"Failed to stitch file: {str(e)}")

# Fallback direct upload for small files
@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Receives drag & drop uploaded media files directly."""
    uploaded = []
    for file in files:
        safe_name = sanitize_filename(file.filename or f"audio_{int(time.time())}.mp3")
        target_path = UPLOAD_DIR / safe_name
        
        counter = 1
        stem = target_path.stem
        suffix = target_path.suffix
        while target_path.exists():
            safe_name = f"{stem}_{counter}{suffix}"
            target_path = UPLOAD_DIR / safe_name
            counter += 1
            
        with target_path.open("wb") as buffer:
            while chunk := await file.read(1024 * 1024 * 4):
                buffer.write(chunk)
                
        probe_data = await probe_media_file(target_path)
        uploaded.append({
            "filename": safe_name,
            "url": f"/api/media/uploads/{safe_name}",
            "metadata": probe_data
        })
    return {"uploaded": uploaded, "count": len(uploaded)}

# ==============================================================================
# Task Engine & Job Runner
# ==============================================================================

def create_job(task_type: str, title: str, meta: Optional[Dict[str, Any]] = None) -> str:
    job_id = str(uuid.uuid4())[:8]
    JOBS[job_id] = {
        "id": job_id,
        "type": task_type,
        "title": title,
        "status": "queued",
        "progress": 0,
        "speed": "0x",
        "logs": [],
        "output_file": None,
        "output_url": None,
        "error": None,
        "created_at": time.time(),
        "updated_at": time.time(),
        "meta": meta or {}
    }
    return job_id

async def run_ffmpeg_command(job_id: str, cmd: List[str], output_filename: str, total_duration: float = 0.0):
    job = JOBS.get(job_id)
    if not job:
        return

    job["status"] = "running"
    job["updated_at"] = time.time()
    logger.info(f"[{job_id}] Executing FFmpeg: {' '.join(cmd)}")
    
    final_cmd = ["ffmpeg", "-hide_banner", "-nostats", "-progress", "pipe:1"] + cmd
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *final_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        PROCESSES[job_id] = proc
        
        out_time_re = re.compile(r"out_time_us=(\d+)")
        speed_re = re.compile(r"speed=\s*([\d.]+)x")
        
        while True:
            line_bytes = await proc.stdout.readline()
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="ignore").strip()
            
            if "out_time_us=" in line:
                match = out_time_re.search(line)
                if match and total_duration > 0:
                    curr_us = int(match.group(1))
                    curr_sec = curr_us / 1000000.0
                    prog = min(99, int((curr_sec / total_duration) * 100))
                    job["progress"] = max(job["progress"], prog)
            elif "speed=" in line:
                match = speed_re.search(line)
                if match:
                    job["speed"] = f"{match.group(1)}x"
            elif "progress=end" in line:
                job["progress"] = 100
                
            job["updated_at"] = time.time()
            
        stderr_bytes = await proc.stderr.read()
        stderr_text = stderr_bytes.decode("utf-8", errors="ignore")
        return_code = await proc.wait()
        
        if job_id in PROCESSES:
            del PROCESSES[job_id]
            
        if return_code == 0:
            out_path = OUTPUT_DIR / output_filename
            if out_path.exists():
                job["status"] = "completed"
                job["progress"] = 100
                job["output_file"] = output_filename
                job["output_url"] = f"/api/media/outputs/{output_filename}"
                job["logs"].append("Audio/Media processing finished successfully.")
                logger.info(f"[{job_id}] Rendered output: {output_filename}")
            else:
                job["status"] = "failed"
                job["error"] = "Output file was not found."
                job["logs"].append(stderr_text[-1000:])
        else:
            if job["status"] != "cancelled":
                job["status"] = "failed"
                job["error"] = f"FFmpeg error ({return_code})"
                job["logs"].append(stderr_text[-2000:])
                logger.error(f"[{job_id}] FFmpeg failed: {stderr_text[-500:]}")
    except Exception as e:
        logger.exception(f"[{job_id}] Exception during FFmpeg execution")
        job["status"] = "failed"
        job["error"] = str(e)
    finally:
        job["updated_at"] = time.time()

# ==============================================================================
# System Info & File Management Endpoints
# ==============================================================================

@app.get("/api/system-info")
async def get_system_info():
    ffmpeg_ver = "Unknown"
    ytdlp_ver = "Unknown"
    try:
        proc = await asyncio.create_subprocess_exec("ffmpeg", "-version", stdout=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        if stdout:
            ffmpeg_ver = stdout.decode().splitlines()[0].replace("ffmpeg version ", "").split(" ")[0]
    except Exception:
        pass

    try:
        proc = await asyncio.create_subprocess_exec("yt-dlp", "--version", stdout=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        if stdout:
            ytdlp_ver = stdout.decode().strip()
    except Exception:
        pass

    total_disk, used_disk, free_disk = shutil.disk_usage(DATA_DIR)
    
    return {
        "status": "online",
        "ffmpeg_version": ffmpeg_ver,
        "ytdlp_version": ytdlp_ver,
        "cpu_count": os.cpu_count() or 1,
        "disk_free_gb": round(free_disk / (1024**3), 2),
        "disk_total_gb": round(total_disk / (1024**3), 2),
        "active_jobs": len([j for j in JOBS.values() if j["status"] in ("running", "queued")]),
        "total_jobs": len(JOBS)
    }

class DownloadUrlRequest(BaseModel):
    url: str
    preset: str = "audio_mp3_320" # audio_mp3_320, audio_flac, audio_wav, audio_m4a, audio_opus, best_video

@app.post("/api/download-url")
async def download_url(req: DownloadUrlRequest, background_tasks: BackgroundTasks):
    """Downloads audio/video directly onto the Ubuntu runner (bypassing browser upload limits)."""
    parsed = urlparse(req.url.strip())
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Invalid URL. Only HTTP and HTTPS are supported.")
    
    job_id = create_job("download", f"Fetch: {req.url[:40]}...", {"url": req.url, "preset": req.preset})
    
    async def _execute_download():
        job = JOBS[job_id]
        job["status"] = "running"
        job["progress"] = 5
        job["logs"].append(f"Fetching audio stream via yt-dlp: {req.url}")
        
        out_template = str(UPLOAD_DIR / "%(title).90s_%(id)s.%(ext)s")
        cmd = ["yt-dlp", "--no-warnings", "--newline", "--progress", "--no-playlist"]
        
        if req.preset == "audio_mp3_320":
            cmd.extend(["-x", "--audio-format", "mp3", "--audio-quality", "0"])
        elif req.preset == "audio_flac":
            cmd.extend(["-x", "--audio-format", "flac"])
        elif req.preset == "audio_wav":
            cmd.extend(["-x", "--audio-format", "wav"])
        elif req.preset == "audio_m4a":
            cmd.extend(["-x", "--audio-format", "m4a", "--audio-quality", "0"])
        elif req.preset == "audio_opus":
            cmd.extend(["-x", "--audio-format", "opus", "--audio-quality", "0"])
        elif req.preset == "best_video":
            cmd.extend(["-f", "bestvideo+bestaudio/best", "--merge-output-format", "mp4"])
        else:
            cmd.extend(["-x", "--audio-format", "mp3", "--audio-quality", "0"])
            
        cmd.extend(["-o", out_template, req.url.strip()])
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            PROCESSES[job_id] = proc
            
            percent_re = re.compile(r"\[download\]\s+([\d.]+)%")
            dest_re = re.compile(r"\[(?:download|Merger|ExtractAudio)\] Destination:\s+(.+)")
            downloaded_file = None
            
            while True:
                line_bytes = await proc.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="ignore").strip()
                
                if "[download]" in line:
                    match_pct = percent_re.search(line)
                    if match_pct:
                        job["progress"] = min(98, max(5, int(float(match_pct.group(1)))))
                elif "Destination:" in line:
                    match_dest = dest_re.search(line)
                    if match_dest:
                        downloaded_file = match_dest.group(1).strip()
                        
                if line and not line.startswith("[download] "):
                    job["logs"].append(line[-200:])
                job["updated_at"] = time.time()
                
            ret = await proc.wait()
            if job_id in PROCESSES:
                del PROCESSES[job_id]
                
            if ret == 0:
                all_uploads = sorted(UPLOAD_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
                target_file = Path(downloaded_file) if (downloaded_file and Path(downloaded_file).exists()) else (all_uploads[0] if all_uploads else None)
                if target_file and target_file.exists():
                    job["status"] = "completed"
                    job["progress"] = 100
                    job["output_file"] = target_file.name
                    job["output_url"] = f"/api/media/uploads/{target_file.name}"
                    job["logs"].append(f"Downloaded successfully: {target_file.name}")
                else:
                    job["status"] = "failed"
                    job["error"] = "Download completed but file could not be located."
            else:
                job["status"] = "failed"
                job["error"] = f"yt-dlp failed (code {ret})"
        except Exception as e:
            job["status"] = "failed"
            job["error"] = str(e)
        finally:
            job["updated_at"] = time.time()

    background_tasks.add_task(_execute_download)
    return {"job_id": job_id, "status": "queued"}

@app.get("/api/files")
async def list_files():
    uploads_data = []
    outputs_data = []
    
    for f in sorted(UPLOAD_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file():
            probe = await probe_media_file(f)
            uploads_data.append({
                "filename": f.name,
                "category": "uploads",
                "size_bytes": f.stat().st_size,
                "size_formatted": probe.get("size_formatted", "0 KB"),
                "mtime": f.stat().st_mtime,
                "url": f"/api/media/uploads/{f.name}",
                "metadata": probe
            })
            
    for f in sorted(OUTPUT_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file():
            probe = await probe_media_file(f)
            outputs_data.append({
                "filename": f.name,
                "category": "outputs",
                "size_bytes": f.stat().st_size,
                "size_formatted": probe.get("size_formatted", "0 KB"),
                "mtime": f.stat().st_mtime,
                "url": f"/api/media/outputs/{f.name}",
                "metadata": probe
            })
            
    return {"uploads": uploads_data, "outputs": outputs_data}

@app.delete("/api/files/{category}/{filename}")
async def delete_file(category: str, filename: str):
    path = get_safe_path(category, filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    try:
        path.unlink()
        return {"success": True, "message": f"Deleted {filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/files/clear")
async def clear_files(category: str = Query(..., regex="^(uploads|outputs|all)$")):
    deleted = 0
    dirs = []
    if category in ("uploads", "all"):
        dirs.append(UPLOAD_DIR)
    if category in ("outputs", "all"):
        dirs.append(OUTPUT_DIR)
        
    for d in dirs:
        for f in d.glob("*"):
            if f.is_file():
                try:
                    f.unlink()
                    deleted += 1
                except Exception:
                    pass
    return {"success": True, "deleted_count": deleted}

# ==============================================================================
# Dedicated Audio Processing Endpoints
# ==============================================================================

class AudioJoinRequest(BaseModel):
    filenames: List[str]
    category: str = "uploads"
    output_format: str = "mp3" # mp3, wav, flac, aac, m4a, ogg, opus
    bitrate_kbps: int = 320
    crossfade_sec: float = 0.0 # 0 to 5 seconds crossfade

@app.post("/api/ops/audio-join")
async def join_audio_tracks(req: AudioJoinRequest, background_tasks: BackgroundTasks):
    """Joins multiple audio tracks with optional smooth crossfading."""
    if len(req.filenames) < 2:
        raise HTTPException(status_code=400, detail="At least 2 audio tracks are required to join.")
        
    file_paths = []
    total_duration = 0.0
    for fn in req.filenames:
        p = get_safe_path(req.category, fn)
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"Track not found: {fn}")
        file_paths.append(p)
        probe = await probe_media_file(p)
        total_duration += probe.get("duration", 0.0)
        
    out_name = f"joined_{int(time.time())}.{req.output_format.lower()}"
    out_path = OUTPUT_DIR / out_name
    job_id = create_job("audio_join", f"Join {len(req.filenames)} tracks -> {out_name}", {"tracks": req.filenames})
    
    async def _execute_join():
        cmd = ["-y"]
        for p in file_paths:
            cmd.extend(["-i", str(p)])
            
        if req.crossfade_sec > 0 and len(file_paths) == 2:
            # 2-track acrossfade filter
            cmd.extend([
                "-filter_complex", f"acrossfade=d={req.crossfade_sec}:c1=tri:c2=tri"
            ])
        else:
            filter_parts = "".join([f"[{i}:a]" for i in range(len(file_paths))])
            filter_parts += f"concat=n={len(file_paths)}:v=0:a=1[aout]"
            cmd.extend(["-filter_complex", filter_parts, "-map", "[aout]"])
            
        # Audio format codecs
        fmt = req.output_format.lower()
        if fmt == "mp3":
            cmd.extend(["-c:a", "libmp3lame", "-b:a", f"{req.bitrate_kbps}k"])
        elif fmt == "wav":
            cmd.extend(["-c:a", "pcm_s16le"])
        elif fmt == "flac":
            cmd.extend(["-c:a", "flac"])
        elif fmt in ("aac", "m4a"):
            cmd.extend(["-c:a", "aac", "-b:a", f"{req.bitrate_kbps}k"])
        elif fmt in ("ogg", "opus"):
            cmd.extend(["-c:a", "libopus", "-b:a", f"{req.bitrate_kbps}k"])
            
        cmd.append(str(out_path))
        await run_ffmpeg_command(job_id, cmd, out_name, total_duration)

    background_tasks.add_task(_execute_join)
    return {"job_id": job_id, "status": "queued", "output_filename": out_name}

class AudioConvertRequest(BaseModel):
    filename: str
    category: str = "uploads"
    output_format: str # mp3, wav, flac, aac, m4a, ogg, opus, aiff
    bitrate_kbps: int = 320 # 64 to 320
    sample_rate: str = "44100" # 44100, 48000, 96000, keep
    channels: str = "keep" # stereo, mono, keep

@app.post("/api/ops/audio-convert")
async def convert_audio(req: AudioConvertRequest, background_tasks: BackgroundTasks):
    """Converts audio format, bitrates, sample rates (44.1k/48k/96k), and stereo/mono."""
    in_path = get_safe_path(req.category, req.filename)
    if not in_path.exists():
        raise HTTPException(status_code=404, detail="Input file not found")
        
    probe = await probe_media_file(in_path)
    duration = probe.get("duration", 0.0)
    
    stem = in_path.stem
    fmt = req.output_format.lower()
    out_name = f"{stem}_converted_{int(time.time())}.{fmt}"
    out_path = OUTPUT_DIR / out_name
    
    job_id = create_job("audio_convert", f"Convert {req.filename} to {fmt.upper()} ({req.bitrate_kbps}k)")
    
    async def _execute_convert():
        cmd = ["-y", "-i", str(in_path), "-vn"]
        
        if req.sample_rate != "keep":
            cmd.extend(["-ar", str(req.sample_rate)])
        if req.channels == "mono":
            cmd.extend(["-ac", "1"])
        elif req.channels == "stereo":
            cmd.extend(["-ac", "2"])
            
        if fmt == "mp3":
            cmd.extend(["-c:a", "libmp3lame", "-b:a", f"{req.bitrate_kbps}k"])
        elif fmt == "wav":
            cmd.extend(["-c:a", "pcm_s16le"])
        elif fmt == "flac":
            cmd.extend(["-c:a", "flac"])
        elif fmt in ("aac", "m4a"):
            cmd.extend(["-c:a", "aac", "-b:a", f"{req.bitrate_kbps}k"])
        elif fmt in ("ogg", "opus"):
            cmd.extend(["-c:a", "libopus", "-b:a", f"{req.bitrate_kbps}k"])
        elif fmt == "aiff":
            cmd.extend(["-c:a", "pcm_s16be"])
            
        cmd.append(str(out_path))
        await run_ffmpeg_command(job_id, cmd, out_name, duration)

    background_tasks.add_task(_execute_convert)
    return {"job_id": job_id, "status": "queued", "output_filename": out_name}

class AudioTrimRequest(BaseModel):
    filename: str
    category: str = "uploads"
    start_time: str # "00:01:15" or seconds
    end_time: Optional[str] = None
    duration: Optional[str] = None
    fade_in_sec: float = 0.0 # 0 to 5 seconds
    fade_out_sec: float = 0.0 # 0 to 5 seconds
    output_format: str = "mp3"

@app.post("/api/ops/audio-trim")
async def trim_audio(req: AudioTrimRequest, background_tasks: BackgroundTasks):
    """Trims audio clips with millisecond precision and fade-in/fade-out curves."""
    in_path = get_safe_path(req.category, req.filename)
    if not in_path.exists():
        raise HTTPException(status_code=404, detail="Input file not found")
        
    start_sec = parse_time_str(req.start_time)
    end_sec = parse_time_str(req.end_time) if req.end_time else 0.0
    dur_sec = parse_time_str(req.duration) if req.duration else 0.0
    
    if end_sec > start_sec:
        cut_duration = end_sec - start_sec
    elif dur_sec > 0:
        cut_duration = dur_sec
    else:
        raise HTTPException(status_code=400, detail="Invalid cut duration")
        
    stem = in_path.stem
    fmt = req.output_format.lower()
    out_name = f"{stem}_trimmed_{int(time.time())}.{fmt}"
    out_path = OUTPUT_DIR / out_name
    
    job_id = create_job("audio_trim", f"Trim {req.filename} ({format_duration(start_sec)} - {format_duration(start_sec + cut_duration)})")
    
    async def _execute_trim():
        cmd = ["-y", "-ss", str(start_sec), "-i", str(in_path), "-t", str(cut_duration), "-vn"]
        
        af_filters = []
        if req.fade_in_sec > 0:
            af_filters.append(f"afade=t=in:st=0:d={req.fade_in_sec}")
        if req.fade_out_sec > 0:
            fade_start = max(0, cut_duration - req.fade_out_sec)
            af_filters.append(f"afade=t=out:st={fade_start}:d={req.fade_out_sec}")
            
        if af_filters:
            cmd.extend(["-af", ",".join(af_filters)])
            
        if fmt == "mp3":
            cmd.extend(["-c:a", "libmp3lame", "-b:a", "320k"])
        elif fmt == "wav":
            cmd.extend(["-c:a", "pcm_s16le"])
        elif fmt == "flac":
            cmd.extend(["-c:a", "flac"])
        else:
            cmd.extend(["-c:a", "aac", "-b:a", "256k"])
            
        cmd.append(str(out_path))
        await run_ffmpeg_command(job_id, cmd, out_name, cut_duration)

    background_tasks.add_task(_execute_trim)
    return {"job_id": job_id, "status": "queued", "output_filename": out_name}

class AudioLoudnessRequest(BaseModel):
    filename: str
    category: str = "uploads"
    mode: str = "ebur128" # ebur128 (standard Spotify/podcast normalization) or boost
    volume_multiplier: float = 1.5 # 0.1 to 3.0 for boost mode
    target_lufs: float = -16.0 # -14 for Spotify/YouTube, -16 for Podcasts

@app.post("/api/ops/audio-loudness")
async def audio_loudness(req: AudioLoudnessRequest, background_tasks: BackgroundTasks):
    """Boosts volume up to 300% or applies broadcast EBU R128 Loudness Normalization."""
    in_path = get_safe_path(req.category, req.filename)
    if not in_path.exists():
        raise HTTPException(status_code=404, detail="Input file not found")
        
    probe = await probe_media_file(in_path)
    duration = probe.get("duration", 0.0)
    
    stem = in_path.stem
    suffix = in_path.suffix.lstrip('.') or "mp3"
    out_name = f"{stem}_loudness_{int(time.time())}.{suffix}"
    out_path = OUTPUT_DIR / out_name
    
    job_id = create_job("audio_loudness", f"Loudness Normalization ({req.mode.upper()}) on {req.filename}")
    
    async def _execute_loudness():
        cmd = ["-y", "-i", str(in_path), "-vn"]
        
        if req.mode == "ebur128":
            cmd.extend(["-af", f"loudnorm=I={req.target_lufs}:TP=-1.5:LRA=11"])
        else: # boost
            cmd.extend(["-af", f"volume={req.volume_multiplier}"])
            
        cmd.extend(["-c:a", "libmp3lame" if suffix == "mp3" else "aac", "-b:a", "320k", str(out_path)])
        await run_ffmpeg_command(job_id, cmd, out_name, duration)

    background_tasks.add_task(_execute_loudness)
    return {"job_id": job_id, "status": "queued", "output_filename": out_name}

class AudioPitchTempoRequest(BaseModel):
    filename: str
    category: str = "uploads"
    tempo: float = 1.0 # 0.5 to 2.0 (Speed without changing pitch)
    pitch_semitones: int = 0 # -12 to +12 semitones
    reverse: bool = False

@app.post("/api/ops/audio-pitch-tempo")
async def audio_pitch_tempo(req: AudioPitchTempoRequest, background_tasks: BackgroundTasks):
    """Changes tempo without pitch shift, or changes musical pitch (-12 to +12 semitones)."""
    in_path = get_safe_path(req.category, req.filename)
    if not in_path.exists():
        raise HTTPException(status_code=404, detail="Input file not found")
        
    probe = await probe_media_file(in_path)
    duration = probe.get("duration", 0.0)
    
    stem = in_path.stem
    suffix = in_path.suffix.lstrip('.') or "mp3"
    out_name = f"{stem}_fx_{int(time.time())}.{suffix}"
    out_path = OUTPUT_DIR / out_name
    
    job_id = create_job("audio_pitch_tempo", f"Pitch ({req.pitch_semitones}st) & Tempo ({req.tempo}x) on {req.filename}")
    
    async def _execute_pitch_tempo():
        cmd = ["-y", "-i", str(in_path), "-vn"]
        af_filters = []
        
        # Pitch shifting via asetrate + aresample + atempo
        if req.pitch_semitones != 0:
            sample_rate = 44100
            for a in probe.get("audio_streams", []):
                if a.get("sample_rate"):
                    sample_rate = int(a["sample_rate"])
                    break
            # pitch factor = 2^(semitones / 12)
            pitch_factor = 2.0 ** (req.pitch_semitones / 12.0)
            new_rate = int(sample_rate * pitch_factor)
            comp_tempo = 1.0 / pitch_factor
            af_filters.append(f"asetrate={new_rate},aresample={sample_rate},atempo={comp_tempo:.4f}")
            
        # Tempo shifting
        if req.tempo != 1.0 and 0.5 <= req.tempo <= 2.0:
            af_filters.append(f"atempo={req.tempo}")
            
        if req.reverse:
            af_filters.append("areverse")
            
        if af_filters:
            cmd.extend(["-af", ",".join(af_filters)])
            
        cmd.extend(["-c:a", "libmp3lame" if suffix == "mp3" else "aac", "-b:a", "320k", str(out_path)])
        calc_dur = duration / req.tempo if req.tempo > 0 else duration
        await run_ffmpeg_command(job_id, cmd, out_name, calc_dur)

    background_tasks.add_task(_execute_pitch_tempo)
    return {"job_id": job_id, "status": "queued", "output_filename": out_name}

class AudioEqRequest(BaseModel):
    filename: str
    category: str = "uploads"
    preset: str # bass_boost, treble_boost, vocal_boost, highpass_rumble, lowpass_hiss

@app.post("/api/ops/audio-eq")
async def audio_equalizer(req: AudioEqRequest, background_tasks: BackgroundTasks):
    """Applies equalizer and noise filtering presets."""
    in_path = get_safe_path(req.category, req.filename)
    if not in_path.exists():
        raise HTTPException(status_code=404, detail="Input file not found")
        
    probe = await probe_media_file(in_path)
    duration = probe.get("duration", 0.0)
    
    stem = in_path.stem
    suffix = in_path.suffix.lstrip('.') or "mp3"
    out_name = f"{stem}_eq_{req.preset}_{int(time.time())}.{suffix}"
    out_path = OUTPUT_DIR / out_name
    
    job_id = create_job("audio_eq", f"Apply EQ [{req.preset.replace('_', ' ').title()}] to {req.filename}")
    
    presets = {
        "bass_boost": "bass=g=9:f=110:w=0.6",
        "treble_boost": "treble=g=8:f=7500:w=0.6",
        "vocal_boost": "equalizer=f=1200:t=q:w=1.2:g=7",
        "highpass_rumble": "highpass=f=80",
        "lowpass_hiss": "lowpass=f=9000"
    }
    af = presets.get(req.preset, "bass=g=6:f=100")
    
    async def _execute_eq():
        cmd = [
            "-y", "-i", str(in_path),
            "-vn",
            "-af", af,
            "-c:a", "libmp3lame" if suffix == "mp3" else "aac",
            "-b:a", "320k",
            str(out_path)
        ]
        await run_ffmpeg_command(job_id, cmd, out_name, duration)

    background_tasks.add_task(_execute_eq)
    return {"job_id": job_id, "status": "queued", "output_filename": out_name}

class AudioTagRequest(BaseModel):
    filename: str
    category: str = "uploads"
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    genre: Optional[str] = None
    year: Optional[str] = None

@app.post("/api/ops/audio-tag")
async def write_audio_tags(req: AudioTagRequest):
    """Writes ID3 tags (Title, Artist, Album, Genre, Year) to an audio file."""
    in_path = get_safe_path(req.category, req.filename)
    if not in_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
        
    stem = in_path.stem
    suffix = in_path.suffix.lstrip('.') or "mp3"
    out_name = f"{stem}_tagged_{int(time.time())}.{suffix}"
    out_path = OUTPUT_DIR / out_name
    
    cmd = ["ffmpeg", "-y", "-i", str(in_path), "-c", "copy"]
    if req.title: cmd.extend(["-metadata", f"title={req.title}"])
    if req.artist: cmd.extend(["-metadata", f"artist={req.artist}"])
    if req.album: cmd.extend(["-metadata", f"album={req.album}"])
    if req.genre: cmd.extend(["-metadata", f"genre={req.genre}"])
    if req.year: cmd.extend(["-metadata", f"date={req.year}"])
    cmd.append(str(out_path))
    
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()
    
    if proc.returncode != 0 or not out_path.exists():
        raise HTTPException(status_code=500, detail=f"Tagging failed: {stderr.decode(errors='ignore')}")
        
    probe = await probe_media_file(out_path)
    return {"success": True, "output_filename": out_name, "metadata": probe}

# ==============================================================================
# Job Polling & File Streaming
# ==============================================================================

@app.get("/api/jobs")
async def list_jobs():
    sorted_jobs = sorted(JOBS.values(), key=lambda j: j["created_at"], reverse=True)
    return {"jobs": sorted_jobs[:50]}

@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job_id in PROCESSES:
        try:
            PROCESSES[job_id].terminate()
            job["status"] = "cancelled"
            job["logs"].append("Process cancelled by user.")
        except Exception as e:
            logger.error(f"Error cancelling {job_id}: {e}")
    return {"success": True, "job_id": job_id}

@app.get("/api/media/{category}/{filename}")
async def stream_media(category: str, filename: str, request: Request):
    """Streams audio/video with Range header support for seeking."""
    path = get_safe_path(category, filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Media file not found")
        
    file_size = path.stat().st_size
    range_header = request.headers.get("Range")
    
    suffix = path.suffix.lower()
    content_types = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".flac": "audio/flac",
        ".aac": "audio/aac",
        ".m4a": "audio/mp4",
        ".ogg": "audio/ogg",
        ".opus": "audio/opus",
        ".aiff": "audio/x-aiff",
        ".mp4": "video/mp4",
        ".mkv": "video/x-matroska",
        ".webm": "video/webm"
    }
    content_type = content_types.get(suffix, "application/octet-stream")
    
    if range_header:
        try:
            byte1, byte2 = 0, None
            m = re.search(r"bytes=(\d+)-(\d*)", range_header)
            if m:
                g = m.groups()
                byte1 = int(g[0])
                if g[1]:
                    byte2 = int(g[1])
            if byte2 is None or byte2 >= file_size:
                byte2 = file_size - 1
            length = byte2 - byte1 + 1
            
            def iterfile(start_pos, chunk_len):
                with path.open("rb") as f:
                    f.seek(start_pos)
                    remaining = chunk_len
                    while remaining > 0:
                        read_bytes = min(1024 * 1024, remaining)
                        data = f.read(read_bytes)
                        if not data:
                            break
                        remaining -= len(data)
                        yield data
                        
            headers = {
                "Content-Range": f"bytes {byte1}-{byte2}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
                "Content-Type": content_type,
            }
            return StreamingResponse(iterfile(byte1, length), status_code=206, headers=headers)
        except Exception as e:
            logger.error(f"Error streaming Range: {e}")
            
    return FileResponse(path, media_type=content_type)

@app.get("/api/download/{category}/{filename}")
async def download_file(category: str, filename: str):
    path = get_safe_path(category, filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=filename, media_type="application/octet-stream")

@app.get("/api/download-all-zip")
async def download_all_zip(category: str = Query("outputs", regex="^(uploads|outputs)$")):
    target_dir = UPLOAD_DIR if category == "uploads" else OUTPUT_DIR
    files = list(target_dir.glob("*"))
    if not files:
        raise HTTPException(status_code=404, detail="No files to zip")
        
    zip_path = TEMP_DIR / f"{category}_audio_bundle_{int(time.time())}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            if f.is_file():
                zf.write(f, arcname=f.name)
                
    return FileResponse(zip_path, filename=f"omniaudio_{category}.zip", media_type="application/zip")

# ==============================================================================
# Mount Static Frontend
# ==============================================================================

STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 7860))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"🚀 Starting OmniMedia & Audio Studio on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
