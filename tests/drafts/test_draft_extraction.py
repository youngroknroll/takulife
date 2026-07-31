"""drafts.extraction(HTML → 행사 필드 추출) 단위 테스트. DB 없는 순수 로직."""
from datetime import date

import pytest

from drafts.extraction import (
    EmptyExtractionError,
    extract_event_fields,
    extract_event_fields_heuristic,
    parse_raw_fields,
)


pytestmark = pytest.mark.unit


class TestTitleExtraction:
    def test_og_title이_있으면_title_태그보다_우선한다(self):
        html = """
        <html><head>
          <meta property="og:title" content="OG 제목">
          <title>타이틀 태그</title>
        </head><body>본문</body></html>
        """
        result = extract_event_fields(html)
        assert result["raw_title"] == "OG 제목"
        assert result["extracted_title"] == "OG 제목"

    def test_og_title이_없으면_title_태그로_대체한다(self):
        html = "<html><head><title>타이틀 태그</title></head><body>본문</body></html>"
        result = extract_event_fields(html)
        assert result["raw_title"] == "타이틀 태그"

    def test_제목과_본문이_모두_없으면_EmptyExtractionError를_발생시킨다(self):
        with pytest.raises(EmptyExtractionError):
            extract_event_fields("<html><head></head><body></body></html>")


class TestTextExtraction:
    def test_메타_설명이_있으면_본문보다_우선한다(self):
        html = """
        <html><head><meta name="description" content="메타 설명"></head>
        <body>본문 텍스트</body></html>
        """
        result = extract_event_fields(html)
        assert result["raw_text"] == "메타 설명"

    def test_메타_설명이_없으면_본문_텍스트를_사용한다(self):
        html = "<html><head><title>제목</title></head><body>본문 텍스트</body></html>"
        result = extract_event_fields(html)
        assert "본문 텍스트" in result["raw_text"]

    def test_요약은_500자로_잘린다(self):
        long_text = "가" * 600
        html = f'<html><head><title>제목</title><meta name="description" content="{long_text}"></head><body></body></html>'
        result = extract_event_fields(html)
        assert len(result["extracted_summary"]) == 500


class TestDateParsing:
    def _extract(self, text):
        html = f'<html><head><title>T</title><meta name="description" content="{text}"></head><body></body></html>'
        return extract_event_fields(html)

    def test_날짜가_하나면_시작일만_설정되고_종료일은_없다(self):
        result = self._extract("행사 기간 2026-07-01 시작")
        assert result["extracted_start_date"] == date(2026, 7, 1)
        assert result["extracted_end_date"] is None

    def test_날짜가_두_개면_시작일과_종료일이_모두_설정된다(self):
        result = self._extract("2026.07.01 부터 2026/07/20 까지")
        assert result["extracted_start_date"] == date(2026, 7, 1)
        assert result["extracted_end_date"] == date(2026, 7, 20)

    def test_잘못된_달력_날짜는_건너뛰고_다음_유효한_날짜를_시작일로_사용한다(self):
        # 2026-13-40은 패턴엔 맞지만 실존 날짜가 아니라 건너뛰고, 다음 유효
        # 날짜가 시작일이 된다.
        result = self._extract("2026-13-40 잘못된 날짜 그리고 2026-08-15")
        assert result["extracted_start_date"] == date(2026, 8, 15)

    def test_날짜가_없으면_시작일과_종료일_모두_없다(self):
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
        ids=["팝업스토어_영문", "팝업스토어_하이픈", "콜라보_카페", "극장_특전", "굿즈_예약", "매칭없음"],
    )
    def test_제목_텍스트로_카테고리를_감지한다(self, text, expected):
        html = f'<html><head><title>{text}</title></head><body></body></html>'
        assert extract_event_fields(html)["extracted_category"] == expected


class TestHeuristicExtraction:
    def test_HTML_없이_추출해도_extract_event_fields와_동일한_키_집합을_반환한다(self):
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

    def test_텍스트만으로도_카테고리와_지역을_감지한다(self):
        result = extract_event_fields_heuristic("Limited POPUP store", "서울 홍대에서 진행")

        assert result["extracted_category"] == "popup_store"
        assert result["extracted_region"] == "seoul"


class TestParseRawFields:
    def test_parse_raw_fields는_extract_event_fields와_동일한_raw_제목과_raw_본문을_반환한다(self):
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

    def test_제목과_본문이_모두_없으면_parse_raw_fields도_EmptyExtractionError를_발생시킨다(self):
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
        ids=["서울_한글", "서울_영문", "부산", "인천", "매칭없음"],
    )
    def test_제목_텍스트로_지역을_감지한다(self, text, expected):
        html = f'<html><head><title>{text}</title></head><body></body></html>'
        assert extract_event_fields(html)["extracted_region"] == expected
