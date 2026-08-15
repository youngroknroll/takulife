"""스태프 콘솔(/staff/) 인증·게이트·대시보드·리다이렉트 검증."""
import base64
import datetime
import re
import secrets
import string

import pytest
from django.utils import timezone

from drafts.models import DraftSource, EventDraft
from events.models import Event
from staff.models import StaffActionLog

pytestmark = pytest.mark.web


def _password():
    """소스 코드에 비밀번호 문자열을 남기지 않으려고 실행 시점에 생성한다."""
    return (
        secrets.choice(string.ascii_uppercase)
        + secrets.choice(string.ascii_lowercase)
        + secrets.choice(string.digits)
        + secrets.token_urlsafe(16)
    )


def _basic_auth(email, password):
    token = base64.b64encode(f"{email}:{password}".encode()).decode()
    return f"Basic {token}"


@pytest.mark.django_db
def test_http_basic_인증으로는_스태프_api에_인증할_수_없다(client, make_user):
    """Basic 인증은 CSRF를 우회하므로 세션 인증만 허용한다. 올바른 자격 증명이어도 미인증으로 처리된다."""
    password = _password()
    staff = make_user(password=password, is_staff=True)

    resp = client.get(
        "/api/event-drafts/stats/",
        HTTP_AUTHORIZATION=_basic_auth(staff.email, password),
    )

    assert resp.status_code == 403, resp.status_code


@pytest.mark.django_db
def test_익명_사용자가_대시보드에_접근하면_로그인_페이지로_리다이렉트된다(client):
    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 302
    assert resp.url == "/accounts/login/?next=/staff/dashboard/"


@pytest.mark.django_db
def test_일반_사용자가_대시보드에_접근하면_403이_된다(client, make_user):
    user = make_user()
    client.force_login(user)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 403


@pytest.mark.django_db
def test_로그인한_일반_사용자의_대시보드_요청은_리다이렉트를_따라가도_최종_403으로_끝난다(client, make_user):
    user = make_user()
    client.force_login(user)

    resp = client.get("/staff/dashboard/", follow=True)

    assert len(resp.redirect_chain) <= 1
    assert resp.status_code == 403


@pytest.mark.django_db
def test_대시보드는_대기중_드래프트_건수와_품질_경고_항목_5종을_컨텍스트로_제공한다(staff_client, make_draft):
    staff, client = staff_client()
    make_draft("https://example.com/a", extracted_title="드래프트 A", review_status=EventDraft.ReviewStatus.PENDING)
    make_draft("https://example.com/b", extracted_title="드래프트 B", review_status=EventDraft.ReviewStatus.APPROVED)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    assert resp.context["pending_count"] == 1
    quality_warnings = resp.context["quality_warnings"]
    assert isinstance(quality_warnings, dict)
    assert set(quality_warnings.keys()) == {
        "missing_official_url",
        "ended_still_published",
        "missing_dates",
        "missing_region",
        "needs_reverification",
        "total",
    }
    for value in quality_warnings.values():
        assert isinstance(value, int)


@pytest.mark.django_db
def test_대시보드_최근_활동_목록은_최신순으로_정렬된다(staff_client, make_draft):
    staff, client = staff_client()
    draft = make_draft("https://example.com/recent-action", extracted_title="드래프트 최근")
    first = StaffActionLog.objects.create(
        actor=staff, action=StaffActionLog.Action.APPROVE, target_draft=draft
    )
    second = StaffActionLog.objects.create(
        actor=staff, action=StaffActionLog.Action.REJECT, target_draft=draft
    )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    recent_actions = resp.context["recent_actions"]
    assert recent_actions is not None
    assert list(recent_actions) == [second, first]


@pytest.mark.django_db
def test_행위자와_대상_드래프트가_없는_최근_활동은_빈_값으로_렌더링된다(staff_client):
    staff, client = staff_client()
    StaffActionLog.objects.create(
        actor=None, action=StaffActionLog.Action.APPROVE, target_draft=None
    )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    # 대상 열(dash-cell-target)과 담당 열(dash-cell-faint) 둘 다 "-"로 표시돼야 한다.
    assert re.search(r'<td class="dash-cell-target">\s*-\s*</td>', content)
    assert re.search(r'<td class="mono dash-cell-faint">\s*-\s*</td>', content)


