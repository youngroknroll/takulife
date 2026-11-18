"""공개 화면 캐시(web/public_cache.py)의 유지 시간·키·격리 계약을 지킨다.

public_month_events는 아직 존재하지 않아, 추가되기 전까지는 이 파일 전체가
수집 단계에서 ModuleNotFoundError로 실패하는 것이 정상이다.
"""

from datetime import date
import time as real_time
from unittest.mock import patch

from django.core.cache import caches
import django.core.cache.backends.base as cache_base
import django.core.cache.backends.locmem as cache_locmem
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import translation
from django.utils.translation import gettext
import pytest

from archive.models import EventInterest
from core.models import Category, HomeConfig
from core.vocab import CATEGORY
from events.models import Event
import web.public_cache as public_cache_module
from web.public_cache import home_public_sections, public_category_choices, public_month_events


class _FakeClock:
    """`time` 모듈을 대신하는, 제어 가능한 가짜 시계."""

    def __init__(self, start):
        self._now = start

    def time(self):
        return self._now

    def advance(self, seconds):
        self._now += seconds


@pytest.fixture
def public_cache_locmem(settings, monkeypatch):
    """공개 캐시는 테스트 설정에서 꺼져 있어(DummyCache) 이 픽스처를 요청한
    테스트만 켠다. 유지 시간 계산(base.py)과 만료 판정(locmem.py)이 서로
    다른 모듈에서 시간을 읽어 두 곳을 같은 가짜 시계로 바꾼다.
    """
    settings.CACHES = {
        **settings.CACHES,
        "public": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-public-cache",
            "OPTIONS": {"MAX_ENTRIES": 200},
        },
    }
    clock = _FakeClock(real_time.time())
    monkeypatch.setattr(cache_base, "time", clock)
    monkeypatch.setattr(cache_locmem, "time", clock)

    caches["public"].clear()
    yield clock
    caches["public"].clear()


@pytest.mark.domain
@pytest.mark.django_db
def test_캐시_유효_시간_안에_같은_달을_다시_조회하면_변경_전_행사_목록을_그대로_돌려준다(
    make_event, public_cache_locmem, django_assert_num_queries
):
    make_event(title="초기행사", start_date=date(2026, 6, 1), end_date=date(2026, 6, 1))

    public_month_events(year=2026, month=6, today=date(2026, 6, 1))

    make_event(title="추가행사", start_date=date(2026, 6, 10), end_date=date(2026, 6, 10))
    public_cache_locmem.advance(59)

    with django_assert_num_queries(0):
        events = public_month_events(year=2026, month=6, today=date(2026, 6, 1))

    assert [event.title for event in events] == ["초기행사"]


@pytest.mark.domain
@pytest.mark.django_db
def test_캐시_유효_시간이_지나_같은_달을_다시_조회하면_새로_반영된_행사_목록을_돌려준다(
    make_event, public_cache_locmem, django_assert_num_queries
):
    make_event(title="초기행사", start_date=date(2026, 6, 1), end_date=date(2026, 6, 1))
    public_month_events(year=2026, month=6, today=date(2026, 6, 1))

    make_event(title="추가행사", start_date=date(2026, 6, 10), end_date=date(2026, 6, 10))
    public_cache_locmem.advance(61)

    with django_assert_num_queries(1):
        events = public_month_events(year=2026, month=6, today=date(2026, 6, 1))

    assert sorted(event.title for event in events) == ["초기행사", "추가행사"]


@pytest.mark.domain
@pytest.mark.django_db
def test_공개_캐시_유효_시간이_0이면_캐시를_거치지_않고_매번_새로_조회한다(
    make_event, public_cache_locmem, settings, monkeypatch
):
    settings.PUBLIC_CACHE_TTL_SECONDS = 0
    make_event(title="초기행사", start_date=date(2026, 6, 1), end_date=date(2026, 6, 1))

    # 캐시를 끄는 값이 캐시 장애 때도 듣는지 보려고 저장소를 일부러 고장 낸다.
    def _raise_cache_failure(*args, **kwargs):
        raise RuntimeError("공개 캐시 장애 주입")

    monkeypatch.setattr(caches["public"], "get", _raise_cache_failure)
    monkeypatch.setattr(caches["public"], "set", _raise_cache_failure)

    public_month_events(year=2026, month=6, today=date(2026, 6, 1))
    make_event(title="추가행사", start_date=date(2026, 6, 10), end_date=date(2026, 6, 10))

    events = public_month_events(year=2026, month=6, today=date(2026, 6, 1))

    assert sorted(event.title for event in events) == ["초기행사", "추가행사"]


