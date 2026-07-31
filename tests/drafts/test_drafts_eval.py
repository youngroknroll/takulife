"""drafts.eval.build_field_accuracy_report(DB 없는 순수 함수) 테스트.

리포트 계약: {"fields": [{"field", "correct", "total", "accuracy",
"both_empty"}, ...], "errors": n, "fallback": n}.
- extract_fn이 예외를 던진 골든 행은 어떤 필드에도 집계되지 않고 "errors"만
  증가한다.
- 골든 값과 추출 값이 둘 다 비어 있는 필드는 correct/total에서 제외되고(안 그러면
  정확도가 부풀려짐) "both_empty"만 증가한다.
- 성공적으로 평가된 행의 extraction_method가 "heuristic"이면 "fallback"이
  증가한다(LLM 모드에서 조용히 대체됐음을 드러낸다).
"""
import pytest

from drafts.eval import EVAL_FIELDS, build_field_accuracy_report

pytestmark = pytest.mark.unit


def _extract_fn(mapping):
    """{(raw_title, raw_text): result_dict} 매핑으로 extract_fn을 만든다."""

    def fn(raw_title, raw_text):
        return mapping[(raw_title, raw_text)]

    return fn


def _by_field(report):
    return {row["field"]: row for row in report["fields"]}


class TestEmptyGoldenSet:
    def test_골든_세트가_비어있으면_0으로_나누지_않고_모든_필드가_0으로_집계된다(self):
        report = build_field_accuracy_report([], extract_fn=lambda raw_title, raw_text: {})

        assert len(report["fields"]) == len(EVAL_FIELDS)
        for row in report["fields"]:
            assert row["total"] == 0
            assert row["correct"] == 0
            assert row["accuracy"] == 0
        assert report["errors"] == 0
        assert report["fallback"] == 0


class TestExactFieldComparison:
    def test_한_필드의_불일치는_그_필드의_정확도만_낮추고_다른_필드에_영향을_주지_않는다(self):
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
    def test_work_title은_공백과_대소문자_차이를_정규화한_뒤_비교한다(self):
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
    def test_category_region_날짜_필드는_정규화_없이_정확히_비교된다(self):
        # work_title/location_name만 정규화 대상이고, 나머지 필드는 공백·대소문자
        # 차이도 그대로 오답으로 취급돼야 한다.
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
    def test_한_행에서_추출_함수가_예외를_던지면_errors로_집계하고_나머지_행은_계속_처리한다(self):
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
    def test_골든_값과_추출_값이_모두_비어있으면_그_필드의_정확도_분모에서_제외된다(self):
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

    def test_빈_문자열도_both_empty_판정에서_비어있는_값으로_취급된다(self):
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
    def test_추출_방식이_heuristic이면_fallback으로_집계된다(self):
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

    def test_추출_방식이_llm이면_fallback으로_집계되지_않는다(self):
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