@pytest.mark.django_db
def test_홈_카테고리_변경_액션은_대시보드에_전용_한글_라벨로_표시된다(staff_client):
    staff, client = staff_client()
    StaffActionLog.objects.create(
        actor=staff, action=StaffActionLog.Action.HOME_CATEGORIES, target_draft=None
    )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "홈 카테고리 변경" in content
    assert "반려" not in content


@pytest.mark.django_db
def test_드래프트_수집_실행_액션은_대시보드에_전용_한글_라벨로_표시된다(staff_client):
    staff, client = staff_client()
    StaffActionLog.objects.create(
        actor=staff, action=StaffActionLog.Action.DRAFT_DISCOVER
    )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "드래프트 수집 실행" in content


@pytest.mark.django_db
def test_이벤트_수정_액션은_전용_라벨과_대상_이벤트_수정_페이지_링크를_함께_표시한다(staff_client):
    staff, client = staff_client()
    event = Event.objects.create(
        title="이벤트 A", publish_status=Event.PublishStatus.PUBLISHED
    )
    StaffActionLog.objects.create(
        actor=staff, action=StaffActionLog.Action.EVENT_UPDATE, target_event=event
    )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "이벤트 수정" in content
    assert f"/staff/events/{event.pk}/edit/" in content
    assert "이벤트 A" in content


@pytest.mark.django_db
def test_대시보드_드래프트_소스_목록은_비활성_우선_이름순으로_정렬된다(staff_client):
    staff, client = staff_client()
    disabled = DraftSource.objects.create(
        name="disabled-source",
        url="https://example.com/disabled-feed/",
        source_type=DraftSource.SourceType.RSS,
        enabled=False,
    )
    enabled = DraftSource.objects.create(
        name="enabled-source",
        url="https://example.com/enabled-feed/",
        source_type=DraftSource.SourceType.RSS,
        enabled=True,
    )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    draft_sources = resp.context["draft_sources"]
    assert list(draft_sources) == [enabled, disabled]


@pytest.mark.django_db
def test_최근_오류가_있는_소스는_대시보드에_오류_배지와_오류_요약을_보여준다(staff_client):
    staff, client = staff_client()
    DraftSource.objects.create(
        name="에러 소스",
        url="https://example.com/error-feed/",
        source_type=DraftSource.SourceType.RSS,
        enabled=True,
        last_error="Connection timed out while fetching feed",
    )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "dash-status-badge--error" in content
    assert "Connection timed out" in content


@pytest.mark.django_db
def test_한번도_수집되지_않은_활성_소스는_대시보드에_지연_배지를_보여준다(staff_client):
    staff, client = staff_client()
    DraftSource.objects.create(
        name="미수집 소스",
        url="https://example.com/never-checked-feed/",
        source_type=DraftSource.SourceType.RSS,
        enabled=True,
        last_checked_at=None,
    )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    assert "dash-status-badge--stale" in resp.content.decode()


@pytest.mark.django_db
def test_지연_임계_시간을_넘겨_수집된_활성_소스는_대시보드에_지연_배지를_보여준다(staff_client, settings):
    settings.DRAFT_SOURCE_STALE_HOURS = 48
    staff, client = staff_client()
    DraftSource.objects.create(
        name="지연 소스",
        url="https://example.com/stale-feed/",
        source_type=DraftSource.SourceType.RSS,
        enabled=True,
        last_checked_at=timezone.now() - datetime.timedelta(hours=49),
    )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    assert "dash-status-badge--stale" in resp.content.decode()


@pytest.mark.django_db
def test_지연_임계_시간_이내에_수집된_활성_소스는_지연_배지를_보여주지_않는다(staff_client, settings):
    settings.DRAFT_SOURCE_STALE_HOURS = 48
    staff, client = staff_client()
    DraftSource.objects.create(
        name="정상 소스",
        url="https://example.com/fresh-feed/",
        source_type=DraftSource.SourceType.RSS,
        enabled=True,
        last_checked_at=timezone.now() - datetime.timedelta(hours=1),
    )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    assert "dash-status-badge--stale" not in resp.content.decode()


