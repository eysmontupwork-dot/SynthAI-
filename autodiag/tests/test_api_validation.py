def test_api_requires_token(client):
    resp = client.get("/api/cars")
    assert resp.status_code == 401


def test_public_page_loads_without_token(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_add_car_requires_brand_and_model(client, auth_headers):
    resp = client.post("/api/cars", json={}, headers=auth_headers)
    assert resp.status_code == 400


def test_add_car_success(client, auth_headers):
    resp = client.post(
        "/api/cars",
        json={"brand": "Ford", "model": "Focus", "year": "2015"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["brand"] == "Ford"
    assert data["model"] == "Focus"
    assert "id" in data
    assert data["diagnostics"] == []


def test_add_car_then_list(client, auth_headers):
    client.post("/api/cars", json={"brand": "Toyota", "model": "Corolla"}, headers=auth_headers)
    resp = client.get("/api/cars", headers=auth_headers)
    assert resp.status_code == 200
    cars = resp.get_json()
    assert len(cars) == 1
    assert cars[0]["brand"] == "Toyota"


def test_add_diagnostic_requires_text(client, auth_headers):
    car_resp = client.post("/api/cars", json={"brand": "Ford", "model": "Focus"}, headers=auth_headers)
    car_id = car_resp.get_json()["id"]
    resp = client.post(f"/api/cars/{car_id}/diagnostic", json={}, headers=auth_headers)
    assert resp.status_code == 400


def test_add_diagnostic_unknown_car_returns_404(client, auth_headers):
    resp = client.post("/api/cars/doesnotexist/diagnostic", json={"text": "hello"}, headers=auth_headers)
    assert resp.status_code == 404


def test_add_adapter_requires_name(client, auth_headers):
    resp = client.post("/api/adapters", json={}, headers=auth_headers)
    assert resp.status_code == 400