@pytest.mark.domain
@pytest.mark.django_db
def test_로컬_날짜가_다르면_같은_달_조회도_서로_다른_캐시_값을_가진다(
    make_event, public_cache_locmem, django_assert_num_queries
):
    make_event(title="초기행사", start_date=date(2026, 6, 1), end_date=date(2026, 6, 1))
    public_month_events(year=2026, month=6, today=date(2026, 6, 1))

    make_event(title="추가행사", start_date=date(2026, 6, 10), end_date=date(2026, 6, 10))

    with django_assert_num_queries(1):
        events = public_month_events(year=2026, month=6, today=date(2026, 6, 2))

    assert sorted(event.title for event in events) == ["초기행사", "추가행사"]


@pytest.mark.domain
@pytest.mark.django_db
def test_달이_다르면_공개_월별_조회는_서로_다른_캐시_값을_가진다(
    make_event, public_cache_locmem, django_assert_num_queries
):
    make_event(title="6월행사", start_date=date(2026, 6, 1), end_date=date(2026, 6, 1))
    make_event(title="7월행사", start_date=date(2026, 7, 1), end_date=date(2026, 7, 1))
    public_month_events(year=2026, month=6, today=date(2026, 6, 1))

    with django_assert_num_queries(1):
        events = public_month_events(year=2026, month=7, today=date(2026, 6, 1))

    assert [event.title for event in events] == ["7월행사"]


@pytest.mark.domain
@pytest.mark.django_db
def test_월별_조회가_실패하면_캐시에_남지_않아_다음_호출이_다시_조회한다(
    make_event, public_cache_locmem, django_assert_num_queries, monkeypatch
):
    make_event(title="초기행사", start_date=date(2026, 6, 1), end_date=date(2026, 6, 1))

    real_query = public_cache_module.list_published_events_for_month

    def _raise(*args, **kwargs):
        raise RuntimeError("월 조회 실패 주입")

    monkeypatch.setattr(public_cache_module, "list_published_events_for_month", _raise)

    with pytest.raises(RuntimeError):
        public_month_events(year=2026, month=6, today=date(2026, 6, 1))

    monkeypatch.setattr(public_cache_module, "list_published_events_for_month", real_query)

    with django_assert_num_queries(1):
        events = public_month_events(year=2026, month=6, today=date(2026, 6, 1))

    assert [event.title for event in events] == ["초기행사"]


@pytest.mark.domain
@pytest.mark.django_db
def test_홈_공개_섹션을_TTL_안에_다시_조회하면_쿼리_없이_같은_값을_돌려준다(
    make_event, public_cache_locmem, django_assert_num_queries
):
    first_category_slug = CATEGORY[0][0]
    second_category_slug = CATEGORY[1][0]
    today = date(2026, 6, 10)
    make_event(
        title="진행행사",
        category=first_category_slug,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 20),
    )

    first_sections = home_public_sections(today=today)

    make_event(
        title="새행사",
        category=second_category_slug,
        start_date=date(2026, 6, 5),
        end_date=date(2026, 6, 25),
    )
    public_cache_locmem.advance(59)

    with django_assert_num_queries(0):
        second_sections = home_public_sections(today=today)

    assert [event.title for event in second_sections["ongoing_rows"]] == ["진행행사"]
    assert second_sections["category_counts"] == {first_category_slug: 1}
    assert second_sections["featured_category_pairs"] == first_sections["featured_category_pairs"]


@pytest.mark.domain
@pytest.mark.django_db
def test_로컬_날짜가_다르면_홈_공개_섹션_캐시도_분리된다(make_event, public_cache_locmem):
    first_category_slug = CATEGORY[0][0]
    make_event(
        title="진행행사",
        category=first_category_slug,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 20),
    )
    home_public_sections(today=date(2026, 6, 10))

    make_event(
        title="새행사",
        category=first_category_slug,
        start_date=date(2026, 6, 5),
        end_date=date(2026, 6, 25),
    )

    sections = home_public_sections(today=date(2026, 6, 11))

    assert sorted(event.title for event in sections["ongoing_rows"]) == ["새행사", "진행행사"]


