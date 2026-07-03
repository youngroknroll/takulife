"""Pure field-accuracy evaluation for draft extraction.

Compares a golden set (human-approved draft fields) against a fresh
extract_fn run over the same raw_title/raw_text, to calibrate LLM vs
heuristic extraction before any auto-approve gate is trusted (Phase 2).

No DB access here — drafts/management/commands/eval_extraction.py is the
thin, DB-aware caller that builds golden_rows and picks extract_fn.
"""
from .extraction import normalize_whitespace

# category/region/start_date/end_date compare exact (no normalization —
# these are vocab slugs / ISO dates, and forgiving whitespace/case here would
# hide real extraction mismatches). work_title/location_name are free text
# scraped from third-party pages, so they compare after normalize_whitespace.
EVAL_FIELDS = (
    "category",
    "region",
    "start_date",
    "end_date",
    "work_title",
    "location_name",
)

NORMALIZED_FIELDS = {"work_title", "location_name"}


def _normalized_equal(expected, actual):
    return normalize_whitespace(expected) == normalize_whitespace(actual)


def _exact_equal(expected, actual):
    return expected == actual


def _is_empty(value):
    return value is None or value == ""


def build_field_accuracy_report(golden_rows, extract_fn):
    """golden_rows: iterable of (raw_title, raw_text, expected_fields).

    expected_fields keys match EVAL_FIELDS (unprefixed); extract_fn's return
    dict uses the extracted_* prefix (extract_event_fields_heuristic /
    extract_event_fields_llm shape).

    Returns {"fields": [...], "errors": n, "fallback": n}.
    - "fields" is a list of {"field", "correct", "total", "accuracy",
      "both_empty"} dicts, one per EVAL_FIELDS entry, in EVAL_FIELDS order.
    - A row whose extract_fn(raw_title, raw_text) call raises is skipped
      entirely (no field counts, no fallback count) and increments "errors" —
      one bad row must not abort the whole batch.
    - A field where both the golden and extracted values are empty (None or
      "") is excluded from that field's correct/total and increments that
      field's "both_empty" — an uncorrected golden row must not inflate
      accuracy by "agreeing" on missing data.
    - A successfully-evaluated row whose result dict has
      extraction_method == "heuristic" increments "fallback", surfacing
      LLM-mode calibration data silently contaminated by heuristic fallback.
    """
    correct_counts = {field: 0 for field in EVAL_FIELDS}
    total_counts = {field: 0 for field in EVAL_FIELDS}
    both_empty_counts = {field: 0 for field in EVAL_FIELDS}
    errors = 0
    fallback = 0

    for raw_title, raw_text, expected_fields in golden_rows:
        try:
            actual_fields = extract_fn(raw_title, raw_text)
        except Exception:
            errors += 1
            continue

        if actual_fields.get("extraction_method") == "heuristic":
            fallback += 1

        for field in EVAL_FIELDS:
            if field not in expected_fields:
                continue
            expected_value = expected_fields[field]
            actual_value = actual_fields.get(f"extracted_{field}")
            if _is_empty(expected_value) and _is_empty(actual_value):
                both_empty_counts[field] += 1
                continue
            total_counts[field] += 1
            compare = _normalized_equal if field in NORMALIZED_FIELDS else _exact_equal
            if compare(expected_value, actual_value):
                correct_counts[field] += 1

    return {
        "fields": [
            {
                "field": field,
                "correct": correct_counts[field],
                "total": total_counts[field],
                "accuracy": (correct_counts[field] / total_counts[field]) if total_counts[field] else 0,
                "both_empty": both_empty_counts[field],
            }
            for field in EVAL_FIELDS
        ],
        "errors": errors,
        "fallback": fallback,
    }
