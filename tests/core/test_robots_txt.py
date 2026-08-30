"""서비스 자체 /robots.txt(크롤링 허용 정책 + Sitemap 안내) 검증.

drafts.robots(외부 사이트 robots.txt 판정, tests/drafts/test_robots.py)와는
전혀 다른 대상이다 — 이 테스트는 taku 서버가 자신의 /robots.txt에서 무엇을
내려주는지만 본다.
"""
import pytest

pytestmark = pytest.mark.web


def test_로봇_배제_파일은_사이트맵_위치와_함께_전체_크롤링을_허용한다(client):
    response = client.get("/robots.txt")

    body = response.content.decode("utf-8")
    assert response.status_code == 200
    assert "User-agent: *" in body
    assert "Disallow: /\n" not in body
    assert "Sitemap: http://testserver/sitemap.xml" in body


def test_로봇_배제_파일은_비제품_경로는_계속_차단한다(client):
    response = client.get("/robots.txt")

    body = response.content.decode("utf-8")
    assert response.status_code == 200
    assert "Disallow: /admin/" in body
    assert "Disallow: /api/" in body
    assert "Disallow: /accounts/" in body
    assert "Disallow: /staff/" in body