@pytest.mark.domain
@pytest.mark.django_db
def test_공개_캐시_유효_시간이_0이면_캐시_장애에도_홈_공개_섹션을_돌려준다(
    make_event, public_cache_locmem, settings, monkeypatch
):
    settings.PUBLIC_CACHE_TTL_SECONDS = 0
    first_category_slug = CATEGORY[0][0]
    make_event(
        title="진행행사",
        category=first_category_slug,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 20),
    )

    # 캐시를 끄는 값이 캐시 장애 때도 듣는지 보려고 저장소를 일부러 고장 낸다.
    def _raise_cache_failure(*args, **kwargs):
        raise RuntimeError("공개 캐시 장애 주입")

    monkeypatch.setattr(caches["public"], "get", _raise_cache_failure)
    monkeypatch.setattr(caches["public"], "set", _raise_cache_failure)

    sections = home_public_sections(today=date(2026, 6, 10))

    assert [event.title for event in sections["ongoing_rows"]] == ["진행행사"]
    assert sections["category_counts"] == {first_category_slug: 1}


@pytest.mark.domain
@pytest.mark.django_db
def test_공개_카테고리_선택지를_TTL_안에_다시_조회하면_쿼리_없이_같은_원문_목록을_돌려준다(
    make_event, public_cache_locmem, django_assert_num_queries
):
    first_category_slug = CATEGORY[0][0]
    make_event(title="초기행사", category=first_category_slug)

    first_choices = public_category_choices()

    Category.objects.create(slug="cache-test-category", label="캐시테스트카테고리")
    public_cache_locmem.advance(59)

    with django_assert_num_queries(0):
        with translation.override("en"):
            second_choices = public_category_choices()

    assert second_choices == first_choices
    slugs = [slug for slug, _ in second_choices]
    assert "cache-test-category" not in slugs
    first_category_label = Category.objects.get(slug=first_category_slug).label
    assert dict(second_choices)[first_category_slug] == first_category_label


@pytest.mark.domain
@pytest.mark.django_db
def test_캐시_유효_시간이_지나_카테고리_선택지도_새로_조회한다(make_event, public_cache_locmem):
    first_category_slug = CATEGORY[0][0]
    make_event(title="초기행사", category=first_category_slug)
    public_category_choices()

    Category.objects.create(slug="cache-test-category", label="캐시테스트카테고리")
    public_cache_locmem.advance(61)

    choices = public_category_choices()

    slugs = [slug for slug, _ in choices]
    assert "cache-test-category" in slugs


@pytest.mark.domain
@pytest.mark.django_db
def test_공개_캐시_유효_시간이_0이면_캐시_장애에도_카테고리_선택지를_돌려준다(
    make_event, public_cache_locmem, settings, monkeypatch
):
    settings.PUBLIC_CACHE_TTL_SECONDS = 0
    first_category_slug = CATEGORY[0][0]
    make_event(title="초기행사", category=first_category_slug)

    # 캐시를 끄는 값이 캐시 장애 때도 듣는지 보려고 저장소를 일부러 고장 낸다.
    def _raise_cache_failure(*args, **kwargs):
        raise RuntimeError("공개 캐시 장애 주입")

    monkeypatch.setattr(caches["public"], "get", _raise_cache_failure)
    monkeypatch.setattr(caches["public"], "set", _raise_cache_failure)

    choices = public_category_choices()

    slugs = [slug for slug, _ in choices]
    assert first_category_slug in slugs


@pytest.mark.web
@pytest.mark.django_db
def test_달력_무필터_요청은_TTL_안에_더_적은_쿼리로_같은_내용을_보여준다(
    make_event, public_cache_locmem, client
):
    make_event(title="달력행사", start_date=date(2026, 6, 10), end_date=date(2026, 6, 10))

    with patch("web.views.events.timezone.localdate", return_value=date(2026, 6, 10)):
        with CaptureQueriesContext(connection) as first_ctx:
            first_response = client.get("/events/calendar/", {"month": "2026-06"})

        with CaptureQueriesContext(connection) as second_ctx:
            second_response = client.get("/events/calendar/", {"month": "2026-06"})

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert "달력행사" in first_response.content.decode()
    assert "달력행사" in second_response.content.decode()
    assert len(second_ctx.captured_queries) < len(first_ctx.captured_queries)


