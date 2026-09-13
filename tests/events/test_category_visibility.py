"""카테고리 노출 분기(HTTP/SSR) — 트랙 27 7단계 Phase A.

같은 어휘가 화면마다 다른 기준으로 갈린다:

- 스태프 등록 폼 선택지 → 활성만
- 소비자 필터 → 활성 + 게시 이벤트가 있는 비활성
- 스태프 필터 멤버십 → 전체(비활성 포함)

2026-09-13 기준 세 화면 모두 core.vocab.CATEGORY 정적 튜플을 그대로 쓰고
있어([코드] `staff/views/events.py:20-21`·`web/views/events.py:32-33`),
DB의 `Category.is_active`나 게시 이벤트 수를 전혀 반영하지 않는다. 그래서
아래 F-01·F-03·F-06은 지금 Red이고, F-02는 이미 Green이다(이유는 각
테스트 docstring에 적었다). 서비스 계층만 검증하는 F-04·F-05는
`test_category_visibility_services.py`로 분리했다(아키텍처 경계 가드
— 파일명 = 검증 계층 규약).
"""
import re

import pytest
from django.urls import reverse

from core.models import Category
from events.models import Event

pytestmark = pytest.mark.django_db


def _select_options(content, select_id):
    """content에서 id=select_id인 <select> 안의 option value 전체를 반환한다."""
    match = re.search(
        rf'<select[^>]*id="{select_id}"[^>]*>(.*?)</select>', content, re.DOTALL
    )
    assert match, content
    return re.findall(r'<option value="([^"]*)"', match.group(1))


def _category_fieldset(content, legend_text):
    """content에서 <legend>legend_text</legend>가 속한 <fieldset> 블록만 잘라
    돌려준다. 지역 필터도 같은 fieldset/label 구조를 공유하므로, legend
    텍스트로 먼저 범위를 자르지 않으면 부분 문자열 검색이 다른 필터
    그룹의 값을 잘못 집을 수 있다(docs/FE/staff-console-redesign.md S11)."""
    legend_pos = content.index(f"<legend>{legend_text}</legend>")
    fieldset_start = content.rfind("<fieldset", 0, legend_pos)
    fieldset_end = content.index("</fieldset>", legend_pos)
    return content[fieldset_start:fieldset_end]


@pytest.mark.web
def test_비활성_카테고리는_스태프_등록_폼_선택지에_없다(staff_client):
    """현재는 CATEGORY 정적 튜플이 그대로 렌더돼 concert가 비활성화돼도
    선택지에 남는다 — Red 예상."""
    _, client = staff_client()
    category = Category.objects.get(slug="concert")
    category.is_active = False
    category.save()

    resp = client.get(reverse("staff:event-create"))

    assert resp.status_code == 200
    options = _select_options(resp.content.decode(), "create-category")
    assert "concert" not in options


@pytest.mark.web
def test_비활성이어도_게시_이벤트가_있으면_소비자_필터에_남는다(client, make_event):
    """CATEGORY 정적 튜플은 활성 여부와 무관하게 항상 concert를 포함하므로
    지금도 참이다 — 이후 구현(활성 + 게시 이벤트 있음)에서도 계속 참이어야
    하는 회귀 핀이다. 이미 Green 예상."""
    make_event(title="F02비활성유지행사", category="concert")
    category = Category.objects.get(slug="concert")
    category.is_active = False
    category.save()

    resp = client.get(reverse("event-list-page"))

    assert resp.status_code == 200
    fieldset = _category_fieldset(resp.content.decode(), "카테고리")
    assert 'value="concert"' in fieldset


@pytest.mark.web
def test_비활성이고_게시_이벤트가_0건이면_소비자_필터에서_사라진다(client, make_event):
    """CATEGORY 정적 튜플은 게시 이벤트 수와 무관하게 concert를 항상
    포함하므로 지금은 사라지지 않는다 — Red 예상.

    게시 이벤트 0건 상태는 events.services.unpublish_event를 거치지 않고
    draft로 직접 만든다(events.services는 이 파일이 검증하는 HTTP/SSR
    경계 밖이다 — 팔레트 슬롯 반납 부수효과는 이 테스트가 보지 않는다)."""
    make_event(
        title="F03비활성소거행사",
        category="concert",
        publish_status=Event.PublishStatus.DRAFT,
    )
    category = Category.objects.get(slug="concert")
    category.is_active = False
    category.save()

    resp = client.get(reverse("event-list-page"))

    assert resp.status_code == 200
    fieldset = _category_fieldset(resp.content.decode(), "카테고리")
    assert 'value="concert"' not in fieldset


@pytest.mark.web
def test_스태프_목록_필터는_비활성_카테고리도_선택할_수_있다(staff_client, make_event):
    """category='lifecycle_visibility_f06'은 core.vocab.CATEGORY 정적
    7종에 없는 슬러그다. 현재 필터 멤버십 검사(`raw_category in
    CATEGORY_LABELS`)는 이 정적 튜플만 보므로 어휘 밖 취급돼 필터가 통째로
    무시된다 — 그래서 다른 카테고리(concert) 이벤트가 결과에 새어 들어와
    단언이 실패한다. Red 예상."""
    _, client = staff_client()
    new_category = Category.objects.create(
        slug="lifecycle_visibility_f06", label="F06비활성카테고리", is_active=False
    )
    make_event(title="F06대상행사", category=new_category.slug)
    make_event(title="F06다른카테고리행사", category="concert")

    resp = client.get(f"/staff/events/?category={new_category.slug}")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "F06대상행사" in content
    assert "F06다른카테고리행사" not in content
