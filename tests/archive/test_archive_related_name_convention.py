"""Model-contract test: EventInterest/UserEventStatus/VisitRecord must share
one related_name naming convention across their user/event/personal_entry FKs.

Owner-role (user FK): related_name starts with "archive_" and is distinct
from the subject-role name. Subject-role (event AND personal_entry FKs,
deliberately sharing one name because they are mutually exclusive — see the
"subject = exactly one of ..." comment on each model): both FKs share the
identical related_name, and that shared name starts with "archive_user_".

No django_db mark — this only introspects model _meta, no database access.
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
