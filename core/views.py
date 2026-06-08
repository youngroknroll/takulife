from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response


def home(request):
    return render(
        request,
        "core/home.html",
        {
            "project_name": "takulife",
        },
    )


def event_list(request):
    return render(
        request,
        "core/event_list.html",
        {
            "project_name": "takulife",
        },
    )


def event_detail(request, event_id):
    return render(
        request,
        "core/event_detail.html",
        {
            "project_name": "takulife",
            "event_id": event_id,
        },
    )


def archive(request):
    return render(
        request,
        "core/archive.html",
        {
            "project_name": "takulife",
        },
    )


def archive_statuses(request):
    return render(
        request,
        "core/archive_statuses.html",
        {
            "project_name": "takulife",
        },
    )


def archive_visits(request):
    return render(
        request,
        "core/archive_visits.html",
        {
            "project_name": "takulife",
        },
    )


def event_drafts(request):
    return render(
        request,
        "core/event_drafts.html",
        {
            "project_name": "takulife",
        },
    )


def event_draft_detail(request, draft_id):
    return render(
        request,
        "core/event_draft_detail.html",
        {
            "project_name": "takulife",
            "draft_id": draft_id,
        },
    )


@api_view(["GET"])
def api_root(request):
    return Response({"name": "OshiLog API"})


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})
