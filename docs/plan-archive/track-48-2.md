# 트랙 48-2: 컨벤션 별도 문서화 + 훅 강제 [v1 — 사용자 지시 2026-10-30 "컨벤션을 따로 문서화해서 에이전트가 참조하도록. 훅으로 강제" [문서 사용자 지시]. PR #405 범위 확장(같은 주제, 미머지)]

> **기준선** [실측 2026-10-30]: 훅 6개 파일(`.claude/hooks/`), `.claude/settings.json`은 PreToolUse만 등록하고 PostToolUse 등록은 0개. 스타일 규칙은 `AGENTS.md` "Python Style Guide" 절(689-743행)에 있고 측정·이력은 `docs/BE/python-style.md`. 어댑터 11개 중 스타일 절을 읽도록 지정한 것은 0개(`rg -i 'python style'`). `# noqa: F401` 5곳: `apps.py` 3곳(시그널 부수효과), `config/settings_test.py`(와일드카드), `drafts/runner_views.py:11`(`RunnerTokenThrottle` 재노출 — 테스트 1개 파일이 이 경로로 가져오는 것뿐이라 `LeaseInvalidError`와 같은 유형). 단일 파일 `uv run --no-sync ruff check` 0.02초. 명시 경로에 `migrations/` 제외를 적용하려면 `--force-exclude`가 필요하다(없으면 제외 설정이 무시됨).
> **Activated Roles**: Backend & Integration Engineer(구현), QVL(훅 판별력·완료 평가). DOR은 이미 PR #405 깊은 검토로 가동 중. **Not Activated**: PSO·SRR·DAR(제품·보안·경계 결정 없음), 프런트 역할.

