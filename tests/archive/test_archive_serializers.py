"""Archive serializer tests — validation guard branches, no HTTP
(moved from tests/core/test_coverage_supplements.py)."""

from archive.serializers import PersonalEntrySerializer


class TestSerializerGuard:
    def test_validate_image_passes_empty_through(self):
        # The optional image guard returns empty values untouched (no upload).
        assert PersonalEntrySerializer().validate_image("") == ""
        assert PersonalEntrySerializer().validate_image(None) is None
