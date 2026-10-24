"""Event.text_translations 필드의 기본값 계약 — DB가 필요한 모델 테스트."""
import pytest

pytestmark = pytest.mark.domain


@pytest.mark.django_db
def test_새_이벤트의_번역_저장소는_빈_dict로_시작한다(make_event):
    event = make_event(title="기본값 확인용")
    event.refresh_from_db()

    assert event.text_translations == {}
