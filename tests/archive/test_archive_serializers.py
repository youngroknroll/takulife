"""아카이브 시리얼라이저 검증 가드 테스트(HTTP 미포함).
tests/core/test_coverage_supplements.py에서 옮겨왔다."""

import pytest

from archive.serializers import PersonalEntrySerializer

pytestmark = pytest.mark.unit


class TestSerializerGuard:
    def test_이미지_값이_비어있으면_검증을_그대로_통과시킨다(self):
        # 이미지가 비어 있으면(업로드 없음) 검증을 그대로 통과시킨다.
        assert PersonalEntrySerializer().validate_image("") == ""
        assert PersonalEntrySerializer().validate_image(None) is None
