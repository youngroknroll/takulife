"""core.error_groups.system_error_summary 검증
(트랙 36 S7, prompt_plan.md 트랙 36 EG-22·EG-23 참고).

대시보드 "시스템 오류" 패널이 그대로 쓸 dict 계약을 고정한다 — 프론트
템플릿은 이 함수가 반환하는 키만 보고 렌더링을 짠다.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

pytestmark = pytest.mark.domain


def _make_group(*, source, error_type, location, last_seen, count=1):
    from core.models import ErrorGroup

    return ErrorGroup.objects.create(
        source=source,
        fingerprint=f"{source}-{error_type}-{location}".ljust(64, "0")[:64],
        error_type=error_type,
        location=location,
        message_sample="",
        first_seen=last_seen,
        last_seen=last_seen,
        count=count,
    )


@pytest.mark.django_db
def test_시스템_오류_요약은_24시간_7일_창_출처별_상위_묶음을_계산한다():
    from core.error_groups import system_error_summary
    from core.models import ErrorGroup

    now = timezone.now()
    recent_backend = _make_group(
        source=ErrorGroup.Source.BACKEND,
        error_type="KeyError",
        location="GET /a/",
        last_seen=now - timedelta(hours=1),
        count=3,
    )
    within_week_frontend = _make_group(
        source=ErrorGroup.Source.FRONTEND,
        error_type="TypeError",
        location="app.js:10",
        last_seen=now - timedelta(days=2),
        count=5,
    )
    _old_backend = _make_group(
        source=ErrorGroup.Source.BACKEND,
        error_type="ValueError",
        location="POST /b/",
        last_seen=now - timedelta(days=10),
        count=1,
    )

    summary = system_error_summary(now=now, limit=5)

    assert summary["total"] == 3
    assert summary["window_24h"] == 1
    assert summary["window_7d"] == 2
    assert summary["by_source"] == {"backend": 2, "frontend": 1}

    top = summary["top"]
    assert len(top) == 3
    assert [row["location"] for row in top] == [
        recent_backend.location,
        within_week_frontend.location,
        _old_backend.location,
    ]
    assert top[0] == {
        "source": "backend",
        "source_label": "백엔드",
        "error_type": "KeyError",
        "location": "GET /a/",
        "count": 3,
        "last_seen": recent_backend.last_seen,
    }
    assert top[1]["source_label"] == "프론트"


@pytest.mark.django_db
def test_시스템_오류_요약은_묶음이_없으면_모두_0이고_출처_키는_유지한다():
    from core.error_groups import system_error_summary

    summary = system_error_summary(now=timezone.now(), limit=5)

    assert summary["total"] == 0
    assert summary["window_24h"] == 0
    assert summary["window_7d"] == 0
    assert summary["by_source"] == {"backend": 0, "frontend": 0}
    assert summary["top"] == []


@pytest.mark.django_db
def test_시스템_오류_요약은_상위_목록을_limit_개수로_자른다():
    from core.error_groups import system_error_summary
    from core.models import ErrorGroup

    now = timezone.now()
    for index in range(6):
        _make_group(
            source=ErrorGroup.Source.BACKEND,
            error_type=f"Error{index}",
            location=f"GET /{index}/",
            last_seen=now - timedelta(minutes=index),
        )

    summary = system_error_summary(now=now, limit=5)

    assert summary["total"] == 6
    assert len(summary["top"]) == 5
    assert summary["top"][0]["error_type"] == "Error0"


@pytest.mark.django_db
def test_시스템_오류_요약_쿼리_수는_묶음_유무와_무관하게_고정이다(django_assert_num_queries):
    from core.error_groups import system_error_summary
    from core.models import ErrorGroup

    now = timezone.now()

    with django_assert_num_queries(2):
        system_error_summary(now=now, limit=5)

    for index in range(10):
        _make_group(
            source=ErrorGroup.Source.BACKEND if index % 2 else ErrorGroup.Source.FRONTEND,
            error_type=f"Error{index}",
            location=f"GET /{index}/",
            last_seen=now - timedelta(minutes=index),
        )

    with django_assert_num_queries(2):
        system_error_summary(now=now, limit=5)
