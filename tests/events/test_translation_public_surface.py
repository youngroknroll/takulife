"""트랙 44-1 묶음 ⑦ AC6 — 번역이 저장소(Event.text_translations)에 쌓여도
공개 API·검색·사이트맵·JSON-LD 응답은 44-1 전과 바이트/키 단위로 같아야
한다. 44-1은 공개 면을 전혀 건드리지 않으므로, 이 파일의 테스트는 구현
변경 없이 바로 Green이어야 한다."""

import json
import re

import pytest

from events.content_translation import TRANSLATED_FIELDS, source_hash
from events.models import Event

pytestmark = [pytest.mark.django_db, pytest.mark.web]


def _translation_fields():
    return {
        "title": "2026 도쿄 코믹마켓",
        "work_title": "원작 없음",
        "location_name": "도쿄 빅사이트",
        "summary": "서브컬처 행사 요약",
    }


def _current_hash_translations():
    fields = _translation_fields()
    return {
        "source_hash": source_hash(fields),
        "manual": False,
        "en": {
            "title": "2026 Tokyo Comic Market",
            "work_title": "No original work",
            "location_name": "Tokyo Big Sight",
            "summary": "Subculture event summary",
        },
        "ja": None,
        "zh-hans": None,
    }


def _json_ld_payload(body):
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', body, re.DOTALL)
    assert match is not None
    return json.loads(match.group(1))


def test_공개_이벤트_API는_번역_저장소를_응답에_담지_않는다(client, make_event):
    translations = _current_hash_translations()
    translated_event = make_event(**_translation_fields(), text_translations=translations)
    plain_event = make_event(**_translation_fields())

    list_response = client.get("/api/events/")
    detail_response = client.get(f"/api/events/{translated_event.id}/")
    plain_detail_response = client.get(f"/api/events/{plain_event.id}/")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert plain_detail_response.status_code == 200

    list_items = list_response.json()["results"]
    translated_item = next(item for item in list_items if item["id"] == translated_event.id)
    plain_item = next(item for item in list_items if item["id"] == plain_event.id)

    assert "text_translations" not in translated_item
    assert set(translated_item.keys()) == set(plain_item.keys())

    detail_body = detail_response.json()
    assert "text_translations" not in detail_body
    assert set(detail_body.keys()) == set(plain_detail_response.json().keys())

    assert "2026 Tokyo Comic Market" not in list_response.content.decode("utf-8")
    assert "2026 Tokyo Comic Market" not in detail_response.content.decode("utf-8")


def test_검색은_번역문을_대상으로_하지_않는다(client, make_event):
    event = make_event(**_translation_fields(), text_translations=_current_hash_translations())

    api_hit = client.get("/api/events/", {"q": "도쿄"})
    web_hit = client.get("/events/", {"q": "도쿄", "status": "all"})
    api_translated = client.get("/api/events/", {"q": "Tokyo"})
    web_translated = client.get("/events/", {"q": "Tokyo", "status": "all"})

    # 양성 대조: 원문(한국어)으로는 검색되어, 번역문 미검색 단언이 빈 결과 때문이 아님을 보인다.
    assert api_hit.status_code == 200
    assert [item["id"] for item in api_hit.json()["results"]] == [event.id]
    assert web_hit.status_code == 200
    assert event in list(web_hit.context["page_obj"].object_list)

    assert api_translated.status_code == 200
    assert api_translated.json()["results"] == []
    assert web_translated.status_code == 200
    assert event not in list(web_translated.context["page_obj"].object_list)


def test_사이트맵은_번역_저장_여부와_무관하다(client, make_event):
    event = make_event(**_translation_fields())

    body_without_translations = client.get("/sitemap.xml").content

    event.text_translations = _current_hash_translations()
    event.save(update_fields=["text_translations"])

    body_with_translations = client.get("/sitemap.xml").content

    assert body_with_translations == body_without_translations


def test_JSON_LD는_번역_저장_여부와_무관하다(client, make_event):
    from datetime import date

    event = make_event(
        **_translation_fields(),
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 3),
    )

    body_without_translations = client.get(f"/events/{event.id}/").content.decode("utf-8")
    payload_without_translations = _json_ld_payload(body_without_translations)

    event.text_translations = _current_hash_translations()
    event.save(update_fields=["text_translations"])

    body_with_translations = client.get(f"/events/{event.id}/").content.decode("utf-8")
    payload_with_translations = _json_ld_payload(body_with_translations)

    assert payload_with_translations == payload_without_translations


def test_공개_면을_만드는_모듈_소스는_번역_저장소를_참조하지_않는다():
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]
    target_paths = [
        project_root / "events" / "serializers.py",
        project_root / "events" / "queries.py",
        project_root / "events" / "presenters.py",
        project_root / "core" / "presenters.py",
        project_root / "web" / "sitemaps.py",
    ]

    violations = [
        path.relative_to(project_root)
        for path in target_paths
        if "text_translations" in path.read_text()
    ]

    assert not violations, violations


def test_TRANSLATED_FIELDS_상수는_네_필드로_고정돼_있다():
    # 이 파일의 헬퍼(_translation_fields)가 TRANSLATED_FIELDS와 어긋나면
    # 위 테스트들이 조용히 다른 필드를 테스트하게 된다 — 그 전제를 핀한다.
    assert set(TRANSLATED_FIELDS) == set(_translation_fields().keys())
