"""Staff Console views.

PR-1a scope: dashboard shell only. The 3 existing draft/home-category views
stay physically in core.views (smaller diff) and are re-routed here via
staff/urls.py.
"""
from django.shortcuts import render

from drafts.queries import draft_review_stats
from events.queries import published_quality_warnings

from .permissions import staff_console_required


@staff_console_required
def dashboard(request):
    """Staff console landing page.

    `recent_actions` is a placeholder for PR-2 — not implemented yet, so it
    is always None here.
    """
    stats = draft_review_stats()
    return render(
        request,
        "staff/dashboard.html",
        {
            "pending_count": stats["pending"],
            "quality_warnings": published_quality_warnings(),
            "recent_actions": None,
        },
    )
