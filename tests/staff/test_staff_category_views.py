"""스태프 카테고리 관리 화면(/staff/categories/) — 트랙 27 11단계.

DB에는 core/migrations/0006_seed_categories가 시딩한 7종
(popup_store/collaboration_cafe/theater_bonus/goods_reservation/exhibition/
fan_meeting/concert)이 이미 존재한다. 새 슬러그·라벨은 이 7종과 겹치지
않게 고른다. 절대 개수 단언은 쓰지 않는다.

Red 기대(전체 공통): `staff/views/categories.py`, `templates/staff/categories/
{list,create,edit,confirm}.html`, `staff/urls.py`의 `staff:category-*` 이름이
전부 아직 없다. 이 파일은 `core.categories.UNASSIGNED_PALETTE`·
`palette_hex_for`도 모듈 최상단에서 import하므로, 그 이름이 없어서
파일 전체가 수집 단계에서 ImportError로 죽는 것도 정상이다.
"""
import re

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

import pytest

from core.categories import UNASSIGNED_PALETTE, palette_hex_for
from core.models import Category
from staff.models import StaffActionLog

pytestmark = pytest.mark.web


def _list_url():
    return reverse("staff:category-list")


def _create_url():
    return reverse("staff:category-create")


def _edit_url(category):
    return reverse("staff:category-edit", args=[category.pk])


def _set_active_url(category):
    return reverse("staff:category-set-active", args=[category.pk])


def _remaining_slot_count():
    return Category.PALETTE_SLOT_COUNT - Category.objects.exclude(palette_slot=None).count()


def _exhaust_palette_slots(prefix="slot_filler"):
    for index in range(_remaining_slot_count()):
        Category.objects.create(slug=f"{prefix}_{index}", label=f"{prefix} 라벨 {index}")


# S-01~S-03 목록 --------------------------------------------------------


@pytest.mark.django_db
def test_슈퍼유저가_카테고리_목록에_접근하면_200과_함께_전체_카테고리_행을_본다(staff_client):
    """S-01"""
    _, client = staff_client(is_superuser=True)
    seeded_slugs = set(Category.objects.values_list("slug", flat=True))

    resp = client.get(_list_url())

    assert resp.status_code == 200
    row_slugs = {row["slug"] for row in resp.context["category_rows"]}
    assert row_slugs == seeded_slugs


@pytest.mark.django_db
def test_카테고리_목록_행에는_슬러그_라벨_활성여부_배정슬롯이_담긴다(staff_client):
    """S-02"""
    target = Category.objects.first()
    _, client = staff_client(is_superuser=True)

    resp = client.get(_list_url())

    row = next(r for r in resp.context["category_rows"] if r["slug"] == target.slug)
    assert row["label"] == target.label
    assert row["is_active"] == target.is_active
    assert row["palette_slot"] == target.palette_slot


@pytest.mark.django_db
def test_카테고리_목록은_배정_슬롯_카운터를_보여준다(staff_client):
    """S-03"""
    _, client = staff_client(is_superuser=True)
    expected_assigned = Category.objects.exclude(palette_slot=None).count()

    resp = client.get(_list_url())

    assert resp.status_code == 200
    assert resp.context["assigned_slot_count"] == expected_assigned
    assert resp.context["palette_slot_count"] == Category.PALETTE_SLOT_COUNT


# S-04~S-11 생성 ---------------------------------------------------------


@pytest.mark.django_db
def test_생성_화면_GET하면_빈_폼과_현재_배정_슬롯_수를_본다(staff_client):
    """S-04"""
    _, client = staff_client(is_superuser=True)
    expected_assigned = Category.objects.exclude(palette_slot=None).count()

    resp = client.get(_create_url())

    assert resp.status_code == 200
    assert resp.context["form_values"] == {"slug": "", "label": ""}
    assert resp.context["assigned_slot_count"] == expected_assigned
    assert resp.context["palette_slot_count"] == Category.PALETTE_SLOT_COUNT


@pytest.mark.django_db
def test_유효한_슬러그_라벨로_POST하면_저장되고_목록으로_리다이렉트된다(staff_client):
    """S-05"""
    _, client = staff_client(is_superuser=True)

    resp = client.post(_create_url(), {"slug": "vintage_market", "label": "빈티지 마켓"})

    assert resp.status_code == 302
    assert resp.url == _list_url()
    created = Category.objects.get(slug="vintage_market")
    assert created.label == "빈티지 마켓"


