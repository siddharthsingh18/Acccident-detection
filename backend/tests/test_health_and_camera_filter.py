import pytest

def test_health_endpoint_details(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "degraded", "down")
    assert "zmq_listener" in data
    assert isinstance(data["zmq_listener"], dict)
    assert "running" in data["zmq_listener"]
    assert "database" in data
    assert data["database"]["accessible"] is True
    assert "ffmpeg" in data

def test_list_incidents_filter_by_camera_id(client):
    # Query with existing camera 1528
    response = client.get("/api/incidents?camera_id=1528")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) > 0
    for item in data["items"]:
        assert item["camera_id"] == 1528

    # Query with non-existent camera id
    response = client.get("/api/incidents?camera_id=999999")
    assert response.status_code == 200
    empty_data = response.json()
    assert empty_data["items"] == []
    assert empty_data["count"] == 0
