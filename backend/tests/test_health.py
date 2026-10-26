def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ("ok", "degraded", "down")
    assert "services" in data
    assert "master" in data["services"]
    assert "detect" in data["services"]
    assert "tracker" in data["services"]
    assert "crash" in data["services"]
    assert "database" in data
    assert data["database"]["accessible"] is True
    assert "ffmpeg" in data
