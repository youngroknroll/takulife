"""Archive serializer tests — validation guard branches, no HTTP
(moved from tests/core/test_coverage_supplements.py)."""

import pytest

from archive.serializers import PersonalEntrySerializer

pytestmark = pytest.mark.unit


class TestSerializerGuard:
    def test_이미지_값이_비어있으면_검증을_그대로_통과시킨다(self):
        # The optional image guard returns empty values untouched (no upload).
        assert PersonalEntrySerializer().validate_image("") == ""
        assert PersonalEntrySerializer().validate_image(None) is None
