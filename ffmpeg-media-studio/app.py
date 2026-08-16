#!/usr/bin/env python3
"""
OmniMedia Studio - FFmpeg & yt-dlp All-In-One Media Suite
A high-performance asynchronous media processing web application for Ubuntu.
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
logger = logging.getLogger("omnimedia-studio")

# Environment & Directory Setup
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("OMNIMEDIA_DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
TEMP_DIR = DATA_DIR / "temp"

for directory in [UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Application state for job tracking
JOBS: Dict[str, Dict[str, Any]] = {}
PROCESSES: Dict[str, asyncio.subprocess.Process] = {}

app = FastAPI(
    title="OmniMedia Studio",
    description="FFmpeg & yt-dlp All-In-One Media Processing Suite",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Middleware for Security Headers
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
# Helper Functions & Utilities
# ==============================================================================

def sanitize_filename(filename: str) -> str:
    """Sanitizes filename and prevents directory traversal."""
    base = os.path.basename(filename)
    # Remove potentially dangerous characters, keep alphanumeric, dots, dashes, underscores
    sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', base)
    if not sanitized or sanitized.startswith('.'):
        sanitized = f"file_{int(time.time())}_{sanitized.lstrip('.')}"
    return sanitized

def get_safe_path(category: str, filename: str) -> Path:
    """Resolves and validates safe path within category directories."""
    clean_name = sanitize_filename(filename)
    if category == "uploads":
        target_dir = UPLOAD_DIR
    elif category == "outputs":
        target_dir = OUTPUT_DIR
    else:
        raise HTTPException(status_code=400, detail="Invalid file category")
    
    target_path = (target_dir / clean_name).resolve()
    # Check directory boundary
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
    """Runs ffprobe on a file to extract detailed metadata."""
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
        
        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        
        duration = float(format_info.get("duration", 0) or 0)
        size_bytes = int(format_info.get("size", 0) or file_path.stat().st_size)
        bit_rate = int(format_info.get("bit_rate", 0) or 0)
        
        result = {
            "filename": file_path.name,
            "size_bytes": size_bytes,
            "size_formatted": f"{size_bytes / (1024 * 1024):.2f} MB",
            "duration": duration,
            "duration_formatted": format_duration(duration),
            "format_name": format_info.get("format_long_name", format_info.get("format_name", "Unknown")),
            "bitrate_kbps": round(bit_rate / 1000) if bit_rate else 0,
            "has_video": len(video_streams) > 0,
            "has_audio": len(audio_streams) > 0,
            "video_streams": [],
            "audio_streams": []
        }
        
        for v in video_streams:
            r_frame_rate = v.get("r_frame_rate", "0/1")
            fps = 0.0
            if "/" in r_frame_rate:
                num, den = r_frame_rate.split("/")
                fps = round(float(num) / float(den), 2) if float(den) != 0 else 0.0
            
            result["video_streams"].append({
                "codec_name": v.get("codec_name", "unknown"),
                "codec_long_name": v.get("codec_long_name", ""),
                "width": v.get("width", 0),
                "height": v.get("height", 0),
                "resolution": f"{v.get('width', 0)}x{v.get('height', 0)}" if v.get("width") else "N/A",
                "fps": fps,
                "aspect_ratio": v.get("display_aspect_ratio", v.get("sample_aspect_ratio", "N/A")),
                "pix_fmt": v.get("pix_fmt", "")
            })
            
        for a in audio_streams:
            result["audio_streams"].append({
                "codec_name": a.get("codec_name", "unknown"),
                "codec_long_name": a.get("codec_long_name", ""),
                "sample_rate": a.get("sample_rate", "0"),
                "channels": a.get("channels", 0),
                "channel_layout": a.get("channel_layout", "stereo"),
                "bitrate_kbps": round(int(a.get("bit_rate", 0)) / 1000) if a.get("bit_rate") else 0
            })
            
        return result
    except Exception as e:
        logger.error(f"Error probing media file {file_path}: {e}")
        return {"error": str(e), "filename": file_path.name}

# ==============================================================================
# Asynchronous Task Engine & Job Runner
# ==============================================================================

def create_job(task_type: str, title: str, meta: Optional[Dict[str, Any]] = None) -> str:
    """Creates a new tracking job record."""
    job_id = str(uuid.uuid4())[:8]
    JOBS[job_id] = {
        "id": job_id,
        "type": task_type,
        "title": title,
        "status": "queued", # queued, running, completed, failed, cancelled
        "progress": 0,
        "eta": "Calculating...",
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
    """Executes FFmpeg with real-time stderr progress parsing."""
    job = JOBS.get(job_id)
    if not job:
        return

    job["status"] = "running"
    job["updated_at"] = time.time()
    logger.info(f"[{job_id}] Starting FFmpeg task: {' '.join(cmd)}")
    
    # Prepend progress flags to capture detailed stdout/stderr stats
    final_cmd = ["ffmpeg", "-hide_banner", "-nostats", "-progress", "pipe:1"] + cmd
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *final_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        PROCESSES[job_id] = proc
        
        # Read progress output in real-time
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
                job["logs"].append("FFmpeg process finished successfully.")
                logger.info(f"[{job_id}] Completed successfully: {output_filename}")
            else:
                job["status"] = "failed"
                job["error"] = "Output file was not created."
                job["logs"].append(stderr_text[-1000:])
        else:
            if job["status"] != "cancelled":
                job["status"] = "failed"
                job["error"] = f"FFmpeg failed with code {return_code}"
                job["logs"].append(stderr_text[-2000:])
                logger.error(f"[{job_id}] FFmpeg failed: {stderr_text[-500:]}")
                
    except asyncio.CancelledError:
        job["status"] = "cancelled"
        job["error"] = "Task was cancelled by user"
    except Exception as e:
        logger.exception(f"[{job_id}] Exception during FFmpeg execution")
        job["status"] = "failed"
        job["error"] = str(e)
    finally:
        job["updated_at"] = time.time()

# ==============================================================================
# REST API Endpoints
# ==============================================================================

@app.get("/api/system-info")
async def get_system_info():
    """Returns system specs, FFmpeg version, and yt-dlp status."""
    ffmpeg_ver = "Unknown"
    ytdlp_ver = "Unknown"
    
    try:
        proc = await asyncio.create_subprocess_exec("ffmpeg", "-version", stdout=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        if stdout:
            first_line = stdout.decode().splitlines()[0]
            ffmpeg_ver = first_line.replace("ffmpeg version ", "").split(" ")[0]
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

@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Receives drag & drop uploaded media files."""
    uploaded = []
    errors = []
    
    for file in files:
        safe_name = sanitize_filename(file.filename or f"upload_{int(time.time())}.tmp")
        target_path = UPLOAD_DIR / safe_name
        
        # Avoid overwriting existing file with exact same name
        counter = 1
        stem = target_path.stem
        suffix = target_path.suffix
        while target_path.exists():
            safe_name = f"{stem}_{counter}{suffix}"
            target_path = UPLOAD_DIR / safe_name
            counter += 1
            
        try:
            with target_path.open("wb") as buffer:
                while chunk := await file.read(1024 * 1024 * 4): # 4MB chunks
                    buffer.write(chunk)
            
            probe_data = await probe_media_file(target_path)
            uploaded.append({
                "filename": safe_name,
                "url": f"/api/media/uploads/{safe_name}",
                "metadata": probe_data
            })
        except Exception as e:
            logger.error(f"Upload error for {file.filename}: {e}")
            errors.append({"filename": file.filename, "error": str(e)})
            
    return {"uploaded": uploaded, "errors": errors, "count": len(uploaded)}

