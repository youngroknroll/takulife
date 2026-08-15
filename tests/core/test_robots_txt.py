"""서비스 자체 /robots.txt(전체 크롤링 차단) 검증.

drafts.robots(외부 사이트 robots.txt 판정, tests/drafts/test_robots.py)와는
전혀 다른 대상이다 — 이 테스트는 taku 서버가 자신의 /robots.txt에서 무엇을
내려주는지만 본다.
"""
import pytest

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_로봇_배제_파일은_전체_경로_크롤링을_차단한다(client):
    response = client.get("/robots.txt")

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/plain")
    body = response.content.decode("utf-8")
    assert "User-agent: *" in body
    assert "Disallow: /" in body
