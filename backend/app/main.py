from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import io
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import imageio_ffmpeg
import yt_dlp
from fastapi import FastAPI, HTTPException
from fastapi.background import BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from PIL import Image


SUPPORTED_DOMAINS = {
    "facebook.com", "fb.watch", "instagram.com", "youtube.com", "youtu.be",
    "tiktok.com", "reddit.com", "redd.it", "x.com", "twitter.com",
}
APPLE_VIDEO_CODECS = {"h264", "hevc"}
APPLE_AUDIO_CODECS = {"aac"}
JOB_TTL_SECONDS = 60 * 60
MAX_ACTIVE_DOWNLOADS = 2

jobs: dict[str, "Job"] = {}
jobs_lock = threading.Lock()
download_slots = threading.Semaphore(MAX_ACTIVE_DOWNLOADS)
work_root = Path(tempfile.gettempdir()) / "mediafetch-web"
work_root.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(cleanup_loop())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(
    title="MediaFetch API", version="1.0.0", docs_url="/api/docs",
    openapi_url="/api/openapi.json", lifespan=lifespan,
)


class AnalyzeRequest(BaseModel):
    url: str = Field(min_length=8, max_length=4096)


class DownloadRequest(AnalyzeRequest):
    media_type: str = Field(pattern="^(MP4|MP3|JPG)$")
    quality: int | None = Field(default=None, ge=144, le=4320)


@dataclass(slots=True)
class Job:
    job_id: str
    status: str = "queued"
    percent: float = 0
    message: str = "Queued"
    path: Path | None = None
    filename: str = ""
    error: str = ""
    created_at: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def json(self) -> dict[str, Any]:
        with self.lock:
            return {
                "job_id": self.job_id, "status": self.status, "percent": self.percent,
                "message": self.message, "filename": self.filename, "error": self.error,
            }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze(request: AnalyzeRequest) -> dict[str, Any]:
    url = validate_url(request.url)
    try:
        return await asyncio.to_thread(analyze_media, url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=friendly_error(exc)) from exc


