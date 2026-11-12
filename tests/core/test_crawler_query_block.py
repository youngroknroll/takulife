"""ClaudeBot 크롤러의 쿼리 문자열 요청 차단 검증.

이 크롤러가 달력·목록의 필터·정렬·페이지 주소를 초당 수십 건씩 긁어 대역폭이
초과됐다. 쿼리 문자열이 있는 요청만 DB 조회 없이 403으로 막고, 쿼리 없는 요청과
다른 방문자는 평소대로 처리하는지 본다.
"""

import pytest

pytestmark = pytest.mark.web

CLAUDEBOT_USER_AGENT = (
    "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; "
    "ClaudeBot/1.0; +claudebot@anthropic.com)"
)
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


@pytest.mark.django_db
def test_차단_대상_크롤러의_쿼리_요청은_조회_없이_거부된다(client, django_assert_num_queries):
    with django_assert_num_queries(0):
        list_response = client.get("/events/?page=2", HTTP_USER_AGENT=CLAUDEBOT_USER_AGENT)
        calendar_response = client.get(
            "/events/calendar/?month=2031-05", HTTP_USER_AGENT=CLAUDEBOT_USER_AGENT
        )

    assert list_response.status_code == 403
    assert calendar_response.status_code == 403


@pytest.mark.django_db
def test_차단_대상_크롤러도_쿼리_없는_요청은_정상_처리된다(client):
    events_response = client.get("/events/", HTTP_USER_AGENT=CLAUDEBOT_USER_AGENT)
    robots_response = client.get("/robots.txt", HTTP_USER_AGENT=CLAUDEBOT_USER_AGENT)

    assert events_response.status_code == 200
    assert robots_response.status_code == 200


@pytest.mark.django_db
def test_일반_방문자의_쿼리_요청은_차단되지_않는다(client):
    response = client.get("/events/?page=2", HTTP_USER_AGENT=BROWSER_USER_AGENT)

    assert response.status_code == 200


@pytest.mark.django_db
def test_크롤러_이름은_대소문자와_무관하게_판별된다(client):
    response = client.get("/events/?page=2", HTTP_USER_AGENT="claudebot/1.0")

    assert response.status_code == 403
