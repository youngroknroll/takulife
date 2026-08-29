import calendar
from datetime import date, timedelta

from django.db import models
from django.db.models import Case, DateField, F, IntegerField, Value, When

CLOSING_SOON_DAYS = 4


class EventQuerySet(models.QuerySet):
    def published(self):
        return self.filter(publish_status="published")

    def overlapping_month(self, year, month):
        """(year, month)와 기간이 겹치는 이벤트(게시 여부 무관, 이중 달력 설계 §6).
        start_date가 없으면 무조건 제외하고, end_date가 없으면 start_date 당일만 있는 것으로 본다.
        """
        month_start = date(year, month, 1)
        month_end = date(year, month, calendar.monthrange(year, month)[1])
        return self.filter(
            start_date__isnull=False,
            start_date__lte=month_end,
        ).filter(
            models.Q(end_date__isnull=True, start_date__gte=month_start)
            | models.Q(end_date__isnull=False, end_date__gte=month_start)
        )

    def filter_for_public_listing(self, params, *, today):
        queryset = self

        if query := params.get("q"):
            queryset = queryset.filter(title__icontains=query)
        if regions := params.get("region"):
            queryset = queryset.filter(region__in=regions)
        if categories := params.get("category"):
            queryset = queryset.filter(category__in=categories)
        if work_title := params.get("work_title"):
            queryset = queryset.filter(work_title__icontains=work_title)
        if start_date_from := params.get("start_date_from"):
            queryset = queryset.filter(start_date__gte=start_date_from)
        if start_date_to := params.get("start_date_to"):
            queryset = queryset.filter(start_date__lte=start_date_to)
        if status := params.get("status"):
            queryset = queryset.with_public_status(status, today=today)

        return queryset

    def with_public_status(self, status, *, today):
        if status == "upcoming":
            return self.filter(start_date__gt=today)
        if status == "ongoing":
            return self.filter(start_date__lte=today, end_date__gte=today)
        if status == "closing_soon":
            return self.filter(
                start_date__lte=today,
                end_date__gte=today,
                end_date__lte=today + timedelta(days=CLOSING_SOON_DAYS),
            )
        if status == "ended":
            return self.filter(end_date__lt=today)
        if status == "active":
            # "active"는 공개 STATUS_CHOICES에 없는 화면 내부 전용 값이다.
            # 종료일이 없는 이벤트는 SQL에서 NULL 비교가 걸러주므로 그대로 유지된다.
            return self.exclude(end_date__lt=today)
        return self

    def increment_view_count(self, pk):
        return self.filter(pk=pk).update(view_count=F("view_count") + 1)

    def ending_within_days(self, days, *, today):
        return self.filter(
            start_date__lte=today,
            end_date__gte=today,
            end_date__lte=today + timedelta(days=days),
        ).order_by("end_date", "id")

    def related_to(self, event, *, today, limit=3):
        """상세 페이지의 관련 이벤트: 같은 카테고리, 자기 자신 제외, 공개 목록과 같은 상태
        순위(진행중→예정→종료)로 정렬해 limit개까지. category가 빈 값이면 결과 없음.
        """
        if not event.category:
            return self.none()
        return (
            self.filter(category=event.category)
            .exclude(pk=event.pk)
            .order_for_public_listing(today=today)[:limit]
        )

    def _ordered_by_closing_soon(self, *, today):
        # 아직 종료 안 된 이벤트(종료일 없음 또는 오늘 이후)를 종료 임박순으로 먼저,
        # 이미 종료된 이벤트는 뒤로 밀어 최근 종료순으로 배치한다.
        return self.annotate(
            _closing_rank=Case(
                When(
                    models.Q(end_date__isnull=True) | models.Q(end_date__gte=today),
                    then=Value(0),
                ),
                default=Value(1),
                output_field=IntegerField(),
            ),
            _closing_active_sort=Case(
                When(
                    models.Q(end_date__isnull=True) | models.Q(end_date__gte=today),
                    then=F("end_date"),
                ),
                output_field=DateField(),
            ),
            _closing_ended_sort=Case(
                When(end_date__lt=today, then=F("end_date")),
                output_field=DateField(),
            ),
        ).order_by(
            "_closing_rank",
            F("_closing_active_sort").asc(nulls_last=True),
            F("_closing_ended_sort").desc(),
            "id",
        )

    def _ordered_by_default_state(self, *, today):
        return self.annotate(
            _state_rank=Case(
                When(start_date__lte=today, end_date__gte=today, then=Value(0)),
                When(start_date__gt=today, then=Value(1)),
                When(end_date__lt=today, then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            ),
            _ongoing_sort=Case(
                When(start_date__lte=today, end_date__gte=today, then=F("end_date")),
                output_field=DateField(),
            ),
            _upcoming_sort=Case(
                When(start_date__gt=today, then=F("start_date")),
                output_field=DateField(),
            ),
            _ended_sort=Case(
                When(end_date__lt=today, then=F("end_date")),
                output_field=DateField(),
            ),
        ).order_by(
            "_state_rank",
            "_ongoing_sort",
            "_upcoming_sort",
            F("_ended_sort").desc(),
            "id",
        )

    def order_for_public_listing(self, *, today, sort=None):
        """게시 이벤트를 공개 목록 순서로 정렬한다. sort 미지정 시 진행중/예정/종료 순위로 정렬한다."""
        if sort == "closing_soon":
            return self._ordered_by_closing_soon(today=today)
        if sort == "start_asc":
            return self.order_by("start_date", "id")
        if sort == "newest":
            return self.order_by("-id")

        return self._ordered_by_default_state(today=today)
