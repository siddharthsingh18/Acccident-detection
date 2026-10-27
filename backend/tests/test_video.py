from pathlib import Path

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

    # Test HTTP Range request (seeking)
    range_headers = {"Range": "bytes=0-100"}
    range_response = client.get("/api/incidents/1528_76/video", headers=range_headers)
    assert range_response.status_code == 206
    assert range_response.headers["content-type"] == "video/mp4"
    assert "Content-Range" in range_response.headers
    assert range_response.headers["Content-Range"].startswith("bytes 0-100/")
    assert len(range_response.content) == 101

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
