import pytest
from django.db import OperationalError, connection

pytestmark = pytest.mark.web


def test_API_루트는_제품명을_응답한다(client):
    response = client.get("/api/")

    assert response.status_code == 200
    assert response.json()["name"] == "takulife API"


@pytest.mark.django_db
def test_헬스_엔드포인트는_정상이면_OK를_응답한다(client):
    response = client.get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_헬스_엔드포인트는_데이터베이스_연결_불가시_503을_응답한다(client, monkeypatch):
    def _raise_operational_error():
        raise OperationalError("simulated DB outage")

    monkeypatch.setattr(connection, "ensure_connection", _raise_operational_error)
    response = client.get("/api/health/")

    assert response.status_code == 503
    assert response.json()["status"] == "error"
