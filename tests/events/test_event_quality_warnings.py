"""events.queries의 품질경고 카운터(스태프 대시보드)를 검증한다.

모든 카운터는 Event.objects.published()만을 대상으로 한다. 각 판정은
컬럼별 독립 검사라(한 행사가 여러 경고에 걸릴 수 있다) 여기에도
구현에도 if/elif 식 분류는 없다.
"""
from datetime import date, datetime, timedelta

import pytest
from django.utils import timezone

from events.queries import (
    count_published_ended_still_published,
    count_published_missing_dates,
    count_published_missing_official_url,
    count_published_missing_region,
    count_published_needs_reverification,
    published_quality_warnings,
)

pytestmark = pytest.mark.domain


@pytest.mark.django_db
class TestCountPublishedMissingOfficialUrl:
    def test_공식_url이_null이면_누락_건수에_포함된다(self, make_event):
        make_event(official_url=None)

        assert count_published_missing_official_url() == 1

    def test_공식_url이_빈_문자열이면_누락_건수에_포함된다(self, make_event):
        make_event(official_url="")

        assert count_published_missing_official_url() == 1

    def test_공식_url이_있으면_누락_건수에서_제외된다(self, make_event):
        make_event(official_url="https://example.com/a")

        assert count_published_missing_official_url() == 0

    def test_미게시_행사는_공식_url_누락_집계에서_제외된다(self, make_draft_event):
        make_draft_event(official_url=None)

        assert count_published_missing_official_url() == 0

    def test_행사가_없으면_공식_url_누락_건수는_0이다(self):
        assert count_published_missing_official_url() == 0

    def test_공식_url이_있는_행사와_없는_행사가_섞이면_없는_행사만_집계된다(self, make_event):
        make_event(official_url=None)
        make_event(official_url="https://example.com/b")

        assert count_published_missing_official_url() == 1

    def test_공식_url이_없는_행사가_두_건이면_누락_건수는_2다(self, make_event):
        # count() 대신 exists()로 되돌리는 뮤테이션은 0/1 케이스는 통과하지만
        # 2건부터는 걸러내지 못해, 이 테스트로 잡는다. official_url은 유니크
        # 제약이라 둘 다 NULL로 둔다("" 두 개는 제약 위반이 난다).
        make_event(official_url=None)
        make_event(official_url=None)

        assert count_published_missing_official_url() == 2


@pytest.mark.django_db
class TestCountPublishedEndedStillPublished:
    def test_종료일이_오늘보다_이전이면_종료후_게시_건수에_포함된다(self, make_event):
        today = date(2020, 6, 15)
        make_event(end_date=today - timedelta(days=1))

        assert count_published_ended_still_published(today=today) == 1

    def test_종료일이_오늘과_같으면_종료후_게시_건수에서_제외된다(self, make_event):
        today = date(2020, 6, 15)
        make_event(end_date=today)

        assert count_published_ended_still_published(today=today) == 0

    def test_종료일이_오늘보다_이후면_종료후_게시_건수에서_제외된다(self, make_event):
        today = date(2020, 6, 15)
        make_event(end_date=today + timedelta(days=1))

        assert count_published_ended_still_published(today=today) == 0

    def test_종료일이_없으면_오류_없이_종료후_게시_건수에서_제외된다(self, make_event):
        today = date(2020, 6, 15)
        make_event(end_date=None)

        assert count_published_ended_still_published(today=today) == 0

    def test_미게시_행사는_종료후_게시_집계에서_제외된다(self, make_draft_event):
        today = date(2020, 6, 15)
        make_draft_event(end_date=today - timedelta(days=1))

        assert count_published_ended_still_published(today=today) == 0

    def test_행사가_없으면_종료후_게시_건수는_0이다(self):
        today = date(2020, 6, 15)

        assert count_published_ended_still_published(today=today) == 0

    def test_기준일을_생략해도_오류_없이_정수_건수를_반환한다(self, make_event):
        make_event(end_date=date(2000, 1, 1))

        result = count_published_ended_still_published()

        assert isinstance(result, int)

    def test_종료일이_지난_행사가_두_건이면_종료후_게시_건수는_2다(self, make_event):
        # count() 대신 exists()로 되돌리는 뮤테이션은 0/1 케이스는 통과하지만
        # 2건부터는 걸러내지 못해, 이 테스트로 잡는다.
        today = date(2020, 6, 15)
        make_event(end_date=today - timedelta(days=1))
        make_event(end_date=today - timedelta(days=2))

        assert count_published_ended_still_published(today=today) == 2


