"""공식 제보(비공식 PersonalEntry를 관리자 드래프트 검토 파이프라인으로
승격)를 위한 중립 조율 계층.

``web``에 둔다: ``archive``는 ``drafts``를 임포트할 수 없고 반대도
마찬가지라, 개인 archive 항목을 검토 드래프트로 연결할 수 있는 유일한
곳이 프레젠테이션·교차도메인 계층인 이 앱이다. 사용자의 PersonalEntry(archive)를
읽어 그 값으로 EventDraft(drafts)를 만들고, 항목을 제출됨으로 표시한다.

항목 자체는 여기서 공개되지 않는다 — 기존 검토 큐에 들어갈 뿐이다.
공개는 여전히 관리자가 드래프트를 승인해야만 일어난다.
"""
from dataclasses import dataclass

from django.db import transaction

from archive.models import PersonalEntry
from drafts.services import DraftCreationDuplicateError, create_draft_from_fields
from drafts.url_safety import InvalidFetchUrlError, UnsafeFetchUrlError, validate_fetch_url


class PromotionNotFoundError(Exception):
    """항목이 없거나 요청한 사용자의 소유가 아니다."""


class PromotionAlreadySubmittedError(Exception):
    """항목이 이미 공식 검토에 제출됐다."""


class PromotionKindNotAllowedError(Exception):
    """이 항목 종류는 승격 대상이 아니다(굿즈 항목은 CollectionItem
    도메인에 속하며 공식 행사 드래프트가 될 수 없다)."""


class PromotionDuplicateError(Exception):
    """제출된 공식 URL로 만든 드래프트가 이미 있다."""


class PromotionUnsafeUrlError(Exception):
    """제출된 공식 URL이 조회 안전 정책(스킴, localhost, 사설/리터럴 IP
    호스트)을 통과하지 못했다."""


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

        # drafts의 조회 안전 정책(스킴 허용 목록 + localhost/사설 IP 리터럴
        # 거부)을 재사용한다. 리졸버를 넘기지 않아 순수 스킴/호스트 검사만
        # 하고 DNS 조회나 네트워크 호출은 없다 — 승격은 URL을 실제로
        # 조회하지 않고 official_url로 저장만 하므로 이걸로 충분하다.
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
