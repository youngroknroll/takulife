"""러너 전체가 같은 "오늘"을 쓰게 하는 공용 시각 유틸이다."""
from datetime import datetime
from zoneinfo import ZoneInfo

# 해외·지난 행사 판정, 해석·탐색 프롬프트의 "오늘" 모두 이 기준으로 통일한다 —
# 서버·러너가 같은 날짜에서 어긋나지 않게 하려는 것이다.
_KST = ZoneInfo("Asia/Seoul")


def today_kst():
    return datetime.now(_KST).date()
