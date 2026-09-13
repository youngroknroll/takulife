"""카테고리 노출 분기(서비스 계층) — 트랙 27 7단계 Phase A.

`test_category_visibility.py`(HTTP/SSR)에서 분리했다. F-04·F-05는 client
계열 픽스처 없이 events.services 함수만 직접 호출해 검증하므로, 아키텍처
경계 가드("API/뷰 계층 테스트 파일은 services/queries를 임포트하지
않는다")가 요구하는 대로 전용 파일에 둔다.
"""
import pytest

from core.models import Category
from events.services import (
    PublishEventCategoryError,
    create_published_event,
    republish_event,
)

pytestmark = pytest.mark.domain


@pytest.mark.django_db
def test_비활성_카테고리를_쓰던_기존_이벤트는_재게시해도_카테고리_오류가_나지_않는다(
    make_draft_event,
):
    """is_valid_category가 이미 core.categories.category_exists(비활성 포함)로
    DB를 본다 — "비활성 ≠ 삭제" 핵심 계약. 이미 Green 예상."""
    event = make_draft_event(
        title="F04재게시행사",
        category="concert",
        official_url="https://example.com/f04-inactive-republish",
    )
    category = Category.objects.get(slug="concert")
    category.is_active = False
    category.save()

    republished = republish_event(event=event)

    assert republished.publish_status == "published"


@pytest.mark.django_db
def test_어휘_밖_임의_문자열은_활성_비활성과_무관하게_계속_거부된다():
    """category_exists는 슬러그가 Category 행으로 없으면 항상 False를
    돌려준다 — 어휘 밖 자유 문자열은 지금도 거부된다. 이미 Green 예상."""
    with pytest.raises(PublishEventCategoryError):
        create_published_event(
            title="F05어휘밖행사",
            category="카페/팝업",
            official_url="https://example.com/f05-outside-vocab",
        )
