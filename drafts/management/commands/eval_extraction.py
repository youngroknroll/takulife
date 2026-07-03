"""Management command: eval_extraction

Reports per-field extraction accuracy against a golden set built from
already-approved drafts (human-verified extracted_* fields), by re-running
extraction over each draft's stored raw_title/raw_text and comparing.

Golden set membership: review_status=APPROVED and raw_text present. Approved
drafts with no raw_text (e.g. created via create_draft_from_fields, which has
no fetch/extraction step) have nothing to re-run extraction against and are
excluded.

Feeds the confidence-threshold calibration for the Phase 2 auto-approve gate
(see prompt_plan.md DEFERRED #1) — this command only reports, it does not
gate or change any draft.
"""
from django.core.management.base import BaseCommand

from drafts.eval import EVAL_FIELDS, build_field_accuracy_report
from drafts.extraction import extract_event_fields_heuristic
from drafts.llm_extraction import extract_event_fields_llm
from drafts.models import EventDraft


DEFAULT_LIMIT = 100


def _golden_rows(limit):
    """limit: max rows to evaluate (most recent first), 0 = unlimited.

    LLM calls cost money per row (SEC guard) — this bounds an accidental
    unbounded eval run against a large approved-draft table.
    """
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