@pytest.mark.web
@pytest.mark.django_db
def test_필터가_있는_달력_요청은_캐시를_쓰지_않아_새_행사를_바로_보여준다(
    make_event, public_cache_locmem, client
):
    first_category_slug = CATEGORY[0][0]
    make_event(
        title="기존행사",
        category=first_category_slug,
        start_date=date(2026, 6, 10),
        end_date=date(2026, 6, 10),
    )

    with patch("web.views.events.timezone.localdate", return_value=date(2026, 6, 10)):
        first_response = client.get(
            "/events/calendar/", {"month": "2026-06", "category": first_category_slug}
        )

        make_event(
            title="새행사",
            category=first_category_slug,
            start_date=date(2026, 6, 12),
            end_date=date(2026, 6, 12),
        )

        # 쿼리 수 대신 새 행사가 보이는지로 캐시 미사용을 확인한다(다른 화면
        # 조각이 캐시되면 쿼리 수 비교가 흔들린다).
        second_response = client.get(
            "/events/calendar/", {"month": "2026-06", "category": first_category_slug}
        )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert "새행사" in second_response.content.decode()


@pytest.mark.web
@pytest.mark.django_db
def test_홈_달력_무필터_요청은_TTL_안에_더_적은_쿼리로_같은_달력을_보여준다(
    make_event, public_cache_locmem, client
):
    make_event(title="홈달력행사", start_date=date(2026, 6, 10), end_date=date(2026, 6, 10))
    # 홈 설정 행은 첫 요청 때 만들어져 쿼리가 늘어나므로 미리 만들어 두고 캐시 효과만 비교한다.
    HomeConfig.get_solo()

    with patch("web.views.events.timezone.localdate", return_value=date(2026, 6, 10)):
        with CaptureQueriesContext(connection) as first_ctx:
            first_response = client.get("/", {"month": "2026-06"})

        with CaptureQueriesContext(connection) as second_ctx:
            second_response = client.get("/", {"month": "2026-06"})

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_titles = [
        row["event"].title for row in first_response.context["home_calendar"]["selected_rows"]
    ]
    second_titles = [
        row["event"].title for row in second_response.context["home_calendar"]["selected_rows"]
    ]
    assert "홈달력행사" in first_titles
    assert "홈달력행사" in second_titles
    # 홈의 다른 구간도 나중에 캐시되므로 정확한 차이 대신 "둘째가 더 적다"만 본다.
    assert len(second_ctx.captured_queries) < len(first_ctx.captured_queries)


@pytest.mark.web
@pytest.mark.django_db
def test_행사_목록_카테고리_선택지는_TTL_안에_더_적은_쿼리로_같은_선택지를_보여준다(
    make_event, public_cache_locmem, client
):
    first_category_slug = CATEGORY[0][0]
    make_event(title="목록행사", category=first_category_slug)

    with CaptureQueriesContext(connection) as first_ctx:
        first_response = client.get("/events/")

    with CaptureQueriesContext(connection) as second_ctx:
        second_response = client.get("/events/")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.context["CATEGORY"] == second_response.context["CATEGORY"]
    assert first_response.context["CATEGORY"]
    assert len(second_ctx.captured_queries) < len(first_ctx.captured_queries)


@pytest.mark.web
@pytest.mark.django_db
def test_필터가_있는_행사_목록_요청에서도_카테고리_선택지는_캐시를_쓰고_행사는_바로_보여준다(
    make_event, public_cache_locmem, client
):
    first_category_slug = CATEGORY[0][0]
    make_event(
        title="기존행사",
        category=first_category_slug,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 20),
    )

    with patch("web.views.events.timezone.localdate", return_value=date(2026, 6, 10)):
        first_response = client.get("/events/", {"category": first_category_slug})

        Category.objects.create(slug="cache-test-category", label="캐시테스트카테고리")
        make_event(
            title="새행사",
            category=first_category_slug,
            start_date=date(2026, 6, 5),
            end_date=date(2026, 6, 25),
        )

        second_response = client.get("/events/", {"category": first_category_slug})

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert "새행사" in second_response.content.decode()
    second_slugs = [slug for slug, *_ in second_response.context["CATEGORY"]]
    assert "cache-test-category" not in second_slugs


