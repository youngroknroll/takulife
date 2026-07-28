"""Staff Console (/staff/) — PR-1a: auth pin, console gate, dashboard, redirects."""
import base64
import datetime
import re
import secrets
import string

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from drafts.models import DraftSource, EventDraft
from events.models import Event
from staff.models import StaffActionLog

pytestmark = pytest.mark.web


def _password():
    """Runtime password with guaranteed complexity, no literal in source."""
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
    """HTTP Basic auth must NOT authenticate against staff DRF endpoints — Basic
    bypasses CSRF, so only SessionAuthentication is accepted. A valid staff
    credential sent via Basic is treated as unauthenticated (403)."""
    password = _password()
    staff = make_user(password=password, is_staff=True)

    resp = client.get(
        "/api/event-drafts/stats/",
        HTTP_AUTHORIZATION=_basic_auth(staff.email, password),
    )

    assert resp.status_code == 403, resp.status_code


# ---------------------------------------------------------------------------
# Console gate (staff_console_required)
# ---------------------------------------------------------------------------

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
def test_대시보드는_대기중_드래프트_건수와_품질_경고_항목_6종을_컨텍스트로_제공한다(staff_client, make_draft):
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
        "missing_poster",
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
    assert "<td>-</td>" in content  # actor.email default fallback
    assert re.search(r"<td>\s*-\s*</td>", content)  # target_draft else branch


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
    """PR-D1 item 1: draft_discover must render its own Korean label, not
    fall through to the "홈 카테고리 변경" catch-all."""
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
    """PR-D1 item 1: event_* actions get their own Korean label and the
    target column links to the event's staff edit page (not "-")."""
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
    """PR-5b: dashboard() must pass draft_sources via drafts.queries.list_draft_sources()
    (-enabled, name ordering), not a raw DraftSource query in the view."""
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
    """PR-D1 item 3: a source with a non-empty last_error gets an error
    badge plus a (truncated) summary of the error text."""
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
    assert "badge-error" in content
    assert "Connection timed out" in content


@pytest.mark.django_db
def test_한번도_수집되지_않은_활성_소스는_대시보드에_지연_배지를_보여준다(staff_client):
    """PR-D1 item 3: an enabled source that has never been checked
    (last_checked_at is None) is stale."""
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
    assert "badge-stale" in resp.content.decode()


@pytest.mark.django_db
def test_지연_임계_시간을_넘겨_수집된_활성_소스는_대시보드에_지연_배지를_보여준다(staff_client, settings):
    """PR-D1 item 3: an enabled source checked longer ago than
    DRAFT_SOURCE_STALE_HOURS is stale."""
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
    assert "badge-stale" in resp.content.decode()


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
    assert "badge-stale" not in resp.content.decode()


@pytest.mark.django_db
def test_비활성_소스는_한번도_수집되지_않았어도_지연_배지를_보여주지_않는다(staff_client):
    """PR-D1 item 3: a disabled source is excluded from the stale check
    regardless of last_checked_at (it is not expected to be collecting)."""
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
    assert "badge-stale" not in resp.content.decode()


@pytest.mark.django_db
def test_드래프트_수집_실행_로그가_전혀_없으면_대시보드는_실행_이력_없음을_보여준다(staff_client):
    """PR-D1 item 4: with no DRAFT_DISCOVER log at all, the dashboard shows
    "실행 이력 없음" rather than a blank/misleading timestamp."""
    staff, client = staff_client()

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    assert resp.context["last_discovery_run_at"] is None
    assert "실행 이력 없음" in resp.content.decode()


@pytest.mark.django_db
def test_수집_실행이_아닌_액션_로그만_있으면_대시보드는_실행_이력_없음을_보여준다(staff_client):
    """PR-D1 item 4: a non-DRAFT_DISCOVER log entry must not be mistaken for
    a discovery run."""
    staff, client = staff_client()
    StaffActionLog.objects.create(actor=staff, action=StaffActionLog.Action.APPROVE)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    assert resp.context["last_discovery_run_at"] is None
    assert "실행 이력 없음" in resp.content.decode()


@pytest.mark.django_db
def test_대시보드는_가장_최근_드래프트_수집_실행_시각을_보여준다(staff_client):
    """PR-D1 item 4: the most recent DRAFT_DISCOVER log's created_at is
    surfaced as last_discovery_run_at and rendered near the run button."""
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


# ---------------------------------------------------------------------------
# Relocation + backward-compat redirects
# ---------------------------------------------------------------------------

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
    """staff_console_required's anonymous branch (redirect, not 403) — the
    non-staff 403 case for this path is already covered by
    test_non_staff_blocked_from_new_staff_paths below."""
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


# ---------------------------------------------------------------------------
# Hero summary-grid: 최근 7일 처리 카운트 + 검토 대기 카드 링크 (Phase 2)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_최근_7일_처리_건수는_최근_활동_목록_표시_제한과_무관하게_실제_건수를_반영한다(staff_client):
    """recent_actions_7d_count must reflect the true 7-day count, not the
    recent_actions list's limit=10 cap (regression guard)."""
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
    assert '<a class="summary-card summary-card-link" href="/staff/drafts/?status=pending">' in content


# ---------------------------------------------------------------------------
# 품질 경고 바 리스트 (Phase 3)
# ---------------------------------------------------------------------------

