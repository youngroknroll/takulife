"""local_runner.claude_code_adapter 단위 테스트(U1·U2) — 방어적 JSON 파싱과
보정 재시도 1회 상한. 아래 계약 테스트 2건만 CLI 호출 인자(argv) 자체를 잡아
확인한다 — 기존 5건은 모두 execute= 스텁으로 _execute_claude를 우회한다."""
import json

import pytest

from local_runner.claude_code_adapter import (
    AdapterOutputError,
    _execute_claude,
    build_exploration_prompt,
    parse_candidates_output,
    parse_json_object,
    run_agent_exploration,
)


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


def _단일_객체_순수_JSON():
    return '{"is_event": true, "title": "코믹월드"}'


def _단일_객체_코드펜스_감싼_JSON():
    return '앞 설명\n```json\n{"is_event": true, "title": "코믹월드"}\n```\n뒤 설명'


def _단일_객체_앞뒤_설명_텍스트():
    return '이건 결과입니다: {"is_event": true, "title": "코믹월드"} 이상입니다.'


@pytest.mark.parametrize(
    "make_output",
    [_단일_객체_순수_JSON, _단일_객체_코드펜스_감싼_JSON, _단일_객체_앞뒤_설명_텍스트],
    ids=["순수_JSON", "코드펜스_감싼_JSON", "앞뒤_설명_텍스트"],
)
def test_어댑터_JSON_복구는_후보_목록과_단일_객체_모두에_같은_복구_순서를_적용한다(make_output):
    result = parse_json_object(make_output())

    assert result == {"is_event": True, "title": "코믹월드"}


def test_단일_객체_JSON을_전혀_복구할_수_없으면_실패를_보고한다():
    with pytest.raises(AdapterOutputError):
        parse_json_object("JSON 없음 텍스트")


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


class _FakeCompletedProcess:
    def __init__(self):
        self.returncode = 0
        self.stdout = json.dumps({"result": '{"candidates": []}', "is_error": False})
        self.stderr = ""


def _capture_argv(monkeypatch):
    """_execute_claude가 실제로 subprocess.run에 넘기는 argv를 붙잡는다.
    최소 JSON 봉투({"result", "is_error"})를 돌려줘 파싱이 끝까지 통과하게 한다."""
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        return _FakeCompletedProcess()

    monkeypatch.setattr("local_runner.claude_code_adapter.subprocess.run", fake_run)
    return captured


@pytest.mark.contract
def test_탐색_실행_명령은_웹_탐색_도구만_허용하고_MCP를_전부_끈다(monkeypatch):
    captured = _capture_argv(monkeypatch)

    _execute_claude("탐색해줘", tools="WebSearch,WebFetch", strict_mcp=True)

    argv = captured["argv"]
    assert "--strict-mcp-config" in argv
    tools_index = argv.index("--tools")
    assert argv[tools_index + 1] == "WebSearch,WebFetch"
    output_format_index = argv.index("--output-format")
    assert argv[output_format_index + 1] == "json"


@pytest.mark.contract
def test_확인_절차를_끄는_모드를_쓰면_MCP_차단_플래그도_함께_있다(monkeypatch):
    captured = _capture_argv(monkeypatch)

    _execute_claude("탐색해줘", tools="WebSearch,WebFetch", strict_mcp=True)

    argv = captured["argv"]
    if "--permission-mode" in argv:
        permission_mode_index = argv.index("--permission-mode")
        if argv[permission_mode_index + 1] == "bypassPermissions":
            assert "--strict-mcp-config" in argv


def test_탐색_프롬프트는_검색어와_판별_기준과_출력_스키마를_포함하고_judgment는_해석_단계로_이관되었다():
    prompt = build_exploration_prompt(query="하츠네 미쿠", max_events=20, max_sources=10)

    assert "<query>하츠네 미쿠</query>" in prompt

    for reason in ["same_name", "fan_made", "ended", "cancelled", "restock_only", "other"]:
        assert reason in prompt

    # official_basis는 소스 블록(계정형 소스의 공식성 근거)에는 남아 있어야
    # 하므로 프롬프트 전체가 아니라 이벤트 스키마 설명 블록만 잘라 확인한다.
    # 계획서 §B 출력 스키마가 `{"events": [...], "sources": [...]}` 순서로
    # 나열되므로, "events" 표시부터 "sources" 표시 직전까지를 이벤트 블록으로
    # 본다.
    events_block_start = prompt.index('"events"')
    sources_block_start = prompt.index('"sources"')
    assert events_block_start < sources_block_start
    events_block = prompt[events_block_start:sources_block_start]

    for key in ["url", "platform", "title_guess", "is_event", "duplicate_urls"]:
        assert key in events_block
    assert "judgment" not in events_block
    assert "official_basis" not in events_block


@pytest.mark.contract
def test_캡션_해석_실행_명령은_도구를_사실상_끄고_MCP를_전부_끈_채_JSON_출력을_요구한다(monkeypatch):
    """--tools는 쉼표로 구분된 유효한 이름이 둘 이상일 때만 실제로 도구를
    제한한다(실측) — 빈 문자열이나 단일 값은 조용히 무시되어 셸·파일 쓰기를
    포함한 기본 도구 전체가 열린다. 그래서 해석 단계는 무해한 도구 이름
    ("TodoWrite")을 일부러 두 번 적어 제약이 실제로 걸리게 한다. 이 중복은
    실수가 아니다 — 지우면 안 된다."""
    captured = _capture_argv(monkeypatch)

    _execute_claude("해석해줘", tools="TodoWrite,TodoWrite", strict_mcp=True)

    argv = captured["argv"]
    tools_index = argv.index("--tools")
    assert argv[tools_index + 1] == "TodoWrite,TodoWrite"
    assert "--strict-mcp-config" in argv
    output_format_index = argv.index("--output-format")
    assert argv[output_format_index + 1] == "json"


@pytest.mark.contract
def test_대역_없이_탐색을_돌리면_탐색용_도구_인자가_실제로_넘어간다(monkeypatch):
    """run_agent_exploration이 execute= 대역 없이 기본 경로(_execute_claude)를
    탈 때도 tools·strict_mcp가 필수 키워드라 타입 오류 없이 호출돼야 한다.
    execute 자체를 대역으로 갈아끼우지 않고 그 아래 subprocess.run만 잡아,
    기본 경로가 실제로 탐색용 인자를 넘기는지 확인한다."""
    captured = _capture_argv(monkeypatch)

    run_agent_exploration("탐색해줘")

    argv = captured["argv"]
    tools_index = argv.index("--tools")
    assert argv[tools_index + 1] == "WebSearch,WebFetch"
    assert "--strict-mcp-config" in argv
