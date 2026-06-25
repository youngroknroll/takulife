"""Tests for the home page view context (core.views.home).

Covers the "카테고리로 둘러보기" tiles: one tile per vocab category, in vocab
order, each carrying the count of *published* events in that category.
"""
import pytest
from django.test import Client

from events.models import Event


def make_event(**kwargs):
    defaults = {"title": "T", "publish_status": Event.PublishStatus.PUBLISHED}
    defaults.update(kwargs)
    return Event.objects.create(**defaults)


@pytest.mark.django_db
class TestHomeCategoryTiles:
    def test_tiles_cover_every_category_in_vocab_order(self):
        resp = Client().get("/")

        assert resp.status_code == 200
        slugs = [t["slug"] for t in resp.context["category_tiles"]]
        assert slugs == [
            "popup_store",
            "collaboration_cafe",
            "theater_bonus",
            "goods_reservation",
            "exhibition",
        ]

    def test_tile_counts_only_published_events_per_category(self):
        make_event(category="popup_store")
        make_event(category="popup_store")
        make_event(category="exhibition")
        # a draft in popup_store must NOT be counted
        make_event(category="popup_store", publish_status=Event.PublishStatus.DRAFT)

        resp = Client().get("/")

        tiles = {t["slug"]: t for t in resp.context["category_tiles"]}
        assert tiles["popup_store"]["count"] == 2
        assert tiles["exhibition"]["count"] == 1
        assert tiles["collaboration_cafe"]["count"] == 0

    def test_tiles_carry_korean_labels(self):
        resp = Client().get("/")

        tiles = {t["slug"]: t for t in resp.context["category_tiles"]}
        assert tiles["popup_store"]["label"] == "팝업스토어"
        assert tiles["theater_bonus"]["label"] == "극장 특전"
