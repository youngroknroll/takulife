"""Staff Console views.

PR-1a scope: dashboard shell only. The 3 existing draft/home-category views
stay physically in core.views (smaller diff) and are re-routed here via
staff/urls.py.
"""
from django.shortcuts import render

from drafts.queries import draft_review_stats

from .permissions import staff_console_required


@staff_console_required
def dashboard(request):
    """Staff console landing page.

    `quality_warnings` and `recent_actions` are placeholders for PR-1b/PR-2 —
    not implemented yet, so they are always None here.
    """
    stats = draft_review_stats()
    return render(
        request,
        "staff/dashboard.html",
        {
            "pending_count": stats["pending"],
            "quality_warnings": None,
            "recent_actions": None,
        },
    )
