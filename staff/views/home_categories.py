"""스태프 콘솔 화면: 홈 카테고리 타일을 고르고 순서를 정한다."""
from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie

from core.models import HomeConfig
from core.vocab import CATEGORY
from events.models import Event

from ..models import StaffActionLog
from ..permissions import staff_console_required
from ._helpers import _action_log_kwargs, _staff_action_metadata


@staff_console_required
@ensure_csrf_cookie
def staff_home_categories(request):
    """GET은 현재 설정으로 폼을 그리고, POST는 저장 후 리다이렉트한다(PRG)."""
    config = HomeConfig.get_solo()

    if request.method == "POST":
        checked = []
        for slug, _ in CATEGORY:
            if request.POST.get(f"feature_{slug}") == "on":
                try:
                    order = int(request.POST.get(f"order_{slug}", "0"))
                except (ValueError, TypeError):
                    order = 9999  # 값이 이상하면 맨 뒤로 보낸다
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

    featured_set = set(config.featured_categories)
    featured_order = {slug: idx + 1 for idx, slug in enumerate(config.featured_categories)}

    # 게시된 이벤트 수 집계 패턴은 core/views/events.py의 홈 카테고리 타일과 같다(B6).
    # 강조 카테고리를 고를 때 실제로 얼마나 채워져 있는지 보여준다.
    event_counts = {
        row["category"]: row["count"]
        for row in Event.objects.published().values("category").annotate(count=Count("id"))
    }

    category_rows = [
        {
            "slug": slug,
            "label": label,
            "checked": slug in featured_set,
            "order": featured_order.get(slug, vocab_idx + 1),
            "event_count": event_counts.get(slug, 0),
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
