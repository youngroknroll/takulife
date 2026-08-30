"""사이트맵이 검색엔진에 노출하는 대상 검증."""
import pytest
from django.urls import reverse

from web.sitemaps import EventSitemap


@pytest.mark.domain
@pytest.mark.django_db
def test_사이트맵_아이템은_발행된_행사만_포함한다(make_event, make_draft_event):
    published = make_event(title="공개 행사")
    make_draft_event(title="비공개 행사")

    items = list(EventSitemap().items())

    assert items == [published]


@pytest.mark.domain
@pytest.mark.django_db
def test_사이트맵_아이템은_pk_오름차순으로_정렬된다(make_event):
    later_pk_first = make_event(pk=200, title="먼저 만들지만 pk가 큰 행사")
    earlier_pk_second = make_event(pk=100, title="나중에 만들지만 pk가 작은 행사")

    items = list(EventSitemap().items())

    assert items == [earlier_pk_second, later_pk_first]


@pytest.mark.web
@pytest.mark.django_db
def test_사이트맵_엔드포인트는_발행된_행사_상세_경로를_응답한다(make_event, client):
    event = make_event(title="공개 행사")

    response = client.get("/sitemap.xml")

    assert response.status_code == 200
    detail_path = reverse("event-detail-page", args=[event.id])
    assert detail_path in response.content.decode("utf-8")


@pytest.mark.contract
@pytest.mark.django_db
def test_사이트맵_URL의_호스트는_요청_호스트를_따른다(make_event, client):
    make_event(title="공개 행사")

    response = client.get("/sitemap.xml")

    body = response.content.decode("utf-8")
    assert "http://testserver/" in body
    assert "example.com" not in body


@pytest.mark.web
@pytest.mark.django_db
def test_사이트맵은_정적_공개_페이지_5종을_포함한다(client):
    response = client.get("/sitemap.xml")

    assert response.status_code == 200
    body = response.content.decode("utf-8")
    host = "http://testserver"
    for name in [
        "home",
        "event-list-page",
        "event-calendar-page",
        "legal-privacy-page",
        "legal-terms-page",
    ]:
        assert f"<loc>{host}{reverse(name)}</loc>" in body


@pytest.mark.web
@pytest.mark.django_db
def test_사이트맵은_비공개_경로_URL을_포함하지_않는다(client):
    response = client.get("/sitemap.xml")

    body = response.content.decode("utf-8")
    assert "/archive/" not in body
    assert "/mypage/" not in body
    assert "/staff/" not in body
    assert "/accounts/" not in body
    assert "/api/" not in body
