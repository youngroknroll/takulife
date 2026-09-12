"""core.models.Category 모델 계약 — 카테고리 어휘를 DB로 옮기는 첫 단계
(트랙 27 1단계 Phase A). 아직 core/models.py에 Category가 없으므로 이
파일의 모든 테스트는 Red다.

- 슬러그·라벨 유일성 위반은 DB 레벨(models.Field(unique=True))로 강제한다고
  가정하고 IntegrityError로 잡는다. 이 저장소의 선례
  tests/auth/test_nickname_model_contracts.py:11-21이 커스텀 매니저 없는
  .objects.create() 경로에서 UniqueConstraint 위반을 IntegrityError로
  잡는 방식을 그대로 따른다 — Category에는 커스텀 매니저를 두지 않을
  예정이므로 같은 경로가 적용된다.
- 슬러그 형식 위반은 모델 필드 validators + full_clean()으로 잡는다
  (ValidationError). 형식 검증은 DB 제약이 아니라 애플리케이션 레벨
  규칙이라 full_clean() 호출이 필요한 경로로 설계했다 — 이 저장소에서
  accounts.validators.validate_nickname도 필드 validators로 등록돼
  있고, 매니저를 거치지 않는 직접 생성 시엔 호출자가 full_clean()을
  불러야 하는 것과 같은 전제다.
"""
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

import pytest

from core.models import Category

pytestmark = [pytest.mark.django_db, pytest.mark.domain]


def test_슬러그가_중복되면_카테고리_생성이_거부된다():
    Category.objects.create(slug="concert_dup", label="콘서트더핑1")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Category.objects.create(slug="concert_dup", label="콘서트더핑2")


def test_라벨이_중복되면_카테고리_생성이_거부된다():
    Category.objects.create(slug="concert_a", label="중복라벨")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Category.objects.create(slug="concert_b", label="중복라벨")


@pytest.mark.parametrize(
    "slug",
    [
        pytest.param("Concert", id="대문자"),
        pytest.param("con cert", id="공백"),
        pytest.param("con-cert", id="하이픈"),
    ],
)
def test_슬러그에_허용되지_않은_문자가_있으면_거부된다(slug):
    category = Category(slug=slug, label=f"라벨_{slug}")

    with pytest.raises(ValidationError):
        category.full_clean()


def test_카테고리를_생성하면_팔레트_슬롯이_자동_배정된다():
    existing_slugs = [
        "popup_store",
        "collaboration_cafe",
        "theater_bonus",
        "goods_reservation",
        "exhibition",
        "fan_meeting",
        "concert",
    ]
    used_slots = set()
    for index, slug in enumerate(existing_slugs):
        category = Category.objects.create(slug=slug, label=f"기존라벨{index}")
        used_slots.add(category.palette_slot)

    new_category = Category.objects.create(slug="new_category", label="새카테고리")

    assert new_category.palette_slot is not None
    assert new_category.palette_slot not in used_slots


def test_비활성화해도_슬러그와_라벨은_남는다():
    category = Category.objects.create(slug="keep_slug", label="유지라벨")

    category.is_active = False
    category.save()
    category.refresh_from_db()

    assert category.is_active is False
    assert category.slug == "keep_slug"
    assert category.label == "유지라벨"


def test_라벨만_수정하면_슬러그는_바뀌지_않는다():
    category = Category.objects.create(slug="fixed_slug", label="원래라벨")

    category.label = "바뀐라벨"
    category.save()
    category.refresh_from_db()

    assert category.slug == "fixed_slug"
    assert category.label == "바뀐라벨"


def test_팔레트_슬롯이_없는_카테고리도_존재할_수_있다():
    # "미배정"은 슬롯을 반납했다가 빈 슬롯이 없어 되찾지 못한 정상 상태다
    # (CLAUDE.md 트랙 27 배경 참고). 생성 경로의 자동 배정 알고리즘과
    # 무관하게, palette_slot=None 자체가 유효한 값인지만 검증한다.
    category = Category(slug="unassigned_slot", label="미배정라벨", palette_slot=None)

    category.full_clean()