@pytest.mark.django_db
def test_허용되지_않는_문자가_있는_슬러그로_POST하면_필드_오류와_함께_입력값을_보존한_채_재렌더된다(staff_client):
    """S-06"""
    _, client = staff_client(is_superuser=True)

    resp = client.post(_create_url(), {"slug": "Bad-Slug!", "label": "잘못된 슬러그"})

    assert resp.status_code == 200
    assert "slug" in resp.context["field_errors"]
    assert resp.context["form_values"] == {"slug": "Bad-Slug!", "label": "잘못된 슬러그"}
    assert not Category.objects.filter(label="잘못된 슬러그").exists()


@pytest.mark.django_db
def test_중복_라벨로_POST하면_필드_오류와_함께_입력값을_보존한_채_재렌더된다(staff_client):
    """S-07"""
    existing = Category.objects.first()
    _, client = staff_client(is_superuser=True)

    resp = client.post(_create_url(), {"slug": "brand_new_slug", "label": existing.label})

    assert resp.status_code == 200
    assert "label" in resp.context["field_errors"]
    assert resp.context["form_values"] == {"slug": "brand_new_slug", "label": existing.label}
    assert not Category.objects.filter(slug="brand_new_slug").exists()


@pytest.mark.django_db
def test_슬롯_소진_상태에서_생성_화면에_GET하면_목록으로_리다이렉트되고_오류_메시지가_뜬다(staff_client):
    """S-08"""
    _exhaust_palette_slots()
    _, client = staff_client(is_superuser=True)

    resp = client.get(_create_url(), follow=True)

    assert resp.status_code == 200
    assert resp.redirect_chain[0][0] == _list_url()
    messages_text = " ".join(str(m) for m in resp.context["messages"])
    assert messages_text


@pytest.mark.django_db
def test_슬롯_소진_상태에서_POST하면_생성하지_않고_입력값을_보존한_채_오류_메시지와_함께_재렌더된다(staff_client):
    """S-09"""
    _exhaust_palette_slots()
    before_count = Category.objects.count()
    _, client = staff_client(is_superuser=True)

    resp = client.post(_create_url(), {"slug": "never_created", "label": "생성 안 됨"})

    assert resp.status_code == 200
    assert resp.context["form_values"] == {"slug": "never_created", "label": "생성 안 됨"}
    assert Category.objects.count() == before_count
    assert not Category.objects.filter(slug="never_created").exists()
    messages_text = " ".join(str(m) for m in resp.context["messages"])
    assert messages_text


@pytest.mark.contract
@pytest.mark.django_db
def test_생성_POST는_카테고리_테이블을_잠그고_슬롯_가용성을_재검사한다(staff_client):
    """S-10

    한계: CaptureQueriesContext는 SELECT ... FOR UPDATE가 실행됐다는 사실만
    증명한다 — 동시 요청 경합이 실제로 해소되는지는 증명하지 못한다. 경합
    해소의 기능적 증거는 S-09(슬롯 소진 시 생성 거부)가 대신 준다
    (tests/staff/test_staff_account_views.py 459행 근처 선례와 같은 한계).
    """
    _, client = staff_client(is_superuser=True)

    with CaptureQueriesContext(connection) as ctx:
        resp = client.post(_create_url(), {"slug": "locking_check", "label": "잠금 확인"})

    assert resp.status_code == 302
    locking_queries = [q for q in ctx.captured_queries if "FOR UPDATE" in q["sql"].upper()]
    assert locking_queries, ctx.captured_queries


@pytest.mark.django_db
def test_생성_성공_시_감사_로그에_category_create와_대상_카테고리가_남는다(staff_client):
    """S-11"""
    staff, client = staff_client(is_superuser=True)

    resp = client.post(_create_url(), {"slug": "audited_category", "label": "감사로그 확인용"})

    assert resp.status_code == 302
    created = Category.objects.get(slug="audited_category")
    log = StaffActionLog.objects.get(target_category=created)
    assert log.action == StaffActionLog.Action.CATEGORY_CREATE
    assert log.actor_id == staff.id


# S-13~S-18 수정(라벨만) --------------------------------------------------


@pytest.mark.django_db
def test_수정_GET하면_현재_라벨과_읽기전용_슬러그를_본다(staff_client):
    """S-13"""
    target = Category.objects.first()
    _, client = staff_client(is_superuser=True)

    resp = client.get(_edit_url(target))

    assert resp.status_code == 200
    assert resp.context["category"].pk == target.pk
    assert resp.context["form_values"] == {"label": target.label}


