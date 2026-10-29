"""번역 대상 필드·해시·제출 검증·노출 선택 등 순수 규칙 모듈. DB·모델을 모른다."""

import hashlib
import re
import unicodedata
from dataclasses import dataclass

TRANSLATED_FIELDS = ("title", "work_title", "location_name", "summary")
TARGET_LANGUAGES = ("en", "ja", "zh-hans")
FIELD_MAX_LENGTH = {"title": 400, "work_title": 400, "location_name": 400, "summary": 2000}
# 공식 표기가 라틴 문자인 작품명·장소명은 그대로 두는 것이 정상 번역이라,
# 이 두 필드는 언어별 문자 판정에서 라틴 문자 단독 표기를 예외로 둔다.
_PROPER_NOUN_FIELDS = ("work_title", "location_name")

_TAG_RE = re.compile(r"<[A-Za-z/!][^>]*>")
_URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_CURRENCY_RE = re.compile(r"(?i)\b(?:USD|EUR|GBP|JPY|CNY|RMB)\b|US\$|\$|[€£¥円]")
_DIGIT_COMMA_RE = re.compile(r"(?<=\d),(?=\d)")
_DIGITS_RE = re.compile(r"\d+")
_TIME_MINUTES_RE = re.compile(r"(?<=\d):00(?!\d)")
_KOREAN_UNIT_RE = re.compile(r"(?<![\d.,])(\d{1,9})\s?(만|천|억)(?!\s?\d)")
_UNIT_ZEROS = {"만": "0000", "천": "000", "억": "00000000"}
_TRAILING_PUNCTUATION = ".,;:!?)]'\""
_BARE_SCHEME_RE = re.compile(r"(?i)^(?:https?://|www\.?)$")
_WHITESPACE_RE = re.compile(r"\s+")
# 한글 음절·자모(완성형·호환 자모·확장 자모)를 전부 잡는다 — NFD로 분해된
# 자모도 걸러야 해서 음절 블록 하나만으로는 부족하다.
_HANGUL_RE = re.compile(r"[\u1100-\u11ff\u3130-\u318f\ua960-\ua97f\uac00-\ud7a3\ud7b0-\ud7ff]")
# 라틴 알파벳(ASCII) + 악센트 라틴 문자. 곱셈(U+00D7)·나눗셈(U+00F7) 기호는 뺀다.
_LATIN_RE = re.compile(r"[A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u024f]")
_KANA_RE = re.compile(r"[\u3040-\u30ff]")
_HANJA_RE = re.compile(r"[\u4e00-\u9fff]")


class SubmissionRejected(Exception):
    """제출 전체를 거부할 때 쓴다. 저장은 하지 않는다.

    사유 코드는 두 갈래다: "schema"·"nul"은 이 모듈의 구조 검증이 올리고,
    "not_found"·"manual_locked"·"stale_source"는 events.translation_queue가
    이벤트 상태(존재·게시 여부·수동 확정·원문 변경)를 확인하다 올린다.
    """

    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ValidationResult:
    languages: dict
    quarantined: dict


@dataclass(frozen=True)
class DisplayText:
    fields: dict
    is_translated: bool


def source_hash(fields):
    # 필드 경계가 값의 내용과 섞여 흐려지지 않도록 구분자로 \x1f(유닛 구분자)를 쓴다.
    values = [unicodedata.normalize("NFC", fields[name] or "") for name in TRANSLATED_FIELDS]
    joined = "\x1f".join(values)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _raw_digits(text):
    normalized = _DIGIT_COMMA_RE.sub("", unicodedata.normalize("NFKC", text))
    return set(_DIGITS_RE.findall(normalized))


def _translated_digits(text):
    normalized = unicodedata.normalize("NFKC", text)
    # 시각 표기의 분(":00")은 번역이 덧붙이는 서식이라 지어낸 숫자로 보지 않는다.
    normalized = _TIME_MINUTES_RE.sub("", normalized)
    normalized = _DIGIT_COMMA_RE.sub("", normalized)
    return {_strip_leading_zeros(token) for token in _DIGITS_RE.findall(normalized)}


def _strip_leading_zeros(token):
    return token.lstrip("0") or "0"


def _source_allowed_digits(text):
    allowed = {_strip_leading_zeros(token) for token in _raw_digits(text)}
    # 만·천·억 표기는 번역이 숫자로 풀어 쓸 수 있어 허용 집합에만 넣고 보존 의무는 만들지 않는다.
    for number, unit in _KOREAN_UNIT_RE.findall(unicodedata.normalize("NFKC", text)):
        allowed.add(_strip_leading_zeros(number + _UNIT_ZEROS[unit]))
    return allowed


def _digits_reason(s, t):
    if _translated_digits(t) - _source_allowed_digits(s):
        return "number_invented"
    translated_raw = _raw_digits(t)
    if any(len(digit) >= 4 and digit not in translated_raw for digit in _raw_digits(s)):
        return "number_missing"
    return None


def _clean_markup_token(token):
    return token.rstrip(_TRAILING_PUNCTUATION)


def _markup_token_is_foreign(token, haystack):
    cleaned = _clean_markup_token(token)
    if not cleaned or _BARE_SCHEME_RE.match(cleaned):
        return True
    return cleaned not in haystack


