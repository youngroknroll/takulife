from datetime import timedelta

from django.db import models
from django.db.models import Case, DateField, F, IntegerField, Value, When

CLOSING_SOON_DAYS = 4


class EventQuerySet(models.QuerySet):
    def published(self):
        return self.filter(publish_status="published")

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
        return self

    def increment_view_count(self, pk):
        return self.filter(pk=pk).update(view_count=F("view_count") + 1)

    def ending_within_days(self, days, *, today):
        return self.filter(
            start_date__lte=today,
            end_date__gte=today,
            end_date__lte=today + timedelta(days=days),
        ).order_by("end_date", "id")

    def most_viewed(self, limit=5):
        return self.order_by("-view_count", "-id")[:limit]

    def order_for_public_listing(self, *, today):
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
