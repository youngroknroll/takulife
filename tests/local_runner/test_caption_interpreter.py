"""local_runner.caption_interpreter — 해석 프롬프트가 어휘·오늘 날짜·최근
드래프트 맥락·공식 여부 판별 기준을 담고, 읽은 텍스트를 <caption> 태그로
감싸는지 검증한다. 공식 여부 판별은 탐색 프롬프트(build_exploration_prompt)
에서 빠지고 이 프롬프트로 옮겨왔다 — 탐색은 페이지를 못 열지만 해석은
읽기 단계가 가져온 본문을 보기 때문이다."""
import pytest

from local_runner.caption_interpreter import build_interpretation_prompt


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