@pytest.mark.django_db
def test_비활성_소스는_한번도_수집되지_않았어도_지연_배지를_보여주지_않는다(staff_client):
    staff, client = staff_client()
    DraftSource.objects.create(
        name="비활성 소스",
        url="https://example.com/disabled-feed/",
        source_type=DraftSource.SourceType.RSS,
        enabled=False,
        last_checked_at=None,
    )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    assert "dash-status-badge--stale" not in resp.content.decode()


@pytest.mark.django_db
def test_드래프트_수집_실행_로그가_전혀_없으면_대시보드는_실행_이력_없음을_보여준다(staff_client):
    staff, client = staff_client()

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    assert resp.context["last_discovery_run_at"] is None
    assert "실행 이력 없음" in resp.content.decode()


@pytest.mark.django_db
def test_수집_실행이_아닌_액션_로그만_있으면_대시보드는_실행_이력_없음을_보여준다(staff_client):
    staff, client = staff_client()
    StaffActionLog.objects.create(actor=staff, action=StaffActionLog.Action.APPROVE)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    assert resp.context["last_discovery_run_at"] is None
    assert "실행 이력 없음" in resp.content.decode()


@pytest.mark.django_db
def test_대시보드는_가장_최근_드래프트_수집_실행_시각을_보여준다(staff_client):
    staff, client = staff_client()
    log = StaffActionLog.objects.create(
        actor=staff, action=StaffActionLog.Action.DRAFT_DISCOVER
    )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    assert resp.context["last_discovery_run_at"] == log.created_at
    content = resp.content.decode()
    assert "마지막 실행" in content
    assert "실행 이력 없음" not in content


@pytest.mark.django_db
def test_등록된_드래프트_소스가_없으면_대시보드_소스_목록은_비어있다(staff_client):
    staff, client = staff_client()

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    assert list(resp.context["draft_sources"]) == []


@pytest.mark.django_db
def test_스태프_루트_경로는_대시보드로_리다이렉트된다(staff_client):
    staff, client = staff_client()

    resp = client.get("/staff/")

    assert resp.status_code == 302
    assert resp.url == "/staff/dashboard/"


@pytest.mark.django_db
def test_예전_드래프트_목록_url은_새_스태프_경로로_리다이렉트된다(client):
    resp = client.get("/event-drafts/")

    assert resp.status_code == 302
    assert resp.url == "/staff/drafts/"


@pytest.mark.django_db
def test_예전_드래프트_목록_url_리다이렉트는_next_쿼리_문자열을_보존한다(client):
    resp = client.get("/event-drafts/?next=/x")

    assert resp.status_code == 302
    assert resp.url == "/staff/drafts/?next=/x"


@pytest.mark.django_db
def test_예전_드래프트_상세_url은_새_스태프_경로로_리다이렉트된다(client):
    resp = client.get("/event-drafts/5/")

    assert resp.status_code == 302
    assert resp.url == "/staff/drafts/5/"


@pytest.mark.django_db
def test_스태프는_새_드래프트_목록_경로에_접근할_수_있다(staff_client):
    staff, client = staff_client()

    resp = client.get("/staff/drafts/")

    assert resp.status_code == 200


@pytest.mark.django_db
def test_스태프는_새_드래프트_상세_경로에_접근할_수_있다(staff_client, make_draft):
    staff, client = staff_client()
    draft = make_draft("https://example.com/c", extracted_title="드래프트 C")

    resp = client.get(f"/staff/drafts/{draft.id}/")

    assert resp.status_code == 200


@pytest.mark.django_db
def test_스태프는_홈_카테고리_관리_경로에_접근할_수_있다(staff_client):
    staff, client = staff_client()

    resp = client.get("/staff/home-categories/")

    assert resp.status_code == 200


