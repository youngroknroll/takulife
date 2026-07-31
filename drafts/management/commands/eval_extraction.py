"""관리 명령어: eval_extraction

이미 승인된 드래프트(사람이 검증한 extracted_* 필드)로 골든셋을 만들어, 저장된
raw_title/raw_text로 추출을 다시 돌려 비교한 뒤 필드별 정확도를 보고한다.

골든셋 조건: review_status=APPROVED이고 raw_text가 있어야 한다. raw_text가 없는
승인 드래프트(예: fetch/추출 단계가 없는 create_draft_from_fields로 만든 것)는
다시 돌릴 대상이 없어 제외한다.

Phase 2 자동 승인 게이트의 신뢰도 임계값을 정하는 데 쓰인다 — 이 명령은 보고만
하고 어떤 드래프트도 바꾸거나 게이트하지 않는다.
"""
from django.core.management.base import BaseCommand

from drafts.eval import EVAL_FIELDS, build_field_accuracy_report
from drafts.extraction import extract_event_fields_heuristic
from drafts.llm_extraction import extract_event_fields_llm
from drafts.models import EventDraft


DEFAULT_LIMIT = 100


def _golden_rows(limit):
    """limit: 평가할 최대 행 수(최신순), 0이면 무제한. 행마다 LLM 호출 비용이
    들어가므로 승인 드래프트 테이블이 커도 실수로 무제한 평가가 돌아가지 않게
    막는다."""
    qs = EventDraft.objects.filter(review_status=EventDraft.ReviewStatus.APPROVED).exclude(
        raw_text=""
    ).order_by("-id")
    total = qs.count()
    if limit:
        qs = qs[:limit]
    rows = [
        (
            draft.raw_title,
            draft.raw_text,
            {field: getattr(draft, f"extracted_{field}") for field in EVAL_FIELDS},
        )
        for draft in qs
    ]
    return rows, total


class Command(BaseCommand):
    help = "Report per-field extraction accuracy against approved drafts (golden set)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--heuristic",
            action="store_true",
            help="Evaluate the heuristic extractor instead of the LLM extractor (no API calls).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=DEFAULT_LIMIT,
            help=f"Max golden-set rows to evaluate, most recent first (default {DEFAULT_LIMIT}; 0 = unlimited).",
        )

    def handle(self, *args, **options):
        golden_rows, total = _golden_rows(options["limit"])

        if not golden_rows:
            self.stdout.write("골든셋 없음 (approved drafts with raw_text: 0건)")
            return

        extract_fn = extract_event_fields_heuristic if options["heuristic"] else extract_event_fields_llm
        report = build_field_accuracy_report(golden_rows, extract_fn=extract_fn)

        self.stdout.write(
            f"골든셋 {len(golden_rows)}/전체 {total}건 평가 ({'heuristic' if options['heuristic'] else 'llm'})"
        )
        for row in report["fields"]:
            self.stdout.write(
                f"{row['field']}: {row['correct']}/{row['total']} "
                f"(accuracy={row['accuracy']:.2f}, both_empty={row['both_empty']})"
            )
        self.stdout.write(f"errors={report['errors']} fallback={report['fallback']}")
