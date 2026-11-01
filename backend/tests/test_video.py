import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch
import pytest

from app.config import settings

def test_thumbnail_extracted_from_video(client, temp_environment):
    # Request thumbnail for 1528_76 where (1528) 76.avi exists
    response = client.get("/media/thumbnails/1528_76.jpg")
    assert response.status_code == 200
    assert response.headers["content-type"] in ("image/jpeg", "image/png")
    assert len(response.content) > 0

    # Ensure thumbnail was cached on disk
    cached_file = temp_environment["thumbnails_dir"] / "1528_76.jpg"
    assert cached_file.exists()

def test_thumbnail_fallback_when_missing(client):
    # Incident 1566_151 has no AVI video in temp_environment
    response = client.get("/media/thumbnails/1566_151.jpg")
    assert response.status_code == 200
    assert response.headers["content-type"] in ("image/png", "image/jpeg")
    assert len(response.content) > 0

def test_video_transcoding_and_streaming(client, temp_environment):
    # Request video for 1528_76
    response = client.get("/api/incidents/1528_76/video")
    assert response.status_code == 200
    assert response.headers["content-type"] == "video/mp4"
    assert len(response.content) > 0

    # Check cached MP4 file
    cached_mp4 = temp_environment["video_cache_dir"] / "1528_76.mp4"
    assert cached_mp4.exists()

def test_video_not_found(client):
    # Request video for non-existent incident
    response = client.get("/api/incidents/9999_99999/video")
    assert response.status_code in (404, 500)
    data = response.json()
    assert "code" in data

    # Request video for incident present in DB but with missing video clip
    response_missing = client.get("/api/incidents/1566_151/video")
    assert response_missing.status_code in (404, 500)
    data_missing = response_missing.json()
    assert "code" in data_missing

def test_video_range_requests_all_variants(client, temp_environment):
    # Ensure video is generated
    init_res = client.get("/api/incidents/1528_76/video")
    assert init_res.status_code == 200
    full_size = len(init_res.content)
    assert full_size > 0

    # 1. HEAD request
    head_res = client.head("/api/incidents/1528_76/video")
    assert head_res.status_code == 200
    assert head_res.headers["Content-Type"] == "video/mp4"
    assert head_res.headers["Accept-Ranges"] == "bytes"
    assert int(head_res.headers["Content-Length"]) == full_size

    # 2. Start Range (0-100)
    r1 = client.get("/api/incidents/1528_76/video", headers={"Range": "bytes=0-100"})
    assert r1.status_code == 206
    assert r1.headers["Content-Type"] == "video/mp4"
    assert r1.headers["Accept-Ranges"] == "bytes"
    assert r1.headers["Content-Range"] == f"bytes 0-100/{full_size}"
    assert len(r1.content) == 101

    # 3. Middle Range (50-150)
    r2 = client.get("/api/incidents/1528_76/video", headers={"Range": "bytes=50-150"})
    assert r2.status_code == 206
    assert r2.headers["Content-Range"] == f"bytes 50-150/{full_size}"
    assert len(r2.content) == 101

    # 4. Open-ended Range (100-)
    r3 = client.get("/api/incidents/1528_76/video", headers={"Range": "bytes=100-"})
    assert r3.status_code == 206
    assert r3.headers["Content-Range"] == f"bytes 100-{full_size - 1}/{full_size}"
    assert len(r3.content) == full_size - 100

    # 5. Suffix Range (-50)
    r4 = client.get("/api/incidents/1528_76/video", headers={"Range": "bytes=-50"})
    assert r4.status_code == 206
    assert r4.headers["Content-Range"] == f"bytes {full_size - 50}-{full_size - 1}/{full_size}"
    assert len(r4.content) == 50

    # 6. Invalid Range (past EOF)
    r5 = client.get("/api/incidents/1528_76/video", headers={"Range": f"bytes={full_size + 1000}-"})
    assert r5.status_code == 416
    assert r5.headers["Content-Range"] == f"bytes */{full_size}"

    # 7. Inverted Range (500-100)
    r6 = client.get("/api/incidents/1528_76/video", headers={"Range": "bytes=500-100"})
    assert r6.status_code == 416

def test_names_with_spaces_and_parentheses_normalized(client, temp_environment):
    # Calling with raw name format '(1528) 76.avi' should normalize to '1528_76'
    res_avi = client.get("/api/incidents/(1528) 76.avi/video")
    assert res_avi.status_code == 200
    assert res_avi.headers["Content-Type"] == "video/mp4"

    # Calling with '(1528) 76'
    res_paren = client.get("/api/incidents/(1528) 76/video")
    assert res_paren.status_code == 200
    assert res_paren.headers["Content-Type"] == "video/mp4"

    # Path traversal must be rejected with 400 (or 404 by router)
    res_traversal = client.get("/api/incidents/invalid..id/video")
    assert res_traversal.status_code == 400
    assert res_traversal.json()["code"] == "INVALID_ID"

    # Attempt with slash traversal
    res_slash = client.get("/api/incidents/..%2Fetc%2Fpasswd/video")
    assert res_slash.status_code in (400, 404)

