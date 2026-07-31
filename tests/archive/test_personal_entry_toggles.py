"""Phase 3 UI: 비공식 페이지(/archive/personal/)는 카드마다 찜·방문예정 토글을
노출해 비공식 항목을 표시할 수 있게 하며, kind에 따라 라벨이 달라진다(goods →
구매…). 렌더링된 토글 상태에 대한 뷰 레벨 검증이다.
"""
import pytest

from archive.models import PersonalEntry

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_굿즈_항목은_목록에서_찜과_방문예정_토글이_숨겨진다(client, make_user, make_entry):
    # GOODS는 더 이상 찜/상태의 대상이 아니다(컬렉션 도메인 설계안 §3-3) — 쓰기
    # 경로가 닫히기 전에 만들어진 레거시 행이어도 토글 마크업이 전혀 렌더되면
    # 안 된다.
    user = make_user(username="toggles-goods-hidden")
    make_entry(user, kind="goods", title="아크릴 스탠드")
    client.force_login(user)

    body = client.get("/archive/personal/").content.decode()

    assert "data-interest-toggle" not in body
    assert "data-status-action" not in body


@pytest.mark.django_db
def test_기존_찜이_있으면_목록에_찜_표시가_반영된다(client, make_user, make_interest, make_entry):
    user = make_user(username="toggles-fav")
    entry = make_entry(user, kind="place", title="비공식 카페")
    interest = make_interest(user, personal_entry=entry)
    client.force_login(user)

    body = client.get("/archive/personal/").content.decode()

    assert f'data-interest-id="{interest.id}"' in body
    assert "♥" in body


@pytest.mark.django_db
def test_굿즈_항목에_기존_참석예정_상태가_있어도_목록에서_숨겨진다(client, make_user, make_status, make_entry):
    # 이미 상태가 있는 goods 행(게이트가 생기기 전 과도기 데이터)도 status-id
    # 마크업을 렌더하면 안 된다 — goods는 찜/상태 액션 영역 전체가 숨겨진다
    # (컬렉션 도메인 설계안 §3-3).
    user = make_user(username="toggles-goods-planned")
    entry = make_entry(user, kind="goods", title="굿즈")
    status = make_status(user, personal_entry=entry, status="planned")
    client.force_login(user)

    body = client.get("/archive/personal/").content.decode()

    assert f'data-status-id="{status.id}"' not in body


@pytest.mark.django_db
def test_장소_항목은_방문_예정_문구를_사용한다(client, make_user, make_entry):
    user = make_user(username="toggles-place")
    make_entry(user, kind="place", title="숨은 카페")
    client.force_login(user)

    body = client.get("/archive/personal/").content.decode()

    assert "방문 예정" in body


@pytest.mark.django_db
def test_검수_미제출_항목은_목록에_공식_제보_버튼이_노출된다(client, make_user, make_entry):
    user = make_user(username="promote-ui-new")
    entry = make_entry(user, kind="place", title="비공식")
    client.force_login(user)

    body = client.get("/archive/personal/").content.decode()

    assert f'data-promote-toggle="{entry.id}"' in body
    assert "검수 중" not in body


@pytest.mark.django_db
def test_검수_제출된_항목은_목록에_검수_중_배지가_노출되고_제보_버튼은_숨겨진다(client, make_user, make_entry):
    user = make_user(username="promote-ui-done")
    entry = make_entry(user, kind="place", title="비공식", promotion_status=PersonalEntry.PromotionStatus.SUBMITTED)
    client.force_login(user)

    body = client.get("/archive/personal/").content.decode()

    assert "검수 중" in body
    assert f'data-promote-toggle="{entry.id}"' not in body
