"""Tests for the draft-creation error mapping in services and the admin view.

create_draft_from_url translates fetch/extract failures into typed
DraftCreation* errors; the admin create endpoint maps those onto HTTP
responses. Both layers' branches are exercised here with fetch_html / the
service stubbed so no network is touched.
"""
import pytest
from django.test import Client

import drafts.services as services
import drafts.views as draft_views
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


@pytest.mark.django_db
class TestAdminCreateEndpointErrorResponses:
    def _admin_client(self, make_user):
        client = Client()
        client.force_login(make_user(is_staff=True, is_superuser=True))
        return client

    def _post(self, client):
        return client.post(
            "/api/event-drafts/",
            data={"source_url": "https://ok.example.com/"},
            content_type="application/json",
        )

    def test_unsupported_content_returns_400(self, make_user, monkeypatch):
        monkeypatch.setattr(
            draft_views, "create_draft_from_url",
            _raise(DraftCreationUnsupportedContentError()),
        )
        resp = self._post(self._admin_client(make_user))
        assert resp.status_code == 400

    def test_response_too_large_returns_400(self, make_user, monkeypatch):
        monkeypatch.setattr(
            draft_views, "create_draft_from_url",
            _raise(DraftCreationResponseTooLargeError()),
        )
        resp = self._post(self._admin_client(make_user))
        assert resp.status_code == 400

    def test_empty_extraction_returns_400(self, make_user, monkeypatch):
        monkeypatch.setattr(
            draft_views, "create_draft_from_url",
            _raise(DraftCreationEmptyExtractionError()),
        )
        resp = self._post(self._admin_client(make_user))
        assert resp.status_code == 400
