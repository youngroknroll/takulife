"""Archive service-layer analytics event recording
(PR-0e checkpoints B5, B6, B7).

(.docs/plans/2026-07-14-stage0-deployment-foundation-plan.md §8 PR-0e)
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from archive.models import UserEventStatus
from archive.services import (
    create_collection_item,
    create_event_interest,
    create_user_event_status,
    create_visit_record,
    create_visit_record_photo,
    mark_visited,
    update_collection_item,
)
from core.models import AnalyticsEvent

pytestmark = pytest.mark.contract


@pytest.mark.django_db
def test_행사_관심을_등록하면_EVENT_INTERESTED_분석_이벤트가_정확히_한_번_기록된다(make_user, make_event):
    user = make_user()
    event = make_event()

    create_event_interest(user=user, event=event)

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.EVENT_INTERESTED
    ).count() == 1


@pytest.mark.django_db
def test_행사_상태를_planned로_생성하면_EVENT_PLANNED_분석_이벤트가_정확히_한_번_기록된다(make_user, make_event):
    user = make_user()
    event = make_event()

    create_user_event_status(user=user, event=event, status=UserEventStatus.Status.PLANNED)

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.EVENT_PLANNED
    ).count() == 1


@pytest.mark.django_db
def test_행사_상태를_visited로_생성하면_EVENT_MARKED_VISITED_분석_이벤트가_정확히_한_번_기록된다(make_user, make_event):
    user = make_user()
    event = make_event()

    create_user_event_status(user=user, event=event, status=UserEventStatus.Status.VISITED)

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.EVENT_MARKED_VISITED
    ).count() == 1


@pytest.mark.django_db
def test_계획_상태를_방문완료로_전환하면_EVENT_MARKED_VISITED_분석_이벤트가_정확히_한_번_기록된다(make_user, make_event, make_status):
    user = make_user()
    event = make_event()
    status = make_status(user, event, status=UserEventStatus.Status.PLANNED)

    mark_visited(user_event_status=status)

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.EVENT_MARKED_VISITED
    ).count() == 1


@pytest.mark.django_db
def test_방문_기록을_생성하면_VISIT_RECORD_CREATED_이벤트가_기록되고_짧은_후기_내용은_컨텍스트에_노출되지_않는다(
    make_user, make_event
):
    user = make_user()
    event = make_event()

    create_visit_record(
        user=user, event=event, visited_on="2026-05-26", short_review="private notes"
    )

    events = AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.VISIT_RECORD_CREATED
    )
    assert events.count() == 1
    assert "short_review" not in events.get().context


@pytest.mark.django_db
def test_방문_기록에_사진을_추가하면_VISIT_PHOTO_ADDED_분석_이벤트가_정확히_한_번_기록된다(
    make_user, make_event, make_visit, png_bytes
):
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")

    create_visit_record_photo(
        visit_record=record,
        image=SimpleUploadedFile("photo.png", png_bytes(), content_type="image/png"),
    )

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.VISIT_PHOTO_ADDED
    ).count() == 1


@pytest.mark.django_db
def test_수집_항목을_생성하면_COLLECTION_ITEM_CREATED_분석_이벤트가_대상_정보와_함께_정확히_한_번_기록된다(make_user):
    user = make_user()

    item = create_collection_item(user=user, name="아크릴 스탠드")

    events = AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_CREATED
    )
    assert events.count() == 1
    assert events.get().target_type == "collection_item"
    assert events.get().target_id == item.id
    assert events.get().context == {}


@pytest.mark.django_db
def test_수집_항목을_수정하면_COLLECTION_ITEM_UPDATED_분석_이벤트가_정확히_한_번_기록된다(make_user, make_collection_item):
    user = make_user()
    item = make_collection_item(user)

    update_collection_item(item=item, memo="새 메모")

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_UPDATED
    ).count() == 1


@pytest.mark.django_db
def test_방문_기록과_연결해_수집_항목을_생성하면_COLLECTION_ITEM_LINKED_TO_VISIT_이벤트가_기록된다(
    make_user, make_event, make_visit
):
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")

    create_collection_item(user=user, name="아크릴 스탠드", visit_record=record)

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_LINKED_TO_VISIT
    ).count() == 1


@pytest.mark.django_db
def test_연결이_없던_수집_항목에_방문_기록을_새로_연결하면_COLLECTION_ITEM_LINKED_TO_VISIT_이벤트가_기록된다(
    make_user, make_collection_item, make_event, make_visit
):
    user = make_user()
    item = make_collection_item(user)  # visit_record=None default
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")

    update_collection_item(item=item, visit_record=record)

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_LINKED_TO_VISIT
    ).count() == 1


@pytest.mark.django_db
def test_이미_연결된_수집_항목의_무관한_필드를_수정해도_COLLECTION_ITEM_LINKED_TO_VISIT_이벤트는_다시_기록되지_않는다(
    make_user, make_event, make_visit, make_collection_item
):
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")
    item = make_collection_item(user, visit_record=record, event=event)  # already linked

    update_collection_item(item=item, memo="무관한 수정")

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_LINKED_TO_VISIT
    ).count() == 0


@pytest.mark.django_db
def test_동일한_방문_기록_값을_재전송해도_COLLECTION_ITEM_LINKED_TO_VISIT_이벤트는_다시_기록되지_않는다(
    make_user, make_event, make_visit, make_collection_item
):
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")
    item = make_collection_item(user, visit_record=record, event=event)  # already linked

    update_collection_item(item=item, visit_record=record)  # explicit resend of same value

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_LINKED_TO_VISIT
    ).count() == 0


@pytest.mark.django_db
def test_원하는_항목으로_수집_항목을_생성하면_COLLECTION_ITEM_MARKED_WANTED_이벤트가_기록된다(make_user):
    user = make_user()

    create_collection_item(user=user, name="아크릴 스탠드", is_wanted=True)

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_MARKED_WANTED
    ).count() == 1


@pytest.mark.django_db
def test_원하는_항목이_아니었던_수집_항목을_원하는_항목으로_전환하면_COLLECTION_ITEM_MARKED_WANTED_이벤트가_기록된다(
    make_user, make_collection_item
):
    user = make_user()
    item = make_collection_item(user, is_wanted=False)

    update_collection_item(item=item, is_wanted=True)

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_MARKED_WANTED
    ).count() == 1


@pytest.mark.django_db
def test_이미_원하는_항목인_수집_항목의_무관한_필드를_수정해도_COLLECTION_ITEM_MARKED_WANTED_이벤트는_다시_기록되지_않는다(
    make_user, make_collection_item
):
    user = make_user()
    item = make_collection_item(user, is_wanted=True)  # already wanted

    update_collection_item(item=item, memo="무관한 수정")

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_MARKED_WANTED
    ).count() == 0


@pytest.mark.django_db
def test_이미_True인_is_wanted_값을_재전송해도_COLLECTION_ITEM_MARKED_WANTED_이벤트는_다시_기록되지_않는다(
    make_user, make_collection_item
):
    user = make_user()
    item = make_collection_item(user, is_wanted=True)  # already wanted

    update_collection_item(item=item, is_wanted=True)  # explicit resend of same value

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_MARKED_WANTED
    ).count() == 0


@pytest.mark.django_db
def test_교환_가능_수량과_함께_수집_항목을_생성하면_COLLECTION_ITEM_MARKED_TRADEABLE_이벤트가_기록된다(make_user):
    user = make_user()

    create_collection_item(user=user, name="아크릴 스탠드", quantity=2, tradeable_quantity=1)

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_MARKED_TRADEABLE
    ).count() == 1


@pytest.mark.django_db
def test_교환_가능_수량이_0에서_양수로_전환되면_COLLECTION_ITEM_MARKED_TRADEABLE_이벤트가_기록된다(
    make_user, make_collection_item
):
    user = make_user()
    item = make_collection_item(user, quantity=2, tradeable_quantity=0)

    update_collection_item(item=item, tradeable_quantity=1)

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_MARKED_TRADEABLE
    ).count() == 1


@pytest.mark.django_db
def test_이미_교환_가능한_수집_항목의_무관한_필드를_수정해도_COLLECTION_ITEM_MARKED_TRADEABLE_이벤트는_다시_기록되지_않는다(
    make_user, make_collection_item
):
    user = make_user()
    item = make_collection_item(user, quantity=2, tradeable_quantity=1)  # already tradeable

    update_collection_item(item=item, memo="무관한 수정")

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_MARKED_TRADEABLE
    ).count() == 0


@pytest.mark.django_db
def test_교환_가능_수량이_양수에서_양수로_바뀌면_경계_교차가_아니므로_COLLECTION_ITEM_MARKED_TRADEABLE_이벤트가_기록되지_않는다(
    make_user, make_collection_item
):
    user = make_user()
    item = make_collection_item(user, quantity=3, tradeable_quantity=1)  # already positive

    update_collection_item(item=item, tradeable_quantity=2)  # positive to positive, not a crossing

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_MARKED_TRADEABLE
    ).count() == 0


@pytest.mark.django_db
def test_동일한_교환_가능_수량_값을_재전송해도_COLLECTION_ITEM_MARKED_TRADEABLE_이벤트는_다시_기록되지_않는다(
    make_user, make_collection_item
):
    user = make_user()
    item = make_collection_item(user, quantity=2, tradeable_quantity=1)  # already positive

    update_collection_item(item=item, tradeable_quantity=1)  # explicit resend of same value

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_MARKED_TRADEABLE
    ).count() == 0


@pytest.mark.django_db
def test_한_번의_수정_요청에서_메모_변경과_원하는_항목_전환이_함께_일어나면_두_이벤트가_각각_독립적으로_기록된다(
    make_user, make_collection_item
):
    user = make_user()
    item = make_collection_item(user, is_wanted=False)

    update_collection_item(item=item, memo="변경", is_wanted=True)

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_UPDATED
    ).count() == 1
    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_MARKED_WANTED
    ).count() == 1


@pytest.mark.django_db
def test_방문_기록_연결과_원하는_항목_설정을_함께_생성하면_세_분석_이벤트가_모두_기록된다(
    make_user, make_event, make_visit
):
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")

    create_collection_item(user=user, name="아크릴 스탠드", visit_record=record, is_wanted=True)

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_CREATED
    ).count() == 1
    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_LINKED_TO_VISIT
    ).count() == 1
    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_MARKED_WANTED
    ).count() == 1


@pytest.mark.django_db
def test_방문_기록_연결과_원하는_항목_전환을_함께_수정하면_세_분석_이벤트가_모두_기록된다(
    make_user, make_collection_item, make_event, make_visit
):
    user = make_user()
    item = make_collection_item(user)  # visit_record=None, is_wanted=False defaults
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")

    update_collection_item(item=item, visit_record=record, is_wanted=True)

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_UPDATED
    ).count() == 1
    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_LINKED_TO_VISIT
    ).count() == 1
    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_MARKED_WANTED
    ).count() == 1