## 결정
- **D1 규칙 정본 = `docs/BE/python-conventions.md`(신설, 한국어)**. 규칙·예시(좋은/나쁜 코드)·도구 명령·훅 동작·채택하지 않은 Google 규칙을 한 곳에 둔다. `AGENTS.md` "Python Style Guide" 절은 "기준선은 Google, 충돌 시 이 저장소 규칙 우선, 정본은 그 문서, CI·훅이 강제" 요지의 짧은 포인터로 줄인다(Source Of Truth 규칙: 공유 정책을 어댑터마다 복사하지 않는다). `docs/BE/python-style.md`는 "적용 기록"(측정·커밋·롤백·상향 절차)으로 남기고 서로 링크한다.
- **D2 에이전트 참조 경로**: 어댑터 `backend-integration-engineer`·`backend-tdd-coach`·`quality-verification-lead`의 읽기 목록에 `docs/BE/python-conventions.md` 한 줄 추가(Python을 쓰거나 판정하는 역할만). `CLAUDE.md` Engineering Guardrails의 스타일 줄은 새 문서를 가리키게 고친다. 프런트 어댑터는 Python을 편집하지 않으므로 제외.
- **D3 훅 1 — `python-style-guard.sh`, PostToolUse `Edit|Write`**: 편집한 파일이 저장소 안 `.py`이고 git-ignored가 아니면 `uv run --no-sync ruff check --force-exclude --no-fix <파일>`과 `uv run --no-sync ruff format --check --force-exclude <파일>`을 돌린다. 위반이면 ruff 출력을 stderr로 내고 exit 2(PostToolUse에서는 차단이 아니라 모델에 즉시 피드백 — 문서 [문서 code.claude.com/docs/en/hooks]). 자동 수정·자동 포맷은 하지 않는다(편집 직후 파일을 조용히 바꾸면 Edit 도구의 파일 상태 추적과 "silent mutation" 금지에 어긋난다). ruff가 없으면 경고 한 줄 후 exit 0(가드는 실수 방지용이지 보안 경계가 아니다).
- **D4 훅 2 — `git-commit-style-guard.sh`, PreToolUse `Bash`**: 명령 세그먼트에 `git commit`이 있으면 스테이지된 `.py`(`git diff --cached --name-only --diff-filter=ACMR -- '*.py'`)에 같은 두 명령을 돌리고 위반이면 exit 2로 커밋을 막는다. 이것이 실제 강제 지점이고 CI 잡은 최종 게이트다. 스테이지된 `.py`가 0개면 통과. 알려진 공백: `bash -c` 중첩·변수 치환(기존 훅과 같음).
- **D5 등록·문서**: `.claude/settings.json`에 PostToolUse 블록 신설 + Bash PreToolUse 목록에 추가(timeout 15000ms — `uv run` 기동 포함). `AGENTS.md` 훅 표에 2행, `CLAUDE.md` 훅 목록에 2개. 롤백 = settings.json 항목 제거(기존 규칙).
- **D6 같은 유형 결함 동반 수정**: `drafts/runner_views.py`의 `RunnerTokenThrottle` 재노출 제거, `tests/drafts/test_discovery_runner_api.py:19`가 `core.runner_auth`에서 직접 가져온다(`tests/events/test_translation_runner_api.py:7`은 이미 그렇게 한다). `monkeypatch.setattr(클래스 객체, …)`라 임포트 경로와 무관.
- **D7 TDD 적용 범위**: 훅은 셸 스크립트라 pytest 대상이 아니다(기존 6개와 같음). 검증은 AGENTS.md 훅 규칙대로 페이로드 세트(차단 6건 이상·허용 6건 이상, 훅마다)와 라이브 위반 1건씩. 계약 테스트 추가 없음.
- **사용자 결정(2026-10-30 [문서 사용자 답변])**: 훅 형태 = 편집 피드백 + 커밋 차단(D3+D4). 자동 수정 없음(알리기만).
- **D8 깊은 검토(DOR, Fable 5.1) 반영 — 같은 PR에서 닫는 문서 결함 3건**: ① `docs/BE/python-style.md` "롤백 순서"와 `ci.yml` 롤백 주석이 "lint 잡에 `if: false`"를 1단계로 적었는데 계약 테스트가 잡 `if:`를 금지해 그대로 하면 Test suite 잡이 빨개진다 → 롤백 = lint 잡 제거(또는 `if: false`)와 `tests/core/test_lint_gate_contract.py`의 CI 단언 함수 삭제를 **한 커밋**으로, `[tool.ruff]`를 되돌릴 때는 설정 단언 함수도 같은 커밋에서 삭제; 머지 뒤 전체 롤백은 `git revert -m 1 <머지 SHA>`가 모순 없는 유일한 단일 경로. ② `docs/deploy-runbook.md` §7에 "main 직접 커밋도 ruff 두 명령을 통과해야 하며(커밋 훅이 로컬에서 막는다), main CI가 lint로 실패하면 `deploy-pr.yml`의 `conclusion == 'success'` 조건으로 deploy PR이 자동 생성되지 않는다" 추가. ③ python-style.md "blame 사용법"에 "SHA는 PR을 merge commit으로 머지할 때만 main 이력에 남는다(squash·rebase 금지). 머지 뒤 `git merge-base --is-ancestor b6dd5035 origin/main`로 확인" 추가.
- **D9 깊은 검토(DAR, Fable 5.1) 반영 — 기존 사각지대 1건, 테스트 전용 소규모라 같은 PR에서 닫는다**: `tests/core/test_architecture_boundaries.py`의 기본 스캐너 `_parse_imported_module_names`가 `from pkg import submodule`을 `pkg`로만 기록해 하위 모듈 금지 집합(`drafts.discovery_runs`·`drafts.candidate_validation`·`core.llm`)을 모듈만 임포트 형태로 우회할 수 있다(현재 코드에 그 형태 0건 [코드 DAR rg]). TR-23 전용 스캐너(`f"{node.module}.{alias.name}"` 추가)와 같은 방식으로 기본 스캐너를 확장하고, 전용 스캐너의 형태 탐지 테스트를 기본 스캐너용으로 복제한다. Red 증거 = 합성 소스 문자열로 `from drafts import discovery_runs`가 `drafts.discovery_runs`로 기록되는지 단언(확장 전 실패).

