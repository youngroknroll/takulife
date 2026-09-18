"""스태프 대시보드 "저장소" 패널 검증
(트랙 37 S3, prompt_plan.md 트랙 37 S2·S3 참고).
"""
from django.db import connection

import pytest

pytestmark = pytest.mark.web


@pytest.mark.django_db
@pytest.mark.skipif(connection.vendor != "postgresql", reason="Postgres 전용 저장소 크기 계약")
def test_대시보드는_저장소_패널에_전체_용량과_상위_테이블을_보여준다(staff_client):
    # RT-15
    staff, client = staff_client()

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    storage = resp.context["storage"]
    assert isinstance(storage["total_label"], str)
    content = resp.content.decode()
    assert "저장소" in content
    assert "<dl" in content
    assert storage["tables"][0]["name"] in content


@pytest.mark.django_db
def test_대시보드는_저장소_크기를_측정할_수_없으면_안내_문구를_보여준다(staff_client, monkeypatch):
    # RT-16
    monkeypatch.setattr("staff.views.database_size_summary", lambda: None)
    staff, client = staff_client()

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "저장소" in content
    assert "Postgres 외 엔진에서는 저장소 크기를 측정할 수 없습니다." in content


@pytest.mark.django_db
def test_대시보드는_전체_용량은_있지만_표_목록이_비면_표_안내_문구를_보여준다(staff_client, monkeypatch):
    # RT-19
    monkeypatch.setattr(
        "staff.views.database_size_summary",
        lambda: {"total_bytes": 1, "total_label": "0.0KB", "tables": []},
    )
    staff, client = staff_client()

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "저장소" in content
    assert "표 크기를 가져오지 못했습니다." in content
