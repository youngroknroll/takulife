"""어휘 가드 — update_draft가 스태프 손편집으로 들어오는 자유 텍스트를 막는다.

update_draft는 *어떤 필드를 고칠 수 있나*(mutable_fields)만 검사하고 *어떤
값인가*는 보지 않았다. 그래서 스태프가 드래프트 카테고리를 임의 문자열로
바꾸면 approve_draft가 그대로 create_published_event에 흘려보냈다.

승인 시점이 아니라 입력 시점에 막는다 — 스태프가 저장하는 순간 알 수 있어야
하고, 승인까지 미루면 잘못된 값이 검토 큐에 머문다.
"""
import pytest

from drafts.services import DraftVocabError, update_draft

pytestmark = pytest.mark.domain


@pytest.mark.django_db
class TestUpdateDraftVocabGuard:
    def test_어휘에_없는_카테고리로_수정하면_거부된다(self, make_draft):
        draft = make_draft(extracted_category="popup_store")

        with pytest.raises(DraftVocabError):
            update_draft(draft_id=draft.id, updates={"extracted_category": "카페/팝업"})

        draft.refresh_from_db()
        assert draft.extracted_category == "popup_store"

    def test_어휘에_없는_지역으로_수정하면_거부된다(self, make_draft):
        draft = make_draft(extracted_region="seoul")

        with pytest.raises(DraftVocabError):
            update_draft(draft_id=draft.id, updates={"extracted_region": "서울특별시"})

        draft.refresh_from_db()
        assert draft.extracted_region == "seoul"

    def test_빈_값은_미분류로_허용된다(self, make_draft):
        draft = make_draft(extracted_category="popup_store", extracted_region="seoul")

        update_draft(
            draft_id=draft.id,
            updates={"extracted_category": "", "extracted_region": ""},
        )

        draft.refresh_from_db()
        assert draft.extracted_category == ""
        assert draft.extracted_region == ""

    def test_어휘_안의_값은_정상_저장된다(self, make_draft):
        draft = make_draft(extracted_category="popup_store", extracted_region="seoul")

        update_draft(
            draft_id=draft.id,
            updates={"extracted_category": "fan_meeting", "extracted_region": "daegu"},
        )

        draft.refresh_from_db()
        assert draft.extracted_category == "fan_meeting"
        assert draft.extracted_region == "daegu"

    def test_어휘_외_값이_섞이면_같은_요청의_정상_필드도_저장되지_않는다(self, make_draft):
        """update_draft는 atomic 블록 안에서 여러 필드를 한 번에 쓴다. 한 필드가
        거부됐는데 다른 필드만 저장되면 스태프가 본 화면과 DB가 어긋난다."""
        draft = make_draft(extracted_title="원래제목", extracted_category="popup_store")

        with pytest.raises(DraftVocabError):
            update_draft(
                draft_id=draft.id,
                updates={"extracted_title": "바뀐제목", "extracted_category": "카페/팝업"},
            )

        draft.refresh_from_db()
        assert draft.extracted_title == "원래제목"
        assert draft.extracted_category == "popup_store"

