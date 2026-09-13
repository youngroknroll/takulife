"""스태프 카테고리 관리 화면(`/staff/categories/`) — 트랙 27 11단계.

팔레트 슬롯 반납·재획득은 이 모듈이 직접 수행하지 않는다 — 활성 상태
전이는 Category.save()의 신호(core.models.category_deactivated →
events/signals.py → core.categories.reconcile_palette_slot)가 이미
처리하므로, 조회(GET) 경로는 물론 이 안에서도 절대 재계산을 호출하지
않는다.
"""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.categories import palette_hex_for
from core.models import Category
from core.validators import validate_category_slug
from events.models import Event

from ..models import StaffActionLog
from ..permissions import superuser_console_required
from ._helpers import _action_log_kwargs, _staff_action_metadata

_ENABLED_VALUES = {"1": True, "0": False}

_ACTIVE_LABELS = {
    True: ("카테고리 활성화", "이 카테고리를 다시 활성화해 소비자 필터에 노출합니다."),
    False: ("카테고리 비활성화", "이 카테고리를 비활성화해 신규 등록 선택지에서 제외합니다."),
}


@superuser_console_required
def category_list(request):
    categories = list(Category.objects.all())
    event_counts = {
        row["category"]: row["count"]
        for row in Event.objects.published().values("category").annotate(count=Count("id"))
    }

    category_rows = [
        {
            "id": category.id,
            "slug": category.slug,
            "label": category.label,
            "is_active": category.is_active,
            "palette_slot": category.palette_slot,
            "palette_hex": palette_hex_for(category.palette_slot),
            "event_count": event_counts.get(category.slug, 0),
        }
        for category in categories
    ]
    assigned_slot_count = sum(1 for category in categories if category.palette_slot is not None)

    return render(
        request,
        "staff/categories/list.html",
        {
            "category_rows": category_rows,
            "assigned_slot_count": assigned_slot_count,
            "palette_slot_count": Category.PALETTE_SLOT_COUNT,
            "slots_exhausted": assigned_slot_count >= Category.PALETTE_SLOT_COUNT,
        },
    )


@superuser_console_required
def category_create(request):
    assigned_slot_count = Category.objects.exclude(palette_slot=None).count()
    slots_exhausted = assigned_slot_count >= Category.PALETTE_SLOT_COUNT

    if request.method != "POST":
        if slots_exhausted:
            messages.error(request, "팔레트 슬롯이 모두 배정돼 새 카테고리를 만들 수 없습니다.")
            return redirect("staff:category-list")
        return render(
            request,
            "staff/categories/create.html",
            {
                "form_values": {"slug": "", "label": ""},
                "field_errors": {},
                "assigned_slot_count": assigned_slot_count,
                "palette_slot_count": Category.PALETTE_SLOT_COUNT,
            },
        )

    slug = request.POST.get("slug", "")
    label = request.POST.get("label", "")
    form_values = {"slug": slug, "label": label}
    field_errors = {}

    try:
        validate_category_slug(slug)
    except ValidationError as exc:
        field_errors["slug"] = exc.messages[0]

    if not label:
        field_errors["label"] = "라벨을 입력하세요."

    if not field_errors:
        with transaction.atomic():
            # 기존 행 전체를 잠가 동시 생성 요청이 같은 슬롯을 두고 경합하지
            # 못하게 한다(BIR D4 TOCTOU) — 커밋 전까지 다른 요청의
            # select_for_update가 이 잠금에 걸려 대기한다.
            locked_slots = list(
                Category.objects.select_for_update().values_list("palette_slot", flat=True)
            )
            locked_assigned = sum(1 for slot in locked_slots if slot is not None)
            if locked_assigned >= Category.PALETTE_SLOT_COUNT:
                messages.error(request, "팔레트 슬롯이 모두 배정돼 새 카테고리를 만들 수 없습니다.")
                return render(
                    request,
                    "staff/categories/create.html",
                    {
                        "form_values": form_values,
                        "field_errors": {},
                        "assigned_slot_count": locked_assigned,
                        "palette_slot_count": Category.PALETTE_SLOT_COUNT,
                    },
                )

            category = None
            try:
                # 내부 atomic()은 세이브포인트라, IntegrityError가 나도
                # 바깥의 select_for_update 잠금과 트랜잭션은 살아 있어
                # 곧이어 Category.objects.filter(...)로 원인을 다시 읽을 수 있다.
                with transaction.atomic():
                    category = Category.objects.create(slug=slug, label=label)
            except IntegrityError:
                if Category.objects.filter(slug=slug).exists():
                    field_errors["slug"] = "이미 사용 중인 슬러그입니다."
                if Category.objects.filter(label=label).exists():
                    field_errors["label"] = "이미 사용 중인 라벨입니다."
                if not field_errors:
                    field_errors["non_field"] = "저장하지 못했습니다. 다시 시도하세요."
            else:
                StaffActionLog.objects.create(
                    **_action_log_kwargs(
                        _staff_action_metadata(request),
                        StaffActionLog.Action.CATEGORY_CREATE,
                        target_category=category,
                    )
                )

    if field_errors:
        return render(
            request,
            "staff/categories/create.html",
            {
                "form_values": form_values,
                "field_errors": field_errors,
                "assigned_slot_count": Category.objects.exclude(palette_slot=None).count(),
                "palette_slot_count": Category.PALETTE_SLOT_COUNT,
            },
        )

    messages.success(request, "카테고리가 생성되었습니다.")
    return redirect("staff:category-list")