@app.post("/api/download", status_code=202)
async def download(request: DownloadRequest, background: BackgroundTasks) -> dict[str, str]:
    url = validate_url(request.url)
    job = Job(uuid.uuid4().hex)
    with jobs_lock:
        jobs[job.job_id] = job
    background.add_task(run_download, job, url, request.media_type, request.quality)
    return {"job_id": job.job_id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict[str, Any]:
    return get_job(job_id).json()


@app.get("/api/files/{job_id}")
def job_file(job_id: str) -> FileResponse:
    job = get_job(job_id)
    if job.status != "complete" or not job.path or not job.path.is_file():
        raise HTTPException(status_code=409, detail="File is not ready.")
    return FileResponse(job.path, filename=job.filename, media_type="application/octet-stream")


def get_job(job_id: str) -> Job:
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Download job not found or expired.")
    return job


def validate_url(raw: str) -> str:
    value = raw.strip()
    try:
        parsed = urlparse(value)
        host = (parsed.hostname or "").lower().rstrip(".")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid URL.") from exc
    if parsed.scheme not in {"http", "https"} or not host:
        raise HTTPException(status_code=400, detail="Invalid URL.")
    if not any(host == domain or host.endswith("." + domain) for domain in SUPPORTED_DOMAINS):
        raise HTTPException(status_code=400, detail="This website is not supported.")
    return value


def ydl_base() -> dict[str, Any]:
    return {
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "socket_timeout": 30, "retries": 5, "fragment_retries": 5,
        "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
    }


def analyze_media(url: str) -> dict[str, Any]:
    options = {**ydl_base(), "skip_download": True}
    with yt_dlp.YoutubeDL(options) as ydl:
        raw = ydl.extract_info(url, download=False)
    info = first_entry(raw)
    if not info:
        raise RuntimeError("No downloadable media was found.")
    heights = sorted({int(item["height"]) for item in info.get("formats") or [] if item.get("height") and int(item["height"]) >= 144}, reverse=True)
    duration = int(info.get("duration") or 0)
    minutes, seconds = divmod(duration, 60)
    hours, minutes = divmod(minutes, 60)
    duration_label = f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"
    return {
        "title": str(info.get("title") or "Untitled media"),
        "creator": str(info.get("uploader") or info.get("channel") or info.get("creator") or "Unknown"),
        "duration": duration_label if duration else "—",
        "platform": str(info.get("extractor_key") or info.get("extractor") or "Media"),
        "thumbnail": best_thumbnail(info), "qualities": heights,
    }


def run_download(job: Job, url: str, media_type: str, quality: int | None) -> None:
    with download_slots:
        folder = work_root / job.job_id
        folder.mkdir(parents=True, exist_ok=True)
        try:
            update_job(job, "analyzing", 1, "Reading media details")
            if media_type == "JPG":
                path = download_jpg(url, folder, job)
            else:
                path = download_av(url, folder, job, media_type, quality)
                if media_type == "MP4":
                    path = ensure_apple_compatible(path, job)
            update_job(job, "complete", 100, "Ready", path=path, filename=path.name)
        except Exception as exc:
            update_job(job, "error", job.percent, "Failed", error=friendly_error(exc))


def download_av(url: str, folder: Path, job: Job, media_type: str, quality: int | None) -> Path:
    def hook(data: dict[str, Any]) -> None:
        downloaded = float(data.get("downloaded_bytes") or 0)
        total = float(data.get("total_bytes") or data.get("total_bytes_estimate") or 0)
        percent = min(94, downloaded / total * 94) if total else job.percent
        update_job(job, "downloading", percent, "Downloading")

    options = {**ydl_base(), "outtmpl": str(folder / "%(title).160B [%(id)s].%(ext)s"), "progress_hooks": [hook]}
    if media_type == "MP3":
        options.update({"format": "bestaudio/best", "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "0"}]})
        target_ext = ".mp3"
    else:
        limit = f"[height<={quality}]" if quality else ""
        options.update({
            "format": f"bestvideo{limit}[vcodec^=avc]+bestaudio[acodec^=mp4a]/best{limit}[vcodec^=avc][acodec^=mp4a]/bestvideo{limit}+bestaudio/best{limit}/best",
            "merge_output_format": "mp4",
            "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}],
        })
        target_ext = ".mp4"
    with yt_dlp.YoutubeDL(options) as ydl:
        raw = ydl.extract_info(url, download=True)
        info = first_entry(raw) or raw
        prepared = Path(ydl.prepare_filename(info))
    path = prepared.with_suffix(target_ext)
    if not path.is_file():
        candidates = sorted(folder.glob(f"*{target_ext}"), key=lambda item: item.stat().st_mtime, reverse=True)
        if not candidates:
            raise RuntimeError("The completed file could not be found.")
        path = candidates[0]
    return path


def download_jpg(url: str, folder: Path, job: Job) -> Path:
    options = {**ydl_base(), "skip_download": True}
    with yt_dlp.YoutubeDL(options) as ydl:
        info = first_entry(ydl.extract_info(url, download=False))
    if not info or not (thumbnail := best_thumbnail(info)):
        raise RuntimeError("This post does not provide a cover image.")
    request = urllib.request.Request(thumbnail, headers={"User-Agent": "Mozilla/5.0 MediaFetch/1.0"})
    update_job(job, "downloading", 50, "Downloading image")
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read(25 * 1024 * 1024 + 1)
    if len(payload) > 25 * 1024 * 1024:
        raise RuntimeError("Image is too large.")
    title = safe_name(str(info.get("title") or "media"))
    path = folder / f"{title} [{info.get('id') or 'media'}].jpg"
    with Image.open(io.BytesIO(payload)) as image:
        image.convert("RGB").save(path, "JPEG", quality=95, optimize=True)
    return path


def ensure_apple_compatible(path: Path, job: Job) -> Path:
    video, audio = probe_codecs(path)
    video_ok = video in APPLE_VIDEO_CODECS
    audio_ok = audio is None or audio in APPLE_AUDIO_CODECS
    if video_ok and audio_ok:
        return path
    update_job(job, "converting", 96, "Optimizing for Apple devices")
    output = path.with_name(f".{path.stem}.apple.mp4")
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(path), "-map", "0:v:0", "-map", "0:a:0?", "-map_metadata", "0"]
    command += ["-c:v", "copy"] if video_ok else ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-tag:v", "avc1"]
    if audio is None: command += ["-an"]
    elif audio_ok: command += ["-c:a", "copy"]
    else: command += ["-c:a", "aac", "-b:a", "192k"]
    command += ["-movflags", "+faststart", str(output)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "Video conversion failed.")
    output.replace(path)
    return path


def probe_codecs(path: Path) -> tuple[str | None, str | None]:
    result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    video = re.search(r"Video:\s*([A-Za-z0-9_]+)", result.stderr)
    audio = re.search(r"Audio:\s*([A-Za-z0-9_]+)", result.stderr)
    if not video: raise RuntimeError("The file has no readable video stream.")
    return video.group(1).lower(), audio.group(1).lower() if audio else None


def first_entry(info: Any) -> dict[str, Any] | None:
    if not isinstance(info, dict): return None
    if "entries" not in info: return info
    return next((item for item in info.get("entries") or [] if isinstance(item, dict)), None)


def best_thumbnail(info: dict[str, Any]) -> str | None:
    candidates = [item for item in info.get("thumbnails") or [] if item.get("url")]
    if candidates:
        return str(max(candidates, key=lambda item: (item.get("width") or 0) * (item.get("height") or 0))["url"])
    return str(info["thumbnail"]) if info.get("thumbnail") else None


def update_job(job: Job, status: str, percent: float, message: str, **values: Any) -> None:
    with job.lock:
        job.status, job.percent, job.message = status, percent, message
        for key, value in values.items(): setattr(job, key, value)


def safe_name(value: str) -> str:
    return re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", value).strip(" .")[:160] or "media"


def friendly_error(exc: Exception) -> str:
    text = re.sub(r"\x1b\[[0-9;]*m", "", str(exc)).removeprefix("ERROR: ").strip()
    if any(word in text.lower() for word in ("login", "cookies", "private")):
        return "This media requires sign-in or is private."
    return text or "The media could not be processed."


async def cleanup_loop() -> None:
    while True:
        await asyncio.sleep(300)
        cutoff = time.time() - JOB_TTL_SECONDS
        with jobs_lock:
            expired = [job_id for job_id, job in jobs.items() if job.created_at < cutoff]
            for job_id in expired: jobs.pop(job_id, None)
        for job_id in expired:
            shutil.rmtree(work_root / job_id, ignore_errors=True)