@pytest.mark.django_db
def test_라벨만_POST하면_라벨이_바뀌고_슬러그는_그대로다(staff_client):
    """S-14"""
    target = Category.objects.first()
    original_slug = target.slug
    _, client = staff_client(is_superuser=True)

    resp = client.post(_edit_url(target), {"label": "새로운 라벨"})

    assert resp.status_code == 302
    target.refresh_from_db()
    assert target.label == "새로운 라벨"
    assert target.slug == original_slug


@pytest.mark.django_db
def test_POST에_다른_슬러그_값을_끼워넣어도_슬러그는_바뀌지_않는다(staff_client):
    """S-15"""
    target = Category.objects.first()
    original_slug = target.slug
    _, client = staff_client(is_superuser=True)

    resp = client.post(_edit_url(target), {"label": "슬러그 주입 시도", "slug": "hijacked_slug"})

    assert resp.status_code == 302
    target.refresh_from_db()
    assert target.slug == original_slug
    assert not Category.objects.filter(slug="hijacked_slug").exists()


@pytest.mark.django_db
def test_이미_쓰이는_라벨로_POST하면_필드_오류와_함께_재렌더된다(staff_client):
    """S-16"""
    target = Category.objects.first()
    other = Category.objects.exclude(pk=target.pk).first()
    _, client = staff_client(is_superuser=True)

    resp = client.post(_edit_url(target), {"label": other.label})

    assert resp.status_code == 200
    assert "label" in resp.context["field_errors"]
    target.refresh_from_db()
    assert target.label != other.label


@pytest.mark.django_db
def test_존재하지_않는_카테고리_수정에_GET하면_404를_응답한다(staff_client):
    """S-17"""
    missing_pk = Category.objects.order_by("-pk").first().pk + 1
    _, client = staff_client(is_superuser=True)

    resp = client.get(reverse("staff:category-edit", args=[missing_pk]))

    assert resp.status_code == 404


@pytest.mark.django_db
def test_수정_성공_시_감사_로그에_category_update와_대상_카테고리가_남는다(staff_client):
    """S-18"""
    target = Category.objects.first()
    staff, client = staff_client(is_superuser=True)

    resp = client.post(_edit_url(target), {"label": "감사로그용 라벨"})

    assert resp.status_code == 302
    log = StaffActionLog.objects.get(
        target_category=target, action=StaffActionLog.Action.CATEGORY_UPDATE
    )
    assert log.actor_id == staff.id


# S-19~S-25 활성/비활성 ---------------------------------------------------


@pytest.mark.django_db
def test_confirmed_없이_비활성화_POST하면_확인_화면을_보여주고_상태를_바꾸지_않는다(staff_client):
    """S-19"""
    target = Category.objects.filter(is_active=True).first()
    _, client = staff_client(is_superuser=True)

    resp = client.post(_set_active_url(target), {"enabled": "0"})

    assert resp.status_code == 200
    target.refresh_from_db()
    assert target.is_active is True


@pytest.mark.django_db
def test_confirmed_없이_재활성화_POST해도_확인_화면을_거친다(staff_client):
    """S-20"""
    target = Category.objects.first()
    target.is_active = False
    target.save()
    _, client = staff_client(is_superuser=True)

    resp = client.post(_set_active_url(target), {"enabled": "1"})

    assert resp.status_code == 200
    target.refresh_from_db()
    assert target.is_active is False


@pytest.mark.django_db
def test_confirmed_yes로_비활성화하면_상태가_바뀌고_감사_로그가_남는다(staff_client):
    """S-21"""
    target = Category.objects.filter(is_active=True).first()
    staff, client = staff_client(is_superuser=True)

    resp = client.post(_set_active_url(target), {"enabled": "0", "confirmed": "yes"})

    assert resp.status_code == 302
    target.refresh_from_db()
    assert target.is_active is False
    log = StaffActionLog.objects.get(
        target_category=target, action=StaffActionLog.Action.CATEGORY_DISABLE
    )
    assert log.actor_id == staff.id


