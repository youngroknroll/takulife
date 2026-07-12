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
def test_staff_api_rejects_http_basic_auth(client, make_user):
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
def test_anonymous_dashboard_redirects_to_accounts_login(client):
    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 302
    assert resp.url == "/accounts/login/?next=/staff/dashboard/"


@pytest.mark.django_db
def test_non_staff_dashboard_returns_403(client, make_user):
    user = make_user()
    client.force_login(user)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 403


@pytest.mark.django_db
def test_authenticated_non_staff_does_not_redirect_loop(client, make_user):
    user = make_user()
    client.force_login(user)

    resp = client.get("/staff/dashboard/", follow=True)

    assert len(resp.redirect_chain) <= 1
    assert resp.status_code == 403


@pytest.mark.django_db
def test_authenticated_non_staff_gets_403_not_login_bounce(client, make_user):
    user = make_user()
    client.force_login(user)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 403


@pytest.mark.django_db
def test_anonymous_still_redirects_to_login_not_403(client):
    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 302
    assert resp.url == "/accounts/login/?next=/staff/dashboard/"


@pytest.mark.django_db
def test_staff_dashboard_returns_200_with_pending_count(staff_client, make_draft):
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
        "total",
    }
    for value in quality_warnings.values():
        assert isinstance(value, int)


@pytest.mark.django_db
def test_staff_dashboard_context_includes_recent_actions_newest_first(staff_client, make_draft):
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
def test_staff_dashboard_renders_recent_action_with_null_actor_and_target(staff_client):
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
def test_staff_dashboard_renders_home_categories_action_label(staff_client):
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
def test_staff_dashboard_renders_draft_discover_action_label(staff_client):
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
def test_staff_dashboard_renders_event_update_action_label_and_target_event_link(staff_client):
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
def test_staff_dashboard_context_includes_draft_sources_ordered(staff_client):
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
def test_staff_dashboard_shows_error_badge_and_summary_for_source_with_last_error(staff_client):
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
def test_staff_dashboard_shows_stale_badge_for_enabled_source_never_checked(staff_client):
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
def test_staff_dashboard_shows_stale_badge_for_enabled_source_past_threshold(staff_client, settings):
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
def test_staff_dashboard_enabled_source_within_threshold_not_stale(staff_client, settings):
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
def test_staff_dashboard_disabled_source_never_checked_not_stale(staff_client):
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
def test_staff_dashboard_shows_no_discovery_run_history_when_none_logged(staff_client):
    """PR-D1 item 4: with no DRAFT_DISCOVER log at all, the dashboard shows
    "실행 이력 없음" rather than a blank/misleading timestamp."""
    staff, client = staff_client()

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    assert resp.context["last_discovery_run_at"] is None
    assert "실행 이력 없음" in resp.content.decode()


@pytest.mark.django_db
def test_staff_dashboard_shows_no_discovery_run_history_when_only_other_actions_logged(staff_client):
    """PR-D1 item 4: a non-DRAFT_DISCOVER log entry must not be mistaken for
    a discovery run."""
    staff, client = staff_client()
    StaffActionLog.objects.create(actor=staff, action=StaffActionLog.Action.APPROVE)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    assert resp.context["last_discovery_run_at"] is None
    assert "실행 이력 없음" in resp.content.decode()


@pytest.mark.django_db
def test_staff_dashboard_shows_last_discovery_run_time(staff_client):
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
def test_staff_dashboard_context_draft_sources_empty_when_none_exist(staff_client):
    staff, client = staff_client()

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    assert list(resp.context["draft_sources"]) == []


@pytest.mark.django_db
def test_staff_root_redirects_to_dashboard(staff_client):
    staff, client = staff_client()

    resp = client.get("/staff/")

    assert resp.status_code == 302
    assert resp.url == "/staff/dashboard/"


# ---------------------------------------------------------------------------
# Relocation + backward-compat redirects
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_old_drafts_list_url_redirects_to_new_path(client):
    resp = client.get("/event-drafts/")

    assert resp.status_code == 302
    assert resp.url == "/staff/drafts/"