@superuser_console_required
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)

    if request.method != "POST":
        return render(
            request,
            "staff/categories/edit.html",
            {
                "category": category,
                "form_values": {"label": category.label},
                "field_errors": {},
                "palette_hex": palette_hex_for(category.palette_slot),
            },
        )

    label = request.POST.get("label", "")
    form_values = {"label": label}
    field_errors = {}

    if not label:
        field_errors["label"] = "라벨을 입력하세요."

    if not field_errors:
        try:
            with transaction.atomic():
                category.label = label
                category.save(update_fields=["label"])
                StaffActionLog.objects.create(
                    **_action_log_kwargs(
                        _staff_action_metadata(request),
                        StaffActionLog.Action.CATEGORY_UPDATE,
                        target_category=category,
                    )
                )
        except IntegrityError:
            field_errors["label"] = "이미 사용 중인 라벨입니다."

    if field_errors:
        return render(
            request,
            "staff/categories/edit.html",
            {
                "category": category,
                "form_values": form_values,
                "field_errors": field_errors,
                "palette_hex": palette_hex_for(category.palette_slot),
            },
        )

    messages.success(request, "카테고리가 수정되었습니다.")
    return redirect("staff:category-list")


@superuser_console_required
@require_POST
def category_set_active(request, pk):
    enabled_raw = request.POST.get("enabled")
    if enabled_raw not in _ENABLED_VALUES:
        return HttpResponseBadRequest("enabled는 1 또는 0만 허용합니다.")
    enabled = _ENABLED_VALUES[enabled_raw]
    category = get_object_or_404(Category, pk=pk)
    action_label, description = _ACTIVE_LABELS[enabled]

    if request.POST.get("confirmed") != "yes":
        return render(
            request,
            "staff/categories/confirm.html",
            {
                "category": category,
                "enabled": enabled,
                "action_label": action_label,
                "description": description,
                "post_url": reverse("staff:category-set-active", args=[pk]),
            },
        )

    changed = False
    with transaction.atomic():
        # 목표 상태 지정이라도 읽고-바꾸는 흐름이라 잠그지 않으면 동시
        # 요청이 같은 상태를 읽고 경쟁한다(계정 활성화 토글과 같은 이유).
        target = get_object_or_404(Category.objects.select_for_update(), pk=pk)
        if target.is_active != enabled:
            target.is_active = enabled
            target.save(update_fields=["is_active"])
            changed = True
            StaffActionLog.objects.create(
                **_action_log_kwargs(
                    _staff_action_metadata(request),
                    StaffActionLog.Action.CATEGORY_ENABLE
                    if enabled
                    else StaffActionLog.Action.CATEGORY_DISABLE,
                    target_category=target,
                )
            )

    if changed:
        messages.success(request, f"{action_label}가 적용되었습니다.")
    else:
        messages.info(request, "이미 해당 상태라 변경하지 않았습니다.")
    return redirect("staff:category-list")
