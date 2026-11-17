"""새 카테고리 점의 팔레트 슬롯 속성이 공개 화면 4곳에 붙는지 검증한다(트랙 59)."""

from datetime import timedelta
from html.parser import HTMLParser

from django.test import Client
from django.utils import timezone
import pytest

from core.models import Category
from core.vocab import CATEGORY_SOURCE_LABELS

pytestmark = [pytest.mark.django_db, pytest.mark.web]


class _AttributeCollector(HTMLParser):
    """모든 시작 태그의 속성을 dict로 모은다."""

    def __init__(self):
        super().__init__()
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append(dict(attrs))

    def handle_startendtag(self, tag, attrs):
        self.elements.append(dict(attrs))


def _parse_elements(body):
    collector = _AttributeCollector()
    collector.feed(body)
    return collector.elements


@pytest.mark.parametrize(
    "path_template",
    ["/", "/events/", "/events/calendar/", "/events/{event_id}/"],
    ids=["홈", "행사_목록", "행사_달력", "행사_상세"],
)
def test_새_카테고리_행사가_있는_공개_화면을_열면_새_카테고리_점에만_배정_슬롯_속성이_붙는다(
    make_event, path_template
):
    category = Category.objects.create(slug="zz_new_slot", label="새슬롯카테고리")
    category.refresh_from_db()
    today = timezone.localdate()
    period = {"start_date": today - timedelta(days=1), "end_date": today + timedelta(days=3)}
    new_event = make_event(title="새 카테고리 행사 1", category=category.slug, **period)
    make_event(title="새 카테고리 행사 2", category=category.slug, **period)
    make_event(title="고정 카테고리 행사", category="popup_store", **period)

    response = Client().get(path_template.format(event_id=new_event.id))

    assert response.status_code == 200
    elements = _parse_elements(response.content.decode())
    new_dots = [el for el in elements if el.get("data-category") == category.slug]
    fixed_dots = [el for el in elements if el.get("data-category") in CATEGORY_SOURCE_LABELS]
    assert new_dots, "새 슬러그의 data-category 요소가 화면에 없다"
    assert [el.get("data-palette-slot") for el in new_dots] == [str(category.palette_slot)] * len(
        new_dots
    )
    assert all("data-palette-slot" not in el for el in fixed_dots)
