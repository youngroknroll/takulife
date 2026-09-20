import datetime

import pytest

from events.models import Event
from events.services import (
    DuplicateOfficialUrlError,
    InvalidEventPeriodError,
    MissingOfficialUrlError,
    PublishEventCategoryError,
    PublishEventRegionError,
    PublishEventTitleError,
    _validate_publish_fields,
    publish_field_checks,
)

BASE_KWARGS = {
    "title": "정상 제목",
    "official_url": "https://example.com/event",
    "start_date": datetime.date(2026, 5, 1),
    "end_date": datetime.date(2026, 5, 10),
    "category": "popup_store",
    "region": "seoul",
}


@pytest.mark.domain
@pytest.mark.django_db
def test_시작일이_종료일보다_늦으면_기간_체크만_실패한다():
    results = publish_field_checks(
        title="정상 제목",
        official_url="https://example.com/event",
        start_date=datetime.date(2026, 5, 10),
        end_date=datetime.date(2026, 5, 1),
        category="popup_store",
        region="seoul",
        existing_queryset=Event.objects.none(),
    )

    checks = {c["key"]: c["passed"] for c in results}
    assert checks == {
        "official_url": True,
        "title": True,
        "title_not_url": True,
        "official_url_unique": True,
        "period": False,
        "category": True,
        "region": True,
    }
    assert [c["key"] for c in results] == [
        "official_url",
        "title",
        "title_not_url",
        "official_url_unique",
        "period",
        "category",
        "region",
    ]


@pytest.mark.domain
@pytest.mark.django_db
def test_제목이_공식_url과_같으면_제목_체크는_통과하고_제목_url_체크만_실패한다():
    results = publish_field_checks(
        title="https://example.com/event",
        official_url="https://example.com/event/",
        start_date=datetime.date(2026, 5, 1),
        end_date=datetime.date(2026, 5, 10),
        category="popup_store",
        region="seoul",
        existing_queryset=Event.objects.none(),
    )

    checks = {c["key"]: c["passed"] for c in results}
    assert checks == {
        "official_url": True,
        "title": True,
        "title_not_url": False,
        "official_url_unique": True,
        "period": True,
        "category": True,
        "region": True,
    }


# 검증기와의 드리프트를 고정하는 핀이라 사설 함수를 직접 부른다
@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize(
    "scenario_name, overrides, expected_exception, expected_failed_keys",
    [
        # URL이 없으면 고유성도 판정할 수 없어 함께 실패로 표시된다(기존 미리보기와 같음)
        (
            "official_url_missing",
            {"official_url": ""},
            MissingOfficialUrlError,
            {"official_url", "official_url_unique"},
        ),
        (
            "title_missing",
            {"title": ""},
            PublishEventTitleError,
            {"title"},
        ),
        (
            "title_equals_url",
            {"title": "https://example.com/event"},
            PublishEventTitleError,
            {"title_not_url"},
        ),
        (
            "period_reversed",
            {"start_date": datetime.date(2026, 5, 10), "end_date": datetime.date(2026, 5, 1)},
            InvalidEventPeriodError,
            {"period"},
        ),
        (
            "category_invalid",
            {"category": "nope"},
            PublishEventCategoryError,
            {"category"},
        ),
        (
            "region_invalid",
            {"region": "nope"},
            PublishEventRegionError,
            {"region"},
        ),
    ],
)
def test_실패_사례별_검증기_예외와_미리보기_실패_key가_짝을_이룬다(
    scenario_name, overrides, expected_exception, expected_failed_keys
):
    kwargs = {**BASE_KWARGS, **overrides}

    with pytest.raises(expected_exception):
        _validate_publish_fields(existing_queryset=Event.objects.none(), **kwargs)

    results = publish_field_checks(existing_queryset=Event.objects.none(), **kwargs)
    failed_keys = {c["key"] for c in results if not c["passed"]}

    assert failed_keys == expected_failed_keys


@pytest.mark.contract
@pytest.mark.django_db
def test_공식_url이_다른_게시_이벤트와_중복되면_url_고유성_체크만_실패한다(make_event):
    make_event(official_url=BASE_KWARGS["official_url"])

    with pytest.raises(DuplicateOfficialUrlError):
        _validate_publish_fields(existing_queryset=Event.objects.all(), **BASE_KWARGS)

    results = publish_field_checks(existing_queryset=Event.objects.all(), **BASE_KWARGS)
    failed_keys = {c["key"] for c in results if not c["passed"]}

    assert failed_keys == {"official_url_unique"}
