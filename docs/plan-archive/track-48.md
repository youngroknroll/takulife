# 트랙 48: Google Python 스타일 가이드 반영 — 문서 + 린터 + 코드 일괄 수정 [v2 — DOR·TDD 코치·QVL 검토 반영(2026-10-29), 사용자 지시 2026-10-29 "코드 컨벤션 수정 https://google.github.io/styleguide/pyguide.html", 범위 답변 "문서 + 코드 일괄 수정", 충돌 처리 답변 "프로젝트 규칙 우선" [문서 사용자 지시]]

> **기준선**: main `02d3b2ab`, 전체 회귀 4297 passed / 10 deselected / 152.02초 [실측 2026-10-29 main `ce27ac2c`]. 현재 린터·포매터·pre-commit 없음, CI 린트 스텝 없음, `pyproject.toml`에 `[tool.ruff]` 없음 [실측 2026-10-29 `rg`]. 컨벤션은 AGENTS.md "Code Comment Policy"(한국어 주석)와 "Pythonic Code Design"뿐이다. 브랜치 `style/track-48-google-python-style`, PR 1개.
> **Activated Roles**: DOR(CI 잡·의존성), TDD 코치(린트 게이트의 Red 증거 설계), Backend & Integration Engineer(구현), QVL(완료 평가). **Not Activated**: PSO(제품 결정 없음), SRR(보안 경계 무변경), 프런트 역할(템플릿·CSS·JS 무변경).
> **사용자 승인 범위**: 린터 도입은 범위 질문 선택지 "문서 + 코드 일괄 수정"(린터 포함 서술) 선택으로 승인된 것으로 본다. 새 개발 의존성은 `ruff` 하나뿐이고 테스트 편의 패키지가 아니다.

## 트랙 48 범위
1. **문서** — `AGENTS.md`에 "Python Style Guide" 절 신설(Code Comment Policy 바로 뒤). Google 가이드 채택 항목, 프로젝트 규칙 우선 예외(아래 D6), 린트·포맷 명령, 줄 길이 100칸(한글 2칸) 기록. `CLAUDE.md` Engineering Guardrails에 한 줄과 명령 목록에 린트 명령 추가. `docs/BE/python-style.md`에 측정·결정 근거 보관(AGENTS는 규칙만).
2. **도구** — `uv add --group dev "ruff>=0.15,<0.16"`(`pyproject.toml` + `uv.lock` 같은 커밋). `[tool.ruff]` 설정은 `pyproject.toml`에 둔다(pytest.ini와 충돌 없음).
3. **커밋 순서(v2, 검토 3역할 합의)** — 절대화가 줄 길이와 정렬 위치를 바꾸므로 정렬·포맷보다 먼저 한다. 중간 커밋마다 CI `lint`가 빨개지지 않도록 CI 잡은 마지막에 넣는다.
   - ⓪ `ruff` 개발 의존성(`pyproject.toml` + `uv.lock` 같은 커밋) + `[tool.ruff]` + 설정 계약 테스트 ST-A(Red→Green).
   - ① `ruff format`만 적용(`.git-blame-ignore-revs` 대상).
   - ② 상대 → 절대 임포트(`--select TID252`로 범위 한정) → `--select I --fix` → `ruff format` 재실행을 한 커밋에(`.git-blame-ignore-revs` 대상).
   - ③ F401·F841·E731 수동 정리(규칙은 D9).
   - ④ 테스트 외 코드 긴 줄 줄바꿈(`drafts/url_safety.py`↔`local_runner/url_safety.py` 쌍은 건드리지 않음).
   - ⑤ CI `lint` 잡 + CI 계약 테스트 ST-B + 문서 + `.git-blame-ignore-revs` + `.gitignore`·`.dockerignore`에 `.ruff_cache`.
