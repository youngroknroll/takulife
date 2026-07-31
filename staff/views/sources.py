"""스태프 콘솔 화면: 수집 소스 전체 목록(N1, `/staff/sources/`).

대시보드의 「수집 소스 상태」 패널과 같은 조회(list_draft_sources)와 같은
행 가공(_build_source_rows)을 그대로 전체 페이지로 확장한다.
"""
from django.shortcuts import render

from drafts.queries import list_draft_sources

from ..permissions import staff_console_required
from ._helpers import _build_source_rows


@staff_console_required
def staff_draft_sources(request):
    sources = list_draft_sources()
    return render(
        request,
        "staff/sources/list.html",
        {
            "draft_sources": sources,
            "draft_source_rows": _build_source_rows(sources),
        },
    )
