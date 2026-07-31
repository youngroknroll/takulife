"""archive 도메인의 읽기 계층 쿼리셋.

상태 값을 모델 상수가 아닌 문자열로 쓰고 VisitRecord를 메서드 안에서 늦게
임포트하는 것은, 모델과 쿼리셋이 서로를 임포트해 순환하는 것을 피하기 위해서다.

놓침(missed) 판정 규칙:
    visited                                            -> visited
    missed (저장된 값)                                  -> missed
    planned, 사용자가 덮어쓰지 않음, 종료일이 있고 지났음,
        방문 기록 없음                                  -> missed (자동)
    그 밖                                               -> planned
"""
from django.db import models
from django.db.models import Case, CharField, Exists, F, OuterRef, Value, When


class UserEventStatusQuerySet(models.QuerySet):
    def with_derived_status(self, *, today):
        """사용자에게 실제로 보이는 상태를 ``derived_status``로 붙인다.

        ``today``를 밖에서 받는 것은 판정을 호출 시점에 고정해 테스트 가능하게
        하려는 것이다.
        """
        from .models import VisitRecord

        no_visit = ~Exists(
            VisitRecord.objects.filter(
                user=OuterRef("user"),
                event=OuterRef("event"),
            )
        )
        return self.annotate(
            derived_status=Case(
                When(status="visited", then=Value("visited")),
                When(status="missed", then=Value("missed")),
                When(
                    no_visit,
                    status="planned",
                    missed_overridden=False,
                    event__end_date__isnull=False,
                    event__end_date__lt=today,
                    then=Value("missed"),
                ),
                default=F("status"),
                output_field=CharField(),
            )
        )
