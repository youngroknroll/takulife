"""Tests for the draft-creation error mapping in services.

create_draft_from_url translates fetch/extract failures into typed
DraftCreation* errors, exercised here with fetch_html stubbed so no network
is touched. The admin create endpoint's HTTP-response mapping for these same
errors lives in tests/drafts/test_drafts_api.py (that endpoint's home).
"""
import pytest

import drafts.services as services
from drafts.fetching import ResponseTooLargeError, UnsupportedContentTypeError
from drafts.services import (
    DraftCreationEmptyExtractionError,
    DraftCreationResponseTooLargeError,
    DraftCreationUnsafeUrlError,
    DraftCreationUnsupportedContentError,
    create_draft_from_url,
)
from drafts.url_safety import UnsafeFetchUrlError


def _raise(exc):
    def _fn(*args, **kwargs):
        raise exc

    return _fn


@pytest.mark.django_db
class TestCreateDraftErrorMapping:
    def test_unsafe_url_from_fetch_maps(self, monkeypatch):
        monkeypatch.setattr(services, "fetch_html", _raise(UnsafeFetchUrlError()))
        with pytest.raises(DraftCreationUnsafeUrlError):
            create_draft_from_url(source_url="https://ok.example.com/")

    def test_unsupported_content_maps(self, monkeypatch):
        monkeypatch.setattr(services, "fetch_html", _raise(UnsupportedContentTypeError()))
        with pytest.raises(DraftCreationUnsupportedContentError):
            create_draft_from_url(source_url="https://ok.example.com/")

    def test_response_too_large_maps(self, monkeypatch):
        monkeypatch.setattr(services, "fetch_html", _raise(ResponseTooLargeError()))
        with pytest.raises(DraftCreationResponseTooLargeError):
            create_draft_from_url(source_url="https://ok.example.com/")

    def test_empty_extraction_maps(self, monkeypatch):
        # Real extraction on contentless HTML raises EmptyExtractionError.
        monkeypatch.setattr(services, "fetch_html", lambda url: "<html></html>")
        with pytest.raises(DraftCreationEmptyExtractionError):
            create_draft_from_url(source_url="https://ok.example.com/")

    def test_create_draft_from_invalid_url_raises_value_error(self):
        """(moved from tests/core/test_coverage_supplements.py)"""
        with pytest.raises(ValueError):
            create_draft_from_url(source_url="ftp://not-allowed/")