def test_partial_cache_file_never_served(client, temp_environment):
    # Create an artificial .tmp file in the cache directory
    tmp_file = temp_environment["video_cache_dir"] / ".tmp_partial.mp4"
    tmp_file.write_bytes(b"partial-data")

    # Request the incident - backend must never serve .tmp file
    res = client.get("/api/incidents/1528_76/video")
    assert res.status_code == 200
    assert res.content != b"partial-data"
    assert len(res.content) > 1000

def test_corrupt_source_returns_422(client, temp_environment):
    # Put a corrupt 10-byte file where (1528) 106.avi would be
    corrupt_file = settings.SAVED_CRASH_VID_DIR / "(1528) 106.avi"
    corrupt_file.write_bytes(b"corrupt-data-not-a-video")

    res = client.get("/api/incidents/1528_106/video")
    assert res.status_code == 422
    data = res.json()
    assert data["code"] in ("CORRUPT_VIDEO", "TRANSCODING_FAILED")

def test_missing_ffmpeg_returns_503_and_health_degraded(client, temp_environment):
    # Delete cached mp4 for 1528_76 to force a transcode attempt
    cached = temp_environment["video_cache_dir"] / "1528_76.mp4"
    if cached.exists():
        cached.unlink()

    with patch("shutil.which", return_value=None):
        # Transcoding attempt must fail with 503
        res = client.get("/api/incidents/1528_76/video")
        assert res.status_code == 503
        assert res.json()["code"] == "TRANSCODER_UNAVAILABLE"

        # Health endpoint must report degraded status and available=False
        health_res = client.get("/api/health")
        assert health_res.status_code == 200
        health_data = health_res.json()
        assert health_data["ffmpeg"]["available"] is False
        assert health_data["status"] == "degraded"

def test_transcoded_video_h264_yuv420p_faststart_validation(client, temp_environment):
    # Request incident 1528_76 to generate cached MP4
    res = client.get("/api/incidents/1528_76/video")
    assert res.status_code == 200

    cached_mp4 = temp_environment["video_cache_dir"] / "1528_76.mp4"
    assert cached_mp4.exists()

    # Validate with ffprobe
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,pix_fmt,width,height",
        "-show_entries", "format=format_name",
        "-of", "json",
        str(cached_mp4),
    ]
    out = json.loads(subprocess.check_output(cmd, text=True))
    stream = out["streams"][0]
    fmt = out["format"]

    assert stream["codec_name"] == "h264"
    assert stream["pix_fmt"] in ("yuv420p", "yuvj420p")
    assert stream["width"] % 2 == 0
    assert stream["height"] % 2 == 0
    assert "mp4" in fmt["format_name"]

    # Verify faststart (moov atom before mdat in the first few KB)
    with open(cached_mp4, "rb") as f:
        head = f.read(4096)
        moov_idx = head.find(b"moov")
        mdat_idx = head.find(b"mdat")
        assert moov_idx != -1, "moov atom must be in the first 4KB"
        if mdat_idx != -1:
            assert moov_idx < mdat_idx, "moov atom must precede mdat atom (faststart)"

def test_sample_video_transcoding_and_streaming(client, temp_environment, tmp_path):
    # Create sample dir and sample video
    sample_dir = tmp_path / "test_samples"
    sample_dir.mkdir(parents=True, exist_ok=True)
    sample_file = sample_dir / "clip1.avi"

    # Copy the valid sample AVI from temp_environment
    shutil.copyfile(temp_environment["sample_avi"], sample_file)

    orig_sample_dirs = settings.SAMPLE_DIRS
    orig_sample_cache = settings.SAMPLE_CACHE_DIR
    settings.SAMPLE_DIRS = [str(sample_dir)]
    settings.SAMPLE_CACHE_DIR = tmp_path / "sample_cache"

    try:
        sample_id = "clip1.avi"
        # 1. Request video for sample
        res = client.get(f"/api/samples/{sample_id}/video")
        assert res.status_code == 200
        assert res.headers["Content-Type"] == "video/mp4"
        assert res.headers["Accept-Ranges"] == "bytes"
        assert len(res.content) > 1000

        # 2. Test range seeking on sample video
        r_range = client.get(f"/api/samples/{sample_id}/video", headers={"Range": "bytes=0-200"})
        assert r_range.status_code == 206
        assert r_range.headers["Content-Type"] == "video/mp4"
        assert len(r_range.content) == 201

        # 3. Transcoded file is cached under sample cache dir
        transcoded_file = settings.SAMPLE_CACHE_DIR / "transcoded" / "clip1.avi.mp4"
        assert transcoded_file.exists()
    finally:
        settings.SAMPLE_DIRS = orig_sample_dirs
        settings.SAMPLE_CACHE_DIR = orig_sample_cache