def _get_with_lang(path, lang):
    """`tests/core/test_category_ui_translations.py`의 `_get` 관례와 같은
    모양으로, 요청 언어를 Accept-Language 헤더로 고른다."""
    headers = {} if lang == "ko" else {"HTTP_ACCEPT_LANGUAGE": lang}
    return Client().get(path, **headers)


@pytest.mark.web
@pytest.mark.django_db
def test_캐시가_채워진_뒤에도_언어가_다른_요청은_각자_번역된_라벨만_받는다(
    make_event, public_cache_locmem
):
    first_category_slug = CATEGORY[0][0]
    make_event(title="초기행사", category=first_category_slug)

    source_label = Category.objects.get(slug=first_category_slug).label
    with translation.override("en"):
        english_label = gettext(source_label)
    assert english_label != source_label

    def _label_for_slug(response, slug):
        return dict((row[0], row[1]) for row in response.context["CATEGORY"])[slug]

    first_response = _get_with_lang("/events/", "en")
    second_response = _get_with_lang("/events/", "ko")
    third_response = _get_with_lang("/events/", "en")

    assert _label_for_slug(first_response, first_category_slug) == english_label
    assert _label_for_slug(second_response, first_category_slug) == source_label
    assert _label_for_slug(third_response, first_category_slug) == english_label


@pytest.mark.web
@pytest.mark.django_db
def test_홈_공개_구간_전체는_TTL_안에_더_적은_쿼리로_같은_홈을_보여준다(
    make_event, public_cache_locmem, client
):
    first_category_slug = CATEGORY[0][0]
    # 홈 설정 행은 첫 요청 때 만들어져 쿼리가 늘어나므로 미리 만들어 두고 캐시 효과만 비교한다.
    HomeConfig.get_solo()
    make_event(
        title="진행행사",
        category=first_category_slug,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 20),
    )

    with patch("web.views.events.timezone.localdate", return_value=date(2026, 6, 10)):
        # 달력 캐시 효과를 빼려고 두 요청의 달을 다르게 한다.
        with CaptureQueriesContext(connection) as first_ctx:
            first_response = client.get("/", {"month": "2026-06"})

        with CaptureQueriesContext(connection) as second_ctx:
            second_response = client.get("/", {"month": "2026-07"})

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_titles = [row["event"].title for row in first_response.context["ongoing_rows"]]
    second_titles = [row["event"].title for row in second_response.context["ongoing_rows"]]
    assert "진행행사" in first_titles
    assert "진행행사" in second_titles
    assert len(second_ctx.captured_queries) < len(first_ctx.captured_queries)


@pytest.mark.web
@pytest.mark.django_db
def test_캐시가_채워진_뒤에도_홈_카테고리_타일은_언어별로_각자_번역된_라벨을_받는다(
    make_event, public_cache_locmem
):
    first_category_slug = CATEGORY[0][0]
    make_event(
        title="진행행사",
        category=first_category_slug,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 20),
    )

    source_label = Category.objects.get(slug=first_category_slug).label
    with translation.override("en"):
        english_label = gettext(source_label)
    assert english_label != source_label

    def _tile_label(response, slug):
        return next(
            tile["label"] for tile in response.context["category_tiles"] if tile["slug"] == slug
        )

    with patch("web.views.events.timezone.localdate", return_value=date(2026, 6, 10)):
        first_response = _get_with_lang("/", "en")
        second_response = _get_with_lang("/", "ko")
        third_response = _get_with_lang("/", "en")

    assert _tile_label(first_response, first_category_slug) == english_label
    assert _tile_label(second_response, first_category_slug) == source_label
    assert _tile_label(third_response, first_category_slug) == english_label


@pytest.mark.web
@pytest.mark.django_db
def test_캐시가_채워진_뒤에도_사용자별_찜_상태는_다른_사용자나_익명에게_안_보인다(
    make_event, make_user, public_cache_locmem, client
):
    first_category_slug = CATEGORY[0][0]
    event = make_event(
        title="진행행사",
        category=first_category_slug,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 20),
    )
    user_a = make_user()
    user_b = make_user()
    EventInterest.objects.create(user=user_a, event=event)

    def _is_interested(response):
        row = next(row for row in response.context["ongoing_rows"] if row["event"].id == event.id)
        return row["user_interested"]

    with patch("web.views.events.timezone.localdate", return_value=date(2026, 6, 10)):
        anonymous_first_response = client.get("/")
        client.force_login(user_a)
        user_a_response = client.get("/")
        client.logout()
        anonymous_second_response = client.get("/")
        client.force_login(user_b)
        user_b_response = client.get("/")

    assert _is_interested(anonymous_first_response) is False
    assert _is_interested(user_a_response) is True
    assert _is_interested(anonymous_second_response) is False
    assert _is_interested(user_b_response) is False


