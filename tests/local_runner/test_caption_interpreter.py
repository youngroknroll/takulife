"""local_runner.caption_interpreter — 해석 프롬프트가 어휘·오늘 날짜·최근
드래프트 맥락·공식 여부 판별 기준을 담고, 읽은 텍스트를 <caption> 태그로
감싸는지 검증한다. 공식 여부 판별은 탐색 프롬프트(build_exploration_prompt)
에서 빠지고 이 프롬프트로 옮겨왔다 — 탐색은 페이지를 못 열지만 해석은
읽기 단계가 가져온 본문을 보기 때문이다."""
import pytest

from local_runner.caption_interpreter import (
    _local_precheck,
    build_interpretation_prompt,
    should_submit,
)


pytestmark = pytest.mark.unit


def test_캡션_해석_프롬프트는_어휘_목록_오늘_날짜_최근_드래프트_맥락과_판별_기준을_포함하고_캡션을_데이터_태그로_감싼다():
    vocab = {
        "categories": ["popup_store", "concert"],
        "regions": ["seoul", "busan"],
    }
    recent_drafts = [
        {"source_url": "https://example.com/notice-1", "title": "이전 공지 1"},
        {"source_url": "https://example.com/notice-2", "title": "이전 공지 2"},
    ]

    prompt = build_interpretation_prompt(
        vocab=vocab,
        today="2026-09-11",
        recent_drafts=recent_drafts,
        text="캡션 원문입니다.",
        platform="instagram",
    )

    # (1) 어휘 slug 전부
    for slug in ["popup_store", "concert", "seoul", "busan"]:
        assert slug in prompt

    # (2) 오늘 날짜
    assert "2026-09-11" in prompt

    # (3) 최근 드래프트 URL
    assert "https://example.com/notice-1" in prompt
    assert "https://example.com/notice-2" in prompt

    # (4) 공식·비공식·불명 판별 기준 — 탐색 프롬프트에서 빠진 것과 같은 기준.
    assert "official" in prompt
    assert "unofficial" in prompt
    assert "unclear" in prompt
    assert "주최사" in prompt or "공식 계정" in prompt or "공식 사이트" in prompt

    # (5) 읽은 텍스트는 신뢰할 수 없는 입력이라 데이터 태그로 감싼다.
    assert "<caption>캡션 원문입니다.</caption>" in prompt


def test_해석_JSON의_어휘_밖_값과_역전된_기간과_원문에_없는_텍스트는_로컬_선검사에서_비워진다():
    """서버가 어차피 같은 어휘·기간 검사를 다시 하지만, 러너가 먼저 걸러내면
    검수 화면에 정정 사유가 애초에 덜 남아 큐가 깨끗해진다(서버 재검증을
    대체하는 게 아니라 앞단 필터). 장소명이 실제로 읽은 본문에 있는지
    확인하는 원문 대조는 러너만 할 수 있다 — 서버는 그 값이 왜 나왔는지
    재확인할 근거(원문)를 갖고 있지 않다."""
    vocab = {"categories": ["popup_store"], "regions": ["seoul"]}
    source_text = "코엑스에서 열리는 하츠네 미쿠 팝업스토어. 기간은 9월1일부터 9월22일까지."
    interpreted = {
        "fields": {
            "category": "concert",
            "region": "seoul",
            "location_name": "가상의장소",
            "start_date": "2026-09-20",
            "end_date": "2026-09-01",
        }
    }

    result = _local_precheck(interpreted=interpreted, source_text=source_text, vocab=vocab)

    assert result["fields"]["category"] == ""
    assert result["fields"]["region"] == "seoul"
    assert result["fields"]["start_date"] is None
    assert result["fields"]["end_date"] is None
    assert result["fields"]["location_name"] == ""


def _payload_is_event_거짓():
    return {"is_event": False, "fields": {"title": "유효한 제목"}}


def _payload_제목_빈_결과():
    return {"is_event": True, "fields": {"title": "   "}}


def _payload_정상():
    return {"is_event": True, "fields": {"title": "유효한 제목"}}


@pytest.mark.parametrize(
    "make_interpreted, expected",
    [
        (_payload_is_event_거짓, False),
        (_payload_제목_빈_결과, False),
        (_payload_정상, True),
    ],
    ids=["is_event_거짓", "제목_빈_결과", "정상"],
)
def test_is_event가_거짓이거나_제목이_빈_해석_결과는_제출_대상에서_빠진다(make_interpreted, expected):
    """제목 없는 드래프트는 승인 게이트를 영원히 못 넘고 검수 큐에만 쌓이므로
    애초에 제출하지 않는다."""
    interpreted = make_interpreted()

    assert should_submit(interpreted=interpreted) is expected
