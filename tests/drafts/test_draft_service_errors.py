"""Tests for the draft-creation error mapping in services.

create_draft_from_url translates fetch/extract failures into typed
DraftCreation* errors, exercised here with fetch_html stubbed so no network
is touched. The admin create endpoint's HTTP-response mapping for these same
errors lives in tests/drafts/test_drafts_api.py (that endpoint's home).
"""
import logging

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

pytestmark = pytest.mark.domain


def _raise(exc):
    def _fn(*args, **kwargs):
        raise exc

    return _fn


@pytest.mark.django_db
class TestCreateDraftErrorMapping:
    def test_fetch_html이_안전하지_않은_url_오류를_던지면_DraftCreationUnsafeUrlError로_변환된다(self, monkeypatch):
        monkeypatch.setattr(services, "fetch_html", _raise(UnsafeFetchUrlError()))
        with pytest.raises(DraftCreationUnsafeUrlError):
            create_draft_from_url(source_url="https://ok.example.com/")

    def test_fetch_단계에서_안전하지_않은_url이_거부되면_단계_표시와_함께_경고가_기록된다(self, monkeypatch, caplog):
        caplog.set_level(logging.WARNING, logger="drafts.services")
        monkeypatch.setattr(services, "fetch_html", _raise(UnsafeFetchUrlError()))

        with pytest.raises(DraftCreationUnsafeUrlError):
            create_draft_from_url(source_url="https://ok.example.com/")

        warnings = [record for record in caplog.records if record.levelno >= logging.WARNING]
        assert len(warnings) == 1
        message = warnings[0].getMessage()
        assert "scheme=https" in message
        assert "ok.example.com" in message
        assert "during fetch" in message

    def test_fetch_html이_지원하지_않는_콘텐츠_타입_오류를_던지면_DraftCreationUnsupportedContentError로_변환된다(self, monkeypatch):
        monkeypatch.setattr(services, "fetch_html", _raise(UnsupportedContentTypeError()))
        with pytest.raises(DraftCreationUnsupportedContentError):
            create_draft_from_url(source_url="https://ok.example.com/")

    def test_fetch_html이_응답_크기_초과_오류를_던지면_DraftCreationResponseTooLargeError로_변환된다(self, monkeypatch):
        monkeypatch.setattr(services, "fetch_html", _raise(ResponseTooLargeError()))
        with pytest.raises(DraftCreationResponseTooLargeError):
            create_draft_from_url(source_url="https://ok.example.com/")

    def test_추출_결과가_비어있으면_DraftCreationEmptyExtractionError로_변환된다(self, monkeypatch):
        # Real extraction on contentless HTML raises EmptyExtractionError.
        monkeypatch.setattr(services, "fetch_html", lambda url: "<html></html>")
        with pytest.raises(DraftCreationEmptyExtractionError):
            create_draft_from_url(source_url="https://ok.example.com/")

    def test_허용되지_않은_url_스킴으로_호출하면_ValueError가_발생한다(self):
        """(moved from tests/core/test_coverage_supplements.py)"""
        with pytest.raises(ValueError):
            create_draft_from_url(source_url="ftp://not-allowed/")


def test_사전_검증에서_안전하지_않은_url이_거부되면_스킴과_호스트만_경고로_기록되고_쿼리는_포함되지_않는다(caplog):
    caplog.set_level(logging.WARNING, logger="drafts.services")

    with pytest.raises(DraftCreationUnsafeUrlError):
        create_draft_from_url(source_url="http://localhost/page?token=secret")

    warnings = [record for record in caplog.records if record.levelno >= logging.WARNING]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert "scheme=http" in message
    assert "localhost" in message
    assert "token" not in message
    assert "secret" not in message
