"""core/partials/_site_header.html — 전역 4탭 기본 내비(홈/이벤트/컬렉션/
내 활동, 목표 IA 계획 D1-D3, .docs/plans/2026-07-16-target-ia-plan.md
§7-a-8). 어느 페이지든 4개 앵커 중 현재 경로가 속한 섹션 하나만
class="active"를 갖고 나머지 3개는 없어야 한다(네 섹션은 파셜 자체에서
서로 겹치지 않는 경로 접두어로 문서화돼 있다).
"""
import pytest

pytestmark = pytest.mark.web

# 헤더 순서대로, 4개 섹션 각각의 (라벨, href).
_SECTIONS = [
    ("홈", "/"),
    ("이벤트", "/events/"),
    ("컬렉션", "/collection/"),
    ("내 활동", "/archive/"),
]


def _active_anchor(label, href):
    return f'<a href="{href}" class="active">{label}</a>'.encode()


def _inactive_anchor(label, href):
    return f'<a href="{href}">{label}</a>'.encode()


def _assert_only_one_active(content, active_href):
    for label, href in _SECTIONS:
        if href == active_href:
            assert _active_anchor(label, href) in content
        else:
            assert _inactive_anchor(label, href) in content


@pytest.mark.django_db
class TestSiteHeaderActiveTab:
    def test_홈에서는_홈_탭만_active이다(self, client):
        resp = client.get("/")

        _assert_only_one_active(resp.content, "/")

    def test_행사_목록에서는_행사_탭만_active이다(self, client):
        resp = client.get("/events/")

        _assert_only_one_active(resp.content, "/events/")

    def test_컬렉션에서는_컬렉션_탭만_active이다(self, user_client):
        _, client = user_client()

        resp = client.get("/collection/")

        _assert_only_one_active(resp.content, "/collection/")

    def test_나의_일정에서는_내_활동_탭만_active이다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/statuses/")

        _assert_only_one_active(resp.content, "/archive/")