@pytest.mark.web
@pytest.mark.django_db
def test_본인_찜_상태_변경은_캐시_유지_시간_안에도_즉시_반영된다(
    make_event, make_user, public_cache_locmem, client
):
    first_category_slug = CATEGORY[0][0]
    event = make_event(
        title="진행행사",
        category=first_category_slug,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 20),
    )
    user = make_user()
    client.force_login(user)

    def _is_interested(response):
        row = next(row for row in response.context["ongoing_rows"] if row["event"].id == event.id)
        return row["user_interested"]

    with patch("web.views.events.timezone.localdate", return_value=date(2026, 6, 10)):
        first_response = client.get("/")
        EventInterest.objects.create(user=user, event=event)
        second_response = client.get("/")

    assert _is_interested(first_response) is False
    assert _is_interested(second_response) is True


@pytest.mark.web
@pytest.mark.django_db
def test_공개_캐시_경로는_django_cache_테이블을_전혀_건드리지_않는다(
    make_event, public_cache_locmem, client
):
    first_category_slug = CATEGORY[0][0]
    make_event(
        title="진행행사",
        category=first_category_slug,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 20),
    )
    HomeConfig.get_solo()

    with patch("web.views.events.timezone.localdate", return_value=date(2026, 6, 10)):
        with CaptureQueriesContext(connection) as ctx:
            responses = [
                client.get("/"),
                client.get("/"),
                client.get("/events/"),
                client.get("/events/"),
                client.get("/events/calendar/", {"month": "2026-06"}),
                client.get("/events/calendar/", {"month": "2026-06"}),
            ]

    assert all(response.status_code == 200 for response in responses)
    assert not any("django_cache" in query["sql"] for query in ctx.captured_queries)


@pytest.mark.domain
@pytest.mark.django_db
@pytest.mark.parametrize(
    "broken_method",
    ["get", "set"],
    ids=["조회_실패", "저장_실패"],
)
def test_공개_캐시_저장소가_장애여도_정상_조회_결과를_돌려준다(
    make_event, public_cache_locmem, monkeypatch, broken_method
):
    make_event(title="초기행사", start_date=date(2026, 6, 1), end_date=date(2026, 6, 1))

    # 기존 장애 테스트는 유지 시간 0 경로만 덮으므로 기본 유지 시간에서 저장소를 고장 낸다.
    def _raise_cache_failure(*args, **kwargs):
        raise RuntimeError("공개 캐시 장애 주입")

    monkeypatch.setattr(caches["public"], broken_method, _raise_cache_failure)

    events = public_month_events(year=2026, month=6, today=date(2026, 6, 1))

    assert [event.title for event in events] == ["초기행사"]


@pytest.mark.web
@pytest.mark.django_db
def test_비공개로_바뀐_행사는_달력에서_유지_시간이_지나야_빠진다(
    make_event, public_cache_locmem, client
):
    event = make_event(title="숨길행사", start_date=date(2026, 6, 10), end_date=date(2026, 6, 10))

    def _titles_on_june_10(response):
        for week in response.context["weeks"]:
            for cell in week:
                if cell["date"] == date(2026, 6, 10):
                    return [item["title"] for item in cell["items"]]
        return []

    with patch("web.views.events.timezone.localdate", return_value=date(2026, 6, 10)):
        first_response = client.get("/events/calendar/", {"month": "2026-06"})

        event.publish_status = Event.PublishStatus.DRAFT
        event.save()

        second_response = client.get("/events/calendar/", {"month": "2026-06"})

        public_cache_locmem.advance(61)

        # 상세 화면은 캐시를 쓰지 않아 비공개 즉시 404다(tests/events/test_event_detail_view.py가
        # 지킨다) — 여기서는 달력의 지연만 본다.
        third_response = client.get("/events/calendar/", {"month": "2026-06"})

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert third_response.status_code == 200
    assert "숨길행사" in _titles_on_june_10(second_response)
    assert "숨길행사" not in _titles_on_june_10(third_response)
