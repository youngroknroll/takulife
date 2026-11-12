# 트랙 46·47: README 재작성 뒤 남은 개선 항목 전부 처리 [v1 — 사용자 지시 2026-10-28 "커밋 하고 남은 개선사항들을 무조건 다 끝내는 방향으로 작업 시작" [문서 사용자 지시]]

> **기준선**: main `8901c96d`(README 재작성 커밋), 전체 회귀 4284 passed / 10 deselected / 149.07초 [실측 2026-10-28 `uv run pytest -q --durations=40`], e2e 10건 미재실행. 트랙 46은 배포·설정 변경, 트랙 47은 테스트 인프라 — PR 2개(브랜치 `ops/track-46-residuals`, `test/track-47-test-infra`).
> **보류 해제 근거**: launchd 자동 시작(이 파일 트랙 39 "제외" 절 "재제안 금지")과 백업 리허설(메모리 infra-actions-lowest-priority T6)은 기록된 보류였으나, 사용자가 2026-10-28에 README 보고의 "남은 개선 사항" 목록(G2·실행시간·멀티워커 실측·백업 리허설·SMTP·러너 정기 실행·web/views 가드)을 지목해 전부 끝내라고 지시했으므로 이 지시를 해제 근거로 삼는다. SMTP는 외부 계정이 필요해 여전히 착수 불가(backlog "착수하지 않는 것").
> **Activated Roles**: DOR(운영 검토 완료 2026-10-28), TDD 코치(Test List 완료 2026-10-28), Backend & Integration Engineer(구현), QVL(완료 평가), SRR(러너 토큰 상속·launchd 위험 — 사후 검토 1회). **Not Activated**: PSO(제품 결정 없음), DAR(의존 방향 변경 없음 — web/views 가드는 기존 문서 규칙의 자동화), WED·BIR·FIE(프론트 변경 없음), AAA(LLM 설계 변경 없음).

## 트랙 46 범위 (배포·운영 잔여)
1. **G2 gunicorn 워커 타임아웃** — `docker/entrypoint.sh` `exec gunicorn` 논리행에 `--timeout "${GUNICORN_TIMEOUT:-120}"` 추가(기본 120초, DOR 결정). `--keep-alive`는 sync 워커가 무시하고 `--graceful-timeout`은 바꿀 데이터가 없어 넣지 않는다 [코드 gunicorn/config.py]. `0`은 타임아웃 해제라 금지. 문서: `.env.example` 행, `docs/deploy-runbook.md` §1 env 표(`GUNICORN_TIMEOUT`·`WEB_CONCURRENCY`), `docs/operations-runbook.md` §8(328·345·352행 부근 "`--timeout` 없음" 문구), `docs/backlog.md` G2·J4, `docs/BE/security-review-2026-09-27.md` 313·340행 부근. 최악 경로 재계산 [계산 python3 2026-10-28]: `fetch_html` 1회 상한 40초(리다이렉트 4홉 × connect 5초 + read 5초), 「지금 수집」 소스 3개 정상 응답 128초 / 소스 1개 42초, 러너 후보 제출 동일 호스트 960초 — 120초는 정상 응답 경로를 덮고 병적 경로는 Deferred(총 소요 데드라인).
2. **멀티워커 rate limit 공유 실측** — 코드 변경 없음. 스크래치 DB `taku_ratelimit_smoke`, `uv run gunicorn config.wsgi:application --workers 3 --access-logformat '%(p)s …'`로 DRF `discovery_runner` 60/minute(`POST /api/discovery/runner/heartbeat/`)에 순차 62회 → 61·62번째가 429이고 첫 429를 낸 워커 PID가 앞 60건을 전부 처리하지 않았으면 공유 판정. 보조: allauth `signup` 5/m/ip 7회. 기록: `docs/deploy-runbook.md` §3-9 "로컬 실측" 블록·§6 표 갱신(프로덕션 통합 환경은 미검증으로 유지).
3. **로컬 러너 launchd 자동 시작** — `local_runner/launchd/kr.takulife.runner.plist`(템플릿, `KeepAlive.SuccessfulExit=false`, `ThrottleInterval=60`, `ExitTimeOut=40`, 토큰은 plist에 넣지 않음)와 `local_runner/launchd/run-runner.sh`(env 파일 존재·권한 600·`claude`/`uv` 존재 확인, 없으면 `exit 0`), 런북 §8.x "launchd 자동 시작" 소절. **설치(`launchctl bootstrap`)는 사용자 액션** — 이 Mac에 `~/.takulife-runner.env`가 없고 `~/Library/LaunchAgents`에 taku 항목이 없다 [실측 ls 2026-10-28]. 같은 유형 소규모 결함(사용자 2026-08-25 지시): `claude` 부재 시 `subprocess.run`의 `FileNotFoundError`가 `AdapterOutputError`로 변환되지 않아 러너 프로세스가 죽는다 [코드 local_runner/claude_code_adapter.py:185-194] → Red-Green 1건.
4. **백업 복구 로컬 리허설** — 로컬 PostgreSQL의 개발 DB를 `pg_dump -Fc` → 새 DB `taku_restore_rehearsal`에 `pg_restore` → 테이블별 행 수 diff 0건 → 복원 DB로 `manage.py check`·`migrate --check` 통과. `docs/deploy-runbook.md` §4 표에 "로컬 리허설" 행과 "운영 리허설 미실시" 행을 구분해 기록(게이트 2 미충족 명시). 덤프·복원 DB는 끝나면 삭제.
- 제외: SMTP(외부 계정), 정기 수집 스케줄러(Render Cron은 유료 — 비용 정책), `Crawl-delay` 상한·후보 루프 시간 예산(정중함 계약을 바꾸는 제품 결정, Deferred 트리거: 프로덕션 `WORKER TIMEOUT` 로그 관측), 러너 로그 회전, `claude` 자식 프로세스 토큰 비상속(SRR 이관).