4. **CI** — `.github/workflows/ci.yml`에 잡 `name: Lint and format (PR gate)` 추가. 기존 잡 패턴(`checkout` → `setup-uv` → `uv python install 3.13` → `uv sync --frozen`)을 따르고 Postgres 서비스는 두지 않는다. 단계는 `uv run ruff check .`, `uv run ruff format --check .`. 워크플로 `name: CI`·`on:` 블록은 건드리지 않는다(`deploy-pr.yml`이 `CI` 이름에 의존). 단계 이름에 `Deployment checklist`를 쓰지 않고 `python3 -c`를 쓰지 않는다(`tests/core/test_ci_command_policy.py` 계약). 롤백 주석 `# Rollback: add if: false`.
5. **blame 보존** — ①·②의 커밋 해시를 `.git-blame-ignore-revs`에 기록(머지 커밋 방식이라 SHA가 유지됨).
6. **런북 줄 번호 정정** — 운영 런북·배포 런북의 `파일:줄` 인용 11줄 [실측 2026-10-29 DOR `rg`]은 장애 대응 때 읽는 문서라 같은 PR에서 재측정해 정정한다(D8 나머지도 2026-10-30에 같은 PR에서 정정 — Evidence "후속 정정" 참조).

## 결정과 근거 (모든 수치는 격리 worktree 시험 결과)
- **D1 도구 = ruff 0.15.12**. Google 가이드의 공식 린터는 pylint지만, 서식·임포트·미사용 규칙은 ruff가 같은 규칙을 몇 초에 검사한다. 나머지는 리뷰로 지킨다(D6).
- **D2 줄 길이 100칸**(ruff는 한글을 2칸으로 센다). Google 80칸 미채택: 88칸 포맷 시 386개 파일 +9,390/−2,928줄, 100칸 시 376개 파일 +4,041/−2,407줄 [실측 2026-10-29 시험 worktree `ruff format --line-length 88/100`]. 기존 코드가 이미 88~100칸 사이로 손 포맷돼 있다.
- **D3 E501은 `tests/**`에서 제외**. 100칸 포맷 뒤 남는 긴 줄 118건 중 81건이 `def` 줄이다 [실측 2026-10-29]. 테스트 이름은 한국어 행동 중심 규칙과 "개명 전 복원" 규칙(AGENTS Test Authoring Policy)으로 줄일 수 없다. 테스트 외 코드의 16건 [실측 2026-10-29]은 줄바꿈한다.
- **D4 `migrations/` 제외** — 생성 코드.
- **D5 규칙 선택** = `E4,E7,E9,E501,W,F,I,B006,TID252`. Google 근거: 줄 길이·공백(E,W), 미사용 임포트·변수·와일드카드(F), 임포트 사전순(I, `force-sort-within-sections=true`, `case-sensitive=false`), 가변 기본 인자 금지(B006, 현재 위반 0건 [실측]), 상대 임포트 금지(TID252, `ban-relative-imports="all"`). 현재 위반: I001 253건, E501 118건, TID252 338건(이름 단위, ruff 위반 건수)=상대 임포트 문장 142개, 69개 파일, 테스트 0건, 레벨 1이 114문장·레벨 2가 28문장(전부 `staff/views/*`) [실측 2026-10-29 ruff·`rg` 교차 확인], F841 17건, F401 11건, E731 1건(`local_runner/translation_flow.py` 비-`noqa` 지점) [실측 2026-10-29 포맷 적용 뒤 시험]. 위반 수치는 착수 직전 `uv run ruff check --select ... --statistics`로 다시 잰다. `config/settings_test.py`의 `import *`는 계약 테스트가 소스 문자열을 고정하므로 기존 `# noqa` 유지.
- **D6 Google 가이드와 충돌해 채택하지 않는 항목(프로젝트 규칙 우선)**:
  - docstring `Args:/Returns:/Raises:` 절과 영어 docstring — Code Comment Policy(한국어, 1~2줄, 주석보다 코드). 현재 `Args:` 블록 0건 [실측 2026-10-29 `rg`]. ruff `D` 규칙 미사용.
  - "패키지·모듈만 임포트" — `from x import Name` 다중 이름 줄 218건 [실측 2026-10-29 `rg`]과 단일 이름 임포트 전반이 Django/DRF 관용이고, 몽키패치 대상(`web.views.events.timezone.localdate`)과 AST 경계 테스트가 이름 임포트에 의존한다.
  - 네이밍 N 규칙 — 테스트 외 코드 위반 6건(N803 3·N806 2·N818 1) [실측 2026-10-29]은 Django 관용(모델 변수 `User` 등)이라 강제하지 않고 리뷰 대상으로 문서화. 테스트 이름 N802 3176건 [실측 2026-10-29]은 한국어 테스트 이름 정책 때문에 대상 아님.
  - 주석 영어 불가, 타입 힌트 의무 없음, pylint 전용 검사.
