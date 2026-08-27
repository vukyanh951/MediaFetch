from pathlib import Path

import pytest
from fastapi import HTTPException

import subprocess

import imageio_ffmpeg

from app.main import Job, ensure_apple_compatible, probe_codecs, safe_name, validate_url


@pytest.mark.parametrize("url", [
    "https://facebook.com/watch?v=1", "https://youtu.be/abc", "https://x.com/user/status/1",
    "https://www.instagram.com/reel/abc", "https://old.reddit.com/r/test/comments/1",
])
def test_supported_urls(url: str):
    assert validate_url(url) == url


def test_rejects_unknown_domain():
    with pytest.raises(HTTPException): validate_url("https://example.com/video")


def test_rejects_subdomain_trick():
    with pytest.raises(HTTPException): validate_url("https://youtube.com.evil.test/video")


def test_safe_filename():
    assert safe_name('A/B:C*D?"E') == "A_B_C_D__E"


def test_job_payload_does_not_expose_server_path(tmp_path: Path):
    job = Job("abc", status="complete", path=tmp_path / "secret.mp4", filename="clip.mp4")
    assert "path" not in job.json()


def test_vp9_video_is_converted_for_apple(tmp_path: Path):
    path = tmp_path / "facebook-vp9.mp4"
    subprocess.run([
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=size=64x64:rate=10",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
        "-t", "0.25", "-c:v", "libvpx-vp9", "-c:a", "aac", str(path),
    ], check=True)
    assert probe_codecs(path) == ("vp9", "aac")
    ensure_apple_compatible(path, Job("test"))
    assert probe_codecs(path) == ("h264", "aac")
