"""스태프 대시보드 "시스템 오류" 패널 검증
(트랙 36 S7, prompt_plan.md 트랙 36 EG-24·EG-25 참고).
"""
import pytest

from core.error_groups import compute_fingerprint
from core.models import ErrorGroup

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_대시보드는_오류_유형에_스크립트가_섞여도_이스케이프해서_보여준다(staff_client):
    staff, client = staff_client()
    dangerous_type = "<script>alert(1)</script>"
    ErrorGroup.objects.create(
        source=ErrorGroup.Source.BACKEND,
        fingerprint=compute_fingerprint("backend", dangerous_type, "GET /x/"),
        error_type=dangerous_type,
        location="GET /x/",
    )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in content
    assert "<script>alert(1)" not in content
    assert resp.context["system_errors"]["total"] == 1


@pytest.mark.django_db
def test_대시보드는_시스템_오류_묶음이_없으면_빈_상태_문구를_보여준다(staff_client):
    staff, client = staff_client()

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "최근 발생한 시스템 오류가 없습니다" in content
    assert resp.context["system_errors"]["total"] == 0
