# 트랙 49: pytest-xdist 도입(백로그 K1) + 러너 launchd 설치·래퍼 PATH 결함 수정 [v1 — 사용자 지시 2026-10-30 "새로운 세션에서 2번 진행 요망" → 이 세션 "2번진(행)" [문서 사용자 지시]. 2번 = 백로그 K1 xdist 도입 + 런북 §8.y launchd 설치(메모리 residuals-track-46-47 정본)]

> **기준선** [실측 2026-10-30, main `73900041`]: 직렬 `uv run pytest -q` 4300 passed / 10 deselected / 134.77초(8코어 Mac, 로컬 PostgreSQL 14.19). `uv.lock`에 xdist 없음 `[실측 rg]`. 로컬 DB 역할 `taku`는 `rolcreatedb=t` `[실측 dbshell]`(워커별 테스트 DB 생성 가능). `~/.takulife-runner.env` 없음, `~/Library/LaunchAgents`에 taku 항목 없음, `claude`는 `~/.nvm/versions/node/v22.14.0/bin/claude`(네이티브 arm64 실행 파일, nvm 경로)이고 래퍼 `run-runner.sh`의 고정 PATH(`~/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin`)에는 그 경로가 없다 `[실측 which/file/ls]` → 현재 템플릿으로 설치하면 래퍼가 "claude 실행 파일을 PATH에서 찾지 못해 시작하지 않는다"로 종료 코드 0으로 끝나 러너가 영구히 뜨지 않는다(결함). `uv run … python`은 SIGTERM을 자식 파이썬에 전달하고 종료 코드 0으로 끝난다 `[실측 2026-10-30 scratchpad sigterm_probe.py]` → 런북 §8.y "미검증" 1건 해소.
> **사용자 명시 승인(패키지 정책)**: `AGENTS.md` "Package And Command Policy"는 새 test-convenience 패키지에 승인된 계획과 사용자 명시 승인을 요구한다. 백로그 K1은 "트리거: 사용자 승인"으로 대기 중이었고, 사용자가 2026-10-30 "2번 진행"으로 K1 착수를 지시했다 — 이를 xdist 도입의 명시 승인으로 기록한다 [문서 사용자 지시]. 계획서는 이 문서(승인된 계획).
> **Activated Roles**: DOR(의존성·CI 잡·launchd 운영), Backend TDD Coach(테스트 대상 유무 판정 — 설정·CI 텍스트 변경과 셸 래퍼라 pytest 대상 테스트가 없다는 판정 확인), Backend & Integration Engineer(구현), QVL(AC↔증거). **Not Activated**: PSO(제품 결정 없음), DAR(도메인 경계 무변경), SRR(토큰 파일·권한 600 규약은 기존 그대로, 새 노출 경로 없음 — 래퍼가 env 파일을 PATH 설정보다 먼저 읽는 순서 변경만), 프런트 역할·AAA.

