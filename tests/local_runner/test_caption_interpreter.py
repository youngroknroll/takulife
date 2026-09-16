"""local_runner.caption_interpreter — 해석 프롬프트가 어휘·오늘 날짜·최근
드래프트 맥락·공식 여부 판별 기준을 담고, 읽은 텍스트를 <caption> 태그로
감싸는지 검증한다. 공식 여부 판별은 탐색 프롬프트(build_exploration_prompt)
에서 빠지고 이 프롬프트로 옮겨왔다 — 탐색은 페이지를 못 열지만 해석은
읽기 단계가 가져온 본문을 보기 때문이다."""
import json
from datetime import date

import pytest

from local_runner.caption_interpreter import (
    _local_precheck,
    build_interpretation_prompt,
    exclusion_reason,
    run_agent_interpretation,
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


def test_해석_프롬프트는_개최지_판정_지시와_출력_필드를_포함한다():
    """DF-13: 러너 제출 payload 최상위 venue_country를 서버가 이미 소비하므로
    (kr 아니면 not_kr일 때만 제외), 해석 프롬프트가 그 값을 실제로 만들도록
    지시와 출력 스키마를 갖춰야 한다."""
    vocab = {"categories": ["popup_store"], "regions": ["seoul"]}
    recent_drafts = []

    prompt = build_interpretation_prompt(
        vocab=vocab,
        today="2026-09-11",
        recent_drafts=recent_drafts,
        text="캡션 원문입니다.",
        platform="instagram",
    )

    # (1) 출력 스키마 최상위 필드와 허용값 3종
    assert "venue_country" in prompt
    assert "kr" in prompt
    assert "not_kr" in prompt
    assert "unclear" in prompt

    # (2) 본문 언어와 무관하게 실제 개최지로 판정하라는 지시
    assert "언어" in prompt

    # (3) 신호가 없으면 unclear로 두고 추측하지 말라는 지시
    assert "신호" in prompt


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


def _interpreted_개최지_키_없음():
    return {"fields": {"title": "제목"}}


def _interpreted_개최지_오타():
    return {"venue_country": "korea", "fields": {"title": "제목"}}


def _interpreted_개최지_타입_불일치():
    return {"venue_country": 123, "fields": {"title": "제목"}}


def _interpreted_개최지_허용값():
    return {"venue_country": "kr", "fields": {"title": "제목"}}


@pytest.mark.parametrize(
    "make_interpreted, expected",
    [
        (_interpreted_개최지_키_없음, "unclear"),
        (_interpreted_개최지_오타, "unclear"),
        (_interpreted_개최지_타입_불일치, "unclear"),
        (_interpreted_개최지_허용값, "kr"),
    ],
    ids=["키_없음", "오타", "타입_불일치", "허용값_유지"],
)
def test_해석_결과의_개최지_값이_허용값_밖이면_불확실로_정리된다(make_interpreted, expected):
    """DF-14: venue_country가 kr·not_kr·unclear 밖이면 서버가 제출을
    엉뚱하게 해석하지 않도록 로컬 선검사에서 unclear로 정리한다."""
    vocab = {"categories": ["popup_store"], "regions": ["seoul"]}
    source_text = "코엑스에서 열리는 팝업스토어."
    interpreted = make_interpreted()

    result = _local_precheck(interpreted=interpreted, source_text=source_text, vocab=vocab)

    assert result["venue_country"] == expected


def _제외_해외():
    return {"venue_country": "not_kr", "fields": {"end_date": "2026-04-14"}}, date(2026, 3, 15), "overseas"


def _제외_종료일_어제():
    return {"venue_country": "kr", "fields": {"end_date": "2026-03-14"}}, date(2026, 3, 15), "ended"


def _제외_시작일만_어제():
    return {"venue_country": "kr", "fields": {"start_date": "2026-03-14"}}, date(2026, 3, 15), "ended"


def _제외_종료일_오늘():
    return {"venue_country": "kr", "fields": {"end_date": "2026-03-15"}}, date(2026, 3, 15), None


def _제외_날짜_없음():
    return {"venue_country": "kr", "fields": {}}, date(2026, 3, 15), None


def _제외_형식_불량():
    return {"venue_country": "kr", "fields": {"end_date": "9월1일"}}, date(2026, 3, 15), None


def _제외_개최지_불확실_미래():
    return {"venue_country": "unclear", "fields": {"end_date": "2026-04-14"}}, date(2026, 3, 15), None


def _제외_해외이면서_지난_종료일():
    return {"venue_country": "not_kr", "fields": {"end_date": "2026-03-14"}}, date(2026, 3, 15), "overseas"


@pytest.mark.parametrize(
    "make_case",
    [
        _제외_해외,
        _제외_종료일_어제,
        _제외_시작일만_어제,
        _제외_종료일_오늘,
        _제외_날짜_없음,
        _제외_형식_불량,
        _제외_개최지_불확실_미래,
        _제외_해외이면서_지난_종료일,
    ],
    ids=[
        "해외",
        "종료일_어제",
        "시작일만_어제",
        "종료일_오늘",
        "날짜_없음",
        "형식_불량",
        "개최지_불확실_미래",
        "해외이면서_지난_종료일_우선순위는_overseas",
    ],
)
def test_제외_판정은_해외와_지난_행사만_사유를_돌려준다(make_case):
    """DF-15: 서버 제출 전 러너 쪽 앞단 필터. 서버와 같은 규칙(개최지가
    not_kr이면 overseas, 종료일이 없으면 시작일이 오늘 이전이면 ended)이며,
    둘 다 해당하면 overseas를 우선한다. 날짜를 못 읽으면 제외하지 않는다."""
    interpreted, today, expected = make_case()

    assert exclusion_reason(interpreted=interpreted, today=today) == expected


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


class _FakeCompletedProcess:
    def __init__(self):
        self.returncode = 0
        self.stdout = json.dumps(
            {"result": '{"is_event": false, "fields": {}}', "is_error": False}
        )
        self.stderr = ""


@pytest.mark.contract
def test_해석_실행은_대역_없이도_도구를_사실상_끄고_MCP를_전부_끈_채_JSON_출력을_요구한다(
    monkeypatch,
):
    # IG-R9에서 놓쳤던 자리다 — 그때는 실행 함수를 직접 불러 인자를 명시했을
    # 뿐, 아무도 인자를 안 넘겨도 기본 경로가 그 값을 채우는지는 검증하지
    # 않았다. execute= 대역을 절대 쓰지 않고 subprocess.run만 잡는다.
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        return _FakeCompletedProcess()

    monkeypatch.setattr(
        "local_runner.claude_code_adapter.subprocess.run", fake_run
    )

    run_agent_interpretation("해석해줘")

    argv = captured["argv"]
    tools_index = argv.index("--tools")
    assert argv[tools_index + 1] == "TodoWrite,TodoWrite"
    assert "--strict-mcp-config" in argv
    output_format_index = argv.index("--output-format")
    assert argv[output_format_index + 1] == "json"