@pytest.mark.django_db
def test_confirmed_yes로_재활성화하면_상태가_바뀌고_감사_로그가_남는다(staff_client):
    """S-22

    palette_slot은 단언하지 않는다 — 재활성화는 슬롯을 되찾지 않는 것이
    설계상 정상이다(재획득 트리거는 게시 재개뿐, core/categories.py의
    reconcile_palette_slot 참고). 감사 로그의 action 값은 확정된 계약에
    없어(카테고리 액션은 create/update/disable 3종뿐, 재활성화 전용 액션은
    아직 없다) 로그 존재 여부만 확인하고 값은 고정하지 않는다.
    """
    target = Category.objects.first()
    target.is_active = False
    target.save()
    staff, client = staff_client(is_superuser=True)

    resp = client.post(_set_active_url(target), {"enabled": "1", "confirmed": "yes"})

    assert resp.status_code == 302
    target.refresh_from_db()
    assert target.is_active is True
    assert StaffActionLog.objects.filter(target_category=target, actor_id=staff.id).exists()


@pytest.mark.django_db
def test_이미_목표_상태면_변경_없이_안내_메시지를_보여주고_로그를_남기지_않는다(staff_client):
    """S-23"""
    target = Category.objects.filter(is_active=True).first()
    _, client = staff_client(is_superuser=True)

    resp = client.post(_set_active_url(target), {"enabled": "1", "confirmed": "yes"}, follow=True)

    assert resp.status_code == 200
    assert StaffActionLog.objects.filter(target_category=target).count() == 0
    messages_text = " ".join(str(m) for m in resp.context["messages"])
    assert messages_text


@pytest.mark.django_db
def test_게시_이벤트가_0건인_카테고리를_화면에서_비활성화하면_팔레트_슬롯이_반납된다(staff_client):
    """S-24 — 새로 만든 카테고리는 어떤 이벤트도 참조하지 않아 게시 이벤트가
    0건이다."""
    target = Category.objects.create(slug="reclaim_check", label="반납 확인용")
    assert target.palette_slot is not None
    _, client = staff_client(is_superuser=True)

    resp = client.post(_set_active_url(target), {"enabled": "0", "confirmed": "yes"})

    assert resp.status_code == 302
    target.refresh_from_db()
    assert target.is_active is False
    assert target.palette_slot is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "enabled_value",
    [
        pytest.param("", id="빈_값"),
        pytest.param("true", id="true"),
        pytest.param("2", id="2"),
    ],
)
def test_enabled가_1_또는_0이_아니면_400이고_상태를_바꾸지_않는다(staff_client, enabled_value):
    """S-25"""
    target = Category.objects.filter(is_active=True).first()
    _, client = staff_client(is_superuser=True)

    resp = client.post(_set_active_url(target), {"enabled": enabled_value, "confirmed": "yes"})

    assert resp.status_code == 400
    target.refresh_from_db()
    assert target.is_active is True


# Q-01~Q-03 미배정 폴백 ----------------------------------------------------


@pytest.mark.django_db
def test_슬롯이_없는_카테고리는_목록_화면에서_정의된_폴백_hex로_렌더된다(staff_client):
    """Q-01"""
    target = Category.objects.first()
    Category.objects.filter(pk=target.pk).update(palette_slot=None)
    _, client = staff_client(is_superuser=True)

    resp = client.get(_list_url())

    assert resp.status_code == 200
    row = next(r for r in resp.context["category_rows"] if r["slug"] == target.slug)
    assert row["palette_hex"] == UNASSIGNED_PALETTE
    body = resp.content.decode()
    assert not re.search(r'style="[^"]*None[^"]*"', body)
    assert 'style=""' not in body


@pytest.mark.django_db
def test_수정_화면에서도_같은_폴백으로_렌더된다(staff_client):
    """Q-02"""
    target = Category.objects.first()
    Category.objects.filter(pk=target.pk).update(palette_slot=None)
    _, client = staff_client(is_superuser=True)

    resp = client.get(_edit_url(target))

    assert resp.status_code == 200
    assert resp.context["palette_hex"] == UNASSIGNED_PALETTE
    body = resp.content.decode()
    assert not re.search(r'style="[^"]*None[^"]*"', body)
    assert 'style=""' not in body


@pytest.mark.django_db
def test_배정된_슬롯이_있는_카테고리는_컨텍스트에_hex_4개가_내려온다(staff_client):
    """Q-03"""
    target = Category.objects.exclude(palette_slot=None).first()
    _, client = staff_client(is_superuser=True)

    resp = client.get(_list_url())

    assert resp.status_code == 200
    row = next(r for r in resp.context["category_rows"] if r["slug"] == target.slug)
    assert row["palette_hex"] == palette_hex_for(target.palette_slot)
    assert set(row["palette_hex"].keys()) == {"light_soft", "light_ink", "dark_soft", "dark_ink"}