## 결정
- **D1 의존성**: `uv add --group dev pytest-xdist` — `pyproject.toml` dev 그룹 + `uv.lock`을 같은 커밋에. 상한은 기존 패턴대로 다음 메이저 미만(`>=3.8,<4.0`).
- **D2 `-n` 위치 = CI 잡과 전체 회귀 명령에만, `pytest.ini` `addopts`에는 넣지 않는다.** 근거: ① Red-Green 루프의 표적 실행(`uv run pytest -q <경로>`)이 워커 기동과 워커별 테스트 DB 생성 비용을 매번 내게 된다(비용은 §Evidence에 실측 기입) ② `addopts`에 넣으면 `-m e2e tests/e2e`(live_server)도 병렬이 되어 CI e2e 잡·문서 전부에 `-n 0`을 덧붙여야 한다 ③ `tests/core/test_test_authoring_policy.py`의 `--strict-markers` 텍스트 계약과 `-m "not e2e"` 치환 규칙은 그대로 유효. 변경: `.github/workflows/ci.yml` test 잡 `run: uv run pytest -q` → `run: uv run pytest -q -n auto`; `CLAUDE.md` "Backend regression" → `uv run pytest -q -n auto`(표적 명령은 그대로). `-n auto`는 물리 코어 수(psutil 없음 → `os.cpu_count()` 폴백 `[문서 xdist configuration.md]`)이고 GitHub 호스트 러너의 워커 수는 CI 로그 머리줄 "N workers"로 확인해 Evidence에 적는다.
- **D3 격리 증거**: 병렬에서 전 테스트 통과가 테스트 간 격리의 증거다. 로컬 `-n auto` 전체 실행을 연속 3회 `[문서 D3 설계값]` 돌려 매회 passed 수가 직렬과 같음을 확인한다(플레이크 탐지). 한 번이라도 실패하면 그 테스트의 공유 상태(파일·캐시·시퀀스)를 결함으로 기록하고 같은 PR에서 고친다(이연 금지 규약).
- **D4 새 pytest 테스트 없음(코치 확인 대상)**: CI 잡의 `-n auto`는 속도 손잡이라 조용히 빠져도 정확성이 약해지지 않는다(트랙 48 린트 게이트와 다름). 셸 래퍼는 기존 훅·래퍼와 같이 pytest 대상이 아니다. 검증은 §Test List의 절차 증거.
- **D5 래퍼 결함 수정(같은 유형·소규모, 같은 PR)**: `local_runner/launchd/run-runner.sh`에서 env 파일 로드(`set -a; . "$ENV_FILE"; set +a`)를 PATH 설정 앞으로 옮기고, env 파일이 `TAKULIFE_RUNNER_PATH_PREPEND`를 주면 그 값을 PATH 맨 앞에 붙인다(`PATH="${TAKULIFE_RUNNER_PATH_PREPEND:+${TAKULIFE_RUNNER_PATH_PREPEND}:}$HOME/.local/bin:…"`). nvm 설치 `claude`처럼 기계마다 다른 경로를 템플릿에 박지 않고 기계별 설정 파일(env)에 둔다. 기존 가드(파일 존재·600·claude·uv 존재 → 종료 코드 0)는 유지. 러너 파이썬 코드는 건드리지 않는다(`claude_code_adapter.py`는 PATH 조회 `argv[0]="claude"` 그대로).
- **D6 이 Mac에 launchd 설치(사용자 지시 범위)**: 런북 §8.y 절차대로 plist 치환·`launchctl bootstrap`. env 파일이 없으므로 래퍼는 메시지 1줄 후 종료 코드 0 → `SuccessfulExit=false`라 재기동하지 않는다. 이 1회 기동으로 두 가지를 실측한다: ① `~/Desktop` 보호 폴더에서 `/bin/sh`가 저장소 스크립트를 읽을 수 있는지("Operation not permitted" 유무) ② 로그 파일 경로·`launchctl print` 상태. **토큰은 서버(Render) 비밀이라 세션이 만들 수 없다** → env 파일 작성(`TAKULIFE_SERVER_URL`·`TAKULIFE_RUNNER_TOKEN`·`TAKULIFE_RUNNER_PATH_PREPEND`)과 `launchctl kickstart`는 사용자 몫으로 런북에 그대로 적는다.
- **D7 문서**: `docs/operations-runbook.md` §8.y(선행 조건 2에 nvm 경로·PATH_PREPEND, SIGTERM 미검증 → 실측 결과, "이 Mac 현재 상태" 갱신), `docs/BE/test-suite-speed.md` §8 신설(도입 결정·`-n` 위치 근거·측정), `docs/backlog.md` K1 → 해소(트랙 49, PR 번호), `CLAUDE.md` 명령 1줄, `.github/workflows/ci.yml` 1줄. `docs/pr-log.md`는 머지 시 롤링.
- **채택하지 않는 것(결정)**: `addopts -n auto`(D2) / `--dist loadfile·loadscope`(기본 `load`로 이미 전부 통과, 바꿀 이유 없음) / `pytest-xdist`의 `--looponfail` / CI e2e 잡 병렬화 / 래퍼에 nvm 경로 하드코딩 / env 파일 자동 생성.

