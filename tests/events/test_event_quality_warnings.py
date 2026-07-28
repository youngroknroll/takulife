"""Tests for events.queries quality-warning counters (staff dashboard PR-1b).

All counters are scoped to Event.objects.published() only. Each predicate is
an independent per-column check (one event can trip multiple warnings), so
there is no if/elif classification anywhere here or in the implementation.
"""
from datetime import date, datetime, timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from events.queries import (
    count_published_ended_still_published,
    count_published_missing_dates,
    count_published_missing_official_url,
    count_published_missing_poster,
    count_published_missing_region,
    count_published_needs_reverification,
    published_quality_warnings,
)

pytestmark = pytest.mark.domain


# ---------------------------------------------------------------------------
# count_published_missing_official_url
# ---------------------------------------------------------------------------


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
        # Guards against a .count() -> .exists() regression: bool is a
        # subclass of int, so an exists()-based count would still pass the
        # 0/1 assertions above but silently break on N>=2.
        # official_url is unique, so use NULL for both (NULLs don't collide;
        # two "" would raise a UNIQUE IntegrityError).
        make_event(official_url=None)
        make_event(official_url=None)

        assert count_published_missing_official_url() == 2


# ---------------------------------------------------------------------------
# count_published_ended_still_published
# ---------------------------------------------------------------------------


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
        # Guards against a .count() -> .exists() regression (bool is a
        # subclass of int; an exists()-based count would still pass 0/1).
        today = date(2020, 6, 15)
        make_event(end_date=today - timedelta(days=1))
        make_event(end_date=today - timedelta(days=2))

        assert count_published_ended_still_published(today=today) == 2


# ---------------------------------------------------------------------------
# count_published_missing_poster
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCountPublishedMissingPoster:
    def test_포스터_이미지가_없으면_누락_건수에_포함된다(self, make_event):
        make_event(official_url=None)

        assert count_published_missing_poster() == 1

    def test_포스터_이미지가_있으면_누락_건수에서_제외된다(self, make_event, png_bytes, settings, tmp_path):
        settings.MEDIA_ROOT = str(tmp_path)
        event = make_event(official_url=None)
        event.poster_image = SimpleUploadedFile(
            "poster.png", png_bytes(), content_type="image/png"
        )
        event.save()

        assert count_published_missing_poster() == 0

    def test_미게시_행사는_포스터_누락_집계에서_제외된다(self, make_draft_event):
        make_draft_event(official_url=None)

        assert count_published_missing_poster() == 0

    def test_행사가_없으면_포스터_누락_건수는_0이다(self):
        assert count_published_missing_poster() == 0

    def test_포스터가_없는_행사가_두_건이면_누락_건수는_2다(self, make_event):
        # Guards against a .count() -> .exists() regression (bool is a
        # subclass of int; an exists()-based count would still pass 0/1).
        make_event(official_url=None)
        make_event(official_url="https://example.com/other")

        assert count_published_missing_poster() == 2


# ---------------------------------------------------------------------------
# count_published_missing_dates
# ---------------------------------------------------------------------------


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
        # Guards against a .count() -> .exists() regression (bool is a
        # subclass of int; an exists()-based count would still pass 0/1).
        make_event(official_url=None, start_date=None, end_date=date(2020, 1, 1))
        make_event(
            official_url="https://example.com/other", start_date=None, end_date=None
        )

        assert count_published_missing_dates() == 2


# ---------------------------------------------------------------------------
# count_published_missing_region
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCountPublishedMissingRegion:
    def test_지역이_빈_문자열이면_지역_누락_건수에_포함된다(self, make_event):
        make_event(official_url=None, region="")

        assert count_published_missing_region() == 1

    def test_지역이_있으면_지역_누락_건수에서_제외된다(self, make_event):
        make_event(official_url=None, region="서울")

        assert count_published_missing_region() == 0

    def test_지역이_공백만_있으면_정규화_없이_지역_누락_건수에서_제외된다(self, make_event):
        # Conscious v1 decision: no strip/normalization. A whitespace-only
        # region is technically "blank" to a human, but this counter only
        # checks region == "" exactly, so it is NOT counted.
        make_event(official_url=None, region=" ")

        assert count_published_missing_region() == 0

    def test_미게시_행사는_지역_누락_집계에서_제외된다(self, make_draft_event):
        make_draft_event(official_url=None, region="")

        assert count_published_missing_region() == 0

    def test_지역이_없는_행사가_두_건이면_누락_건수는_2다(self, make_event):
        # Guards against a .count() -> .exists() regression (bool is a
        # subclass of int; an exists()-based count would still pass 0/1).
        make_event(official_url=None, region="")
        make_event(official_url="https://example.com/other", region="")

        assert count_published_missing_region() == 2


