import re
import unicodedata
from datetime import date

from bs4 import BeautifulSoup


class EmptyExtractionError(Exception):
    pass


DATE_PATTERN = re.compile(r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})")


def normalize_whitespace(text):
    """text를 NFKC 정규화하고 공백을 하나로 줄인 뒤 소문자로 바꾼다.

    drafts.llm_extraction과 drafts.eval이 같은 방식으로 비교하도록 공유한다.
    """
    normalized = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"\s+", " ", normalized).strip().lower()


def _parse_date_candidates(text):
    dates = []
    for match in DATE_PATTERN.finditer(text):
        year, month, day = map(int, match.groups())
        try:
            dates.append(date(year, month, day))
        except ValueError:
            continue
    return dates


def _detect_category(text):
    lowered = text.lower()
    if "popup" in lowered or "pop-up" in lowered:
        return "popup_store"
    if "collaboration cafe" in lowered or "콜라보 카페" in text:
        return "collaboration_cafe"
    if "theater bonus" in lowered or "극장" in text:
        return "theater_bonus"
    if "goods reservation" in lowered or "예약" in text:
        return "goods_reservation"
    return ""


def _detect_region(text):
    lowered = text.lower()
    if "seoul" in lowered or "서울" in text:
        return "seoul"
    if "busan" in lowered or "부산" in text:
        return "busan"
    if "incheon" in lowered or "인천" in text:
        return "incheon"
    return ""


def extract_event_fields_heuristic(raw_title, raw_text):
    candidates = _parse_date_candidates(raw_text)
    extracted_start_date = candidates[0] if candidates else None
    extracted_end_date = candidates[1] if len(candidates) > 1 else None

    return {
        "raw_title": raw_title,
        "raw_text": raw_text,
        "extracted_title": raw_title,
        "extracted_summary": raw_text[:500],
        "extracted_category": _detect_category(f"{raw_title} {raw_text}"),
        "extracted_region": _detect_region(f"{raw_title} {raw_text}"),
        "extracted_start_date": extracted_start_date,
        "extracted_end_date": extracted_end_date,
        "extracted_work_title": "",
        "extracted_location_name": "",
    }


def parse_raw_fields(html):
    soup = BeautifulSoup(html, "html.parser")

    og_title = soup.find("meta", attrs={"property": "og:title"})
    title_tag = soup.find("title")
    meta_description = soup.find("meta", attrs={"name": "description"})

    raw_title = (
        (og_title.get("content") if og_title else None)
        or (title_tag.get_text(strip=True) if title_tag else "")
    ).strip()
    raw_text = (
        (meta_description.get("content") if meta_description else None)
        or soup.get_text(" ", strip=True)
    ).strip()

    if not raw_title and not raw_text:
        raise EmptyExtractionError

    return {"raw_title": raw_title, "raw_text": raw_text}


def extract_event_fields(html):
    raw_fields = parse_raw_fields(html)
    return extract_event_fields_heuristic(raw_fields["raw_title"], raw_fields["raw_text"])
