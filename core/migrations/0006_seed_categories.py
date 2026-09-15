# 데이터 전용 마이그레이션(트랙 27 3단계) — core.vocab.CATEGORY의 기존
# 7종을 core.models.Category 행으로 옮긴다(스키마는 0005가 이미 만들었다).
#
# palette_slot = sort_order = CATEGORY 튜플 안에서의 인덱스. core.categories의
# PALETTE 슬롯 0~6이 기존 7종과 정확히 같은 색으로 맞춰져 있으므로, 인덱스를
# 그대로 슬롯 번호로 써야 기존 이벤트 색이 한 픽셀도 바뀌지 않는다.
#
# apps.get_model("core", "Category")의 히스토리컬 모델은 core/models.py의
# Category.save()(빈 슬롯 자동 배정)를 갖지 않는다 — 여기서 palette_slot을
# 인덱스로 직접 지정하는 이유가 바로 이것이다. 나중에 실제 모델을 임포트하는
# 방식으로 이 마이그레이션을 고치면 자동 배정이 걸려 슬롯이 인덱스와 어긋나고
# 기존 색이 바뀔 수 있다 — 반드시 apps.get_model만 쓴다.
#
# 멱등성: get_or_create(slug=...)로 이미 같은 슬러그 행이 있으면 아무것도
# 하지 않는다(재실행·재적용 시 중복 생성 방지).
#
# reverse_code는 RunPython.noop이 아니다 — 되돌릴 수 있는 단순 삽입이라
# 정보 손실 근거가 없다(archive/0017_migrate_goods_to_collection_items 선례).
# 시딩한 슬러그만 정확히 일치시켜 삭제한다.

from django.db import migrations

# core.vocab.CATEGORY의 동결 스냅샷(2026-09-13 기준) — core.vocab에서
# 라이브 import하지 않는다. 이 마이그레이션(트랙 27 3단계)이 바로 그
# 어휘를 DB로 옮기는 마이그레이션이므로, import를 두면 이후 core.vocab이
# 바뀔 때마다(트랙 27 4단계 포함) 신규 DB에서 `manage.py migrate`로 전체
# 이력을 재생할 때 이 마이그레이션이 그 시점의 어휘가 아니라 최신 어휘를
# 심어버린다 — archive/0017_migrate_goods_to_collection_items의 선례를
# 그대로 따른다(approved 2026-07-16, PO sign-off).
_CATEGORY = (
    ("popup_store", "팝업스토어"),
    ("collaboration_cafe", "콜라보 카페"),
    ("theater_bonus", "극장 특전"),
    ("goods_reservation", "굿즈 예약"),
    ("exhibition", "전시"),
    ("fan_meeting", "팬미팅"),
    ("concert", "콘서트"),
)


def seed_categories(apps, schema_editor):
    Category = apps.get_model("core", "Category")
    for index, (slug, label) in enumerate(_CATEGORY):
        Category.objects.get_or_create(
            slug=slug,
            defaults={
                "label": label,
                "is_active": True,
                "palette_slot": index,
                "sort_order": index,
            },
        )


def delete_seeded_categories(apps, schema_editor):
    Category = apps.get_model("core", "Category")
    seeded_slugs = [slug for slug, _label in _CATEGORY]
    Category.objects.filter(slug__in=seeded_slugs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_category"),
    ]

    operations = [
        migrations.RunPython(seed_categories, reverse_code=delete_seeded_categories),
    ]
