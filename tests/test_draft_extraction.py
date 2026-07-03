"""Unit tests for drafts.extraction — HTML → event-field extraction.

Pure logic (no DB), previously only exercised indirectly through the draft
service flow, leaving the title/text fallbacks, date parsing, and category/
region detection branches uncovered.
"""
from datetime import date

import pytest

from drafts.extraction import (
    EmptyExtractionError,
    extract_event_fields,
    extract_event_fields_heuristic,
    parse_raw_fields,
)


class TestTitleExtraction:
    def test_prefers_og_title_over_title_tag(self):
        html = """
        <html><head>
          <meta property="og:title" content="OG 제목">
          <title>타이틀 태그</title>
        </head><body>본문</body></html>
        """
        result = extract_event_fields(html)
        assert result["raw_title"] == "OG 제목"
        assert result["extracted_title"] == "OG 제목"

    def test_falls_back_to_title_tag_without_og(self):
        html = "<html><head><title>타이틀 태그</title></head><body>본문</body></html>"
        result = extract_event_fields(html)
        assert result["raw_title"] == "타이틀 태그"

    def test_empty_title_and_text_raises(self):
        with pytest.raises(EmptyExtractionError):
            extract_event_fields("<html><head></head><body></body></html>")


class TestTextExtraction:
    def test_prefers_meta_description_over_body(self):
        html = """
        <html><head><meta name="description" content="메타 설명"></head>
        <body>본문 텍스트</body></html>
        """
        result = extract_event_fields(html)
        assert result["raw_text"] == "메타 설명"

    def test_falls_back_to_body_text(self):
        html = "<html><head><title>제목</title></head><body>본문 텍스트</body></html>"
        result = extract_event_fields(html)
        assert "본문 텍스트" in result["raw_text"]

    def test_summary_truncated_to_500_chars(self):
        long_text = "가" * 600
        html = f'<html><head><title>제목</title><meta name="description" content="{long_text}"></head><body></body></html>'
        result = extract_event_fields(html)
        assert len(result["extracted_summary"]) == 500


class TestDateParsing:
    def _extract(self, text):
        html = f'<html><head><title>T</title><meta name="description" content="{text}"></head><body></body></html>'
        return extract_event_fields(html)

    def test_single_date_sets_start_only(self):
        result = self._extract("행사 기간 2026-07-01 시작")
        assert result["extracted_start_date"] == date(2026, 7, 1)
        assert result["extracted_end_date"] is None

    def test_two_dates_set_start_and_end(self):
        result = self._extract("2026.07.01 부터 2026/07/20 까지")
        assert result["extracted_start_date"] == date(2026, 7, 1)
        assert result["extracted_end_date"] == date(2026, 7, 20)

    def test_invalid_calendar_date_is_skipped(self):
        # 2026-13-40 matches the pattern but is not a real date → skipped, the
        # following valid date becomes the start.
        result = self._extract("2026-13-40 잘못된 날짜 그리고 2026-08-15")
        assert result["extracted_start_date"] == date(2026, 8, 15)

    def test_no_date_leaves_both_none(self):
        result = self._extract("날짜 없는 설명")
        assert result["extracted_start_date"] is None
        assert result["extracted_end_date"] is None


class TestCategoryDetection:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Limited POPUP store", "popup_store"),
            ("pop-up event", "popup_store"),
            ("콜라보 카페 오픈", "collaboration_cafe"),
            ("극장 특전 배포", "theater_bonus"),
            ("굿즈 예약 안내", "goods_reservation"),
            ("아무 관련 없는 내용", ""),
        ],
    )
    def test_category(self, text, expected):
        html = f'<html><head><title>{text}</title></head><body></body></html>'
        assert extract_event_fields(html)["extracted_category"] == expected


class TestHeuristicExtraction:
    def test_extract_event_fields_heuristic_returns_same_keys_without_html(self):
        result = extract_event_fields_heuristic("제목", "서울 2026-07-01 팝업")

        assert set(result.keys()) == {
            "raw_title",
            "raw_text",
            "extracted_title",
            "extracted_summary",
            "extracted_category",
            "extracted_region",
            "extracted_start_date",
            "extracted_end_date",
            "extracted_work_title",
            "extracted_location_name",
        }

    def test_extract_event_fields_heuristic_detects_category_and_region_from_text(self):
        result = extract_event_fields_heuristic("Limited POPUP store", "서울 홍대에서 진행")

        assert result["extracted_category"] == "popup_store"
        assert result["extracted_region"] == "seoul"


class TestParseRawFields:
    def test_returns_same_raw_title_and_raw_text_as_extract_event_fields(self):
        html = """
        <html><head>
          <meta property="og:title" content="OG 제목">
          <meta name="description" content="메타 설명">
        </head><body>본문</body></html>
        """

        parsed = parse_raw_fields(html)
        extracted = extract_event_fields(html)

        assert parsed == {"raw_title": "OG 제목", "raw_text": "메타 설명"}
        assert parsed["raw_title"] == extracted["raw_title"]
        assert parsed["raw_text"] == extracted["raw_text"]

    def test_empty_title_and_text_raises(self):
        with pytest.raises(EmptyExtractionError):
            parse_raw_fields("<html><head></head><body></body></html>")


class TestRegionDetection:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("서울 홍대에서 진행", "seoul"),
            ("Event in SEOUL", "seoul"),
            ("부산 벡스코", "busan"),
            ("인천 송도", "incheon"),
            ("온라인 전용", ""),
        ],
    )
    def test_region(self, text, expected):
        html = f'<html><head><title>{text}</title></head><body></body></html>'
        assert extract_event_fields(html)["extracted_region"] == expected
