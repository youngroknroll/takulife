"""모델 계약 테스트: EventInterest/UserEventStatus/VisitRecord는
user/event/personal_entry FK 전체에 걸쳐 하나의 related_name 명명 규칙을
공유해야 한다.

소유자 역할(user FK): related_name은 "archive_"로 시작하고 대상 역할 이름과
달라야 한다. 대상 역할(event와 personal_entry FK — 두 필드는 상호 배타적이라
의도적으로 이름을 공유한다. 각 모델의 "subject = exactly one of ..." 주석
참고): 두 FK가 동일한 related_name을 공유하며, 그 이름은 "archive_user_"로
시작해야 한다.

django_db 마커 없음 — 모델 _meta만 조회하고 DB 접근은 없다.
"""
import pytest

from archive.models import EventInterest, UserEventStatus, VisitRecord

pytestmark = pytest.mark.contract

RELATED_NAME_CONVENTION_MODELS = [EventInterest, UserEventStatus, VisitRecord]
RELATED_NAME_CONVENTION_MODEL_IDS = ["행사_찜", "사용자_행사_상태", "방문_기록"]


def _related_name(model, field_name):
    return model._meta.get_field(field_name).remote_field.related_name


@pytest.mark.parametrize(
    "model", RELATED_NAME_CONVENTION_MODELS, ids=RELATED_NAME_CONVENTION_MODEL_IDS
)
def test_대상_역할_FK인_event와_personal_entry는_related_name을_공유하고_archive_user_로_시작한다(model):
    event_related_name = _related_name(model, "event")
    personal_entry_related_name = _related_name(model, "personal_entry")

    assert event_related_name == personal_entry_related_name
    assert event_related_name.startswith("archive_user_")


@pytest.mark.parametrize(
    "model", RELATED_NAME_CONVENTION_MODELS, ids=RELATED_NAME_CONVENTION_MODEL_IDS
)
def test_소유자_역할_FK인_user는_archive_접두사를_가지며_대상_역할과_구분된다(model):
    user_related_name = _related_name(model, "user")
    subject_related_name = _related_name(model, "event")

    assert user_related_name.startswith("archive_")
    assert user_related_name != subject_related_name