- **D7 임포트 절대화 영향(v2 수정)** — `web/views/__init__.py` 재노출이 `from web.views.events import home` 형태가 된다. 절대화 뒤에는 `tests/core/test_architecture_boundaries.py`와 `tests/local_runner/test_local_runner_isolation.py`가 처음으로 이 임포트들을 스캔한다(두 스캐너는 상대 임포트를 건너뛴다). QVL 코드 추적 결과 상대 임포트는 전부 자기 최상위 패키지 안으로 해석되므로 새 앱 간 위반·접두 오탐은 생기지 않을 것으로 보지만 실행으로 확인하지 못했다. ② 커밋의 필수 통과 조건은 이 두 파일과 `tests/core/test_web_views_package_boundaries.py` Green이며, Red면 기존 위반(같은 트랙에서 수정) 또는 스캐너 오탐(합성 파일 Red-Green)으로 분류해 처리한다.
- **D8 문서 `파일:줄` 참조 드리프트** — 문서 15개에 `.py:NNN` 형태 참조 244줄(매치 273건) [실측 2026-10-29 `rg`]. 포맷·정렬로 줄 번호가 바뀐다. 처음에는 운영·배포 런북 11줄(D 범위 6번)만 정정하고 나머지를 이연했으나, 사용자 지적(2026-10-30 "백로그 남기지 말라고 했는데" [문서 사용자 지시])으로 전부 같은 PR에서 정정했다. `.lineno`를 쓰는 테스트 6개 파일 [실측 2026-10-29 QVL `rg -c`]은 줄 번호를 실패 메시지에만 쓰고 특정 줄을 단언하지 않아 포맷에 깨지지 않는다.
- **D9 수동 정리 규칙(F401·F841·E731)** — 자동 수정하지 않는다. F841은 변수만 지우고 우변은 보존한다(`x = f()` → `f()`, 튜플 언패킹의 미사용 이름 → `_`, 우변이 상수·이름일 때만 문장 삭제 허용). F401은 항목별로 `M.N` 문자열 패치 대상·`from M import N` 재노출·`config/settings.py` 점 표기·마이그레이션 직접 참조·`__all__`·`# noqa: F401` 부수효과 임포트(`events/apps.py`·`accounts/apps.py`·`archive/apps.py`의 `from . import signals`, `drafts/runner_views.py`)를 `rg`로 확인하고 히트하면 지우지 않는다. 함수 안 지연 임포트(production 12개 파일 33줄 [실측 2026-10-29 QVL `rg`])는 절대화해도 함수 안에 남긴다. E731은 `if translate is None:` 안 중첩 `def`로 바꾸되 `__name__` 참조 여부를 `rg`로 확인한다. 변경 전후 파일 단위 `Call` 노드 수가 같아야 한다(호출 삭제 방지).
- **D10 롤백 순서** — (a) lint 잡만 끄기: 잡에 `if: false`. (b) `[tool.ruff]`만 되돌리면 `format --check`가 88칸 기본값으로 수백 개 파일에서 실패하므로 반드시 (a)와 함께 한다. (c) 코드 되돌리기: 커밋별 `git revert`, ② 되돌림은 ③ 이후 커밋과 충돌할 수 있고 `.git-blame-ignore-revs`의 해당 SHA 줄도 같이 정리한다. DB 마이그레이션이 없어 데이터 롤백은 없다.
- **D11 훅 미도입** — 린트를 `PostToolUse` 훅으로 강제하지 않는다. 훅은 CI에서 적용되지 않고 신설에 6+6 페이로드 증명이 필요하다(AGENTS "Harness Enforcement"). CI `lint` 잡이 게이트다.
- **D12 승인 근거** — `ruff`는 테스트 편의 패키지가 아니라 개발 도구이고, 사용자가 범위 질문에서 "문서 + 코드 일괄 수정"을 고른 것을 린터 포함 승인으로 읽는다. 최종 보고에 이 해석을 적어 사용자가 이의를 낼 수 있게 한다.

