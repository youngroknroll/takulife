"""Staff Console view: select and order the home page category tiles."""
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie

from core.models import HomeConfig
from core.vocab import CATEGORY

from ..models import StaffActionLog
from ..permissions import staff_console_required
from ._helpers import _action_log_kwargs, _staff_action_metadata


@staff_console_required
@ensure_csrf_cookie
def staff_home_categories(request):
    """Staff page: select and order the home page category tiles.

    GET  — render a form with current HomeConfig state.
    POST — parse checked/order fields, validate against vocab, save, redirect (PRG).
    """
    config = HomeConfig.get_solo()

    if request.method == "POST":
        checked = []
        for slug, _ in CATEGORY:
            if request.POST.get(f"feature_{slug}") == "on":
                try:
                    order = int(request.POST.get(f"order_{slug}", "0"))
                except (ValueError, TypeError):
                    order = 9999  # Safe fallback: append to end
                checked.append((slug, order))

        checked.sort(key=lambda pair: pair[1])
        config.featured_categories = [slug for slug, _ in checked]

        with transaction.atomic():
            config.save()
            StaffActionLog.objects.create(
                **_action_log_kwargs(
                    _staff_action_metadata(request), StaffActionLog.Action.HOME_CATEGORIES
                )
            )

        messages.success(request, "카테고리 설정이 저장되었습니다.")
        return redirect("staff:home-categories")

    # GET: build form rows — one per vocab category, with current state
    featured_set = set(config.featured_categories)
    featured_order = {slug: idx + 1 for idx, slug in enumerate(config.featured_categories)}

    category_rows = [
        {
            "slug": slug,
            "label": label,
            "checked": slug in featured_set,
            "order": featured_order.get(slug, vocab_idx + 1),
        }
        for vocab_idx, (slug, label) in enumerate(CATEGORY)
    ]

    return render(
        request,
        "core/staff/home_categories.html",
        {
            "category_rows": category_rows,
            "config": config,
        },
    )