## Test List / 검증 절차 (정식 pytest 테스트 1건 — D4는 CI `-n auto`에만 유효, 래퍼는 코치 판정으로 T49-RW1 추가)
- **T49-RW1** `tests/core/test_run_runner_wrapper_contract.py::test_환경파일의_PATH_PREPEND_디렉터리에_있는_claude_스텁을_래퍼가_찾는다` — Given 가짜 HOME·env 파일(600, `TAKULIFE_RUNNER_PATH_PREPEND=<스텁 디렉터리>`)·스텁 `claude`/`uv` / When 래퍼를 최소 PATH(`/usr/bin:/bin`)로 subprocess 실행 / Then stdout에 `stub-uv-started` 있고 "claude 실행 파일을 PATH에서 찾지 못해" 없음, 종료 0. 경계 contract(셸 실행), DB/HTTP 없음. Status: Green(Red 사유 확인 뒤). Evidence는 §Evidence.
- V-1 `uv add --group dev pytest-xdist` 후 `git diff --stat`에 `pyproject.toml`·`uv.lock` 둘만, `uv sync --frozen` 성공, `uv run pytest --version`으로 플러그인 로드 확인(`-n` 옵션이 `--help`에 있음).
- V-2 전체 회귀 `uv run pytest -q -n auto` 연속 3회 `[문서 D3 설계값]`: passed 수 = 직렬 4300 `[실측 기준선]`, 실패 0, 각 회 실행시간 기록 [실측 기입].
- V-3 표적 실행 비용: `tests/archive/test_visit_records_api.py` 직렬 vs `-n auto` 실행시간, 단일 파일 `tests/core/test_entrypoint_contract.py` 직렬 vs `-n auto` [실측 기입] → D2 근거.
- V-4 e2e 직렬 유지: `uv run pytest -q -m e2e tests/e2e` 머리줄에 "workers" 없음(xdist 비활성), 10 passed `[실측 2026-10-27 기준]`.
- V-5 `sh -n local_runner/launchd/run-runner.sh` OK; env 파일 부재 → 메시지 1줄·종료 0; env 파일(권한 644) → 권한 메시지·종료 0; `TAKULIFE_RUNNER_PATH_PREPEND` 없이 → "claude … 찾지 못해"·종료 0; `TAKULIFE_RUNNER_PATH_PREPEND=~/.nvm/…/bin` → claude·uv 통과(exec 직전까지, 토큰 더미로 러너 `load_config`까지 가지 않도록 `TAKULIFE_RUNNER_TOKEN` 빈 값이면 러너가 `RuntimeError`로 즉시 종료 — 그 종료 코드 ≠0 확인). 시험용 env 파일은 scratchpad에 두고 `HOME`을 바꿔 실행한다(실제 `~`에 더미 토큰 파일을 만들지 않는다).
- V-6 launchd 설치: `plutil -lint` OK → `launchctl bootstrap gui/$(id -u) …` → `launchctl print gui/$(id -u)/kr.takulife.runner`의 `last exit code = 0`, `~/Library/Logs/takulife-runner.log`에 "러너 환경 파일이 없어 시작하지 않는다" 1줄, "Operation not permitted" 0줄.
- V-7 계약·회귀: `uv run ruff check .`·`ruff format --check .` 0, `tests/core/test_ci_command_policy.py`·`test_lint_gate_contract.py`·`test_ci_trigger_policy.py`·`test_test_authoring_policy.py` passed, 전체 직렬 회귀 1회 passed(병렬 전용 통과가 아님을 확인).

## AC
- AC1 `pytest-xdist`가 dev 그룹에 있고 `uv.lock`과 같은 커밋이며 CI test 잡이 `-n auto`로 돈다(CI 로그에 "N workers", N은 Evidence에 기입).
- AC2 `-n auto` 전체 회귀 연속 3회 `[문서 D3 설계값]` 모두 직렬과 같은 passed 수, 표적·e2e 명령은 직렬 그대로.
- AC3 래퍼가 env 파일의 `TAKULIFE_RUNNER_PATH_PREPEND`를 PATH 맨 앞에 반영하고 기존 가드 4개(파일·600·claude·uv) `[코드 run-runner.sh]`가 그대로 동작한다.
- AC4 이 Mac에 plist가 설치되어 `launchctl print`로 보이고, 1회 기동 로그가 V-6과 일치한다. 사용자 잔여 = env 파일 작성 + `kickstart`(런북에 명시).
- AC5 문서 D7 전부 반영, 숫자마다 단위·출처.

## 파일
`pyproject.toml`·`uv.lock` / `.github/workflows/ci.yml` / `CLAUDE.md` / `local_runner/launchd/run-runner.sh` / `docs/operations-runbook.md` / `docs/BE/test-suite-speed.md` / `docs/backlog.md`. 브랜치 `test/track-49-xdist-launchd`, PR 1개. 경계: `local_runner/`는 Django·서버 모듈을 임포트하지 않는 규칙 그대로(셸만 변경). 결합·응집: 변경은 전부 설정·운영 계층이고 도메인 코드 0파일.

## 이연
없음(발견 즉시 같은 PR — D5).

