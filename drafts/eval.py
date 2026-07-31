"""드래프트 추출 필드 정확도를 평가하는 순수 함수 모음.

사람이 승인한 골든셋과 extract_fn 결과를 비교해, 자동 승인 게이트를 신뢰하기 전에
LLM과 휴리스틱 추출을 검증한다. DB 접근은 하지 않으며,
drafts/management/commands/eval_extraction.py가 DB를 다루는 얇은 호출부다.
"""
from .extraction import normalize_whitespace

# category/region/start_date/end_date는 어휘 슬러그·ISO 날짜라 정규화 없이 정확히
# 비교한다 — 느슨하게 봐주면 실제 추출 오류를 놓친다. work_title/location_name은
# 외부 사이트에서 긁은 자유 텍스트라 공백 정규화 후 비교한다.
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
    """golden_rows: (raw_title, raw_text, expected_fields) 이터러블.

    반환값 {"fields": [...], "errors": n, "fallback": n}.
    - extract_fn 호출이 예외를 내면 그 행은 통째로 건너뛰고 errors만 늘린다 — 행 하나의
      오류가 전체 배치를 중단시키면 안 된다.
    - 골든값과 추출값이 둘 다 비어 있는 필드는 그 필드의 정확도 집계에서 빼고
      both_empty만 늘린다 — 누락 데이터끼리 "일치"한 것으로 쳐서 정확도를 부풀리면
      안 된다.
    - 결과의 extraction_method가 "heuristic"이면 fallback을 늘린다 — LLM 모드 보정
      데이터가 휴리스틱 폴백으로 조용히 섞이는 걸 드러내기 위해서다.
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
            # except-ok: 추출 실패는 개수를 세어 평가 요약에 보고하므로 예외를 삼켜도 된다
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
