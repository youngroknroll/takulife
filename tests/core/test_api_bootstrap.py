from django.db import OperationalError, connection
import pytest

from core import views as core_views

pytestmark = pytest.mark.web


@pytest.fixture(autouse=True)
def _reset_health_db_check_cache(monkeypatch):
    # 헬스 뷰는 마지막 DB 확인 시각을 프로세스 메모리에 두므로 테스트마다 비운다.
    monkeypatch.setattr(core_views, "_last_db_check_at", None)


def test_API_루트는_제품명을_응답한다(client):
    response = client.get("/api/")

    assert response.status_code == 200
    assert response.json()["name"] == "takulife API"


@pytest.mark.django_db
def test_헬스_엔드포인트는_정상이면_OK를_응답한다(client):
    response = client.get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.contract
@pytest.mark.django_db
def test_헬스_확인은_DB_점검이_실패하면_503을_응답하고_바로_다음_호출에서도_다시_점검한다(
    client, monkeypatch, django_assert_num_queries
):
    def _raise_operational_error(*args, **kwargs):
        raise OperationalError("simulated DB outage")

    real_cursor = connection.cursor
    monkeypatch.setattr(connection, "cursor", _raise_operational_error)
    failed = client.get("/api/health/")

    assert failed.status_code == 503
    assert failed.json() == {"status": "error"}

    monkeypatch.setattr(connection, "cursor", real_cursor)

    with django_assert_num_queries(1):
        recovered = client.get("/api/health/")

    assert recovered.status_code == 200
    assert recovered.json() == {"status": "ok"}


@pytest.mark.contract
@pytest.mark.django_db
def test_헬스_확인은_실패_뒤_복구되면_간격_안_재호출은_다시_점검을_건너뛴다(
    client, monkeypatch, django_assert_num_queries
):
    def _raise_operational_error(*args, **kwargs):
        raise OperationalError("simulated DB outage")

    real_cursor = connection.cursor
    monkeypatch.setattr(connection, "cursor", _raise_operational_error)
    client.get("/api/health/")

    monkeypatch.setattr(connection, "cursor", real_cursor)
    client.get("/api/health/")

    with django_assert_num_queries(0):
        response = client.get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.contract
@pytest.mark.django_db
def test_헬스_확인은_첫_호출에서_DB를_점검하고_간격_안_재호출은_점검을_건너뛴다(
    client, django_assert_num_queries
):
    with django_assert_num_queries(1):
        first = client.get("/api/health/")

    with django_assert_num_queries(0):
        second = client.get("/api/health/")

    assert first.status_code == 200
    assert first.json() == {"status": "ok"}
    assert second.status_code == 200
    assert second.json() == {"status": "ok"}


class _FakeMonotonicClock:
    """`time` 모듈을 대신하는, 제어 가능한 가짜 단조 시계."""

    def __init__(self, start):
        self._now = start

    def monotonic(self):
        return self._now

    def advance(self, seconds):
        self._now += seconds


@pytest.mark.contract
@pytest.mark.django_db
def test_헬스_확인은_점검_간격_30분이_지나면_DB를_다시_점검한다(
    client, django_assert_num_queries, monkeypatch
):
    clock = _FakeMonotonicClock(start=1000.0)
    monkeypatch.setattr(core_views, "time", clock)
    client.get("/api/health/")

    clock.advance(30 * 60 + 1)

    with django_assert_num_queries(1):
        response = client.get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.contract
@pytest.mark.django_db
def test_헬스_확인은_마지막_확인_뒤_정확히_30분이_되면_DB를_다시_점검한다(
    client, django_assert_num_queries, monkeypatch
):
    clock = _FakeMonotonicClock(start=1000.0)
    monkeypatch.setattr(core_views, "time", clock)
    client.get("/api/health/")

    clock.advance(30 * 60)

    with django_assert_num_queries(1):
        response = client.get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.contract
@pytest.mark.django_db
def test_헬스_확인은_마지막_확인_뒤_30분이_안_됐으면_DB_점검을_건너뛴다(
    client, django_assert_num_queries, monkeypatch
):
    clock = _FakeMonotonicClock(start=1000.0)
    monkeypatch.setattr(core_views, "time", clock)
    client.get("/api/health/")

    clock.advance(30 * 60 - 1)

    with django_assert_num_queries(0):
        response = client.get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
