"""스태프 콘솔이 어휘 위반을 해당 필드의 오류로 렌더링하는지.

카테고리/지역 입력은 템플릿에서 <select>지만, 그건 브라우저 안에서만 유효한
제약이다. 폼 밖에서 만든 POST는 임의 문자열을 실어 보낼 수 있고 — 실제로 dev DB에
"카페/팝업" 같은 값이 그렇게 들어왔다 — 서비스 계층 가드가 이제 그걸 막는다.
여기서 확인하는 건 그 거부가 500이나 뭉뚱그린 문구가 아니라 **해당 필드의 오류로
표시되고 입력값이 보존되는지**다(이 파일의 다른 불변식 오류들과 같은 관례).
"""
import pytest

from events.models import Event

CREATE_URL = "/staff/events/new/"

pytestmark = pytest.mark.web


def _payload(**overrides):
    values = {
        "title": "어휘오류행사",
        "category": "popup_store",
        "work_title": "",
        "location_name": "",
        "region": "seoul",
        "start_date": "",
        "end_date": "",
        "official_url": "https://staff-vocab.example/1",
        "source_name": "",
        "summary": "",
    }
    return {**values, **overrides}


@pytest.mark.django_db
class TestStaffEventCreateVocabErrors:
    def test_어휘_밖_카테고리를_POST하면_카테고리_필드_오류로_렌더링된다(self, staff_client):
        _staff, client = staff_client()

        resp = client.post(CREATE_URL, _payload(category="카페/팝업"))

        assert resp.status_code == 400  # 폼 오류 재렌더(이 뷰의 기존 관례)
        assert resp.context["field_errors"].get("category")
        assert not Event.objects.filter(title="어휘오류행사").exists()

    def test_어휘_밖_지역을_POST하면_지역_필드_오류로_렌더링된다(self, staff_client):
        _staff, client = staff_client()

        resp = client.post(CREATE_URL, _payload(region="서울특별시"))

        assert resp.status_code == 400
        assert resp.context["field_errors"].get("region")
        assert not Event.objects.filter(title="어휘오류행사").exists()

    def test_어휘_오류로_거절돼도_입력값이_폼에_보존된다(self, staff_client):
        _staff, client = staff_client()

        resp = client.post(CREATE_URL, _payload(category="카페/팝업", title="보존확인행사"))

        assert resp.context["form_values"]["title"] == "보존확인행사"
        assert resp.context["form_values"]["category"] == "카페/팝업"

    def test_새로_추가된_지역_슬러그는_정상_생성된다(self, staff_client):
        """확장된 지역 어휘가 실제 등록 경로까지 정상 동작하는지 확인한다."""
        _staff, client = staff_client()

        resp = client.post(CREATE_URL, _payload(region="daegu"))

        assert resp.status_code == 302
        assert Event.objects.get(title="어휘오류행사").region == "daegu"


@pytest.mark.django_db
class TestStaffEventEditVocabErrors:
    def test_어휘_밖_카테고리로_수정하면_필드_오류로_렌더링되고_기존_값이_남는다(
        self, staff_client, make_event
    ):
        _staff, client = staff_client()
        event = make_event(
            title="수정어휘행사",
            category="popup_store",
            official_url="https://staff-vocab.example/edit",
        )

        resp = client.post(
            f"/staff/events/{event.id}/edit/",
            _payload(
                title=event.title,
                category="전시/행사",
                official_url=event.official_url,
            ),
        )

        assert resp.status_code == 400
        assert resp.context["field_errors"].get("category")
        event.refresh_from_db()
        assert event.category == "popup_store"
