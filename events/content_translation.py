"""번역 대상 필드·해시 등 순수 규칙 모듈. DB·모델을 모른다.
"""
import hashlib
import unicodedata

TRANSLATED_FIELDS = ("title", "work_title", "location_name", "summary")


def source_hash(fields):
    # 필드 경계가 값의 내용과 섞여 흐려지지 않도록 구분자로 \x1f(유닛 구분자)를 쓴다.
    values = [unicodedata.normalize("NFC", fields[name] or "") for name in TRANSLATED_FIELDS]
    joined = "\x1f".join(values)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()