@pytest.mark.django_db
def test_익명_사용자가_홈_카테고리_관리_경로에_접근하면_로그인_페이지로_리다이렉트된다(client):
    resp = client.get("/staff/home-categories/")

    assert resp.status_code == 302
    assert resp.url == "/accounts/login/?next=/staff/home-categories/"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    [
        "/staff/dashboard/",
        "/staff/drafts/",
        "/staff/drafts/1/",
        "/staff/home-categories/",
    ],
    ids=["대시보드", "드래프트_목록", "드래프트_상세", "홈_카테고리"],
)
def test_일반_사용자는_새_스태프_경로_전부에서_403으로_차단된다(client, make_user, path):
    user = make_user()
    client.force_login(user)

    resp = client.get(path)

    assert resp.status_code == 403


@pytest.mark.django_db
def test_최근_7일_처리_건수는_최근_활동_목록_표시_제한과_무관하게_실제_건수를_반영한다(staff_client):
    staff, client = staff_client()
    for _ in range(12):
        StaffActionLog.objects.create(actor=staff, action=StaffActionLog.Action.APPROVE)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "최근 7일 처리" in content
    assert "12건" in content


@pytest.mark.django_db
def test_대시보드는_지난주_처리_건수를_함께_보여준다(staff_client):
    staff, client = staff_client()
    for _ in range(2):
        StaffActionLog.objects.create(actor=staff, action=StaffActionLog.Action.APPROVE)
    for _ in range(3):
        log = StaffActionLog.objects.create(actor=staff, action=StaffActionLog.Action.APPROVE)
        StaffActionLog.objects.filter(pk=log.pk).update(
            created_at=timezone.now() - datetime.timedelta(days=10)
        )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    assert "지난주 3건" in resp.content.decode()


@pytest.mark.django_db
def test_대기중_건수_요약_카드는_대기중_드래프트_목록으로_연결된다(staff_client):
    staff, client = staff_client()

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert '<a class="dash-metric dash-metric-link" href="/staff/drafts/?status=pending">' in content


def _clean_quality_event_kwargs(index):
    """품질 경고 4종 중 아무것도 걸리지 않는 이벤트 필드값."""
    today = timezone.localdate()
    return {
        "official_url": f"https://example.com/quality-warning-{index}",
        "start_date": today,
        "end_date": today + datetime.timedelta(days=30),
        "region": "서울",
    }


@pytest.mark.django_db
def test_품질_경고_4종은_각각_필터_링크가_달린_막대로_렌더링된다(staff_client, make_event):
    staff, client = staff_client()
    make_event()

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "dash-warning-list" in content
    for key in (
        "missing_official_url",
        "ended_still_published",
        "missing_dates",
        "missing_region",
    ):
        assert f"?warning={key}" in content


@pytest.mark.django_db
def test_품질_경고_막대는_건수_내림차순으로_정렬된다(staff_client, make_event):
    staff, client = staff_client()
    for i in range(3):
        kwargs = _clean_quality_event_kwargs(i)
        kwargs.pop("region")
        make_event(**kwargs)
    kwargs = _clean_quality_event_kwargs(100)
    kwargs.pop("official_url")
    make_event(**kwargs)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert content.index("지역 정보 없음") < content.index("공식 URL 없음")


@pytest.mark.django_db
def test_건수가_0인_품질_경고는_막대_채움을_렌더링하지_않는다(staff_client, make_event):
    staff, client = staff_client()
    kwargs = _clean_quality_event_kwargs(0)
    kwargs.pop("region")
    # start_date/end_date가 D-7 재확인 창에도 걸리므로 verified_at을 명시해 needs_reverification까지 함께 트립되는 것을 막는다.
    kwargs["verified_at"] = timezone.now()
    make_event(**kwargs)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert content.count("dash-warning-fill") == 1


@pytest.mark.django_db
def test_품질_경고_표는_시작_임박_미확인_행을_렌더링한다(staff_client, make_event):
    staff, client = staff_client()
    make_event(**_clean_quality_event_kwargs(0))

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "시작 임박, 미확인" in content
    assert "?warning=needs_reverification" in content


@pytest.mark.django_db
def test_품질_경고가_하나도_없으면_대시보드는_경고_없음_안내를_보여준다(staff_client):
    staff, client = staff_client()

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "현재 품질 경고가 없습니다" in content
    assert "dash-warning-list" not in content