## Test List (v2) — 정식 pytest 테스트는 계약 테스트 ST-A·ST-B뿐이고 나머지 V-1~V-6은 행동 시나리오가 아니라 검증 절차(비테스트 증거)다 [문서 TDD 코치 권고 2026-10-29]
| ID | 행위 | 경계 | 테스트 이름 / 검증 | 상태 |
|---|---|---|---|---|
| ST-A | 린트 기준을 조용히 느슨하게 만드는 설정 변경이 실패한다: `tomllib`로 `[tool.ruff]`를 읽어 `line-length == 100`, `lint.select ⊇ {E4,E7,E9,E501,W,F,I,B006,TID252}`, `ban-relative-imports == "all"` | contract | `tests/core/test_lint_gate_contract.py::test_린트_설정은_줄_길이_100칸과_필수_규칙_집합을_유지한다`. Red 이유 = `[tool.ruff]` 섹션 부재(선행 단언 메시지로 확인, KeyError면 틀린 Red) | Green |
| ST-B | CI 워크플로가 `uv run ruff check .`와 `uv run ruff format --check .`를 실행하는 잡을 가지며 그 잡에 `continue-on-error`가 없다 | contract | `tests/core/test_lint_gate_contract.py::test_CI_워크플로는_린트_잡에서_ruff_check와_ruff_format_check를_uv_run으로_실행한다`. Red 이유 = `ci.yml`에 `ruff` 문자열 없음 | Green |
| V-1 | 커밋마다 `ruff check .` 위반 수가 단조 감소해 마지막에 0, `format --check` 0 — 커밋별 `--statistics` 기록이 Red→Green 증거. `ruff check --show-files`와 `git ls-files '*.py'` 집합 차이는 `migrations/`뿐 | 절차 | `uv run ruff check . --statistics` | 완료 |
| V-2 | 위반 주입 게이트 — 종료 코드가 정확히 1이고 `--output-format=json`의 규칙 코드 집합이 기대값과 같음: F401·I001·E501(`core/` 아래 101칸)·TID252 3형태(`from .x`·`from . import x`·`from ..x`)·B006·F403·E402·W291·F841·E731, 포맷만 어기는 주입 1종(`format --check` 종료 코드 1). 음성 대조: `tests/**` 101칸 줄 통과, `migrations/` 위반 무시, 기존 `# noqa` 줄 통과. isort 분류: 프로젝트 앱이 first-party로 정렬되는지 | 절차 | 스크래치 worktree 주입 스크립트(커밋 안 함) | 완료 |
| V-3 | ① 포맷 커밋 동일성 — 전후 모든 `.py`: `ast.dump`(docstring 공백 정규화) 동일, `tokenize` COMMENT 토큰 다중집합 동일, 문자열 상수 다중집합 동일, 파일 집합 동일 | 절차 | `scratchpad/ast_equiv.py`(확장) | 완료 |
| V-4 | ② 임포트 커밋 동일성 — 각 임포트 문장 `(절대 해석 모듈, 이름, 별칭, 함수 안/밖)` 다중집합 동일, 임포트 외 노드 `ast.dump` 동일, 주석 토큰 동일. 모든 프로덕션 모듈을 새 인터프리터에서 임포트하는 스모크(`django.setup()` 포함, 러너는 Django 없이) | 절차 | 스크립트 + 모듈 임포트 스모크(`git ls-files` 기반 모듈 목록) | 완료 |
| V-5 | ③ 수동 정리 동일성 — 파일 단위 `Call`/`Await` 노드 수 동일(호출 삭제 방지), 사이트별 판별 `rg` 결과를 커밋 메시지 표에 기록 | 절차 | 스크립트 | 완료 |
| V-6 | CI `lint` 잡 — 성공 쪽은 트랙 PR의 `gh pr checks`, 실패 쪽은 폐기용 드래프트 PR에 위반 1종을 얹어 확인 후 머지 없이 닫기 | ci | `gh pr checks` | 완료 |

