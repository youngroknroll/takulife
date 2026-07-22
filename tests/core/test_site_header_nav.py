"""core/partials/_site_header.html — the global 4-tab primary nav (Home /
Events / Collection / Activity, target IA plan D1-D3, .docs/plans/2026-07-16-
target-ia-plan.md §7-a-8). Exactly one of the 4 anchors carries class="active"
on any given page, matching the section the current path belongs to; the
other 3 render without it (the four sections are documented as mutually
exclusive prefixes in the partial itself).
"""
import pytest

pytestmark = pytest.mark.web

# (label, href) for each of the 4 sections, in header order.
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
