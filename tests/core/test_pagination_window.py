"""Pager windowing rules (core/pagination.py).

Pure arithmetic, no DB — the window is what decides whether a user can tell
where they are in a long list, and every boundary case here was a judgement
call worth pinning.
"""

import pytest
from django.core.paginator import Paginator

from core.pagination import ELLIPSIS, page_window, pager_context


class TestPageWindow:
    def test_전체_페이지가_창_크기_이하면_생략부호_없이_전부_보여준다(self):
        assert page_window(current=3, total=5) == [1, 2, 3, 4, 5]
        assert page_window(current=1, total=1) == [1]

    def test_첫_블록에서는_블록정렬_1부터_5까지_뒤에_마지막_페이지를_붙인다(self):
        # 시안: "1 2 3 4 5 … 20" — 현재 페이지가 블록 내 어디에 있든 블록은 고정.
        assert page_window(current=1, total=20) == [1, 2, 3, 4, 5, ELLIPSIS, 20]
        assert page_window(current=3, total=20) == [1, 2, 3, 4, 5, ELLIPSIS, 20]

    def test_중간_블록은_선행_생략부호_없이_블록정렬되고_마지막_페이지가_뒤에_붙는다(self):
        assert page_window(current=10, total=20) == [6, 7, 8, 9, 10, ELLIPSIS, 20]
        assert page_window(current=6, total=20) == [6, 7, 8, 9, 10, ELLIPSIS, 20]

    def test_블록_끝이_마지막_페이지와_인접하면_생략부호가_접힌다(self):
        assert page_window(current=16, total=21) == [16, 17, 18, 19, 20, 21]

    def test_마지막_블록에서는_뒤쪽에_추가로_붙는_페이지가_없다(self):
        assert page_window(current=20, total=20) == [16, 17, 18, 19, 20]

    def test_현재_페이지는_항상_창_안에_있다(self):
        for total in (6, 11, 20, 57):
            for current in range(1, total + 1):
                assert current in page_window(current, total), (current, total)

    def test_창은_항상_오름차순이고_중복이_없다(self):
        for total in (6, 11, 20, 57):
            for current in range(1, total + 1):
                nums = [n for n in page_window(current, total) if n != ELLIPSIS]
                assert nums == sorted(nums)
                assert len(nums) == len(set(nums))

    def test_마지막_블록이_외톨이_숫자_하나면_이전_블록에_합쳐진다(self):
        # total ≡ 1 (mod 5)면 마지막 블록이 [total] 하나뿐이라 페이저가
        # "« ‹ 16" 같은 외톨이 숫자로 렌더됐다 — 이전 블록에 합쳐 붙인다.
        assert page_window(current=6, total=6) == [1, 2, 3, 4, 5, 6]
        assert page_window(current=16, total=16) == [11, 12, 13, 14, 15, 16]
        assert page_window(current=21, total=21) == [16, 17, 18, 19, 20, 21]

    def test_외톨이_합침_전후_페이지가_같은_숫자_행을_공유한다(self):
        # 합쳐진 마지막 페이지와, 같은 블록에 이미 속해 있던 인접 페이지는
        # current만 다를 뿐 동일한 숫자 행을 보여줘야 한다.
        assert page_window(current=11, total=16) == [11, 12, 13, 14, 15, 16]
        assert page_window(current=16, total=16) == [11, 12, 13, 14, 15, 16]


def _page(number, total_items, per_page=10):
    return Paginator(list(range(total_items)), per_page).get_page(number)


class TestPagerContext:
    def test_첫_블록에서만_뒤로가기_화살표가_숨는다(self):
        assert pager_context(_page(1, 200))["show_back"] is False
        assert pager_context(_page(6, 200))["show_back"] is True

    def test_마지막_블록에서만_앞으로가기_화살표가_숨는다(self):
        assert pager_context(_page(1, 200))["show_forward"] is True
        assert pager_context(_page(20, 200))["show_forward"] is False
        assert pager_context(_page(16, 200))["show_forward"] is False

    def test_점프_화살표는_5페이지씩_이동하고_끝단에서_클램프된다(self):
        ctx = pager_context(_page(10, 200))
        assert ctx["jump_back"] == 5
        assert ctx["jump_forward"] == 15

        first = pager_context(_page(1, 200))
        assert first["jump_back"] == 1

        last = pager_context(_page(20, 200))
        assert last["jump_forward"] == 20

    def test_이전_다음_화살표_대상은_한_페이지씩_이동하고_끝단에서_클램프된다(self):
        first = pager_context(_page(1, 200))
        assert first["previous"] == 1

        last = pager_context(_page(20, 200))
        assert last["next"] == last["total"] == 20

    def test_생략부호_기호를_컨텍스트로_노출한다(self):
        assert pager_context(_page(1, 200))["ellipsis"] == ELLIPSIS

    def test_외톨이_블록이_합쳐진_마지막_페이지에서도_화살표는_정상이다(self):
        # 160개 항목/10개씩 = 16페이지 — 16 % 5 == 1이라 합침이 없으면
        # 마지막 블록이 [16] 하나뿐이었을 케이스.
        ctx = pager_context(_page(16, 160))
        assert ctx["show_back"] is True
        assert ctx["show_forward"] is False


@pytest.mark.django_db
class TestPagerRendering:
    """페이저는 7개 목록이 공유하는 파셜이라, 컬렉션 하나로 렌더 계약을 고정한다."""

    def _paginated(self, user_client):
        from archive.models import CollectionItem

        user, client = user_client()
        # 컬렉션은 10개/페이지 — 3블록 이상(>10페이지)을 만들어야 첫/마지막 블록의
        # 화살표 부재를 각각 확인할 수 있다.
        CollectionItem.objects.bulk_create(
            CollectionItem(user=user, name=f"굿즈 {i}", work_title="작품 A")
            for i in range(115)
        )
        return client

    def test_페이저는_현재_페이지를_링크가_아닌_aria_current로_렌더한다(self, user_client):
        html = self._paginated(user_client).get("/collection/").content.decode()

        assert 'class="pager-page is-current" aria-current="page"' in html
        # 현재 페이지가 링크로도 렌더되면 클릭 가능한 제자리 이동이 생긴다
        assert 'class="pager-page" href="?page=1"' not in html

    def test_첫_블록에서는_뒤로가기_화살표가_렌더되지_않는다(self, user_client):
        html = self._paginated(user_client).get("/collection/?page=1").content.decode()

        assert 'aria-label="이전 페이지"' not in html
        assert 'aria-label="5페이지 뒤로"' not in html
        assert 'aria-label="다음 페이지"' in html

    def test_마지막_블록에서는_앞으로가기_화살표가_렌더되지_않는다(self, user_client):
        client = self._paginated(user_client)
        # 115개 항목 / 10개씩 = 12페이지(마지막 페이지)
        html = client.get("/collection/?page=12").content.decode()

        assert 'aria-label="다음 페이지"' not in html
        assert 'aria-label="5페이지 앞으로"' not in html
        assert 'aria-label="이전 페이지"' in html