## 수용 기준·검증
- AC1 마지막 커밋에서 `uv run ruff check .`·`uv run ruff format --check .` 종료 코드 0, `manage.py check` 0건, `makemigrations --check --dry-run` 변경 없음, `git diff --stat -- '*/migrations/*' templates static` 비어 있음(`migrations/`는 ruff 제외라 포맷 대상 아님).
- AC2 V-2 전 항목: 종료 코드 정확히 1 + 규칙 코드 일치 → 원복 후 0. 실패 메시지(규칙 코드)를 Evidence에 인용.
- AC3 V-3·V-4·V-5 불일치 0건 [실측 예정]. 불일치가 나오면 원인 파일을 원복·조사.
- AC4 순수 변환 커밋(①②③④)마다 전체 회귀가 직전 커밋과 같은 건수로 통과하고 `uv run pytest --collect-only -q` 노드 ID 집합 diff가 0이다. 기준선은 `ce27ac2c`의 4297건이지만 ⓪에서 계약 테스트 1건이 늘어 ① 이후 비교 기준은 4298건이다 [실측 2026-10-29]. 계약 테스트를 추가하는 커밋(⓪⑤)만 기대값을 +N으로 바꾼다. 건수만이 아니라 노드 ID로 비교한다.
- AC5 e2e: 로컬 `uv run pytest -q -m e2e tests/e2e` 1회와 CI `e2e` 잡(관측) [실측 예정].
- AC6 AGENTS.md 신설 절·CLAUDE.md·`docs/BE/python-style.md`의 모든 수치에 단위·출처 태그. `rg "ruff|Python Style Guide"`로 정합 확인. `docs/BE/contract-guards.md`의 "상대 임포트는 건너뛴다" 서술을 절대화 이후 상태에 맞게 정정.
- AC7 PR의 CI 잡 전부 성공(기존 워크플로 잡 4개와 신설 `lint` 잡, 외부 체크 GitGuardian은 별도 구분) [실측 예정 `gh pr checks`].

## 채택하지 않는 것(결정이며 이연·백로그 항목이 아니다)
- Google 가이드의 docstring 절 체계·"모듈만 임포트"·영어 가이드 전체 채택 — 프로젝트 규칙(한국어 주석, Django 관용) 우선 결정이라 재제안하지 않는다(사용자 2026-10-29 [문서 사용자 지시]).
- pylint 도입, 타입 힌트 의무화, N 규칙 강제, 테스트 `E501` 정리 — 이 트랙에서 하지 않기로 한 결정이다. 근거는 `AGENTS.md` "Python Style Guide"와 `docs/BE/python-style.md`.
- (해소됨) 문서 `파일:줄` 참조 재측정 — 2026-10-30 같은 PR에서 전부 정정했다. Evidence "후속 정정" 참조.