@pytest.mark.django_db
class TestCountPublishedMissingDates:
    def test_시작일이_없으면_날짜_누락_건수에_포함된다(self, make_event):
        make_event(official_url=None, start_date=None, end_date=date(2020, 1, 1))

        assert count_published_missing_dates() == 1

    def test_종료일이_없으면_날짜_누락_건수에_포함된다(self, make_event):
        make_event(official_url=None, start_date=date(2020, 1, 1), end_date=None)

        assert count_published_missing_dates() == 1

    def test_시작일과_종료일이_모두_있으면_날짜_누락_건수에서_제외된다(self, make_event):
        make_event(
            official_url=None, start_date=date(2020, 1, 1), end_date=date(2020, 1, 2)
        )

        assert count_published_missing_dates() == 0

    def test_시작일과_종료일이_모두_없어도_날짜_누락_건수에는_한_번만_집계된다(self, make_event):
        make_event(official_url=None, start_date=None, end_date=None)

        assert count_published_missing_dates() == 1

    def test_미게시_행사는_날짜_누락_집계에서_제외된다(self, make_draft_event):
        make_draft_event(official_url=None, start_date=None, end_date=None)

        assert count_published_missing_dates() == 0

    def test_날짜가_누락된_행사가_두_건이면_날짜_누락_건수는_2다(self, make_event):
        # count() 대신 exists()로 되돌리는 뮤테이션은 0/1 케이스는 통과하지만
        # 2건부터는 걸러내지 못해, 이 테스트로 잡는다.
        make_event(official_url=None, start_date=None, end_date=date(2020, 1, 1))
        make_event(
            official_url="https://example.com/other", start_date=None, end_date=None
        )

        assert count_published_missing_dates() == 2


@pytest.mark.django_db
class TestCountPublishedMissingRegion:
    def test_지역이_빈_문자열이면_지역_누락_건수에_포함된다(self, make_event):
        make_event(official_url=None, region="")

        assert count_published_missing_region() == 1

    def test_지역이_있으면_지역_누락_건수에서_제외된다(self, make_event):
        make_event(official_url=None, region="서울")

        assert count_published_missing_region() == 0

    def test_지역이_공백만_있으면_정규화_없이_지역_누락_건수에서_제외된다(self, make_event):
        # v1의 의도적 결정: 공백 트림·정규화를 하지 않는다. 사람 눈엔 공백만
        # 있는 지역도 "빈 값"처럼 보이지만, 이 카운터는 region == ""만 판정하므로
        # 여기서는 집계되지 않는다.
        make_event(official_url=None, region=" ")

        assert count_published_missing_region() == 0

    def test_미게시_행사는_지역_누락_집계에서_제외된다(self, make_draft_event):
        make_draft_event(official_url=None, region="")

        assert count_published_missing_region() == 0

    def test_지역이_없는_행사가_두_건이면_누락_건수는_2다(self, make_event):
        # count() 대신 exists()로 되돌리는 뮤테이션은 0/1 케이스는 통과하지만
        # 2건부터는 걸러내지 못해, 이 테스트로 잡는다.
        make_event(official_url=None, region="")
        make_event(official_url="https://example.com/other", region="")

        assert count_published_missing_region() == 2


