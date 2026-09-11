"""서버 수집 유형 상수와 콘텐츠타입 매핑이 같은 키 집합을 유지하는지 지키는
가드다. 서버 수집 유형이 늘었는데 콘텐츠타입 매핑을 빠뜨리면 배포 전이 아니라
런타임 조회 실패로 새어나가므로, 그 어긋남을 여기서 먼저 잡는다."""
import pytest

from drafts.candidate_intake import LISTING_CONTENT_TYPES_BY_SOURCE_TYPE
from drafts.models import DraftSource


pytestmark = pytest.mark.contract


def test_서버_수집_유형_상수와_콘텐츠타입_매핑_키가_일치한다():
    assert set(DraftSource.SERVER_COLLECTED_SOURCE_TYPES) == set(
        LISTING_CONTENT_TYPES_BY_SOURCE_TYPE.keys()
    )