## Test List / 검증 절차
- HK-1 `python-style-guard.sh` 페이로드: 차단 — 미사용 임포트, 상대 임포트, 101칸 줄, 포맷 어긋남(작은따옴표), 가변 기본 인자, 정렬 어긋난 임포트 / 허용 — 깨끗한 `.py`, `tests/` 101칸 줄, `migrations/` 파일, `.md` 파일, 저장소 밖 `.py`, git-ignored `.docs/x.py`, JSON 파싱 불가.
- HK-2 `git-commit-style-guard.sh` 페이로드: 차단 — 스테이지된 위반 `.py`로 `git commit -m`, `git commit -F`, `cd x && git commit`, `-q` 옵션, 위반 2파일 중 1파일만 위반, 포맷만 어긋남 / 허용 — 스테이지 0개, 깨끗한 파일만, `git commit`이 아닌 `git log`, 스테이지된 `.md`만, `migrations/`만 스테이지, JSON 파싱 불가.
- HK-3 라이브: 워커가 위반 `.py`를 Edit → 훅 피드백이 워커 보고에 나타난다. 오케스트레이터가 위반 파일을 스테이지하고 `git commit` → 차단 메시지 [실측]. 그 뒤 원복.
- HK-4 회귀: 전체 `uv run pytest -q`, `ruff check .`·`ruff format --check .` 0.

## AC
- AC1 `docs/BE/python-conventions.md`가 규칙 정본이고 `AGENTS.md`·`CLAUDE.md`·어댑터 3개·`docs/BE/python-style.md`가 그 문서를 가리킨다.
- AC2 훅 2개가 settings.json에 등록되고 HK-1·HK-2 전 케이스가 기대대로, HK-3 라이브 위반이 실제로 피드백·차단된다.
- AC3 `CLAUDE.md` 200줄 미만 유지(현재 182줄 [실측 wc]).
- AC4 `# noqa: F401` 재노출 0곳(남는 noqa는 시그널 부수효과 3곳과 와일드카드 1곳뿐).