## Evidence (2026-10-29, 브랜치 `style/track-48-google-python-style`, PR #405)
- 설치된 ruff는 0.15.22였다(시험은 0.15.12). 커밋 7개: `6863b242` 의존성·설정·ST-A, `b6dd5035` 포맷, `9debe14c` 절대화·정렬, `a33f00c4` 수동 정리, `69b49271` 긴 줄, `035c4881` CI 잡·ST-B, `3aae98a7` 문서 [실측 `git log`].
- ST-A Red: `AssertionError: pyproject.toml에 [tool.ruff] 섹션이 없다` → Green 1 passed [실측]. ST-B Red: `ci.yml에 'Lint and format (PR gate)' 잡이 없다`(전체 회귀 4298 passed + 이 1건 실패) → Green [실측].
- V-1 위반 수 추이(`ruff check . --statistics`): 설정 직후 712건(TID252 338·I001 256·E501 86·F841 17·F401 11·W291 2·E731 1·W292 1) → 포맷·절대화·정렬 뒤 45건(F841 17·E501 16·F401 11·E731 1) → 수동 정리 뒤 16건(E501) → 긴 줄 뒤 0건 [실측]. `ruff check --show-files` 대 `git ls-files '*.py'` 차이는 `migrations/` 79개뿐(새 테스트 파일은 미추적이라 일시 차이) [실측].
- V-2 위반 주입 14종 전부 종료 코드 정확히 1 + 기대 규칙 코드 일치(F401·I001·E501·TID252 3형태·B006·F403·E402·W291·F841·E731·first-party 그룹 순서), 포맷 전용 위반은 `check` 0·`format --check` 1, 음성 4종(tests 101칸·migrations·noqa 줄·올바른 그룹 순서) 통과, 실행 뒤 worktree clean [실측].
- V-3 포맷 커밋: 추적 .py 537개 구문 트리·주석 토큰 불일치 0건(비교 스크립트는 `.docs/`·`.shots/`의 추적되지 않는 로컬 파일 2개를 존재 여부 차이로 보고하나 git 비추적) [실측]. `pytest --collect-only` 테스트 ID 4298개 전후 차이 0 [실측].
- V-4 절대화 커밋: 임포트 (절대 모듈·이름·별칭·함수 안/밖) 다중집합 불일치 0건, 168개 프로덕션 모듈 새 인터프리터 임포트 실패 0건(러너는 Django 없이) [실측]. 경계 가드 74건 통과 [실측]. 첫 스모크는 `python -I`가 cwd를 빼서 러너 모듈이 실패했고 스크립트 문제라 `-I`를 빼고 재실행.
- V-5 수동 정리: 파일별 Call/Await 수 불일치 0건, 임포트 변화는 F401 10건 제거뿐 [실측]. **결함 1건**: 워커의 한 줄 `rg`가 여러 줄 임포트를 놓쳐 `LeaseInvalidError` 재노출(`drafts/runner_views.py`·`tests/drafts/test_candidate_validation.py`가 사용)을 지웠고 수집 오류 2건(ImportError)이 났다 → AST 전수 검사 스크립트로 11건 재확인(재노출 사용처 1건뿐) → 임포트 복구 + `# noqa: F401` + 한국어 사유. 교훈: 재노출 판별은 줄 단위 `rg`가 아니라 AST로 한다.
- ④ 긴 줄 16건(주석 8·docstring 2·문자열 6): docstring 제외 코드 AST 동일, 다른 4298건 통과 [실측].
- 최종: `ruff check .`·`ruff format --check .` 종료 코드 0, `manage.py check`·`makemigrations --check --dry-run` 이상 없음, `migrations/`·`templates/`·`static/` diff 0, 전체 회귀 4299 passed / 10 deselected / 130.20초, 로컬 e2e 10 passed(Playwright 크로미움을 이 Mac에 새로 설치한 뒤) [실측].
- AC4 커밋별 전체 회귀 [실측 2026-10-29]: ① 4298 passed / 134.60초 + 노드 ID 차이 0, ② 4298 passed / 132.80초 + 노드 ID 차이 0 + 경계 가드 74건, ③ 비-core 3136 passed + `tests/core` 1162 passed = 4298 + 노드 ID 차이 0(재노출 복구 뒤), ④ 4298 passed + 의도한 Red 1건(ST-B), ⑤ 4299 passed / 130.20초.
- V-6 [실측 2026-10-29]: PR #405의 CI 6건(Test suite·E2E·Lint and format·Dependency audit·Docker build·GitGuardian) 전부 pass, Lint 잡 12초. 폐기용 드래프트 PR #406에 미사용 임포트 1줄을 얹자 Lint 잡이 11초 만에 `F401 [*] os imported but unused --> core/zz_v6_violation.py:1:8`, `Found 1 error.`, `exit code 1`로 실패. PR #406은 머지 없이 닫고 브랜치와 진행 중이던 실행을 정리.
- QVL 완료 평가(2026-10-29): 판정 Complete with gaps, High 결함 없음. 같은 PR에서 반영: README CI 행에 `lint` 추가, `docs/BE/python-style.md`의 `F` 예외 서술·정렬 위반 수치 시점 정정, AGENTS.md 예외 서술 정정과 기존 예외 클래스 비개명 명시(이 명시는 아래 후속 정정에서 개명으로 대체), `test_architecture_boundaries.py` 낡은 주석 갱신. 계획 상태표(Test List, AC4) 갱신. 처음에 이연한 계약 테스트 약화 경로(`lint.ignore` 확대·`|| true`·잡 `if: false`)와 `LeaseInvalidError` 재노출 대안은 2026-10-30 같은 PR에서 해소했다(Evidence "후속 정정"). `main`은 브랜치 보호가 없어 필수 체크 등록 문제가 없다 [실측 `gh api` 404 "Branch not protected"].
- 후속 정정(2026-10-30, 사용자 지적 "백로그 남기지 말라고 했는데" [문서 사용자 지시]): 이연 5건을 `docs/backlog.md` M절에 올린 것은 CLAUDE.md의 "같은 유형·소규모 결함은 같은 트랙에서 고친다" 위반이었다. 5건을 같은 PR에서 해소하고 M절을 삭제했다 [실측 `git log`: `4626ea3c`·`e2e848e8`·`9d227ae2`·`bca5e55e`].
  - ① `LeaseInvalidError`: `drafts/runner_views.py`와 `tests/drafts/test_candidate_validation.py`가 `drafts.discovery_runs`에서 직접 가져오고 `candidate_validation`의 `# noqa: F401` 재노출을 지웠다(파일 3개 [실측 `git diff --stat`]).
  - ② `SubmissionRejected`→`SubmissionRejectedError`: 옛 이름 24곳, 소스 4개·테스트 2개 파일 [실측 `rg`]. 이전 서술 "임포트·테스트를 넓게 건드린다"는 크기를 재지 않고 쓴 것이었다. 개명 전후 테스트 ID 4299개, 차이 0개 [실측 `pytest --collect-only`], AGENTS.md의 비개명 단서 삭제.
  - ③ 계약 테스트 강화: 설정 키 집합·값 고정, 하위 ruff 설정 파일 차단, `run:` 줄 전체 일치, `if:`·`|| true`·`|| exit 0`·`--exit-zero`·`pull_request` 트리거 검사. 약화 주입 14종이 전부 실패(종료 코드 1, 기대한 단언 메시지)하고 매번 `git diff --quiet` 복원 확인 [실측 scratchpad `mutate_lint_gate.py`, 커밋하지 않음]. 테스트 한 건 0.76초 [실측 `--durations`].
  - ④ `파일:줄` 참조: 변경 전 `02d3b2ab` 기준으로 줄 번호를 사상해 문서 12개 파일 202개(머리 번호 184개·쉼표 꼬리 18개)와 코드 주석 10개 파일 11개, 합 213개를 정정 [실측 사상 스크립트]. 처음 측정(문서 15개 244줄)은 쉼표로 이어 쓴 번호와 코드 주석을 빠뜨려 작았다. 독립 재검증: 옛 번호와 새 번호 쌍 563개가 가리키는 줄 내용 일치, 직접 정한 6개 외 설명되지 않는 불일치 0개 [실측]. 변경 전부터 틀렸던 `staff/views/__init__.py:284`는 `system_errors` 줄 288로 바로잡았다. 참조 숫자 외 변경 구간 0개(파일 20개) [실측 difflib]. 날짜가 박힌 검토 문서의 `drafts/runner_views.py:250-265`·`:253-259`는 검토 당시 코드를 인용한 역사 기록이라 유지.
  - ⑤ ruff 상향: 이연이 아니라 `docs/BE/python-style.md`에 이미 있는 절차라 백로그 항목만 삭제하고, 절차에 참조 점검 단계(4번)를 더했다.
  - 최종 확인: 전체 회귀 4299 passed / 10 deselected / 138.82초 [실측 `uv run pytest -q`], `ruff check`·`ruff format --check` 종료 코드 0, 458개 파일 정상, `manage.py check` 이상 0건 [실측].
- 검토: DOR·TDD 코치·QVL 3역할이 계획 v1을 검토해 커밋 순서(절대화→정렬→포맷)·ST-5 범위·단위 오기(338건=이름 단위, 142문장)·롤백 단락·`.ruff_cache` 무시를 지적했고 v2에 반영. QVL 완료 평가는 PR #405 오픈 뒤 요청.

---

