"""스태프 대시보드 주간 분석 요약 검증."""
import re

import pytest

from core.models import AnalyticsEvent

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_대시보드는_주간_활성_사용자_수를_보여준다(staff_client):
    staff, client = staff_client()
    AnalyticsEvent.objects.create(
        event_name=AnalyticsEvent.EventName.EVENT_LIST_VIEWED, user_key="user-a"
    )
    AnalyticsEvent.objects.create(
        event_name=AnalyticsEvent.EventName.EVENT_SEARCHED, user_key="user-a"
    )
    AnalyticsEvent.objects.create(
        event_name=AnalyticsEvent.EventName.EVENT_LIST_VIEWED, user_key="user-b"
    )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "주간 활성 사용자" in content
    assert resp.context["weekly_active_user_count"] == 2
    # 값(mono dash-metric-value)과 단위(dash-metric-unit)가 각각 다른 span이라
    # "2명"이 문자열로 이어 붙어 있지 않다 — 값·단위가 같은 카드에 나란히
    # 렌더링됐는지를 함께 확인한다.
    assert re.search(
        r'<span class="mono dash-metric-value">2</span>\s*'
        r'<span class="dash-metric-unit">명</span>',
        content,
    )


@pytest.mark.django_db
def test_대시보드는_주간_이벤트_기록_건수를_보여준다(staff_client):
    staff, client = staff_client()
    for _ in range(3):
        AnalyticsEvent.objects.create(
            event_name=AnalyticsEvent.EventName.EVENT_LIST_VIEWED, user_key="user-a"
        )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "주간 이벤트 기록" in content
    assert resp.context["weekly_event_count"] == 3
    assert re.search(
        r'<span class="mono dash-metric-value">3</span>\s*'
        r'<span class="dash-metric-unit">건</span>',
        content,
    )


@pytest.mark.django_db
def test_분석_이벤트가_없으면_대시보드는_0명_0건으로_표시한다(staff_client):
    staff, client = staff_client()

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    # "0건"을 본문 전체에서 찾으면 검토 대기·품질 경고 카드의 0에도 걸린다.
    # 해당 카드 안으로 좁혀야 이 카드가 0을 보여준다는 증거가 된다.
    assert resp.context["weekly_active_user_count"] == 0
    assert resp.context["weekly_event_count"] == 0
    for label, unit in (("주간 활성 사용자", "명"), ("주간 이벤트 기록", "건")):
        card = re.search(
            rf'<p class="dash-metric-label">{label}</p>.*?</article>', content, re.S
        )
        assert card, label
        assert re.search(
            r'<span class="mono dash-metric-value">0</span>\s*'
            rf'<span class="dash-metric-unit">{unit}</span>',
            card.group(),
        ), label