@pytest.mark.django_db
def test_old_drafts_list_url_preserves_next_query_string(client):
    resp = client.get("/event-drafts/?next=/x")

    assert resp.status_code == 302
    assert resp.url == "/staff/drafts/?next=/x"


@pytest.mark.django_db
def test_old_drafts_detail_url_redirects_to_new_path(client):
    resp = client.get("/event-drafts/5/")

    assert resp.status_code == 302
    assert resp.url == "/staff/drafts/5/"


@pytest.mark.django_db
def test_staff_can_access_new_drafts_list_url(staff_client):
    staff, client = staff_client()

    resp = client.get("/staff/drafts/")

    assert resp.status_code == 200


@pytest.mark.django_db
def test_staff_can_access_new_draft_detail_url(staff_client, make_draft):
    staff, client = staff_client()
    draft = make_draft("https://example.com/c", extracted_title="드래프트 C")

    resp = client.get(f"/staff/drafts/{draft.id}/")

    assert resp.status_code == 200


@pytest.mark.django_db
def test_staff_can_access_home_categories_url(staff_client):
    staff, client = staff_client()

    resp = client.get("/staff/home-categories/")

    assert resp.status_code == 200


@pytest.mark.django_db
def test_anonymous_home_categories_redirects_to_accounts_login(client):
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
)
def test_non_staff_blocked_from_new_staff_paths(client, make_user, path):
    user = make_user()
    client.force_login(user)

    resp = client.get(path)

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Hero summary-grid: 최근 7일 처리 카운트 + 검토 대기 카드 링크 (Phase 2)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_staff_dashboard_recent_7d_count_reflects_actual_count_beyond_limit(staff_client):
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
def test_staff_dashboard_shows_prev_week_context(staff_client):
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
def test_staff_dashboard_pending_card_links_to_pending_queue(staff_client):
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
def test_staff_dashboard_quality_warnings_render_as_bars_with_all_five_hrefs(staff_client, make_event):
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
def test_staff_dashboard_quality_warning_bars_sort_descending_by_count(staff_client, make_event, png_bytes):
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
def test_staff_dashboard_quality_warning_zero_rows_have_no_bar_fill(staff_client, make_event, png_bytes):
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
def test_staff_dashboard_quality_warnings_shows_notice_when_none(staff_client):
    staff, client = staff_client()

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "현재 품질 경고가 없습니다" in content
    assert "warning-bars" not in content


@pytest.mark.django_db
def test_staff_dashboard_quality_warning_track_is_aria_hidden(staff_client, make_event, png_bytes):
    staff, client = staff_client()
    kwargs = _clean_quality_event_kwargs(0)
    kwargs.pop("region")
    event = make_event(**kwargs)
    _attach_poster(event, png_bytes, 0)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert '<span class="warning-bar-track" aria-hidden="true">' in content


# ---------------------------------------------------------------------------
# 최근 14일 활동 미니 컬럼 차트 (Phase 4)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_staff_dashboard_activity_chart_renders_14_columns_with_a11y_summary(staff_client):
    staff, client = staff_client()
    StaffActionLog.objects.create(actor=staff, action=StaffActionLog.Action.APPROVE)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    columns = re.findall(r'<span class="activity-col[^"]*"', content)
    assert len(columns) == 14
    assert 'role="img"' in content
    assert 'aria-label="최근 14일 일별 처리 활동, 총 1건"' in content


@pytest.mark.django_db
def test_staff_dashboard_activity_chart_marks_exactly_one_today_column_as_last(staff_client):
    staff, client = staff_client()
    StaffActionLog.objects.create(actor=staff, action=StaffActionLog.Action.APPROVE)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    columns = re.findall(r'<span class="activity-col[^"]*"', content)
    assert sum(1 for col in columns if "activity-col--today" in col) == 1
    assert "activity-col--today" in columns[-1]


@pytest.mark.django_db
def test_staff_dashboard_activity_chart_height_pct_scales_to_daily_max(staff_client):
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
def test_staff_dashboard_activity_chart_shows_notice_when_no_logs(staff_client):
    staff, client = staff_client()

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "최근 14일 처리 내역이 없습니다" in content
    assert "activity-columns" not in content
