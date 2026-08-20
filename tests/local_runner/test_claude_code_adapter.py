"""local_runner.claude_code_adapter 단위 테스트(U1·U2) — 방어적 JSON 파싱과
보정 재시도 1회 상한."""
import pytest

from local_runner.claude_code_adapter import AdapterOutputError, parse_candidates_output, run_agent_exploration


pytestmark = pytest.mark.unit


def _순수_JSON():
    return '{"candidates": [{"name": "a"}]}'


def _코드펜스_감싼_JSON():
    return '앞 설명\n```json\n{"candidates": [{"name": "a"}]}\n```\n뒤 설명'


def _앞뒤_설명_텍스트():
    return '이건 결과입니다: {"candidates": [{"name": "a"}]} 이상입니다.'


@pytest.mark.parametrize(
    "make_output",
    [_순수_JSON, _코드펜스_감싼_JSON, _앞뒤_설명_텍스트],
    ids=["순수_JSON", "코드펜스_감싼_JSON", "앞뒤_설명_텍스트"],
)
def test_어댑터는_코드펜스와_잡텍스트가_섞인_응답에서_JSON을_복구한다(make_output):
    result = parse_candidates_output(make_output())

    assert result == [{"name": "a"}]


def test_JSON을_전혀_복구할_수_없으면_실패를_보고한다():
    with pytest.raises(AdapterOutputError):
        parse_candidates_output("JSON 없음 텍스트")


def test_candidates_키가_없거나_리스트가_아니면_실패를_보고한다():
    with pytest.raises(AdapterOutputError):
        parse_candidates_output('{"candidates": "문자열"}')


def test_어댑터의_보정_재시도는_1회만_일어난다():
    calls = []

    def _always_broken(prompt):
        calls.append(prompt)
        return "이건 JSON이 아니다"

    with pytest.raises(AdapterOutputError):
        run_agent_exploration("탐색해줘", execute=_always_broken)

    assert len(calls) == 2


def test_보정_재시도가_성공하면_후보를_반환한다():
    calls = []

    def _fails_once_then_succeeds(prompt):
        calls.append(prompt)
        if len(calls) == 1:
            return "이건 JSON이 아니다"
        return '{"candidates": [{"name": "a"}]}'

    result = run_agent_exploration("탐색해줘", execute=_fails_once_then_succeeds)

    assert result == [{"name": "a"}]
    assert len(calls) == 2