## 트랙 47 범위 (테스트 인프라)
1. **web/views 서브모듈 단방향 가드** — 새 파일 `tests/core/test_web_views_package_boundaries.py`(기존 `test_architecture_boundaries.py`는 937줄 [실측 rg 2026-10-28]로 800줄 상한 초과). 상대 임포트를 `web.views.<형제>`로 해석하는 전용 해석기(기존 `_package_name_for_file`은 최상위 패키지명만 돌려줘 중첩 패키지에서 `web.archive`로 오해석 [코드 tests/core/test_architecture_boundaries.py:780-785]). 문서: `docs/BE/web-views-package.md` Guardrail 3번을 "강제"로, `docs/BE/contract-guards.md`에 새 가드 절.
2. **테스트 실행시간 2차** — 측정 결과 단일 병목 없음(최장 테스트 2.07초, 픽스처 셋업 합계 1,129건 기준 약 2초 [실측 2026-10-28 스크래치 플러그인]). `uv run --with pytest-xdist pytest -q -n 4` → 4284 passed / 53.87초 [실측 2026-10-28, 8코어]. **pytest-xdist 추가는 AGENTS.md 패키지 정책상 사용자 명시 승인 필요 → 이 트랙에서는 측정 기록만** `docs/BE/test-suite-speed.md`에 남기고 승인 질문을 보고에 싣는다.

