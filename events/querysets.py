import calendar
from datetime import date, timedelta

from django.db import models
from django.db.models import Case, DateField, F, IntegerField, Value, When

CLOSING_SOON_DAYS = 4


class EventQuerySet(models.QuerySet):
    def published(self):
        return self.filter(publish_status="published")

    def overlapping_month(self, year, month):
        """Published-or-not events whose run overlaps the given (year, month)
        (dual-calendar service design §6). A null start_date always excludes
        an event. An event with no end_date is treated as a single day on
        start_date, so its "effective end" is start_date itself.
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
            # View-internal only: "active" is not in the public STATUS_CHOICES
            # contract. NULL end_date is kept (SQL NULL < today is unknown, so
            # exclude() does not drop it) — an event with no end date is not
            # ended. `__lt`, not `__lte`: an event ending today is not ended
            # yet.
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

    def most_viewed(self, limit=5):
        return self.order_by("-view_count", "-id")[:limit]

    def related_to(self, event, *, today, limit=3):
        """Related events for a detail page: same category, excluding the event
        itself, ordered by the public-listing state ranking (ongoing → upcoming →
        ended), capped at ``limit``. An event with a blank category has no
        related events. Chain after ``published()`` to restrict to public events.
        """
        if not event.category:
            return self.none()
        return (
            self.filter(category=event.category)
            .exclude(pk=event.pk)
            .order_for_public_listing(today=today)[:limit]
        )

    def order_for_public_listing(self, *, today, sort=None):
        """Order published events for the public listing.

        sort (optional): explicit user-selected ordering from the browse UI's
        "sort" select. When omitted/falsy, falls back to the original
        ongoing/upcoming/ended state ranking below (unchanged behaviour).
        """
        if sort == "closing_soon":
            # "종료 임박순" ranks not-yet-ended events (end_date null or >= today)
            # first, soonest-ending first (nulls last); already-ended events are
            # pushed to the back, most-recently-ended first, so a plain end_date
            # ascending sort never surfaces long-ended events at the top.
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
        if sort == "start_asc":
            return self.order_by("start_date", "id")
        if sort == "newest":
            return self.order_by("-id")

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