## Evidence (2026-10-30, 브랜치 `style/track-48-google-python-style`, HEAD `cc5d8036`)
- 깊은 검토(Fable 5.1, 사용자 지시 "fable5.1 깊은 검토"): QVL "Complete with gaps, High 없음", DAR "결함 없음", DOR "배포 블로커 없음". 반영 내역은 D8·D9와 아래.
- QVL 증거 공백 해소: (G-1) 9d227ae2의 약화 주입 14종 = `lint.ignore` 추가·`per-file-ignores` 확대·`extend-exclude` 확대·`[tool.ruff.format]` 추가·하위 `ruff.toml`·하위 `pyproject.toml [tool.ruff]`·`|| true`·`--exit-zero`·잡 `if: false`·단계 `if:`·`pull_request` 삭제·`ruff check drafts` 범위 축소·`format --check` 제거·`continue-on-error` [실측 scratchpad `mutate_lint_gate.py`]. 86610c6a 추가 변이 3종(`paths-ignore` 추가·`branches-ignore` 확대·lint `needs:`) 전부 종료 코드 1 [실측]. (G-2) 최종 회귀는 HEAD `cc5d8036` 직전 작업 트리(커밋 5개 내용 전부 포함)에서 4300 passed / 10 deselected / 136.58초 [실측 `uv run pytest -q`], 테스트 ID 4300개(4299 + 스캐너 테스트 1) [실측 `--collect-only`]. (G-4) 분할된 gettext msgid는 `xgettext`가 한 문자열로 인식(일치 1건) [실측]. (G-5) 이 PR 커밋은 17개(7 + 45a14f82 + 후속 4 + 48-2 5) [실측 `git log`].
- QVL Low 4건 전부 같은 PR에서 해소(67e5a925·0a577a17): noqa 사유 2곳, 람다 3곳, `GoodsMigrationBlockedError`(파일 밖 참조 0건 [실측 rg]), `RunnerTokenThrottle`. 재노출 전수 AST 검사(모든 `from X import Y`의 Y가 X에 정의되는지)에서 1건 더 발견 — `STAFF_ACTION_LOG_PAGE_SIZE`(`staff/views/__init__.py`만 정의 모듈로; 뷰 계층 테스트 파일은 경계 가드 `test_api_view_계층_테스트_파일은_...`가 queries 직접 임포트를 금지하므로 뷰 모듈 경유 유지 — 컨벤션 문서에 구분 명시).
- D9 스캐너: 확장 3줄 제거 상태에서 `AssertionError: assert 'drafts.discovery_runs' in {'drafts'}` Red → 복원 Green [실측]. 확장이 기존 경계 가드 64건에 새 위반을 만들지 않음 [실측 전체 회귀].
- HK-1·HK-2 페이로드 32건(차단 16·허용 16) 전부 기대와 일치, 시작·종료 `git status --porcelain` 동일 [실측 `hook_cases.py` 오케스트레이터 재실행]. 라이브: (1) 위반 `.py`를 Write 도구로 만들자 PostToolUse 훅이 F401 2건·B006·포맷 차이를 즉시 피드백 [실측 — 실행 중 세션에 바로 적용됨]; (2) 파일이 미리 있는 상태에서 `git add x.py && git commit`을 한 명령으로 보내자 PreToolUse 훅이 차단 [실측]. **라이브가 잡은 결함 1건**: 첫 버전은 `git diff --cached`만 봐서 같은 명령의 `git add` 경로를 놓쳐 통과시켰다(탐침 커밋 1건 생성 → `git reset --soft`로 제거) → 같은 명령의 `git add`·`git commit <경로>` 인자를 합집합으로 검사하도록 수정. **본질적 공백 1건**: 같은 명령에서 파일을 만들고 커밋하면 PreToolUse 시점에 파일이 없어 검사에서 빠진다(훅 머리 주석·AGENTS.md 훅 표에 기재, 고치지 않음).
- 문서: `docs/BE/python-conventions.md` 10개 절, CLAUDE.md 184줄 [실측 wc], 어댑터 3개에 참조 문장, AGENTS.md 스타일 절은 포인터. `E731`은 `E7`에 포함돼 도구가 잡는 것으로 확인(`f = lambda x: x`에 보고) [실측 ruff 0.15.22].
- 최종 확인: `ruff check .` 0, `ruff format --check .` 458개 파일 정상, `manage.py check` 0, `settings.json` JSON 유효 [실측]. 커밋 5개 = `0a577a17`·`67e5a925`·`86610c6a`·`2ba1ca6e`·`cc5d8036`, 푸시 완료, PR #405 본문 갱신(REST PATCH).
- **머지(2026-10-30T12:21Z, 사용자 "머지승인")**: `gh pr merge 405 --merge` → main `ef31e650`(merge commit). `b6dd5035`·`9debe14c`가 main 조상 [실측 `git merge-base --is-ancestor`]. PR 규모 440개 파일 +5,708/−3,201줄, 커밋 17개 [실측 `git diff --shortstat 02d3b2ab..ef31e650`]. `docs/pr-log.md` 롤링(#405 상세, #403·#404·#399 한 줄, 200줄 유지, 머지 PR 398건 [실측 gh]) → main `e274bd61` 직접 커밋·푸시(후속 PR 금지 규약). main CI·deploy PR 갱신 결과는 아래 줄에.
- main CI: 머지 커밋 `ef31e650`의 실행은 pr-log 푸시가 바로 뒤따라 `concurrency` 취소됐고, 같은 내용을 담은 `e274bd61` 실행이 success [실측 `gh run list`]. Deploy PR 워크플로 success → 열린 deploy PR #402(main → production)에 반영(머지는 사용자 결정). 백로그 기준일 줄을 `e274bd61`로 갱신해 main 직접 커밋. 트랙 48·48-2 종결.

---

