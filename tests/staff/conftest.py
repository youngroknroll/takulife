"""Staff-domain fixtures."""
import pytest


@pytest.fixture
def staff_event_payload():
    """스태프 이벤트 폼의 유효 페이로드 팩토리 — create/edit 파일의 _valid_payload 사본을 대체."""
    def _make(**overrides):
        payload = {
            "title": "새 이벤트",
            "category": "popup_store",
            "work_title": "작품명",
            "location_name": "장소명",
            "region": "seoul",
            "start_date": "2026-09-01",
            "end_date": "2026-09-10",
            "official_url": "https://example.com/new-event",
            "source_name": "공식 출처",
            "summary": "요약",
        }
        payload.update(overrides)
        return payload

    return _make
