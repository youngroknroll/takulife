"""카테고리 활성 상태 전이(True→False) 신호를 받아 팔레트 슬롯을 반납한다.

core.models.Category는 events를 임포트할 수 없어(아키텍처 경계 R1) 게시
이벤트 수를 스스로 셀 수 없다. 그래서 Category.save()는 "비활성으로
바뀌었다"는 신호(core_models.category_deactivated)만 보내고, 실제 반납
판단(게시 이벤트 수를 세어 core.categories.reconcile_palette_slot 호출)은
events 쪽인 여기서 한다 — 이벤트를 한 번도 만들지 않은 채 카테고리를
비활성화해도(게시상태 전이가 영영 없는 경우) 슬롯이 반납되게 하려면
카테고리 전이 자체도 반납 트리거여야 하기 때문이다.
"""
from django.dispatch import receiver

from core.models import category_deactivated

from .services import reconcile_category_palette_slot


@receiver(category_deactivated)
def _reconcile_palette_slot_on_category_deactivation(sender, category, **kwargs):
    reconcile_category_palette_slot(category_slug=category.slug)
