"""Read layer querysets for the archive domain.

Keeps reusable query intent (the derived 'missed' overlay) in the queryset,
mirroring events/querysets.py. Status values are string literals so this module
does not import its own model back (avoids a model<->queryset import cycle);
VisitRecord is imported lazily inside the method for the same reason.

Derivation contract (see .docs/plans/2026-06-26-archive-missed-status-design.md):
    visited                                            -> visited
    missed (stored)                                    -> missed
    planned, not overridden, end_date < today,
        end_date not null, no visit record             -> missed (auto)
    otherwise                                          -> planned
"""
from django.db import models
from django.db.models import Case, CharField, Exists, F, OuterRef, Value, When


class UserEventStatusQuerySet(models.QuerySet):
    def with_derived_status(self, *, today):
        """Annotate ``derived_status`` — the effective status shown to the user.

        ``today`` is passed in (caller uses ``timezone.localdate()``) so the
        overlay is deterministic and testable, exactly like EventQuerySet.
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
