"""어휘 가드 — category/region이 core.vocab 밖의 값으로 저장되는 것을 막는다.

배경: 이 두 필드는 choices 없는 CharField다. LLM 추출 경로(_revalidate_vocab)와
공개 API(읽기 전용)는 이미 안전하지만, 스태프 경로는 템플릿 <select>에만
의존하고 있었다 — 브라우저 밖에서 만든 POST는 그대로 통과했다. 실제로 dev DB에
"카페/팝업" 같은 자유 텍스트가 이 경로로 들어와 카테고리 색 체계를 무력화했다.

가드는 create_published_event / update_published_event가 이미 공유하는
_validate_publish_fields에 얹혀 있다(새 초크포인트를 만들지 않음).
"""
import pytest

from core.vocab import CATEGORY, REGION
from events.models import Event
from events.services import (
    PublishEventCategoryError,
    PublishEventRegionError,
    create_published_event,
    update_published_event,
)

pytestmark = pytest.mark.domain

_VALID = dict(
    title="어휘가드행사",
    official_url="https://vocab-guard.example/1",
)


@pytest.mark.django_db
class TestCreateVocabGuard:
    def test_어휘에_없는_카테고리로_생성하면_거부된다(self):
        with pytest.raises(PublishEventCategoryError):
            create_published_event(**_VALID, category="카페/팝업")

        assert not Event.objects.filter(official_url=_VALID["official_url"]).exists()

    def test_어휘에_없는_지역으로_생성하면_거부된다(self):
        with pytest.raises(PublishEventRegionError):
            create_published_event(**_VALID, region="서울")

        assert not Event.objects.filter(official_url=_VALID["official_url"]).exists()

    def test_빈_값은_미분류로_허용된다(self):
        """category/region은 blank=True이고 '미분류'가 유효한 상태다.
        가드가 이걸 막으면 지역 미상 행사를 아예 등록할 수 없게 된다."""
        event = create_published_event(**_VALID, category="", region="")

        assert event.category == ""
        assert event.region == ""

    @pytest.mark.parametrize("slug", [slug for slug, _ in CATEGORY])
    def test_어휘의_모든_카테고리_슬러그가_통과한다(self, slug):
        event = create_published_event(
            title="카테고리통과행사",
            official_url=f"https://vocab-guard.example/cat-{slug}",
            category=slug,
        )
        assert event.category == slug

    @pytest.mark.parametrize("slug", [slug for slug, _ in REGION])
    def test_어휘의_모든_지역_슬러그가_통과한다(self, slug):
        event = create_published_event(
            title="지역통과행사",
            official_url=f"https://vocab-guard.example/reg-{slug}",
            region=slug,
        )
        assert event.region == slug


@pytest.mark.django_db
class TestUpdateVocabGuard:
    def test_어휘에_없는_카테고리로_수정하면_거부되고_기존_값이_남는다(self, make_event):
        event = make_event(
            title="수정가드행사",
            category="popup_store",
            official_url="https://vocab-guard.example/upd-cat",
        )

        with pytest.raises(PublishEventCategoryError):
            update_published_event(
                event=event,
                title=event.title,
                category="전시/행사",
                official_url=event.official_url,
            )

        event.refresh_from_db()
        assert event.category == "popup_store"

    def test_어휘에_없는_지역으로_수정하면_거부되고_기존_값이_남는다(self, make_event):
        event = make_event(
            title="수정지역가드행사",
            region="seoul",
            official_url="https://vocab-guard.example/upd-reg",
        )

        with pytest.raises(PublishEventRegionError):
            update_published_event(
                event=event,
                title=event.title,
                region="대구광역시",
                official_url=event.official_url,
            )

        event.refresh_from_db()
        assert event.region == "seoul"


@pytest.mark.django_db
class TestRegionVocabExpansion:
    """2026-07-23 사용자 결정(a): 실데이터가 이미 쓰고 있던 대구·대전·광주를
    어휘에 추가한다. 가드를 걸면서 이 셋을 빼면 해당 도시 행사를 새로 등록할
    수 없게 되므로, 어휘 확장이 가드의 선행 조건이다."""

    @pytest.mark.parametrize("slug,label", [("daegu", "대구"), ("daejeon", "대전"), ("gwangju", "광주")])
    def test_추가된_도시가_어휘에_있다(self, slug, label):
        assert (slug, label) in REGION