## Evidence (2026-10-30, 브랜치 `test/track-49-xdist-launchd`, PR #407)
- 사전 검토: DOR "배포·CI 블로커 없음, Medium 1(런북 갱신 시 측정 전 기록 보존·재현 명령 인라인)·Low 2(SIGTERM 재현 경로, CI DB 권한은 CI 그린으로 간접 검증)" → 전부 문서 단계에 반영. TDD 코치: CI `-n auto`에는 테스트 불필요(속도 손잡이), 래퍼 수정에는 실행형 계약 테스트 1건 필요(T49-RW1, 선례 `tests/core/test_entrypoint_contract.py`) → 수용. 기존 계약 테스트 4개 파일과 충돌 없음(코치·DOR 각자 파일:줄 확인).
- V-1: `uv add --group dev "pytest-xdist>=3.8,<4.0"` → `pyproject.toml`·`uv.lock`만 변경, 커밋 `e15b57dd`; `uv sync --frozen` 성공; `uv run pytest --help`에 `-n, --numprocesses` 있음 [실측].
- 측정 [실측 2026-10-30, 8코어]: 직렬 134.77초(4300 passed) / 의존성 추가 전 `--with pytest-xdist -n auto` 42.86초·`-n 4` 49.31초 / 표적 37건 4.46초 → 6.41초 / 단일 파일 0.01초(벽시계 0.53초) → 1.39초(벽시계 2.16초) → D2 확정.
- V-2: 도입 후 `uv run pytest -q -n auto` 4회 중 첫 회만 1 failed(= Green 전이던 새 래퍼 계약 테스트, 격리 결함 아님), 이후 3회 연속 4301 passed / 41.72·43.57·44.14초 [실측].
- V-4: `-m e2e tests/e2e` 10 passed / 11.09초, xdist 머리줄 없음(직렬) [실측].
- T49-RW1 Red: `AssertionError: assert 'stub-uv-started' in 'claude 실행 파일을 PATH에서 찾지 못해 시작하지 않는다\n'`(기대한 이유) → D5 구현 → Green 1 passed / 0.24초, `sh -n` OK [실측]. 커밋 `d44b60ce`(테스트+래퍼), `c686becd`(ci.yml·CLAUDE.md).
- V-5 가짜 HOME 프로브 [실측]: env 부재 → 메시지·종료 0 / 권한 644 → 메시지·종료 0 / PREPEND 없음 → "claude … 찾지 못해"·종료 0 / PREPEND=스텁 → `stub-uv-started`·종료 0 / 실제 nvm 경로+빈 토큰 → 러너 `RuntimeError: TAKULIFE_RUNNER_TOKEN environment variable is required.`·종료 코드 1.
- V-6 1차(`~/Desktop` 저장소, 계획 D6 그대로) **실패**: 로그 `shell-init: … getcwd … Operation not permitted`, `/bin/sh: …/run-runner.sh: Operation not permitted`, `last exit code = 126`, `state = spawn scheduled`(재기동 루프 진입) → 즉시 `launchctl bootout`(로그 2줄에서 멈춤) [실측]. 런북이 미검증으로 적어둔 보호 폴더 문제가 실제임을 확인. **결정(계획 변경)**: `/bin/sh` 전체 디스크 접근 부여 대신 보호 폴더 밖 전용 클론 `~/takulife-runner`(`git clone -b test/track-49-xdist-launchd`, `uv sync --frozen`, 336MB [실측 du])를 러너 실행 트리로 쓴다. 개발 트리 이동은 사용자 결정으로 남김.
- V-6 2차(클론 기준 plist) [실측]: `plutil -lint` OK, bootstrap 종료 0, `runs = 1`·`last exit code = 0`·`state = not running`, 로그 1줄 "러너 환경 파일이 없어 시작하지 않는다", "Operation not permitted" 0줄, 65초 뒤 `runs = 1` 유지(재기동 없음). AC4 충족. 사용자 잔여: env 파일(3변수, 600) 작성 + `launchctl kickstart`; 머지 뒤 클론을 `main`으로 전환.
- SIGTERM 전달 [실측 2026-10-30]: `uv run --frozen python <probe>`에 `kill -TERM <uv pid>` → 자식 핸들러 신호 15 수신·종료, 잔존 프로세스 0개, uv 종료 코드 0. 런북 §8.y 미검증 항목 해소(재현 한 줄 명령을 런북에 기입).
- CI 쪽 워커별 DB 생성 권한은 사전 dbshell 점검 불가 → PR #407 CI test 잡 통과로 간접 검증(DOR Low 반영). PR #407 첫 CI(`c686becd`, run 41070183412) 6잡 전부 pass; "Run test suite" 단계 82초(main `73900041`, run 41055310841) → 55초, test 잡 전체 116초 → 102초 [실측 gh run view 2026-10-30]. `-q`가 xdist 머리줄을 억제해 워커 수는 로그에 없음(AC1의 "N workers"는 실행시간 비교로 대체).
- V-7 [실측 2026-10-30, 문서 커밋 `7fd850c1` 뒤]: `uv run ruff check .` 0, `ruff format --check .` 459개 파일 정상, 계약 테스트 5파일 8 passed, 직렬 전체 회귀 `uv run pytest -q` 4301 passed / 10 deselected / 131.17초(병렬 전용 통과가 아님 확인). 문서 반영: 런북 §8.y(취소선 보존 3곳)·속도 문서 §1·§7·§8·백로그 K1 해소.
- QVL 최종 평가: "Complete with gaps, Failed 없음" — AC3·AC4 Complete, AC1·AC2·AC5 gaps(①AC1 "N workers" 문구 vs 실행시간 대체 → 이 줄로 재해석 기록: AC1의 의도는 "CI가 실제로 분산 실행됨"이고 `-q` 억제 때문에 82초→55초 단계 시간으로 충족 ②V-7 증거 누락 → 위 줄에 기입 완료 ③T49-RW1 Test List 행 누락 → 추가 ④**macOS 전용 skipif라 CI가 래퍼 회귀를 못 잡음** → 같은 PR에서 해소: 래퍼 `stat -f %Lp … 2>/dev/null || stat -c %a`(BSD→GNU 폴백) + skipif·`import sys` 제거, 로컬 3 passed·`sh -n` OK·ruff 0 [실측], 커밋 `38286b21` ⑤CI 수치 재확인 요청 → 오케스트레이터가 `gh run view` 직접 실측한 값임). 잔여 1건(클론 삭제 절차 부재) → 런북 해제 항목에 한 줄 추가(같은 커밋). Linux에서 테스트가 skip 아닌 실행인지는 `38286b21` CI test 잡 요약("skipped" 유무)으로 확인해 아래 줄에.
- Linux 실행 확인 [실측 gh run 41072014098]: 이전 CI(`c686becd`)는 "4300 passed, 1 skipped"였고 `38286b21`은 "1 failed, 4300 passed" — 테스트가 ubuntu에서 실제로 돌았고 **기대와 다른 이유로 Red**: `AssertionError: assert 'stub-uv-started' in '러너 환경 파일 권한이 600이 아니어서 시작하지 않는다: …'`. 원인: GNU `stat -f %Lp FILE`은 `%Lp`를 파일로 보고 exit 1을 내면서도 FILE의 파일시스템 정보를 stdout에 남겨, 폴백 `600`이 그 뒤에 덧붙어 `"600"`과 불일치. 수정 `37e62d69`: `stat -c %a … 2>/dev/null || stat -f %Lp …`(GNU 먼저, macOS BSD는 `-c`에서 stdout 없이 실패 → 폴백; macOS 프로브 600 [실측]). 로컬 1 passed·`sh -n` OK. `37e62d69` CI(run 41072565204) 5잡 success, test 잡 "4301 passed"(skipped 0, Linux에서 래퍼 계약 테스트 실행·통과), "Run test suite" 단계 59초 [실측 gh 2026-10-30]. **트랙 49 구현 완료.**
- **머지(2026-10-31, 사용자 "머지 승인")**: `gh pr merge 407 --merge` → main `45afc5fe`(merge commit). pr-log 롤링(#407 상세, #405 한 줄, 192줄 ≤ 200 [실측 wc])·백로그 기준일 `45afc5fe`·회귀 4301 → main `73cb7d80` 직접 커밋·푸시(후속 PR 금지 규약). 클론 `~/takulife-runner`는 main `45afc5fe`로 전환·`uv sync --frozen` 완료 [실측]. 남은 사용자 몫: env 파일 작성·`launchctl kickstart`, deploy PR #402 머지. main CI(`73cb7d80`, run 41077223620) 5잡 success; deploy PR #402 head가 `73cb7d80`으로 갱신됨(커밋 40개, OPEN) [실측 gh 2026-10-31]. **트랙 49 종결.**

---