@pytest.mark.django_db
class TestPublishedQualityWarnings:
    def test_행사가_없으면_품질_경고_다섯_항목이_모두_0으로_반환된다(self):
        result = published_quality_warnings()

        assert result == {
            "missing_official_url": 0,
            "ended_still_published": 0,
            "missing_dates": 0,
            "missing_region": 0,
            "needs_reverification": 0,
            "total": 0,
        }
        for value in result.values():
            assert isinstance(value, int)

    def test_품질_경고_총합은_네_항목_건수의_합과_같다(self, make_event):
        make_event(official_url=None, region="")

        result = published_quality_warnings()

        assert result["total"] == (
            result["missing_official_url"]
            + result["ended_still_published"]
            + result["missing_dates"]
            + result["missing_region"]
        )

    def test_한_행사가_두_조건에_걸리면_총합에_2가_반영된다(self, make_event):
        # 한 행사에서 공식 url과 지역이 동시에 누락되고 다른 조건은 모두
        # 통과시켰다. total은 행사 수가 아니라 깃발의 합이므로 정확히 2가 된다.
        today = date(2020, 6, 15)
        make_event(
            official_url=None,
            region="",
            start_date=date(2020, 1, 1),
            end_date=today + timedelta(days=30),
        )

        result = published_quality_warnings(today=today)

        assert result["total"] == 2

    def test_각_행사가_서로_다른_조건에_걸리면_해당_항목에만_독립적으로_집계된다(self, make_event):
        today = date(2020, 6, 15)
        future_end = today + timedelta(days=30)

        # 각 행사는 정확히 한 조건에만 걸리도록 나머지 조건은 모두 깨끗하게
        # 둔다. 아래 공식url/지역 행사들은 start_date=2020-01-01과 아직
        # 끝나지 않은 미래 end_date를 공유해 D-7 재확인 창 안에도 들어간다.
        # verified_at을 명시하지 않으면 이들도 needs_reverification에 함께
        # 걸려 "정확히 한 조건"이라는 전제가 깨지므로, reverify_deadline
        # (2019-12-25) 이후 시각으로 verified_at을 설정해 이미 검증된 상태로
        # 만든다.
        make_event(
            official_url=None,
            region="서울",
            start_date=date(2020, 1, 1),
            end_date=future_end,
            verified_at=timezone.make_aware(datetime(2020, 6, 1)),
        )
        make_event(
            official_url="https://example.com/ended",
            region="서울",
            start_date=date(2020, 1, 1),
            end_date=today - timedelta(days=1),
        )
        make_event(
            official_url="https://example.com/dates",
            region="서울",
            start_date=None,
            end_date=future_end,
        )
        make_event(
            official_url="https://example.com/region",
            region="",
            start_date=date(2020, 1, 1),
            end_date=future_end,
            verified_at=timezone.make_aware(datetime(2020, 6, 1)),
        )

        result = published_quality_warnings(today=today)

        assert result == {
            "missing_official_url": 1,
            "ended_still_published": 1,
            "missing_dates": 1,
            "missing_region": 1,
            "needs_reverification": 0,
            "total": 4,
        }

    def test_재확인_대상_행사가_있어도_총합에는_반영되지_않고_재확인_대상_건수에는_실제_값이_반영된다(
        self, make_event
    ):
        # 나머지 네 조건(공식url·종료·날짜·지역)은 모두 깨끗하게 채우고,
        # start_date를 오늘로 잡아 D-7 재확인 창 안에 들어오게 한다.
        # verified_at은 의도적으로 비워 둔다(NULL): 미검증 행사가 이
        # 시나리오의 전제다.
        today = date(2020, 6, 15)
        make_event(
            official_url="https://example.com/reverify",
            region="서울",
            start_date=today,
            end_date=today + timedelta(days=30),
        )

        result = published_quality_warnings(today=today)

        # 핵심 단언은 total == 0: needs_reverification은 1이지만 total은
        # 그것을 세지 않는다. total 계산에서 5번째 항목(needs_reverification)이
        # 빠진다는 결정을 여기서 고정한다.
        assert result == {
            "missing_official_url": 0,
            "ended_still_published": 0,
            "missing_dates": 0,
            "missing_region": 0,
            "needs_reverification": 1,
            "total": 0,
        }

    def test_한_행사가_두_조건에_걸리면_해당_두_항목_각각에_1씩_집계된다(self, make_event):
        make_event(official_url=None, region="")

        result = published_quality_warnings()

        assert result["missing_official_url"] == 1
        assert result["missing_region"] == 1

    def test_미게시_행사는_모든_조건에_걸려도_품질_경고_집계가_0이다(self, make_draft_event):
        today = date(2020, 6, 15)
        make_draft_event(
            official_url=None,
            region="",
            start_date=None,
            end_date=today - timedelta(days=1),
        )

        result = published_quality_warnings(today=today)

        assert result == {
            "missing_official_url": 0,
            "ended_still_published": 0,
            "missing_dates": 0,
            "missing_region": 0,
            "needs_reverification": 0,
            "total": 0,
        }

    def test_행사_품질_요약은_포스터_경고_없이_네_표시_항목만_합산한다(self, make_event):
        # 공식url·지역을 채우고, 날짜는 시작이 today+30(=D-7 재확인 창 밖)이라
        # needs_reverification에도 안 걸리도록 명시적으로 "깨끗한" 행사를
        # 만든다. verified_at은 굳이 채우지 않아도 D-7 창 자체가 안 열린다.
        today = date(2020, 6, 15)
        make_event(
            official_url="https://example.com/clean",
            region="서울",
            start_date=today + timedelta(days=30),
            end_date=today + timedelta(days=40),
        )

        result = published_quality_warnings(today=today)

        # missing_poster 키가 이제 없다는 것 자체가 이 단언의 핵심이다: 포스터
        # 필드가 품질 조건에서 완전히 빠진 반환 계약을 고정한다.
        assert result == {
            "missing_official_url": 0,
            "ended_still_published": 0,
            "missing_dates": 0,
            "missing_region": 0,
            "needs_reverification": 0,
            "total": 0,
        }

    def test_기준일_인자가_종료후_게시_판정에도_전달된다(self, make_event):
        fixed_today = date(2020, 1, 1)
        make_event(
            official_url="https://example.com/x",
            region="서울",
            start_date=date(2019, 1, 1),
            end_date=date(2019, 12, 31),  # fixed_today 기준으로만 종료된 상태다
        )

        result = published_quality_warnings(today=fixed_today)

        assert result["ended_still_published"] == 1