@pytest.mark.django_db
def test_재확인_대상만_있어도_대시보드는_경고_없음_안내를_보여주지_않고_히어로_카드에_실제_값을_보여준다(
    staff_client, make_event
):
    """total은 needs_reverification(5번째 경고)을 빼고 세므로, 이것만 걸리면 total==0이어도 표는 남아야 한다."""
    staff, client = staff_client()
    # 앞 4개 경고는 모두 정상값으로 채우고 verified_at만 비워서 needs_reverification만 D-7 창에서 트립되게 한다.
    kwargs = _clean_quality_event_kwargs(0)
    make_event(**kwargs)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "dash-warning-list" in content
    assert "현재 품질 경고가 없습니다" not in content
    # 품질 경고 히어로 카드(total)는 0건이어도 값 자체는 계속 렌더링돼야 한다.
    quality_card = re.search(
        r'<p class="dash-metric-label">품질 경고</p>.*?</article>', content, re.S
    )
    assert quality_card
    assert re.search(
        r'<span class="mono dash-metric-value">0</span>\s*'
        r'<span class="dash-metric-unit">건</span>',
        quality_card.group(),
    )
    # total은 needs_reverification을 빼고 센다(events/queries.py의
    # published_quality_warnings). 문구가 "포함"이라고 말하면 사실과 반대다.
    assert "시작 임박·미확인 1건은 이 합계에 없음" in quality_card.group()


@pytest.mark.django_db
def test_건수가_동률인_품질_경고는_라벨_정의_순서대로_렌더링된다(
    staff_client, make_event
):
    """건수가 같으면 sort() 결과 순서가 아니라 QUALITY_WARNING_LABELS 정의 순서로 렌더링돼야 한다."""
    staff, client = staff_client()
    kwargs0 = _clean_quality_event_kwargs(0)
    kwargs0.pop("official_url")
    make_event(**kwargs0)
    kwargs1 = _clean_quality_event_kwargs(1)
    kwargs1["start_date"] = None
    kwargs1["end_date"] = None
    make_event(**kwargs1)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert content.index("공식 URL 없음") < content.index("날짜 정보 누락")


@pytest.mark.django_db
def test_최근_활동_차트는_항상_14개_열을_렌더링한다(staff_client):
    staff, client = staff_client()
    StaffActionLog.objects.create(actor=staff, action=StaffActionLog.Action.APPROVE)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    columns = re.findall(r'<span class="dash-activity-col[^"]*"', content)
    assert len(columns) == 14


@pytest.mark.django_db
def test_최근_활동_차트는_마지막_열_하나만_오늘로_표시한다(staff_client):
    staff, client = staff_client()
    StaffActionLog.objects.create(actor=staff, action=StaffActionLog.Action.APPROVE)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    columns = re.findall(r'<span class="dash-activity-col[^"]*"', content)
    assert sum(1 for col in columns if "dash-activity-col--today" in col) == 1
    assert "dash-activity-col--today" in columns[-1]


@pytest.mark.django_db
def test_최근_활동_차트_막대_높이는_일별_최대_건수_대비_비율로_계산된다(staff_client):
    staff, client = staff_client()
    for _ in range(2):
        StaffActionLog.objects.create(actor=staff, action=StaffActionLog.Action.APPROVE)
    yesterday_log = StaffActionLog.objects.create(actor=staff, action=StaffActionLog.Action.APPROVE)
    StaffActionLog.objects.filter(pk=yesterday_log.pk).update(
        created_at=timezone.now() - datetime.timedelta(days=1)
    )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "--col-h: 100%" in content
    assert "--col-h: 50%" in content


@pytest.mark.django_db
def test_액션_로그가_없으면_최근_활동_차트_대신_안내_문구를_보여준다(staff_client):
    staff, client = staff_client()

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "최근 14일 처리 내역이 없습니다" in content
    assert "dash-activity-columns" not in content