class DownloadUrlRequest(BaseModel):
    url: str
    preset: str = "best" # best, 1080p, 720p, 480p, audio_mp3, audio_m4a, audio_wav
    custom_filename: Optional[str] = None

@app.post("/api/download-url")
async def download_url(req: DownloadUrlRequest, background_tasks: BackgroundTasks):
    """Downloads video or audio from URL via yt-dlp."""
    parsed = urlparse(req.url.strip())
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Invalid URL protocol. Only HTTP and HTTPS are supported.")
    
    job_id = create_job("download", f"Download: {req.url[:45]}...", {"url": req.url, "preset": req.preset})
    
    async def _execute_download(jid: str, url: str, preset: str, custom_name: Optional[str]):
        job = JOBS[jid]
        job["status"] = "running"
        job["progress"] = 5
        job["logs"].append(f"Starting yt-dlp fetch for URL: {url}")
        
        out_template = str(UPLOAD_DIR / "%(title).100s_%(id)s.%(ext)s")
        
        cmd = ["yt-dlp", "--no-warnings", "--newline", "--progress", "--no-playlist"]
        
        if preset == "best":
            cmd.extend(["-f", "bestvideo+bestaudio/best", "--merge-output-format", "mp4"])
        elif preset == "1080p":
            cmd.extend(["-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best", "--merge-output-format", "mp4"])
        elif preset == "720p":
            cmd.extend(["-f", "bestvideo[height<=720]+bestaudio/best[height<=720]/best", "--merge-output-format", "mp4"])
        elif preset == "480p":
            cmd.extend(["-f", "bestvideo[height<=480]+bestaudio/best[height<=480]/best", "--merge-output-format", "mp4"])
        elif preset == "audio_mp3":
            cmd.extend(["-x", "--audio-format", "mp3", "--audio-quality", "0"])
        elif preset == "audio_m4a":
            cmd.extend(["-x", "--audio-format", "m4a", "--audio-quality", "0"])
        elif preset == "audio_wav":
            cmd.extend(["-x", "--audio-format", "wav"])
        else:
            cmd.extend(["-f", "bestvideo+bestaudio/best", "--merge-output-format", "mp4"])
            
        cmd.extend(["-o", out_template, url])
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            PROCESSES[jid] = proc
            
            percent_re = re.compile(r"\[download\]\s+([\d.]+)%")
            dest_re = re.compile(r"\[(?:download|Merger|ExtractAudio)\] Destination:\s+(.+)")
            already_re = re.compile(r"\[download\]\s+(.+)\s+has already been downloaded")
            
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
                    match_al = already_re.search(line)
                    if match_al:
                        downloaded_file = match_al.group(1).strip()
                elif "Destination:" in line:
                    match_dest = dest_re.search(line)
                    if match_dest:
                        downloaded_file = match_dest.group(1).strip()
                        
                if line and not line.startswith("[download] "):
                    job["logs"].append(line[-200:])
                job["updated_at"] = time.time()
                
            stderr_bytes = await proc.stderr.read()
            stderr_text = stderr_bytes.decode("utf-8", errors="ignore")
            ret = await proc.wait()
            
            if jid in PROCESSES:
                del PROCESSES[jid]
                
            if ret == 0:
                # Find most recently modified file in UPLOAD_DIR
                all_uploads = sorted(UPLOAD_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
                target_file = None
                if downloaded_file and Path(downloaded_file).exists():
                    target_file = Path(downloaded_file)
                elif all_uploads:
                    target_file = all_uploads[0]
                    
                if target_file and target_file.exists():
                    clean_name = target_file.name
                    job["status"] = "completed"
                    job["progress"] = 100
                    job["output_file"] = clean_name
                    job["output_url"] = f"/api/media/uploads/{clean_name}"
                    job["logs"].append(f"Successfully downloaded: {clean_name}")
                else:
                    job["status"] = "failed"
                    job["error"] = "Download finished but output file could not be located."
            else:
                job["status"] = "failed"
                job["error"] = f"yt-dlp failed with exit code {ret}"
                job["logs"].append(stderr_text[-1000:])
        except Exception as e:
            logger.exception(f"[{jid}] Error during download")
            job["status"] = "failed"
            job["error"] = str(e)
        finally:
            job["updated_at"] = time.time()
            
    background_tasks.add_task(_execute_download, job_id, req.url.strip(), req.preset, req.custom_filename)
    return {"job_id": job_id, "status": "queued"}

@app.get("/api/files")
async def list_files():
    """Lists all files in uploads and outputs directories with probed metadata."""
    uploads_data = []
    outputs_data = []
    
    # Process uploads
    for f in sorted(UPLOAD_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file():
            probe = await probe_media_file(f)
            uploads_data.append({
                "filename": f.name,
                "category": "uploads",
                "size_bytes": f.stat().st_size,
                "size_formatted": f"{f.stat().st_size / (1024 * 1024):.2f} MB",
                "mtime": f.stat().st_mtime,
                "url": f"/api/media/uploads/{f.name}",
                "metadata": probe
            })
            
    # Process outputs
    for f in sorted(OUTPUT_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file():
            probe = await probe_media_file(f)
            outputs_data.append({
                "filename": f.name,
                "category": "outputs",
                "size_bytes": f.stat().st_size,
                "size_formatted": f"{f.stat().st_size / (1024 * 1024):.2f} MB",
                "mtime": f.stat().st_mtime,
                "url": f"/api/media/outputs/{f.name}",
                "metadata": probe
            })
            
    return {"uploads": uploads_data, "outputs": outputs_data}

@app.delete("/api/files/{category}/{filename}")
async def delete_file(category: str, filename: str):
    """Deletes a file safely."""
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
    """Clears uploaded files, output files, or both."""
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
# FFmpeg Media Operations Endpoints
# ==============================================================================

class MergeRequest(BaseModel):
    filenames: List[str]
    category: str = "uploads"
    output_format: str = "mp4"
    normalize_resolution: bool = True
    target_resolution: str = "1920x1080" # 1920x1080, 1280x720, original

@app.post("/api/ops/merge")
async def merge_media(req: MergeRequest, background_tasks: BackgroundTasks):
    """Merges multiple video or audio files in order with resolution normalization."""
    if len(req.filenames) < 2:
        raise HTTPException(status_code=400, detail="At least 2 files are required to merge.")
    
    file_paths = []
    total_duration = 0.0
    has_any_video = False
    
    for fn in req.filenames:
        p = get_safe_path(req.category, fn)
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {fn}")
        file_paths.append(p)
        probe = await probe_media_file(p)
        total_duration += probe.get("duration", 0.0)
        if probe.get("has_video", False):
            has_any_video = True
            
    out_name = f"merged_{int(time.time())}.{req.output_format.lower()}"
    out_path = OUTPUT_DIR / out_name
    job_id = create_job("merge", f"Merge {len(req.filenames)} files into {out_name}", {"files": req.filenames})
    
    async def _execute_merge():
        cmd = ["-y"]
        
        if not has_any_video:
            # Pure audio concatenation
            filter_complex = []
            for idx, p in enumerate(file_paths):
                cmd.extend(["-i", str(p)])
                filter_complex.append(f"[{idx}:a:0]")
            filter_str = "".join(filter_complex) + f"concat=n={len(file_paths)}:v=0:a=1[aout]"
            cmd.extend([
                "-filter_complex", filter_str,
                "-map", "[aout]",
                "-c:a", "libmp3lame" if req.output_format == "mp3" else "aac",
                "-b:a", "192k",
                str(out_path)
            ])
        else:
            # Video concatenation with smart normalization
            if req.normalize_resolution:
                w, h = req.target_resolution.split("x") if "x" in req.target_resolution else ("1920", "1080")
                filter_parts = []
                for idx, p in enumerate(file_paths):
                    cmd.extend(["-i", str(p)])
                    # Scale and pad to uniform resolution and 30fps
                    filter_parts.append(
                        f"[{idx}:v:0]scale={w}:{h}:force_original_aspect_ratio=decrease,"
                        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{idx}];"
                        f"[{idx}:a:0]aformat=sample_rates=48000:channel_layouts=stereo[a{idx}];"
                    )
                concat_inputs = "".join([f"[v{i}][a{i}]" for i in range(len(file_paths))])
                filter_parts.append(f"{concat_inputs}concat=n={len(file_paths)}:v=1:a=1[v_out][a_out]")
                
                cmd.extend([
                    "-filter_complex", "".join(filter_parts),
                    "-map", "[v_out]",
                    "-map", "[a_out]",
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "22",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-movflags", "+faststart",
                    str(out_path)
                ])
            else:
                # Concat demuxer via temporary file list
                concat_list_file = TEMP_DIR / f"concat_{job_id}.txt"
                with concat_list_file.open("w", encoding="utf-8") as lf:
                    for p in file_paths:
                        # Escape single quotes for ffmpeg concat demuxer
                        escaped_p = str(p).replace("'", "'\\''")
                        lf.write(f"file '{escaped_p}'\n")
                
                cmd.extend([
                    "-f", "concat",
                    "-safe", "0",
                    "-i", str(concat_list_file),
                    "-c", "copy",
                    str(out_path)
                ])
                
        await run_ffmpeg_command(job_id, cmd, out_name, total_duration)
        # Clean up temp concat list if created
        concat_list_file = TEMP_DIR / f"concat_{job_id}.txt"
        if concat_list_file.exists():
            try:
                concat_list_file.unlink()
            except Exception:
                pass

    background_tasks.add_task(_execute_merge)
    return {"job_id": job_id, "status": "queued", "output_filename": out_name}

class ConvertRequest(BaseModel):
    filename: str
    category: str = "uploads"
    output_format: str # mp4, mkv, webm, avi, mov, mp3, wav, aac, flac, ogg, gif
    video_codec: str = "libx264" # libx264, libx265, libvpx-vp9, libaom-av1, copy, none
    audio_codec: str = "aac" # aac, libmp3lame, libopus, flac, copy, none
    crf: int = 23 # 0-51
    preset: str = "medium" # ultrafast, fast, medium, slow
    video_bitrate_kbps: Optional[int] = None
    audio_bitrate_kbps: int = 192
    resolution_scale: Optional[str] = None # 1920x1080, 1280x720, 854x480, etc.
    fps: Optional[int] = None
    gif_fps: int = 15
    gif_width: int = 480

@app.post("/api/ops/convert")
async def convert_media(req: ConvertRequest, background_tasks: BackgroundTasks):
    """Converts media to various video, audio, or animated GIF formats."""
    in_path = get_safe_path(req.category, req.filename)
    if not in_path.exists():
        raise HTTPException(status_code=404, detail="Input file not found")
        
    probe = await probe_media_file(in_path)
    duration = probe.get("duration", 0.0)
    
    stem = in_path.stem
    out_format = req.output_format.lower()
    out_name = f"{stem}_converted_{int(time.time())}.{out_format}"
    out_path = OUTPUT_DIR / out_name
    
    job_id = create_job("convert", f"Convert {req.filename} to {out_format.upper()}", {"input": req.filename, "format": out_format})
    
    async def _execute_convert():
        cmd = ["-y", "-i", str(in_path)]
        
        if out_format == "gif":
            # High-quality 2-pass GIF palette filter
            fps = max(1, min(30, req.gif_fps))
            width = max(120, min(1920, req.gif_width))
            vf = f"fps={fps},scale={width}:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
            cmd.extend(["-vf", vf, str(out_path)])
        elif out_format in ("mp3", "wav", "aac", "flac", "ogg", "m4a", "opus"):
            # Audio-only extraction / conversion
            cmd.extend(["-vn"])
            if out_format == "mp3":
                cmd.extend(["-c:a", "libmp3lame", "-b:a", f"{req.audio_bitrate_kbps}k"])
            elif out_format == "wav":
                cmd.extend(["-c:a", "pcm_s16le"])
            elif out_format == "aac" or out_format == "m4a":
                cmd.extend(["-c:a", "aac", "-b:a", f"{req.audio_bitrate_kbps}k"])
            elif out_format == "flac":
                cmd.extend(["-c:a", "flac"])
            elif out_format == "ogg" or out_format == "opus":
                cmd.extend(["-c:a", "libopus", "-b:a", f"{req.audio_bitrate_kbps}k"])
            cmd.append(str(out_path))
        else:
            # Video Conversion
            vf_filters = []
            if req.resolution_scale and "x" in req.resolution_scale:
                w, h = req.resolution_scale.split("x")
                vf_filters.append(f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2")
            if req.fps and req.fps > 0:
                vf_filters.append(f"fps={req.fps}")
                
            if vf_filters:
                cmd.extend(["-vf", ",".join(vf_filters)])
                
            if req.video_codec == "none":
                cmd.append("-vn")
            elif req.video_codec == "copy":
                cmd.extend(["-c:v", "copy"])
            else:
                cmd.extend(["-c:v", req.video_codec, "-preset", req.preset])
                if req.video_bitrate_kbps:
                    cmd.extend(["-b:v", f"{req.video_bitrate_kbps}k"])
                else:
                    cmd.extend(["-crf", str(req.crf)])
                    
            if req.audio_codec == "none":
                cmd.append("-an")
            elif req.audio_codec == "copy":
                cmd.extend(["-c:a", "copy"])
            else:
                cmd.extend(["-c:a", req.audio_codec, "-b:a", f"{req.audio_bitrate_kbps}k"])
                
            if out_format in ("mp4", "m4v", "mov"):
                cmd.extend(["-movflags", "+faststart"])
                
            cmd.append(str(out_path))
            
        await run_ffmpeg_command(job_id, cmd, out_name, duration)

    background_tasks.add_task(_execute_convert)
    return {"job_id": job_id, "status": "queued", "output_filename": out_name}

class TrimRequest(BaseModel):
    filename: str
    category: str = "uploads"
    start_time: str # "00:00:10" or "10.5"
    end_time: Optional[str] = None # "00:00:45"
    duration: Optional[str] = None # "35.0"
    mode: str = "precise" # precise (re-encode) or fast (stream copy)

@app.post("/api/ops/trim")
async def trim_media(req: TrimRequest, background_tasks: BackgroundTasks):
    """Trims / cuts video or audio accurately."""
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
        raise HTTPException(status_code=400, detail="Must provide valid end_time or duration greater than start_time")
        
    stem = in_path.stem
    suffix = in_path.suffix.lstrip('.')
    out_name = f"{stem}_trimmed_{int(time.time())}.{suffix}"
    out_path = OUTPUT_DIR / out_name
    
    job_id = create_job("trim", f"Trim {req.filename} ({format_duration(start_sec)} -> {format_duration(start_sec + cut_duration)})")
    
    async def _execute_trim():
        cmd = ["-y"]
        if req.mode == "fast":
            # Fast keyframe seek with stream copy
            cmd.extend([
                "-ss", str(start_sec),
                "-i", str(in_path),
                "-t", str(cut_duration),
                "-c", "copy",
                str(out_path)
            ])
        else:
            # Frame-accurate cut with re-encode
            cmd.extend([
                "-ss", str(start_sec),
                "-i", str(in_path),
                "-t", str(cut_duration),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "20",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                str(out_path)
            ])
        await run_ffmpeg_command(job_id, cmd, out_name, cut_duration)

    background_tasks.add_task(_execute_trim)
    return {"job_id": job_id, "status": "queued", "output_filename": out_name}

class CompressRequest(BaseModel):
    filename: str
    category: str = "uploads"
    target_size_mb: Optional[float] = None # e.g. 8.0 for Discord
    resolution_scale: Optional[str] = "1280x720" # 1920x1080, 1280x720, 854x480, 640x360
    crf: int = 28 # 18-35

@app.post("/api/ops/compress")
async def compress_media(req: CompressRequest, background_tasks: BackgroundTasks):
    """Compresses video to fit within target size (e.g. Discord 8MB/25MB) or scale resolution."""
    in_path = get_safe_path(req.category, req.filename)
    if not in_path.exists():
        raise HTTPException(status_code=404, detail="Input file not found")
        
    probe = await probe_media_file(in_path)
    duration = probe.get("duration", 0.0)
    if duration <= 0:
        duration = 10.0
        
    stem = in_path.stem
    out_name = f"{stem}_compressed_{int(time.time())}.mp4"
    out_path = OUTPUT_DIR / out_name
    
    job_id = create_job("compress", f"Compress {req.filename} to {req.target_size_mb or 'CRF ' + str(req.crf)} MB")
    
    async def _execute_compress():
        cmd = ["-y", "-i", str(in_path)]
        vf_filters = []
        
        if req.resolution_scale and "x" in req.resolution_scale:
            w, h = req.resolution_scale.split("x")
            vf_filters.append(f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2")
            
        if vf_filters:
            cmd.extend(["-vf", ",".join(vf_filters)])
            
        if req.target_size_mb and req.target_size_mb > 0:
            # Calculate target video bitrate = (target_bytes * 8) / duration - audio_bitrate
            target_bits = req.target_size_mb * 8 * 1024 * 1024 * 0.95 # 5% safety margin
            audio_bitrate_kbps = 96
            video_bitrate_kbps = max(50, int((target_bits / duration) / 1000 - audio_bitrate_kbps))
            cmd.extend([
                "-c:v", "libx264",
                "-b:v", f"{video_bitrate_kbps}k",
                "-maxrate", f"{int(video_bitrate_kbps * 1.3)}k",
                "-bufsize", f"{int(video_bitrate_kbps * 2)}k",
                "-preset", "medium",
                "-c:a", "aac",
                "-b:a", f"{audio_bitrate_kbps}k",
                "-movflags", "+faststart",
                str(out_path)
            ])
        else:
            cmd.extend([
                "-c:v", "libx264",
                "-crf", str(req.crf),
                "-preset", "medium",
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                str(out_path)
            ])
            
        await run_ffmpeg_command(job_id, cmd, out_name, duration)

    background_tasks.add_task(_execute_compress)
    return {"job_id": job_id, "status": "queued", "output_filename": out_name}

class AudioReplaceRequest(BaseModel):
    video_filename: str
    audio_filename: str
    video_category: str = "uploads"
    audio_category: str = "uploads"
    action: str = "replace" # replace, mix
    video_volume: float = 1.0 # 0.0 - 2.0
    audio_volume: float = 1.0 # 0.0 - 2.0
    match_duration_to_video: bool = True

@app.post("/api/ops/audio-replace")
async def audio_replace_mix(req: AudioReplaceRequest, background_tasks: BackgroundTasks):
    """Replaces original video audio with another audio track or mixes them together."""
    v_path = get_safe_path(req.video_category, req.video_filename)
    a_path = get_safe_path(req.audio_category, req.audio_filename)
    
    if not v_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    if not a_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
        
    probe_v = await probe_media_file(v_path)
    v_duration = probe_v.get("duration", 0.0)
    
    stem = v_path.stem
    out_name = f"{stem}_{req.action}Audio_{int(time.time())}.mp4"
    out_path = OUTPUT_DIR / out_name
    
    job_id = create_job("audio_mix", f"{req.action.capitalize()} audio on {req.video_filename}")
    
    async def _execute_audio_mux():
        cmd = ["-y", "-i", str(v_path), "-i", str(a_path)]
        
        if req.action == "replace":
            cmd.extend([
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-af", f"volume={req.audio_volume}"
            ])
            if req.match_duration_to_video:
                cmd.append("-shortest")
        else: # mix
            filter_str = (
                f"[0:a]volume={req.video_volume}[a0];"
                f"[1:a]volume={req.audio_volume}[a1];"
                f"[a0][a1]amix=inputs=2:duration={'first' if req.match_duration_to_video else 'longest'}[aout]"
            )
            cmd.extend([
                "-map", "0:v:0",
                "-filter_complex", filter_str,
                "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k"
            ])
            
        cmd.extend(["-movflags", "+faststart", str(out_path)])
        await run_ffmpeg_command(job_id, cmd, out_name, v_duration)

    background_tasks.add_task(_execute_audio_mux)
    return {"job_id": job_id, "status": "queued", "output_filename": out_name}

class TransformRequest(BaseModel):
    filename: str
    category: str = "uploads"
    speed: float = 1.0 # 0.25 to 4.0
    reverse: bool = False
    rotate: int = 0 # 0, 90, 180, 270
    hflip: bool = False
    vflip: bool = False

@app.post("/api/ops/transform")
async def transform_media(req: TransformRequest, background_tasks: BackgroundTasks):
    """Applies speed change, reverse, rotate, or flip effects."""
    in_path = get_safe_path(req.category, req.filename)
    if not in_path.exists():
        raise HTTPException(status_code=404, detail="Input file not found")
        
    probe = await probe_media_file(in_path)
    duration = probe.get("duration", 0.0)
    has_video = probe.get("has_video", False)
    
    stem = in_path.stem
    out_name = f"{stem}_fx_{int(time.time())}.mp4"
    out_path = OUTPUT_DIR / out_name
    
    job_id = create_job("transform", f"Transform {req.filename} (Speed {req.speed}x)")
    
    async def _execute_transform():
        cmd = ["-y", "-i", str(in_path)]
        vf = []
        af = []
        
        # Speed adjustment
        if req.speed != 1.0 and 0.25 <= req.speed <= 4.0:
            pts_mult = 1.0 / req.speed
            vf.append(f"setpts={pts_mult}*PTS")
            # FFmpeg atempo only supports 0.5 to 2.0 per filter instance; chain if needed
            sp = req.speed
            while sp > 2.0:
                af.append("atempo=2.0")
                sp /= 2.0
            while sp < 0.5:
                af.append("atempo=0.5")
                sp /= 0.5
            af.append(f"atempo={sp}")
            
        if req.reverse:
            vf.append("reverse")
            af.append("areverse")
            
        if req.rotate == 90:
            vf.append("transpose=1")
        elif req.rotate == 180:
            vf.append("transpose=1,transpose=1")
        elif req.rotate == 270:
            vf.append("transpose=2")
            
        if req.hflip:
            vf.append("hflip")
        if req.vflip:
            vf.append("vflip")
            
        if vf and has_video:
            cmd.extend(["-vf", ",".join(vf), "-c:v", "libx264", "-preset", "fast", "-crf", "22"])
        else:
            cmd.extend(["-c:v", "copy"])
            
        if af:
            cmd.extend(["-af", ",".join(af), "-c:a", "aac", "-b:a", "192k"])
        else:
            cmd.extend(["-c:a", "copy"])
            
        cmd.extend(["-movflags", "+faststart", str(out_path)])
        calc_duration = duration / req.speed if req.speed > 0 else duration
        await run_ffmpeg_command(job_id, cmd, out_name, calc_duration)

    background_tasks.add_task(_execute_transform)
    return {"job_id": job_id, "status": "queued", "output_filename": out_name}

class SnapshotRequest(BaseModel):
    filename: str
    category: str = "uploads"
    timestamp: str # "00:00:15" or "15.0"
    format: str = "png" # png, jpg

@app.post("/api/ops/snapshot")
async def extract_snapshot(req: SnapshotRequest):
    """Extracts a high-resolution screenshot frame at timestamp."""
    in_path = get_safe_path(req.category, req.filename)
    if not in_path.exists():
        raise HTTPException(status_code=404, detail="Input file not found")
        
    ts_sec = parse_time_str(req.timestamp)
    stem = in_path.stem
    fmt = "jpg" if req.format.lower() in ("jpg", "jpeg") else "png"
    out_name = f"{stem}_frame_{int(ts_sec)}s_{int(time.time())}.{fmt}"
    out_path = OUTPUT_DIR / out_name
    
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(ts_sec),
        "-i", str(in_path),
        "-frames:v", "1",
        "-q:v", "2",
        str(out_path)
    ]
    
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()
    
    if proc.returncode != 0 or not out_path.exists():
        raise HTTPException(status_code=500, detail=f"Frame extraction failed: {stderr.decode(errors='ignore')}")
        
    return {
        "success": True,
        "filename": out_name,
        "url": f"/api/media/outputs/{out_name}"
    }

# ==============================================================================
# Job Status & File Serving Endpoints
# ==============================================================================

@app.get("/api/jobs")
async def list_jobs():
    """Lists all active and completed jobs."""
    sorted_jobs = sorted(JOBS.values(), key=lambda j: j["created_at"], reverse=True)
    return {"jobs": sorted_jobs[:50]}

@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Returns status and progress of a single job."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancels a running job."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if job_id in PROCESSES:
        proc = PROCESSES[job_id]
        try:
            proc.terminate()
            job["status"] = "cancelled"
            job["logs"].append("Process terminated by user request.")
        except Exception as e:
            logger.error(f"Error terminating process {job_id}: {e}")
            
    return {"success": True, "job_id": job_id}

@app.get("/api/media/{category}/{filename}")
async def stream_media(category: str, filename: str, request: Request):
    """Streams video / audio with Range header support for seeking."""
    path = get_safe_path(category, filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Media file not found")
        
    file_size = path.stat().st_size
    range_header = request.headers.get("Range")
    
    # Determine mime type
    suffix = path.suffix.lower()
    content_types = {
        ".mp4": "video/mp4",
        ".mkv": "video/x-matroska",
        ".webm": "video/webm",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".aac": "audio/aac",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
        ".opus": "audio/opus",
        ".m4a": "audio/mp4",
        ".gif": "image/gif",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg"
    }
    content_type = content_types.get(suffix, "application/octet-stream")
    
    if range_header:
        # Partial Content / Seek
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
            logger.error(f"Error handling Range request: {e}")
            
    return FileResponse(path, media_type=content_type)

@app.get("/api/download/{category}/{filename}")
async def download_file(category: str, filename: str):
    """Forces browser file download attachment."""
    path = get_safe_path(category, filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=filename, media_type="application/octet-stream")

@app.get("/api/download-all-zip")
async def download_all_zip(category: str = Query("outputs", regex="^(uploads|outputs)$")):
    """Packages all files from category into a single downloadable ZIP."""
    target_dir = UPLOAD_DIR if category == "uploads" else OUTPUT_DIR
    files = list(target_dir.glob("*"))
    if not files:
        raise HTTPException(status_code=404, detail="No files available to zip")
        
    zip_path = TEMP_DIR / f"{category}_bundle_{int(time.time())}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            if f.is_file():
                zf.write(f, arcname=f.name)
                
    return FileResponse(zip_path, filename=f"omnimedia_{category}.zip", media_type="application/zip")

# ==============================================================================
# Static UI Assets Mount
# ==============================================================================

STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 7860))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"🚀 Starting OmniMedia Studio on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
