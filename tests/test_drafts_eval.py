"""Tests for drafts.eval.build_field_accuracy_report — a pure function, no DB.

golden_rows: iterable of (raw_title, raw_text, expected_fields_dict).
extract_fn: callable(raw_title, raw_text) -> extracted fields dict, matching
the extract_event_fields_heuristic/extract_event_fields_llm return shape.

Report contract: {"fields": [{"field", "correct", "total", "accuracy",
"both_empty"}, ...], "errors": n, "fallback": n}.
- A golden row whose extract_fn call raises is skipped entirely (not counted
  in any field, or in fallback) and increments "errors".
- A field where both the golden value and the extracted value are empty
  (None or "") is excluded from that field's correct/total (would inflate
  accuracy on an uncorrected golden set) and increments that field's
  "both_empty".
- A successfully-evaluated row whose result dict has
  extraction_method == "heuristic" increments "fallback" (surfaces silent
  LLM-mode fallback contaminating the calibration data).
"""
from drafts.eval import EVAL_FIELDS, build_field_accuracy_report


def _extract_fn(mapping):
    """Builds an extract_fn from {(raw_title, raw_text): result_dict}."""

    def fn(raw_title, raw_text):
        return mapping[(raw_title, raw_text)]

    return fn


def _by_field(report):
    return {row["field"]: row for row in report["fields"]}


class TestEmptyGoldenSet:
    def test_empty_golden_set_reports_zero_total_without_zero_division(self):
        report = build_field_accuracy_report([], extract_fn=lambda raw_title, raw_text: {})

        assert len(report["fields"]) == len(EVAL_FIELDS)
        for row in report["fields"]:
            assert row["total"] == 0
            assert row["correct"] == 0
            assert row["accuracy"] == 0
        assert report["errors"] == 0
        assert report["fallback"] == 0


class TestExactFieldComparison:
    def test_category_mismatch_lowers_accuracy_for_that_field_only(self):
        golden_rows = [
            ("Title A", "Text A", {"category": "popup_store", "region": "seoul"}),
            ("Title B", "Text B", {"category": "collaboration_cafe", "region": "seoul"}),
        ]
        mapping = {
            ("Title A", "Text A"): {"extracted_category": "popup_store", "extracted_region": "seoul"},
            ("Title B", "Text B"): {"extracted_category": "popup_store", "extracted_region": "seoul"},
        }

        report = build_field_accuracy_report(golden_rows, extract_fn=_extract_fn(mapping))
        by_field = _by_field(report)

        assert by_field["category"]["correct"] == 1
        assert by_field["category"]["total"] == 2
        assert by_field["category"]["accuracy"] == 0.5
        assert by_field["region"]["accuracy"] == 1.0


class TestNormalizedFieldComparison:
    def test_work_title_matches_after_whitespace_normalization(self):
        golden_rows = [
            ("Title A", "Text A", {"work_title": "아이브 IVE"}),
        ]
        mapping = {
            ("Title A", "Text A"): {"extracted_work_title": "  아이브   ive "},
        }

        report = build_field_accuracy_report(golden_rows, extract_fn=_extract_fn(mapping))
        by_field = _by_field(report)

        assert by_field["work_title"]["correct"] == 1
        assert by_field["work_title"]["total"] == 1
        assert by_field["work_title"]["accuracy"] == 1.0


class TestExactFieldsAreNotNormalized:
    def test_category_region_and_dates_are_not_normalization_matched(self):
        # Whitespace/case difference must NOT be forgiven for exact fields —
        # only work_title/location_name get normalization.
        golden_rows = [
            (
                "Title A",
                "Text A",
                {
                    "category": "Popup_Store",
                    "region": "Seoul",
                    "start_date": "2026-07-01",
                    "end_date": "2026-07-20",
                },
            ),
        ]
        mapping = {
            ("Title A", "Text A"): {
                "extracted_category": "popup_store",
                "extracted_region": "seoul",
                "extracted_start_date": "2026-07-01",
                "extracted_end_date": "2026-07-20",
            },
        }

        report = build_field_accuracy_report(golden_rows, extract_fn=_extract_fn(mapping))
        by_field = _by_field(report)

        assert by_field["category"]["accuracy"] == 0.0
        assert by_field["region"]["accuracy"] == 0.0
        assert by_field["start_date"]["accuracy"] == 1.0
        assert by_field["end_date"]["accuracy"] == 1.0


class TestRowLevelExceptionIsolation:
    def test_one_row_raising_is_skipped_and_counted_as_error_without_killing_batch(self):
        golden_rows = [
            ("Title A", "Text A", {"category": "popup_store"}),
            ("Title B", "Text B", {"category": "popup_store"}),
        ]

        def flaky_extract_fn(raw_title, raw_text):
            if raw_title == "Title A":
                raise RuntimeError("boom")
            return {"extracted_category": "popup_store"}

        report = build_field_accuracy_report(golden_rows, extract_fn=flaky_extract_fn)
        by_field = _by_field(report)

        assert report["errors"] == 1
        assert by_field["category"]["correct"] == 1
        assert by_field["category"]["total"] == 1
        assert by_field["category"]["accuracy"] == 1.0


class TestBothEmptyExclusion:
    def test_both_expected_and_actual_empty_excluded_from_accuracy_denominator(self):
        golden_rows = [
            ("Title A", "Text A", {"start_date": None}),
        ]
        mapping = {
            ("Title A", "Text A"): {"extracted_start_date": None},
        }

        report = build_field_accuracy_report(golden_rows, extract_fn=_extract_fn(mapping))
        by_field = _by_field(report)

        assert by_field["start_date"]["total"] == 0
        assert by_field["start_date"]["correct"] == 0
        assert by_field["start_date"]["both_empty"] == 1
        assert by_field["start_date"]["accuracy"] == 0

    def test_empty_string_counts_as_empty_for_both_empty_check(self):
        golden_rows = [
            ("Title A", "Text A", {"work_title": ""}),
        ]
        mapping = {
            ("Title A", "Text A"): {"extracted_work_title": ""},
        }

        report = build_field_accuracy_report(golden_rows, extract_fn=_extract_fn(mapping))
        by_field = _by_field(report)

        assert by_field["work_title"]["total"] == 0
        assert by_field["work_title"]["both_empty"] == 1


class TestFallbackVisibility:
    def test_row_with_heuristic_extraction_method_counts_as_fallback(self):
        golden_rows = [
            ("Title A", "Text A", {"category": "popup_store"}),
        ]
        mapping = {
            ("Title A", "Text A"): {
                "extracted_category": "popup_store",
                "extraction_method": "heuristic",
            },
        }

        report = build_field_accuracy_report(golden_rows, extract_fn=_extract_fn(mapping))

        assert report["fallback"] == 1

    def test_row_with_llm_extraction_method_does_not_count_as_fallback(self):
        golden_rows = [
            ("Title A", "Text A", {"category": "popup_store"}),
        ]
        mapping = {
            ("Title A", "Text A"): {
                "extracted_category": "popup_store",
                "extraction_method": "llm",
            },
        }

        report = build_field_accuracy_report(golden_rows, extract_fn=_extract_fn(mapping))

        assert report["fallback"] == 0
