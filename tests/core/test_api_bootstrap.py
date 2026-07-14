import pytest
from django.db import OperationalError, connection


def test_api_root_returns_product_name(client):
    response = client.get("/api/")

    assert response.status_code == 200
    assert response.json()["name"] == "takulife API"


@pytest.mark.django_db
def test_health_endpoint_returns_ok(client):
    response = client.get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_health_endpoint_returns_503_when_database_unreachable(client, monkeypatch):
    def _raise_operational_error():
        raise OperationalError("simulated DB outage")

    monkeypatch.setattr(connection, "ensure_connection", _raise_operational_error)
    response = client.get("/api/health/")

    assert response.status_code == 503
    assert response.json()["status"] == "error"