# ---------------------------------------------------------------------------
# published_quality_warnings (composite)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPublishedQualityWarnings:
    def test_행사가_없으면_품질_경고_여섯_항목이_모두_0으로_반환된다(self):
        result = published_quality_warnings()

        assert result == {
            "missing_official_url": 0,
            "ended_still_published": 0,
            "missing_poster": 0,
            "missing_dates": 0,
            "missing_region": 0,
            "needs_reverification": 0,
            "total": 0,
        }
        for value in result.values():
            assert isinstance(value, int)

    def test_품질_경고_총합은_다섯_항목_건수의_합과_같다(self, make_event):
        make_event(official_url=None, region="")

        result = published_quality_warnings()

        assert result["total"] == (
            result["missing_official_url"]
            + result["ended_still_published"]
            + result["missing_poster"]
            + result["missing_dates"]
            + result["missing_region"]
        )

    def test_한_행사가_두_조건에_걸리면_총합에_2가_반영된다(
        self, make_event, png_bytes, settings, tmp_path
    ):
        # official_url and region both missing on the same event, with every
        # other predicate deliberately kept clean: this is a sum-of-flags
        # total, not a distinct-event count, so it contributes exactly 2.
        settings.MEDIA_ROOT = str(tmp_path)
        today = date(2020, 6, 15)
        event = make_event(
            official_url=None,
            region="",
            start_date=date(2020, 1, 1),
            end_date=today + timedelta(days=30),
        )
        event.poster_image = SimpleUploadedFile(
            "poster.png", png_bytes(), content_type="image/png"
        )
        event.save()

        result = published_quality_warnings(today=today)

        assert result["total"] == 2

    def test_각_행사가_서로_다른_조건에_걸리면_해당_항목에만_독립적으로_집계된다(self, make_event, png_bytes, settings, tmp_path):
        settings.MEDIA_ROOT = str(tmp_path)
        today = date(2020, 6, 15)
        future_end = today + timedelta(days=30)

        def _with_poster(event):
            event.poster_image = SimpleUploadedFile(
                "poster.png", png_bytes(), content_type="image/png"
            )
            event.save()
            return event

        # Each event trips exactly one predicate; every other predicate on it
        # is deliberately kept "clean" so the 6 counts stay independent.
        #
        # The official-url/poster/region events below all share
        # start_date=2020-01-01 and an unended future end_date, which also
        # puts them inside the needs_reverification D-7 window. Without an
        # explicit verified_at, they would additionally trip
        # needs_reverification and break the "exactly one predicate" premise
        # this test is named after, so verified_at is set to a moment after
        # their reverify_deadline (2019-12-25) to mark them as already
        # verified and keep needs_reverification at 0 for this test.
        _with_poster(
            make_event(
                official_url=None,
                region="서울",
                start_date=date(2020, 1, 1),
                end_date=future_end,
                verified_at=timezone.make_aware(datetime(2020, 6, 1)),
            )
        )
        _with_poster(
            make_event(
                official_url="https://example.com/ended",
                region="서울",
                start_date=date(2020, 1, 1),
                end_date=today - timedelta(days=1),
            )
        )
        make_event(
            official_url="https://example.com/poster",
            region="서울",
            start_date=date(2020, 1, 1),
            end_date=future_end,
            verified_at=timezone.make_aware(datetime(2020, 6, 1)),
        )  # left without a poster on purpose
        _with_poster(
            make_event(
                official_url="https://example.com/dates",
                region="서울",
                start_date=None,
                end_date=future_end,
            )
        )
        _with_poster(
            make_event(
                official_url="https://example.com/region",
                region="",
                start_date=date(2020, 1, 1),
                end_date=future_end,
                verified_at=timezone.make_aware(datetime(2020, 6, 1)),
            )
        )

        result = published_quality_warnings(today=today)

        assert result == {
            "missing_official_url": 1,
            "ended_still_published": 1,
            "missing_poster": 1,
            "missing_dates": 1,
            "missing_region": 1,
            "needs_reverification": 0,
            "total": 5,
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
            "missing_poster": 0,
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
            end_date=date(2019, 12, 31),  # ended relative to fixed_today only
        )

        result = published_quality_warnings(today=fixed_today)

        assert result["ended_still_published"] == 1


# ---------------------------------------------------------------------------
# Event.verified_at (D-7 재확인 정책, B1)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEventVerifiedAt:
    def test_이벤트를_생성하면_검증_시각은_비어있다(self, make_event):
        event = make_event()

        event.refresh_from_db()

        assert event.verified_at is None


# ---------------------------------------------------------------------------
# count_published_needs_reverification
# ---------------------------------------------------------------------------


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
