"""스태프 콘솔이 새로 만든 카테고리를 슬러그가 아니라 라벨로 보여주는지 검증한다
(트랙 59 확장). 스태프 화면은 한국어 전용이라 `lang` 속성은 다루지 않는다."""

import re

from django.db import connection
from django.test.utils import CaptureQueriesContext
import pytest

from core.models import Category

pytestmark = [pytest.mark.django_db, pytest.mark.web]


def test_스태프_행사_목록은_새_카테고리_행을_슬러그가_아니라_카테고리_라벨로_보여준다(
    staff_client, make_event
):
    _, client = staff_client()
    Category.objects.create(slug="night_market", label="나이트 마켓")
    make_event(title="스태프 새 카테고리 행사", category="night_market")

    resp = client.get("/staff/events/")

    assert resp.status_code == 200
    cells = re.findall(
        r'<td class="events-category-cell">\s*(.*?)\s*</td>',
        resp.content.decode(),
        flags=re.DOTALL,
    )
    assert cells == ["나이트 마켓"]


def test_스태프_행사_목록은_새_카테고리_행이_많아져도_쿼리_수가_행_수에_비례하지_않는다(
    staff_client, make_event
):
    _, client = staff_client()
    Category.objects.create(slug="night_market", label="나이트 마켓")
    for 번호 in range(2):
        make_event(title=f"적은 행 {번호}", category="night_market")
    with CaptureQueriesContext(connection) as 적은_행_쿼리:
        client.get("/staff/events/")

    Category.objects.create(slug="flea_market", label="벼룩 마켓")
    Category.objects.create(slug="book_market", label="책 마켓")
    for 번호, 슬러그 in enumerate(["night_market", "flea_market", "book_market"] * 2):
        make_event(title=f"많은 행 {번호}", category=슬러그)
    with CaptureQueriesContext(connection) as 많은_행_쿼리:
        client.get("/staff/events/")

    assert len(많은_행_쿼리) == len(적은_행_쿼리)


def test_스태프_행사_목록의_빈_상태_필터_요약은_새_카테고리를_라벨로_보여준다(staff_client):
    _, client = staff_client()
    Category.objects.create(slug="night_market", label="나이트 마켓")

    resp = client.get("/staff/events/?category=night_market")

    assert resp.status_code == 200
    항목들 = re.findall(r"<li>(.*?)</li>", resp.content.decode(), flags=re.DOTALL)
    assert "카테고리: 나이트 마켓" in [항목.strip() for 항목 in 항목들]


def test_스태프_드래프트_목록은_새_카테고리_행을_슬러그가_아니라_카테고리_라벨로_보여준다(
    staff_client, make_draft
):
    _, client = staff_client()
    Category.objects.create(slug="night_market", label="나이트 마켓")
    make_draft(extracted_title="새 카테고리 드래프트", extracted_category="night_market")

    resp = client.get("/staff/drafts/")

    assert resp.status_code == 200
    assert resp.context["draft_rows"][0]["category_label"] == "나이트 마켓"


def test_스태프_드래프트_목록은_새_카테고리_행이_많아져도_쿼리_수가_행_수에_비례하지_않는다(
    staff_client, make_draft
):
    _, client = staff_client()
    Category.objects.create(slug="night_market", label="나이트 마켓")
    for 번호 in range(2):
        make_draft(extracted_title=f"적은 행 {번호}", extracted_category="night_market")
    with CaptureQueriesContext(connection) as 적은_행_쿼리:
        client.get("/staff/drafts/")

    Category.objects.create(slug="flea_market", label="벼룩 마켓")
    Category.objects.create(slug="book_market", label="책 마켓")
    for 번호, 슬러그 in enumerate(["night_market", "flea_market", "book_market"] * 2):
        make_draft(extracted_title=f"많은 행 {번호}", extracted_category=슬러그)
    with CaptureQueriesContext(connection) as 많은_행_쿼리:
        client.get("/staff/drafts/")

    assert len(많은_행_쿼리) == len(적은_행_쿼리)


def test_스태프_드래프트_상세는_새_카테고리를_슬러그가_아니라_카테고리_라벨로_담는다(
    staff_client, make_draft
):
    _, client = staff_client()
    Category.objects.create(slug="night_market", label="나이트 마켓")
    draft = make_draft(extracted_title="새 카테고리 상세", extracted_category="night_market")

    resp = client.get(f"/staff/drafts/{draft.id}/")

    assert resp.status_code == 200
    assert resp.context["category_label"] == "나이트 마켓"
