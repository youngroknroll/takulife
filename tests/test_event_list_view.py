"""Tests for the public browse page view (core.views.event_list).

Behavior under test: an invalid or unmatched filter value renders the empty
state ("행사 없음"), never a hard error screen. The JSON API keeps rejecting the
same input with 400 (covered in test_events_api.py) — only the browse page
degrades gracefully.
"""
import pytest
from django.test import Client


@pytest.mark.django_db
class TestEventListInvalidFilters:
    def test_invalid_status_shows_empty_state_not_error(self, make_event):
        make_event(title="Live event")

        resp = Client().get("/events/", {"status": "zzz"})

        assert resp.status_code == 200
        body = resp.content.decode()
        assert "조건에 맞는 행사가 없어요" in body
        assert "잘못된 필터 값" not in body

    def test_invalid_category_shows_empty_state(self, make_event):
        make_event(title="Live event")

        resp = Client().get("/events/", {"category": "zzz"})

        assert resp.status_code == 200
        assert "조건에 맞는 행사가 없어요" in resp.content.decode()

    def test_valid_category_filter_lists_matches(self, make_event):
        make_event(title="Popup match", category="popup_store")

        resp = Client().get("/events/", {"category": "popup_store"})

        assert resp.status_code == 200
        body = resp.content.decode()
        assert "검색 결과" in body
        assert "Popup match" in body
