"""events.presenters.is_recently_added(신규 뱃지 노출 기간)에 대한 단위 테스트.

created_at으로부터 NEW_WINDOW_DAYS(10)일 미만이면 "신규"다(0~9일차는 신규,
10일차부터는 아니다). 이 헬퍼는 event.created_at만 읽으므로 DB 없이 단순
스텁 객체로 경계값을 검증한다.
"""
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from events.presenters import NEW_WINDOW_DAYS, is_recently_added

pytestmark = pytest.mark.unit

TODAY = date(2026, 6, 27)


def _event(created):
    return SimpleNamespace(created_at=created)


class TestIsRecentlyAdded:
    def test_신규_뱃지_노출_기간_상수는_10일이다(self):
        assert NEW_WINDOW_DAYS == 10

    def test_오늘_생성된_행사는_신규로_판정된다(self):
        assert is_recently_added(_event(datetime(2026, 6, 27, 9, 0)), today=TODAY) is True

    def test_9일_전에_생성된_행사는_아직_신규로_판정된다(self):
        assert is_recently_added(_event(datetime(2026, 6, 18, 23, 0)), today=TODAY) is True

    def test_정확히_10일_전에_생성된_행사는_더이상_신규가_아니다(self):
        assert is_recently_added(_event(datetime(2026, 6, 17, 1, 0)), today=TODAY) is False

    def test_오래전에_생성된_행사는_신규가_아니다(self):
        assert is_recently_added(_event(datetime(2020, 1, 1, 0, 0)), today=TODAY) is False

    def test_생성_시각이_없으면_신규로_판정되지_않는다(self):
        assert is_recently_added(_event(None), today=TODAY) is False
