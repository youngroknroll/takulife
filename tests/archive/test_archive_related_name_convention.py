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


RELATED_NAME_CONVENTION_MODELS = [EventInterest, UserEventStatus, VisitRecord]


def _related_name(model, field_name):
    return model._meta.get_field(field_name).remote_field.related_name


@pytest.mark.parametrize("model", RELATED_NAME_CONVENTION_MODELS, ids=lambda m: m.__name__)
def test_subject_fks_share_one_archive_user_related_name(model):
    event_related_name = _related_name(model, "event")
    personal_entry_related_name = _related_name(model, "personal_entry")

    assert event_related_name == personal_entry_related_name
    assert event_related_name.startswith("archive_user_")


@pytest.mark.parametrize("model", RELATED_NAME_CONVENTION_MODELS, ids=lambda m: m.__name__)
def test_owner_fk_related_name_is_archive_prefixed_and_distinct_from_subject(model):
    user_related_name = _related_name(model, "user")
    subject_related_name = _related_name(model, "event")

    assert user_related_name.startswith("archive_")
    assert user_related_name != subject_related_name
