"""Neutral orchestration for 공식 제보 (promoting an unofficial PersonalEntry into
the admin draft-review pipeline).

This lives in ``core`` on purpose: ``archive`` must not import ``drafts`` (and
vice versa), so the one place allowed to wire a private archive item to a review
draft is this neutral layer. It reads the user's PersonalEntry (archive) and
seeds an EventDraft (drafts) from it, then marks the item as submitted.

The item itself never becomes public here — it only enters the existing review
queue. Publication still happens solely through admin approval of the draft.
"""
from dataclasses import dataclass

from django.db import transaction

from archive.models import PersonalEntry
from drafts.services import DraftCreationDuplicateError, create_draft_from_fields
from drafts.url_safety import InvalidFetchUrlError, UnsafeFetchUrlError, validate_fetch_url


class PromotionNotFoundError(Exception):
    """The entry does not exist or is not owned by the requesting user."""


class PromotionAlreadySubmittedError(Exception):
    """The entry has already been submitted for official review."""


class PromotionKindNotAllowedError(Exception):
    """The entry's kind is not eligible for promotion (goods entries live in
    the CollectionItem domain and never become an official-venue draft)."""


class PromotionDuplicateError(Exception):
    """A draft already exists for the supplied official URL."""


class PromotionUnsafeUrlError(Exception):
    """The supplied official URL fails the fetch-safety policy (scheme,
    localhost, or private/literal IP host)."""


@dataclass(frozen=True)
class PromotionResult:
    personal_entry: PersonalEntry
    draft_id: int


def promote_personal_entry(*, user, personal_entry_id, official_url):
    with transaction.atomic():
        try:
            entry = PersonalEntry.objects.select_for_update().get(
                pk=personal_entry_id, user=user
            )
        except PersonalEntry.DoesNotExist as exc:
            raise PromotionNotFoundError from exc

        if entry.kind != PersonalEntry.Kind.PLACE:
            raise PromotionKindNotAllowedError

        if entry.promotion_status == PersonalEntry.PromotionStatus.SUBMITTED:
            raise PromotionAlreadySubmittedError

        # Reuse drafts' fetch-safety policy (scheme allowlist + localhost/private
        # IP literal rejection). No resolver is passed, so this is a pure
        # scheme/host check — no DNS lookup, no network call — appropriate here
        # since promotion never fetches the URL, only stores it as official_url.
        try:
            validate_fetch_url(official_url)
        except (InvalidFetchUrlError, UnsafeFetchUrlError) as exc:
            raise PromotionUnsafeUrlError from exc

        try:
            draft = create_draft_from_fields(
                source_url=official_url,
                title=entry.title,
                category=entry.category,
                work_title=entry.work_title,
                location_name=entry.location_name,
                region=entry.region,
                summary=entry.memo,
            )
        except DraftCreationDuplicateError as exc:
            raise PromotionDuplicateError from exc

        entry.promotion_status = PersonalEntry.PromotionStatus.SUBMITTED
        entry.save(update_fields=["promotion_status", "updated_at"])
        return PromotionResult(personal_entry=entry, draft_id=draft.id)