@pytest.mark.django_db
class TestEventVerifiedAt:
    def test_이벤트를_생성하면_검증_시각은_비어있다(self, make_event):
        event = make_event()

        event.refresh_from_db()

        assert event.verified_at is None


@pytest.mark.django_db
class TestCountPublishedNeedsReverification:
    def test_시작이_임박한_행사가_검증_이력이_없으면_재확인_대상_건수에_포함된다(self, make_event):
        today = date(2020, 6, 15)
        make_event(
            official_url=None,
            start_date=today,
            end_date=today + timedelta(days=1),
        )

        assert count_published_needs_reverification(today=today) == 1

    def test_시작일이_없는_행사는_재확인_대상_건수에서_제외된다(self, make_event):
        # end_date는 오늘로부터 30일 뒤(아직 종료되지 않은 유효한 미래 날짜)로
        # 명시해, D-7 상한("종료 안 된 행사") 게이트는 통과시킨다. 이렇게 해야
        # start_date=None 단 하나만이 이 행을 배제하는 유일한 이유가 된다 —
        # end_date까지 기본값(NULL)에 맡기면 두 게이트가 동시에 걸려, start_date
        # 배제 로직만 되돌리는 뮤테이션에도 거짓으로 초록이 나온다.
        today = date(2020, 6, 15)
        make_event(
            official_url=None,
            start_date=None,
            end_date=today + timedelta(days=30),
        )

        assert count_published_needs_reverification(today=today) == 0

    def test_시작일이_오늘로부터_8일_뒤이면_아직_재확인_대상이_아니다(self, make_event):
        # end_date는 오늘로부터 30일 뒤로 명시해 "종료 안 된 행사" 게이트를
        # 통과시킨다. D-7 창(시작일 - 7일 <= 오늘) 경계 하나만이 이 행을
        # 배제하는 유일한 이유가 되게 한다.
        today = date(2020, 6, 15)
        make_event(
            official_url=None,
            start_date=today + timedelta(days=8),
            end_date=today + timedelta(days=30),
        )

        assert count_published_needs_reverification(today=today) == 0

    def test_시작일이_오늘로부터_정확히_7일_뒤이면_재확인_대상_건수에_포함된다(self, make_event):
        # end_date는 오늘로부터 30일 뒤로 명시해 "종료 안 된 행사" 게이트를
        # 통과시킨다. D-7 창 경계(시작일 - 7일 == 오늘)가 포함되는지가
        # 이 테스트의 유일한 관심사다.
        today = date(2020, 6, 15)
        make_event(
            official_url=None,
            start_date=today + timedelta(days=7),
            end_date=today + timedelta(days=30),
        )

        assert count_published_needs_reverification(today=today) == 1

    def test_종료일이_없는_행사는_재확인_대상_건수에서_제외된다(self, make_event):
        # start_date는 오늘로 명시해, D-7 기한 게이트(오늘로부터 7일 이내 시작)를
        # 이미 충족시킨다. 이렇게 해야 end_date=None 단 하나만이 이 행을 배제하는
        # 유일한 이유가 된다 — start_date까지 기본값(NULL)에 맡기면 두 게이트가
        # 동시에 걸려, end_date 배제 로직만 되돌리는 뮤테이션에도 거짓으로
        # 초록이 나온다.
        today = date(2020, 6, 15)
        make_event(
            official_url=None,
            start_date=today,
            end_date=None,
        )

        assert count_published_needs_reverification(today=today) == 0

    def test_이미_종료된_행사는_D_7_창_안에_있어도_재확인_대상_건수에서_제외된다(self, make_event):
        # start_date는 오늘로부터 90일 전으로 명시해, D-7 창 조건(시작일 - 7일
        # <= 오늘)을 통과시킨다. verified_at은 기본값(NULL)에 맡겨 신선도
        # 조건도 무조건 참이 되게 한다. 두 조건 모두 통과한 상태에서 남는
        # 유일한 배제 사유는 end_date가 60일 전이라 "종료 안 된 행사"라는
        # 상한 절뿐이다 — 몇 달 전 미검증 행사가 영원히 경고로 남는 것을
        # 막는 그 절이다.
        today = date(2020, 6, 15)
        make_event(
            official_url=None,
            start_date=today - timedelta(days=90),
            end_date=today - timedelta(days=60),
        )

        assert count_published_needs_reverification(today=today) == 0

    def test_종료일이_오늘이면_아직_재확인_대상_건수에_포함된다(self, make_event):
        # start_date와 end_date를 둘 다 오늘로 명시해 D-7 창 조건을 확실히
        # 통과시킨다. verified_at은 기본값(NULL)에 맡겨 신선도 조건도 무조건
        # 참이 되게 한다. end_date == today 경계가 아직 배제 대상이 아님을
        # 확인한다.
        today = date(2020, 6, 15)
        make_event(
            official_url=None,
            start_date=today,
            end_date=today,
        )

        assert count_published_needs_reverification(today=today) == 1

    def test_검증_시각이_재확인_기한일과_같으면_아직_재확인_대상이_아니다(self, make_event):
        # start_date는 오늘로부터 7일 뒤로 잡아 reverify_deadline(start_date - 7일)이
        # 정확히 오늘이 되게 한다. end_date는 오늘로부터 30일 뒤로 명시해 "종료 안
        # 된 행사" 상한 게이트를 통과시킨다. verified_at을 기한일 당일로 잡으면
        # 신선도 절만이 이 행을 배제하는 유일한 이유가 된다.
        today = date(2020, 6, 15)
        make_event(
            official_url=None,
            start_date=today + timedelta(days=7),
            end_date=today + timedelta(days=30),
            verified_at=timezone.make_aware(datetime(2020, 6, 15, 9, 0)),
        )

        assert count_published_needs_reverification(today=today) == 0

    def test_검증_시각이_재확인_기한일보다_이전이면_재확인_대상_건수에_포함된다(self, make_event):
        # 기한 여백 12일 + 검증 격차 5일: B2/B3에 배정된 days=6/days=8 뮤테이션이
        # 만드는 ±1일 이동에 이 테스트가 흔들리지 않도록 일부러 여유를 크게
        # 두었다(둘 다 D-7 창 경계 검증용이며, 기한 여백을 0으로 잡으면 이 행이
        # 신선도 절에 닿기도 전에 D-7 게이트에서 먼저 탈락해버린다). start_date는
        # 오늘로부터 5일 전(reverify_deadline = 오늘 - 12일)으로 잡아 D-7 창
        # 조건을 확실히 통과시키고, end_date는 오늘로부터 30일 뒤로 명시해 "종료
        # 안 된 행사" 상한 게이트도 통과시킨다.
        today = date(2020, 6, 15)
        make_event(
            official_url=None,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=30),
            verified_at=timezone.make_aware(datetime(2020, 5, 29, 10, 0)),
        )

        assert count_published_needs_reverification(today=today) == 1
