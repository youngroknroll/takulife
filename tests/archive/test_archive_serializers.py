"""아카이브 시리얼라이저 검증 가드 테스트(HTTP 미포함).
tests/core/test_coverage_supplements.py에서 옮겨왔다."""

import pytest

from archive.serializers import PersonalEntrySerializer, VisitRecordSerializer


@pytest.mark.unit
class TestSerializerGuard:
    def test_이미지_값이_비어있으면_검증을_그대로_통과시킨다(self):
        # 이미지가 비어 있으면(업로드 없음) 검증을 그대로 통과시킨다.
        assert PersonalEntrySerializer().validate_image("") == ""
        assert PersonalEntrySerializer().validate_image(None) is None


@pytest.mark.domain
@pytest.mark.django_db
@pytest.mark.parametrize(
    ("is_published", "expected_valid"),
    [
        pytest.param(True, True, id="게시_행사"),
        pytest.param(False, False, id="비공개_행사"),
    ],
)
def test_요청_없이_만든_방문_기록_시리얼라이저는_게시된_행사만_받아들인다(
    make_event, make_draft_event, is_published, expected_valid
):
    event = make_event() if is_published else make_draft_event()

    serializer = VisitRecordSerializer(data={"event": event.id, "visited_on": "2026-05-26"})

    assert serializer.is_valid() is expected_valid
    assert ("event" in serializer.errors) is not expected_valid