def _markup_reason(s, ks, t, kt):
    # 전각 문자로 쓴 위장 표기를 잡으려 접힌(NFKC) 문자열에도 같은 검사를 돈다.
    markup_tokens = _TAG_RE.findall(t) + _URL_RE.findall(t) + _EMAIL_RE.findall(t)
    folded_markup_tokens = _TAG_RE.findall(kt) + _URL_RE.findall(kt) + _EMAIL_RE.findall(kt)
    if any(_markup_token_is_foreign(token, s) for token in markup_tokens) or any(
        _markup_token_is_foreign(token, ks) for token in folded_markup_tokens
    ):
        return "unexpected_markup"
    return None


def _has_control_char(t):
    for ch in t:
        if ch in ("\n", "\t"):
            continue
        if unicodedata.category(ch) in ("Cc", "Cf", "Cs"):
            return True
    return False


def _script_reason(language, field, kt, kt_nospace):
    # 고유명사 필드(work_title·location_name)이 가나·한자 없이 라틴
    # 문자만으로 쓰였으면 공식 라틴 표기로 보고 문자 판정을 건너뛴다.
    is_proper_noun_latin_exception = (
        field in _PROPER_NOUN_FIELDS
        and language in ("ja", "zh-hans")
        and _LATIN_RE.search(kt)
        and not _KANA_RE.search(kt)
        and not _HANJA_RE.search(kt)
    )

    if language == "en":
        if not _LATIN_RE.search(kt):
            return "wrong_script"
    elif language == "ja":
        if not is_proper_noun_latin_exception and not _KANA_RE.search(kt):
            # 가나가 없어도 짧고(10자 이하) 한자만 있으면 통과한다.
            if not (len(kt_nospace) <= 10 and _HANJA_RE.search(kt)):
                return "wrong_script"
    elif language == "zh-hans":
        if not is_proper_noun_latin_exception and (not _HANJA_RE.search(kt) or _KANA_RE.search(kt)):
            return "wrong_script"
    else:
        raise ValueError(f"unknown language: {language}")
    return None


def _field_quarantine_reason(language, field, source_value, translated_value):
    s = source_value or ""
    t = translated_value or ""
    s_stripped = s.strip()
    t_stripped = t.strip()

    # 큰 입력이 이후 전수 순회·정규화로 가기 전에 절대 상한에서 먼저 자른다.
    if len(t) > FIELD_MAX_LENGTH[field]:
        return "too_long"
    if _has_control_char(t):
        return "control_char"
    if not s_stripped and not t_stripped:
        return None

    ks = unicodedata.normalize("NFKC", s)
    kt = unicodedata.normalize("NFKC", t)
    ks_nospace = _WHITESPACE_RE.sub("", ks)
    kt_nospace = _WHITESPACE_RE.sub("", kt)
    if len(kt_nospace) > max(40, 6 * len(ks_nospace)):
        return "too_long"

    reason = _markup_reason(s, ks, t, kt)
    if reason is not None:
        return reason

    if any(match.upper() not in ks.upper() for match in _CURRENCY_RE.findall(kt)):
        return "currency_changed"

    reason = _digits_reason(s, t)
    if reason is not None:
        return reason

    if not s_stripped and t_stripped:
        return "nonempty_for_empty_source"
    if s_stripped and not t_stripped:
        return "empty_translation"

    if _HANGUL_RE.search(kt):
        return "hangul_residue"

    # 원문이 ASCII뿐이고 번역이 원문과 글자 그대로 같으면(대문자 영문 약어
    # 등) 언어별 문자 판정을 건너뛴다.
    if ks_nospace and ks.strip().isascii() and kt.strip() == ks.strip():
        return None

    return _script_reason(language, field, kt, kt_nospace)


def quarantine_reason(language, source_fields, translated_fields):
    if language not in TARGET_LANGUAGES:
        raise ValueError(f"unknown language: {language}")

    for field in TRANSLATED_FIELDS:
        reason = _field_quarantine_reason(
            language, field, source_fields[field], translated_fields[field]
        )
        if reason is not None:
            return reason
    return None


def validate_translations(source_fields, translations):
    if not isinstance(translations, dict) or set(translations.keys()) != set(TARGET_LANGUAGES):
        raise SubmissionRejected("schema")
    for language_value in translations.values():
        if not isinstance(language_value, dict) or set(language_value.keys()) != set(
            TRANSLATED_FIELDS
        ):
            raise SubmissionRejected("schema")
        for value in language_value.values():
            if not isinstance(value, str):
                raise SubmissionRejected("schema")

    for language_value in translations.values():
        for value in language_value.values():
            if "\x00" in value:
                raise SubmissionRejected("nul")

    languages = {}
    quarantined = {}
    for language in TARGET_LANGUAGES:
        translated_fields = translations[language]
        reason = quarantine_reason(language, source_fields, translated_fields)
        if reason is None:
            languages[language] = {
                field: unicodedata.normalize("NFC", translated_fields[field])
                for field in TRANSLATED_FIELDS
            }
        else:
            languages[language] = None
            quarantined[language] = reason

    return ValidationResult(languages=languages, quarantined=quarantined)


def select_display(source_fields, text_translations, language):
    if isinstance(text_translations, dict) and language in TARGET_LANGUAGES:
        if text_translations.get("source_hash") == source_hash(source_fields):
            translated = text_translations.get(language)
            if isinstance(translated, dict) and all(
                isinstance(translated.get(name), str) for name in TRANSLATED_FIELDS
            ):
                fields = {name: translated[name] for name in TRANSLATED_FIELDS}
                return DisplayText(fields=fields, is_translated=True)

    fields = {name: (source_fields[name] or "") for name in TRANSLATED_FIELDS}
    return DisplayText(fields=fields, is_translated=False)