## Test List
| ID | 행위 | 경계 | 테스트 이름 | 상태 |
|---|---|---|---|---|
| G2-1 | `exec gunicorn` 논리행에 `--timeout "${GUNICORN_TIMEOUT:-120}"`가 있고 기본값이 120초 [코드 docker/entrypoint.sh] | contract | `tests/core/test_entrypoint_contract.py::test_컨테이너_기동_명령은_GUNICORN_TIMEOUT_환경변수와_문서화된_기본_타임아웃으로_워커_타임아웃을_정한다` | Green(PR #403, 뮤테이션 3종 Red [실측 2026-10-28]) |
| RUN-1 | `claude` 실행 파일이 없으면 어댑터가 `AdapterOutputError`를 던진다 | unit | `tests/local_runner/test_claude_code_adapter.py::test_claude_실행_파일이_없으면_어댑터_출력_오류로_변환된다` | Green(PR #403) |
| RUN-2 | `_run_once`가 어댑터 오류를 받으면 경고 로그 1건을 남기고 실패 보고를 보낸다 | unit | `tests/local_runner/test_runner_loop.py::test_탐색_에이전트_실행이_어댑터_출력_오류로_실패하면_경고_로그를_남기고_실패_보고를_보낸다` | Green(PR #403, Red = caplog 0건 [실측 2026-10-29]) |
| WVG-3 | 형제 뷰 임포트 6형태(상대 from 모듈 / 상대 from 점만 / 상위 상대 / 절대 from 모듈 / 절대 import / 절대 from 패키지 별칭)를 해석기가 탐지 | contract | `test_형제_임포트_스캐너는_형제_뷰_모듈_임포트_형태를_모두_탐지한다`(parametrize) | Pending(진짜 Red) |
| WVG-5 | 동명 도메인 앱 `archive.*` 임포트를 형제로 오탐하지 않음 | contract | `test_형제_임포트_스캐너는_같은_이름의_도메인_앱_임포트를_형제로_오탐하지_않는다` | Pending(즉시 Green → 뮤테이션) |
| WVG-4 | 실제 `archive.py`의 `collection`·`_helpers` 임포트가 해석기에 보임(공허 통과 방지) | contract | `test_실제_아카이브_뷰_모듈의_컬렉션_단방향_임포트가_스캐너에_보인다` | Pending(즉시 Green → 뮤테이션) |
| WVG-2 | `collection.py`는 `archive.py`를 임포트하지 않음 | contract | `test_컬렉션_뷰_모듈은_아카이브_뷰_모듈을_임포트하지_않는다` | Pending(즉시 Green → 주입 뮤테이션 2형태) |
| WVG-1 | `_helpers.py`는 형제를 임포트하지 않는 리프 | contract | `test_뷰_공용_헬퍼_모듈은_형제_뷰_모듈을_임포트하지_않는다` | Pending(즉시 Green → 주입 뮤테이션) |
| G2-2 | `.env.example` 행 핀 | — | 없음(문서 검증 `rg -n GUNICORN_TIMEOUT docker docs .env.example`) | Deferred |
| WVG-6 | 패키지 퍼사드 임포트 `from web.views import <뷰>` | contract | 미정 | Deferred(실사례 0건 [실측 rg]) |

## 수용 기준·검증
- AC1 G2-1 Red 메시지 기록 → Green → 뮤테이션 3종(기본값 변경·env 이름 변경·주석화) 전부 Red → 원복, `sh -n docker/entrypoint.sh` 통과, `GUNICORN_TIMEOUT=77`과 미설정에서 gunicorn `--print-config`(지원 시) 값 확인 [실측 예정].
- AC2 멀티워커 실측 표(엔드포인트·요청 수·첫 429 번호·PID별 처리 건수·판정) 런북 기입 [실측 예정]; 앞 60건에 PID 2개 이상이어야 유효.
- AC3 `plutil -lint` 통과, `sh -n run-runner.sh` 통과, `uv run pytest -q tests/local_runner` 통과, RUN-1 Red→Green.
- AC4 로컬 리허설 행 수 diff 0건, `migrate --check` 종료 코드 0 [실측 예정].
- AC5 WVG 전 시나리오 Green + 즉시-Green 4건의 뮤테이션 Red 증거(종료 코드 판정), `git diff --stat -- web/` 비어 있음.
- AC6 각 트랙 전체 회귀 `uv run pytest -q` 통과, `manage.py check` 0건, `makemigrations --check` 변경 없음; README "알려진 한계" 목록 갱신.

## 이연
- 수집 총 소요 데드라인·`Crawl-delay` 상한 — 트리거: 프로덕션 gunicorn 로그 `WORKER TIMEOUT (pid:` 관측.
- 운영 Supabase 복구 리허설·R2 복구 — 자격 증명 필요(사용자).
- pytest-xdist 도입 — 사용자 승인 대기(측정 53.87초 [실측 2026-10-28]).
- WVG-6, 허용 목록(기본 거부) 방식 형제 방향표.

## Evidence (2026-10-28)
- AC1 G2-1: Red `assert None is not None`(선행 단언 통과) → Green → 뮤테이션 3종(기본값 90으로 변경 / env 이름 `GUNICORN_TIMEOUTS` / `--timeout` 줄 주석화) 전부 종료 코드 1 → 원복 종료 코드 0, `git diff --stat docker/entrypoint.sh` 4 insertions·1 deletion [실측 2026-10-28]. `sh -n docker/entrypoint.sh` 통과.
- RUN-1: Red `FileNotFoundError: [Errno 2] No such file or directory: 'claude'` 전파 → Green. `tests/core/test_entrypoint_contract.py tests/local_runner tests/core/test_test_settings_boundary.py` 250 passed / 2.18초 [실측].
- AC2 멀티워커(gunicorn 26.0.0 `--workers 3`, 로컬 PostgreSQL 14.19, 스크래치 DB): DRF `discovery_runner` 62회 순차(22:03:28~22:03:32 KST) → 1~60번 204, 61·62번 429, 1~60번 PID별 15/22/23건, 첫 429 PID는 22건 처리 → 공유 판정 [실측]. 대조군 `LocMemCache`: 62회 전부 204, PID별 12/25/25 [실측] → 시험의 판별력 확인. allauth `signup` POST 7회: 1~3번 200, 4~7번 429, 통과 3건은 PID 28162, 429 중 3건은 다른 PID [실측] — 한도 5 대비 4번째 제한 이유 미확인.
- AC3 `plutil -lint` OK, `sh -n run-runner.sh` 통과 [실측]. launchd 실설치는 미검증(이 Mac에 env 파일 없음).
- AC4 백업 로컬 리허설: pg_dump/psql 14.19, 덤프 243,865바이트, 테이블 40개·행 1,452건 diff 0건, `check` 0 issues, `migrate --check` 종료 코드 0, `django_cache` 54행 포함 [실측 2026-10-28]. 스크래치 DB 2개·덤프 삭제 완료.
- AC1 추가: gunicorn `--print-config`로 `GUNICORN_TIMEOUT=77` → `timeout = 77`, 미설정 → 120, 빈 값 → 120 [실측 2026-10-29].
- 검토 반영(QVL D1~D8, SRR M1·L2): stale 문서 3곳(architecture-overview·error-groups·security-review :324) 정정, 128초 계산식·120초 유지 결정·fetch 데드라인/Crawl-delay 상한 이연(SRR Medium) 백로그 기입, 런북 §8.y에 uv SIGTERM 전달 미검증·크래시 루프 조건·로그 무회전·토큰 상속 한계 추가, §4 pg_dump 버전 주의. RUN-2(신규): `_run_once`가 `AdapterOutputError`를 받으면 경고 로그 1건 + 실패 보고 — `tests/local_runner/test_runner_loop.py::test_탐색_에이전트_실행이_어댑터_출력_오류로_실패하면_경고_로그를_남기고_실패_보고를_보낸다`. "다른 두 워커"(D6)는 액세스 로그 429 PID 28146·28135·28146·28162로 확인 [실측 2026-10-28].
- 트랙 47 AC5 [실측 2026-10-29]: `tests/core/test_web_views_package_boundaries.py` 스텁 단계 6케이스 전부 Red(`assert 'archive' in set()`) → 해석기 구현 후 10 passed. 뮤테이션(종료 코드 판정): `collection.py` `if False:` 상대 주입 → WVG-2 Red(기존 `test_architecture_boundaries.py`는 Green 유지 = 기존 파서 미탐지 확인), 절대 `import web.views.archive` 주입 → Red, `_helpers.py` 형제 주입 → WVG-1 Red, 해석기 첫 세그먼트 `archive` 오탐 뮤테이션 → WVG-5 Red, 해석기 `return set()` → WVG-3·WVG-4 Red, 전부 원복 후 10 passed·`git diff -- web/` 0줄.
- 트랙 47 실행시간: 측정 기록·xdist 결정 항목을 `docs/BE/test-suite-speed.md` §7·`docs/backlog.md` K1에 기입(코드 변경 없음, 사용자 승인 대기).
- AC6 전체 회귀(트랙 46 브랜치, 문서 통합 후): `manage.py check` 0 issues, `makemigrations --check --dry-run` 변경 없음, `uv run pytest -q` 4286 passed / 10 deselected / 152.38초 [실측 2026-10-28 23시대 KST].

---

