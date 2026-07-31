"""감사 로그·대시보드가 쓰는 행동 라벨이 모든 행동을 덮는지 본다.

빠지면 화면에 영어 코드(`event_verify` 등)가 그대로 새어 나간다 —
실제로 event_verify가 그렇게 빠져 있었다.
"""
import pytest

from staff.action_labels import ACTION_LABELS
from staff.models import StaffActionLog

pytestmark = pytest.mark.contract


def test_모든_스태프_행동에_한국어_표시_라벨이_있다():
    missing = [value for value in StaffActionLog.Action.values if value not in ACTION_LABELS]

    assert missing == [], missing