@pytest.mark.django_db
def test_최근_수집된_활성_소스는_정상_상태_배지로_표시된다(staff_client):
    staff, client = staff_client()
    DraftSource.objects.create(
        name="정상 소스",
        url="https://example.com/status-ok-feed/",
        source_type=DraftSource.SourceType.RSS,
        enabled=True,
        last_checked_at=timezone.now() - datetime.timedelta(hours=1),
    )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    # 새 디자인은 상태별 색을 점(span) 자체가 아니라 감싸는 배지 수식자 클래스가 진다.
    assert re.search(
        r'<span class="dash-status-badge dash-status-badge--ok">\s*'
        r'<span class="dash-status-dot" aria-hidden="true"></span>\s*활성',
        content,
    )


@pytest.mark.django_db
def test_비활성_소스는_비활성_상태_배지로_표시된다(staff_client):
    staff, client = staff_client()
    DraftSource.objects.create(
        name="비활성 소스",
        url="https://example.com/status-disabled-feed/",
        source_type=DraftSource.SourceType.RSS,
        enabled=False,
    )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert re.search(
        r'<span class="dash-status-badge dash-status-badge--disabled">\s*'
        r'<span class="dash-status-dot" aria-hidden="true"></span>\s*비활성',
        content,
    )


@pytest.mark.django_db
def test_최근_오류가_있는_활성_소스는_오류_상태_배지로_표시된다(staff_client):
    staff, client = staff_client()
    DraftSource.objects.create(
        name="에러 소스",
        url="https://example.com/status-error-feed/",
        source_type=DraftSource.SourceType.RSS,
        enabled=True,
        last_checked_at=timezone.now() - datetime.timedelta(hours=1),
        last_error="Connection timed out while fetching feed",
    )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert re.search(
        r'<span class="dash-status-badge dash-status-badge--error">\s*'
        r'<span class="dash-status-dot" aria-hidden="true"></span>\s*오류',
        content,
    )


@pytest.mark.django_db
def test_한번도_수집되지_않은_활성_소스는_지연_상태_배지로_표시된다(staff_client):
    staff, client = staff_client()
    DraftSource.objects.create(
        name="미수집 소스",
        url="https://example.com/status-stale-feed/",
        source_type=DraftSource.SourceType.RSS,
        enabled=True,
        last_checked_at=None,
    )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert re.search(
        r'<span class="dash-status-badge dash-status-badge--stale">\s*'
        r'<span class="dash-status-dot" aria-hidden="true"></span>\s*지연',
        content,
    )


@pytest.mark.django_db
def test_오류와_지연이_동시에_성립하면_상태_배지는_지연보다_오류를_우선한다(staff_client):
    """미수집+오류가 동시에 성립할 수 있어, 상태 배지가 소스 이름 옆 오류 요약과 어긋나지 않도록 오류를 우선한다."""
    staff, client = staff_client()
    DraftSource.objects.create(
        name="에러+지연 소스",
        url="https://example.com/status-error-and-stale-feed/",
        source_type=DraftSource.SourceType.RSS,
        enabled=True,
        last_checked_at=None,
        last_error="Connection timed out while fetching feed",
    )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "dash-status-badge--error" in content
    assert "dash-status-badge--stale" not in content


@pytest.mark.django_db
def test_지금_수집_폼은_연타_가드를_옵트인한다(staff_client):
    """속성 하나가 가드의 전부라 대시보드를 다시 생성하면 조용히 사라진다."""
    _, client = staff_client()

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    form = re.search(
        r'<form[^>]*action="[^"]*draft-discovery[^"]*"[^>]*>',
        resp.content.decode(),
    ) or re.search(r'<form[^>]*dash-panel-head-action[^>]*>', resp.content.decode())
    assert form, "지금 수집 폼을 찾지 못했다"
    assert "data-submit-guard" in form.group()


@pytest.mark.django_db
def test_검색을_지원하지_않는_화면에는_검색창이_없다(staff_client):
    """대시보드에 검색창을 띄우면 눌러도 아무 일이 없다."""
    _, client = staff_client()

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    assert 'id="staff-commandbar-q"' not in resp.content.decode()


@pytest.mark.django_db
def test_검색을_지원하는_화면에는_검색창이_있다(staff_client):
    _, client = staff_client()

    resp = client.get("/staff/audit-log/")

    assert resp.status_code == 200
    assert 'id="staff-commandbar-q"' in resp.content.decode()
