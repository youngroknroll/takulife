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
        assert page_window(current=1, total=1) == [1]
        assert page_window(current=3, total=5) == [1, 2, 3, 4, 5]

    def test_첫_페이지에서는_앞쪽_생략부호_없이_1부터_5까지_보여준다(self):
        # 시안: 1페이지에서 "1 2 3 4 5 … › »"
        assert page_window(current=1, total=20) == [1, 2, 3, 4, 5, ELLIPSIS]

    def test_마지막_페이지에서는_뒤쪽_생략부호가_없다(self):
        assert page_window(current=20, total=20) == [ELLIPSIS, 16, 17, 18, 19, 20]

    def test_중간_페이지는_양쪽_생략부호와_현재_페이지_중심_창을_보여준다(self):
        assert page_window(current=10, total=20) == [
            ELLIPSIS, 8, 9, 10, 11, 12, ELLIPSIS
        ]

    def test_창은_끝에서_줄어들지_않고_안쪽으로_밀린다(self):
        """경계에서 창이 좁아지면 페이저 폭이 흔들려 다음 클릭 위치가 어긋난다.
        2페이지에서도 숫자 5개가 유지되어야 한다."""
        assert [n for n in page_window(current=2, total=20) if n != ELLIPSIS] == [
            1, 2, 3, 4, 5
        ]
        assert [n for n in page_window(current=19, total=20) if n != ELLIPSIS] == [
            16, 17, 18, 19, 20
        ]

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


def _page(number, total_items, per_page=10):
    return Paginator(list(range(total_items)), per_page).get_page(number)


class TestPagerContext:
    def test_화살표_대상은_범위를_벗어나지_않게_고정된다(self):
        first = pager_context(_page(1, 200))
        assert first["previous"] == 1
        assert first["jump_back"] == 1
        assert first["has_previous"] is False

        last = pager_context(_page(20, 200))
        assert last["next"] == 20
        assert last["jump_forward"] == 20
        assert last["has_next"] is False

    def test_점프_화살표는_5페이지씩_이동한다(self):
        ctx = pager_context(_page(10, 200))
        assert ctx["jump_back"] == 5
        assert ctx["jump_forward"] == 15

    def test_점프_화살표는_10페이지_이하에서는_숨는다(self):
        """10페이지 이하면 한 칸씩 넘겨도 충분해서 « »는 자리만 차지한다."""
        assert pager_context(_page(1, 100))["show_jump_arrows"] is False
        assert pager_context(_page(1, 110))["show_jump_arrows"] is True

    def test_생략부호_기호를_컨텍스트로_노출한다(self):
        assert pager_context(_page(1, 200))["ellipsis"] == ELLIPSIS


@pytest.mark.django_db
class TestPagerRendering:
    """페이저는 7개 목록이 공유하는 파셜이라, 컬렉션 하나로 렌더 계약을 고정한다."""

    def _paginated(self, user_client):
        from archive.models import CollectionItem

        user, client = user_client()
        CollectionItem.objects.bulk_create(
            CollectionItem(user=user, name=f"굿즈 {i}", work_title="작품 A")
            for i in range(25)
        )
        return client

    def test_페이저는_현재_페이지를_링크가_아닌_aria_current로_렌더한다(self, user_client):
        html = self._paginated(user_client).get("/collection/").content.decode()

        assert 'class="pager-page is-current" aria-current="page"' in html
        # 현재 페이지가 링크로도 렌더되면 클릭 가능한 제자리 이동이 생긴다
        assert 'class="pager-page" href="?page=1"' not in html

    def test_첫_페이지에서_이전_화살표는_비활성_상태로_자리를_지킨다(self, user_client):
        html = self._paginated(user_client).get("/collection/").content.decode()

        assert '<span class="pager-arrow is-disabled" aria-hidden="true">‹</span>' in html
        assert 'aria-label="다음 페이지"' in html