def _clean_quality_event_kwargs(index):
    """Field values for a published Event that trips none of the 5 quality
    warnings (unique official_url, both dates set with end_date in the
    future, non-blank region). poster_image is deliberately NOT included
    here — callers that want a fully clean event must also attach an
    uploaded poster_image and save() (see events/queries.py predicates)."""
    today = timezone.localdate()
    return {
        "official_url": f"https://example.com/quality-warning-{index}",
        "start_date": today,
        "end_date": today + datetime.timedelta(days=30),
        "region": "서울",
    }


def _attach_poster(event, png_bytes, index):
    event.poster_image = SimpleUploadedFile(
        f"quality-warning-poster-{index}.png", png_bytes(), content_type="image/png"
    )
    event.save()
    return event


@pytest.mark.django_db
def test_품질_경고_5종은_각각_필터_링크가_달린_막대로_렌더링된다(staff_client, make_event):
    staff, client = staff_client()
    make_event()  # bare event trips several warnings at once

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "warning-bars" in content
    for key in (
        "missing_official_url",
        "ended_still_published",
        "missing_poster",
        "missing_dates",
        "missing_region",
    ):
        assert f"?warning={key}" in content


@pytest.mark.django_db
def test_품질_경고_막대는_건수_내림차순으로_정렬된다(staff_client, make_event, png_bytes):
    staff, client = staff_client()
    # 3 events trip only missing_poster (poster left unset).
    for i in range(3):
        make_event(**_clean_quality_event_kwargs(i))
    # 1 event trips only missing_official_url (official_url left unset).
    kwargs = _clean_quality_event_kwargs(100)
    kwargs.pop("official_url")
    event = make_event(**kwargs)
    _attach_poster(event, png_bytes, 100)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert content.index("포스터 없음") < content.index("공식 URL 없음")


@pytest.mark.django_db
def test_건수가_0인_품질_경고는_막대_채움을_렌더링하지_않는다(staff_client, make_event, png_bytes):
    """Only missing_region trips (count=1); the other 4 warnings stay at 0
    and must not render a .warning-bar-fill span."""
    staff, client = staff_client()
    kwargs = _clean_quality_event_kwargs(0)
    kwargs.pop("region")
    event = make_event(**kwargs)
    _attach_poster(event, png_bytes, 0)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert content.count("warning-bar-fill") == 1


@pytest.mark.django_db
def test_품질_경고가_하나도_없으면_대시보드는_경고_없음_안내를_보여준다(staff_client):
    staff, client = staff_client()

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "현재 품질 경고가 없습니다" in content
    assert "warning-bars" not in content


@pytest.mark.django_db
def test_건수가_동률인_품질_경고는_라벨_정의_순서대로_렌더링된다(
    staff_client, make_event, png_bytes
):
    """Regression guard for _build_quality_warning_rows' tie-break: two
    warnings tied at count=1 must render in QUALITY_WARNING_LABELS'
    definition order (missing_official_url before missing_poster), not in
    whatever order sort() happens to leave them."""
    staff, client = staff_client()
    # Trips only missing_poster (poster left unset).
    make_event(**_clean_quality_event_kwargs(0))
    # Trips only missing_official_url (official_url left unset).
    kwargs = _clean_quality_event_kwargs(1)
    kwargs.pop("official_url")
    event = make_event(**kwargs)
    _attach_poster(event, png_bytes, 1)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert content.index("공식 URL 없음") < content.index("포스터 없음")


# ---------------------------------------------------------------------------
# 최근 14일 활동 미니 컬럼 차트 (Phase 4)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_최근_활동_차트는_항상_14개_열을_렌더링한다(staff_client):
    staff, client = staff_client()
    StaffActionLog.objects.create(actor=staff, action=StaffActionLog.Action.APPROVE)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    columns = re.findall(r'<span class="activity-col[^"]*"', content)
    assert len(columns) == 14


@pytest.mark.django_db
def test_최근_활동_차트는_마지막_열_하나만_오늘로_표시한다(staff_client):
    staff, client = staff_client()
    StaffActionLog.objects.create(actor=staff, action=StaffActionLog.Action.APPROVE)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    columns = re.findall(r'<span class="activity-col[^"]*"', content)
    assert sum(1 for col in columns if "activity-col--today" in col) == 1
    assert "activity-col--today" in columns[-1]


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
    assert "activity-columns" not in content


# ---------------------------------------------------------------------------
# 수집 소스 상태 점 (Phase 5)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_최근_수집된_활성_소스는_정상_상태_점으로_표시된다(staff_client):
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
    assert '<span class="status-dot status-dot--ok"></span>' in content


@pytest.mark.django_db
def test_비활성_소스는_비활성_상태_점으로_표시된다(staff_client):
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
    assert '<span class="status-dot status-dot--disabled"></span>' in content


@pytest.mark.django_db
def test_최근_오류가_있는_활성_소스는_오류_상태_점으로_표시된다(staff_client):
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
    assert '<span class="status-dot status-dot--error"></span>' in content


@pytest.mark.django_db
def test_한번도_수집되지_않은_활성_소스는_지연_상태_점으로_표시된다(staff_client):
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
    assert '<span class="status-dot status-dot--stale"></span>' in content


@pytest.mark.django_db
def test_오류와_지연이_동시에_성립하면_상태_점은_지연보다_오류를_우선한다(staff_client):
    """PR-D1 item 3 established error+stale can both be true simultaneously
    (never-checked + last_error set) — status_level must pick error, not
    stale, so the dot doesn't disagree with the "오류" badge next to it."""
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
    assert '<span class="status-dot status-dot--error"></span>' in content
    assert "status-dot--stale" not in content
