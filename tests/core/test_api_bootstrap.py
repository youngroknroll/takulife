def test_api_root_returns_product_name(client):
    response = client.get("/api/")

    assert response.status_code == 200
    assert response.json()["name"] == "OshiLog API"


def test_health_endpoint_returns_ok(client):
    response = client.get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
