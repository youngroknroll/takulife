"""EventDraft.origin의 한국어 라벨 상수(drafts/labels.py ORIGIN_LABELS) 계약 테스트."""
import pytest

from drafts.models import EventDraft

pytestmark = pytest.mark.domain


def test_ORIGIN_LABELS의_키는_Origin_choices값과_일치한다():
    from drafts.labels import ORIGIN_LABELS

    assert set(ORIGIN_LABELS) == set(EventDraft.Origin.values)
