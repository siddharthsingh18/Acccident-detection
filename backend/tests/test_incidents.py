def test_list_incidents_default(client):
    response = client.get("/api/incidents")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["count"] == 5
    assert len(data["items"]) == 5
    first = data["items"][0]
    assert "id" in first
    assert "camera_id" in first
    assert "crash_time" in first
    assert "thumbnail_url" in first
    assert "video_url" in first

def test_list_incidents_filter_city(client):
    response = client.get("/api/incidents?city=Cairo")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["items"][0]["city"] == "Cairo"
    assert data["items"][0]["camera_id"] == 1559

def test_list_incidents_filter_date(client):
    response = client.get("/api/incidents?start_date=2021-01-07&end_date=2021-01-07&start_time=09:00&end_time=10:00")
    assert response.status_code == 200
    data = response.json()
    # Shibin El Kom (09:39:31, 09:39:32)
    assert data["count"] == 2
    for item in data["items"]:
        assert item["city"] == "Shibin El Kom"

def test_list_incidents_pagination(client):
    # Fetch with limit=2
    response1 = client.get("/api/incidents?limit=2")
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["count"] == 2
    assert data1["has_more"] is True
    assert data1["next_cursor"] is not None

    cursor = data1["next_cursor"]
    response2 = client.get(f"/api/incidents?limit=2&cursor={cursor}")
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["count"] == 2
    # Ensure items in page 2 are different from page 1
    ids_page1 = {item["id"] for item in data1["items"]}
    ids_page2 = {item["id"] for item in data2["items"]}
    assert ids_page1.isdisjoint(ids_page2)

def test_recent_incidents(client):
    response = client.get("/api/incidents/recent")
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    assert len(items) == 5  # total sample size is 5
    assert items[0]["camera_id"] == 1559

def test_get_incident_by_composite_id(client):
    response = client.get("/api/incidents/1528_76")
    assert response.status_code == 200
    item = response.json()
    assert item["id"] == "1528_76"
    assert item["camera_id"] == 1528
    assert item["starting_frame_id"] == 76
    assert item["city"] == "Shibin El Kom"

def test_get_incident_by_rowid(client):
    # Lookup by rowid 1
    response = client.get("/api/incidents/1")
    assert response.status_code == 200
    item = response.json()
    assert item["camera_id"] == 1528
    assert item["starting_frame_id"] == 76

def test_get_incident_not_found(client):
    response = client.get("/api/incidents/9999_9999")
    assert response.status_code == 404
    data = response.json()
    assert data["code"] == "NOT_FOUND"
    assert "message" in data

def test_path_traversal_validation(client):
    # Invalid characters triggering sanitize_id validation error
    response = client.get("/api/incidents/invalid..id")
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "INVALID_ID"
    assert "Invalid identifier format" in data["message"]

    # Traversal attempt
    response2 = client.get("/api/incidents/..%2F..%2Fetc%2Fpasswd")
    assert response2.status_code in (400, 404)
    data2 = response2.json()
    assert "code" in data2
