# Python 스타일 가이드 적용 기록

이 문서는 `AGENTS.md` "Python Style Guide" 절의 근거와 측정을 보관한다. 규칙 자체는
`AGENTS.md`가 정본이고 여기에는 두지 않는다. 트랙 48(2026-10-29)에서 도입했다.

## 목적

**Current fact.** 트랙 48 이전에는 린터·포매터·pre-commit이 없었고 컨벤션은
`AGENTS.md`의 한국어 주석 규칙과 Pythonic Code Design뿐이었다.

**Decision.** 기준선은 Google Python Style Guide
(https://google.github.io/styleguide/pyguide.html)이고, 충돌하면 이 저장소 규칙이
이긴다. 도구는 `ruff` 하나이며 CI 잡 "Lint and format (PR gate)"가 게이트다.

## 채택 항목과 설정 위치

| 구분 | 항목 | 강제 수단 |
|---|---|---|
| 도구 | 줄 길이 100칸, `ruff format` 서식 | `pyproject.toml` `[tool.ruff]`, CI |
| 도구 | 임포트 전체 모듈 경로 사전순(대소문자 무시, import/from 혼합) | ruff `I`, `force-sort-within-sections`, `case-sensitive = false` |
| 도구 | 절대 임포트만 | ruff `TID252`, `ban-relative-imports = "all"` |
| 도구 | 미사용 임포트·변수, 와일드카드 임포트 | ruff `F`. 와일드카드 예외는 `config/settings_test.py` 한 곳(`# noqa: F401,F403`)이고, 계약 테스트 `test_test_settings_boundary.py`는 그 임포트 뒤의 덮어쓰기 순서를 고정한다. 부수효과 때문에 남기는 임포트(`apps.py` 3곳)는 `# noqa: F401`과 한국어 사유를 단다. 재노출은 두지 않는다 |
| 도구 | 가변 기본 인자 금지 | ruff `B006` |
| 도구 | `migrations/` 제외, `tests/**` 줄 길이(E501) 제외 | `[tool.ruff]` 제외 설정 |
| 리뷰 | 이름 규칙, 예외 클래스 `Error` 접미, bare except 금지, `TODO(<scope>)` | 사람 |

활성 규칙 집합은 `E4,E7,E9,E501,W,F,I,B006,TID252`이고, 설정을 조용히 느슨하게 만드는
변경은 계약 테스트 `tests/core/test_lint_gate_contract.py`가 막는다. 보호 범위는 설정 키 집합 고정, 하위 ruff 설정 파일 우회 차단, CI 단계 `run:` 줄 전체 일치, 잡 `if:`·`|| true`·`--exit-zero` 차단, `pull_request` 트리거 유지이다.

## 채택하지 않는 항목(프로젝트 규칙 우선)

| Google 항목 | 미채택 근거 |
|---|---|
| docstring `Args:`/`Returns:`/`Raises:` 절, 영어 docstring | Code Comment Policy가 한국어 1~2줄을 요구한다. Google 형식 `Args:` docstring 블록은 0건이다 [실측 2026-10-29 rg] |
| "패키지·모듈만 임포트" | `from x import a, b` 다중 이름 줄이 218줄이다 [실측 2026-10-29 rg]. Django/DRF 이름 임포트가 관용이고 몽키패치 대상과 AST 경계 테스트가 이름 임포트에 의존한다 |
| 타입 힌트 의무화 | 현재 규칙에 없고 도입 이득을 측정하지 않았다 |
| pylint 전용 검사 | ruff로 대체하며 나머지는 리뷰로 지킨다 |
| 네이밍 N 규칙 강제 | 테스트 외 코드 위반이 6건(N803 3·N806 2·N818 1)이고 Django 관용이다 [실측 2026-10-29 ruff N 규칙 시험]. 리뷰 대상으로만 둔다 |

## 줄 길이 결정

ruff는 한글을 2칸으로 센다. Google의 80칸은 채택하지 않았다.

| 시험 | 변경 파일 | 변경 줄 | 출처 |
|---|---|---|---|
| 88칸 포맷 | 386개 | +9,390 / −2,928줄 | [실측 2026-10-29 ruff 0.15.12 격리 worktree 시험] |
| 100칸 포맷 | 376개 | +4,041 / −2,407줄 | [실측 2026-10-29 ruff 0.15.12 격리 worktree 시험] |
| 100칸 실제 적용 | 377개 | +4,042 / −2,407줄 | [실측 2026-10-29 ruff 0.15.22, 커밋 b6dd5035] |

기존 코드가 이미 88~100칸 사이로 손 포맷되어 있어 100칸이 변경량이 가장 작다.

`tests/**`의 E501은 제외한다. 100칸 포맷 뒤 남은 긴 줄 118건 중 81건이 `def` 줄(테스트
이름)이고 테스트 외 코드는 16건이다 [실측 2026-10-29]. 한국어 행동 중심 테스트 이름은
줄일 수 없다(Test Authoring Policy). 테스트 외 코드의 긴 줄은 줄바꿈으로 처리한다.

## 위반 현황과 처리 결과

| 위반 | 건수 | 처리 | 출처 |
|---|---|---|---|
| 상대 임포트 | 임포트 문장 142개(이름 단위 338건), 69개 파일, 레벨 1이 114문장·레벨 2가 28문장(전부 `staff/views`) | 모두 절대 임포트로 변환(커밋 9debe14c) | [실측 2026-10-29] |
| 임포트 정렬 위반 | 272건(상대 임포트를 절대화한 직후 측정. 설정 직후에는 256건이었고 포맷 전 시험에서는 253건으로 시점마다 다르다) | `--select I --fix`로 정리(커밋 9debe14c) | [실측 2026-10-29, 커밋 9debe14c] |
| 포맷 | 377개 파일 | `ruff format` 적용(커밋 b6dd5035) | [실측 2026-10-29 ruff 0.15.22] |
| 미사용 임포트·변수(F401·F841), E731 | 29건(F401 11·F841 17·E731 1) | 수동 정리(커밋 a33f00c4). F401은 10건 제거, 1건(`drafts/candidate_validation.py`의 `LeaseInvalidError`)은 이 커밋에서는 `# noqa: F401`로 유지했다가 같은 PR의 후속 커밋에서 재노출을 없애고 `drafts/runner_views.py`와 테스트가 `drafts.discovery_runs`에서 직접 가져오게 바꿔, F401 11건이 모두 코드에서 제거·해소됐다. `drafts/runner_views.py`의 `RunnerTokenThrottle` `# noqa: F401` 재노출도 같은 PR에서 제거하고 테스트가 `core.runner_auth`에서 직접 가져오게 했다. 첫 시도에서 한 줄 검색이 여러 줄 임포트를 놓쳐 수집 오류(ImportError)가 났고 구문 트리 전수 검사로 나머지 10건을 다시 확인했다. F841은 대입만 지우고 호출은 보존 | [실측 2026-10-29] |
| 테스트 외 코드 긴 줄 | 16건(주석 8·docstring 2·문자열 6) | 줄바꿈(커밋 69b49271). 문자열은 인접 리터럴로 나눠 값 불변 | [실측 2026-10-29] |
| 문서·코드 주석의 `파일:줄` 참조 | 포맷·임포트 변경으로 이동한 참조 213개: 문서 12개 파일 202개(머리 번호 184개, 쉼표로 이어 쓴 꼬리 18개), 코드 주석 10개 파일 11개 | 변경 전 줄 번호를 `git diff -U0` 구간으로 새 줄 번호에 옮기고 대상 줄 내용이 같은지 확인한 뒤 정정. 줄이 합쳐지거나 나뉜 5개와, 옛 번호부터 틀렸던 `staff/views/__init__.py:284`(실제 `system_errors` 줄은 288)는 직접 정했다. 옛 번호와 새 번호의 쌍 563개가 가리키는 줄 내용을 독립 스크립트로 다시 대조해 설명되지 않은 불일치 0개. 날짜가 박힌 검토 문서가 검토 당시 코드를 인용한 `drafts/runner_views.py:250-265`·`:253-259`는 역사 기록이라 그대로 둠 | [실측 2026-10-30] |
| CI 잡 | — | `ci.yml`에 "Lint and format (PR gate)" 잡 추가, 계약 테스트 `test_CI_워크플로는_린트_잡에서_...`가 Red→Green | [코드 .github/workflows/ci.yml] |

변환의 동일성은 다음으로 확인했다 [실측 2026-10-29].

- 포맷: 추적 `.py` 537개 파일의 구문 트리와 주석 토큰이 변환 전후 동일하다.
- 절대화: 임포트의 (절대 모듈, 이름, 별칭, 함수 안/밖) 다중집합이 동일하다.
- 168개 프로덕션 모듈이 새 인터프리터에서 임포트에 성공했다.
- 전체 회귀 4,298 passed / 10 deselected, 테스트 ID 차이 0건.
- 마지막 커밋 기준 전체 회귀 4,299 passed / 10 deselected(계약 테스트 1건 추가)와 e2e 10 passed,
  `ruff check .`·`ruff format --check .` 종료 코드 0 [실측 2026-10-29].

게이트 시험: 위반을 주입한 14종이 모두 종료 코드 1과 기대한 규칙 코드로 잡혔고, 음성
대조 4종은 통과했다 [실측 2026-10-29].

## blame 사용법

포맷만 바꾼 커밋은 저장소 루트의 `.git-blame-ignore-revs`에 기록한다. 새 포맷 전용
커밋도 같은 파일에 추가한다.

- 로컬: `git config blame.ignoreRevsFile .git-blame-ignore-revs`
- GitHub 웹 blame은 이 파일을 자동으로 적용한다.
- 두 SHA는 PR을 merge commit으로 머지할 때만 main 이력에 남는다. squash·rebase 머지는 하지 않는다. 머지 뒤 `git merge-base --is-ancestor b6dd5035 origin/main && git merge-base --is-ancestor 9debe14c origin/main; echo $?`가 0이어야 한다.

## 롤백 순서

계약 테스트가 잡 `if:`를 금지하므로 `if: false`로 잡만 끄면 Test suite 잡이 빨개진다. 아래 순서를 따른다.

1. lint 잡 제거(또는 `if: false`)와 `tests/core/test_lint_gate_contract.py`의 CI 단언 함수 삭제를 한
   커밋으로 한다.
2. `[tool.ruff]`를 되돌릴 때는 설정 단언 함수도 같은 커밋에서 삭제한다(결국 계약 테스트 파일 전체
   삭제와 `[tool.ruff]` 제거를 한 커밋으로 한다). 설정을 지우면 기본값 88칸으로 `format --check`가
   실패하므로 잡 제거와 반드시 같이 한다.
3. 머지 뒤 전체 롤백은 `git revert -m 1 <머지 SHA>`이다. 코드·설정·테스트·문서가 함께 돌아가
   모순이 없다. 개별 revert는 역순(69b49271 → a33f00c4 → 9debe14c → b6dd5035)으로 하며, 포맷
   revert는 문서 `파일:줄` 정정 커밋 bca5e55e와 함께 되돌린다. 임포트 절대화 커밋을 되돌리면 이후
   커밋과 충돌할 수 있고, `.git-blame-ignore-revs`의 해당 커밋 줄도 같이 정리한다.

마이그레이션이 없어 데이터 롤백은 없다.

## ruff 상향 절차

1. `pyproject.toml`의 ruff 범위를 바꾸고 `uv.lock`을 같은 커밋에서 갱신한다
   (`uv add --group dev`).
2. `uv run ruff format --check .`를 다시 잰다. 변경이 나오면 같은 PR에서 포맷 전용
   커밋을 만들고 그 해시를 `.git-blame-ignore-revs`에 추가한다.
3. `uv run ruff check .`가 새 규칙으로 늘어난 위반이 없는지 확인한다.
4. 포맷 전용 커밋이 생기면 문서·코드 주석의 `파일:줄` 참조가 밀린다. 같은 PR에서 `git diff -U0 <기준>`의 구간으로 옛 줄 번호를 새 줄 번호로 옮기고, 가리키는 줄 내용이 같은지 확인한 뒤 고친다(이번 트랙에서 쓴 방법).

## 알려진 한계

- 임포트 외 의미 결합과 pylint 전용 검사는 린트가 보지 못하므로 리뷰로 지킨다.
