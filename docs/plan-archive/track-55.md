# 트랙 55: 전수 검토(2026-11-11) 결함·문서 정리 + 계획서 닫힌 트랙 보관 [v1 — 사용자 지시 2026-11-12 "이 세션에서 추천하는 작업을 하도록" + "훅 빈틈막고, 닫힌 트랙을 보관파일로 옮겨서 커밋하도록, 그에맞게 운영규약 변경" [문서 사용자 지시]. 51~54는 디자인 시스템 B~E 예약이라 55번 [문서 트랙 50 전체 구조]] · **PR #411 머지 완료(2026-11-12T11:43:49Z, merge commit `21a9e408`, 사용자 "머지승인") `[실측 gh]`**

> **기준선** [실측 2026-11-11~12, main `b89cae8c`]: `uv run pytest -q -n auto` 4301 passed, `manage.py check` 0건, 마이그레이션 드리프트 없음, ruff check·format 통과(459파일). 계획서 6,584줄·H1 절 46개 → 열린 절 6개(50·44·38·31·17·12) 911줄, 닫힌 절 40개 5,673줄 [계산 python, 절 경계 `^# `], HEAD 사본 410줄 [실측 git show]. 원본 백업 scratchpad `backup/plan-before-archive.md` SHA-256 `de519f62…` [실측 shasum]. 검토자 원문 8건 scratchpad `reports/*.md`.
> **Activated Roles**: Backend TDD Coach(훅 계약 테스트·B1·B4의 Test List와 Red 이유, B2 리팩터 허용 판정), Backend & Integration Engineer(훅·백엔드·일반 문서), WED·BIR(F1~F4 사전 명세·사후 판정), FIE(F1~F4, `docs/FE/design-principles.md`), DOR(`.claude/settings.json` 훅 timeout 단위, `.env.example`), QVL(AC↔증거). **Not Activated**: PSO(제품 범위 변경 없음, 사용자 지시 범위), DAR(소유·의존 방향 변경 없음 — B2는 `archive` 안 정리), SRR(신뢰 경계 변경 없음, 훅은 보안 경계가 아님 [문서 AGENTS.md Harness Enforcement]), AAA(LLM 무관).

## 범위
- **55-1 훅 빈틈 + 회귀 페이로드 보존**. 통과 형태 10건·오탐 1건 [실측 2026-11-11 scratchpad `recheck.py`]: git-destructive-guard `git checkout prompt_plan.md`(`--` 없음)·`git checkout HEAD <path>`·`git -C . reset --hard`, 오탐 `git clean -nd`(dry-run) / git-stage-all-guard `git add -u`·`git commit -m x prompt_plan.md`·`git -C . add -A` / plan-bash-write-guard `rm prompt_plan.md`·`perl -pi -e`·`<<<` here-string 뒤 줄의 리다이렉트 / uv-only-guard `python3 -u manage.py`. 새 계약 테스트 `tests/core/test_harness_hooks_contract.py`(훅 4개 각각 차단 6건 이상·허용 6건 이상 [문서 AGENTS.md Harness 절 "6 blocking cases and 6 allowed cases"], 선례 `tests/core/test_run_runner_wrapper_contract.py`). `.claude/settings.json` timeout 5000·15000 [코드]의 단위 확인 후 정정(DOR). AGENTS.md Harness 표 Known gaps를 고친 뒤 남는 공백으로 갱신.
- **55-2 계획서 닫힌 트랙 보관 + 운영 규약**. 닫힌 절 40개를 `docs/plan-archive/track-<id>.md`(절 1개 = 파일 1개, 원문 그대로)로 옮기고 계획서에는 이 트랙과 열린 절 6개만 남긴다. 1회 이동은 scratchpad 스크립트로 한다: Edit 도구로 5,673줄 [계산]을 옮기는 것은 불가능하고, 사용자 지시가 계획서 재작성을 배정했다(CLAUDE.md "unless assigned"). 검증 = 남은 계획서 + 보관 파일 재조립이 백업과 줄 단위 diff 0. 규약(사용자 결정 2026-11-12): 트랙 머지 뒤 그 절을 보관 파일로 옮겨 main 직접 커밋(pr-log 롤링과 같은 시점), 이후 이동은 Edit(잘라내기)+Write(새 파일). 보관 파일은 고정 이력(수정 금지, 상태의 정본은 backlog·pr-log). 반영 위치: AGENTS.md Operating Workflow 8·Orchestrator Contract 5(보류 검색에 보관 폴더 포함)·Harness 절·Commit And PR Cadence, CLAUDE.md Instruction Placement, docs 안 `prompt_plan.md 트랙 N` 참조, 메모리 `docs-commit-policy`.
- **55-3 프론트 4건** [코드 2026-11-11 재확인]: F1 `templates/core/partials/_archive_results_visits.html:90-94` 빈 상태 행동 링크 없음(형제 `_archive_results_record.html:97`) / F2 오류 문단 `aria-live` 누락 4곳 `personal_create.html:119`·`personal_edit.html:114`·`collection_create.html:147`·`collection_edit.html:140`(선례 `visit_create.html:96`) / F3 `static/js/pages/visit.js:44` 대응 폼 없는 죽은 코드 / F4 `static/js/staff/draft_bulk.js:495-546` 인스펙터 개별 승인·반려 뒤 `updateToolbarState()` 미호출.
- **55-4 백엔드** [코드]: B1 `archive/services.py` `mark_visited`·`mark_missed`·`revert_to_planned`가 잠금 재조회 없이 메모리 직전 상태를 기록(같은 파일 `update_collection_item`은 `select_for_update` 재조회) / B2 `archive/serializers.py:169-188`이 `_SubjectScopedPersonalEntryMixin`(76-93행) 복제 / B3 `tests/drafts/test_drafts_queries.py:688`·`tests/core/test_system_error_summary.py:119` 쿼리 수 계약에 `contract` 마커 없음 / B4 `staff/search.py` 100자 절단 테스트 0건 / B5 없는 테스트 이름 주석 2곳(`tests/archive/test_archive_services.py:860`·`tests/archive/test_collection_items_api.py:483`) / B6 `.env.example` 누락 4개(`GOOGLE_SITE_VERIFICATION`·`GA_MEASUREMENT_ID`·`PORT`·`WEB_CONCURRENCY`).
- **55-5 문서** (검토자 지적은 워커가 쓰기 전 재측정 [메모리 docs-audit-2026-10-27 ③]): G 거버넌스 — 같은 트랙 소규모 결함 규칙을 AGENTS.md로(현재 CLAUDE.md:144-149에만), AGENTS.md:34 정본 순환, 78-79행 링크 없는 "linked proposal", 어댑터에만 있는 규칙 3개(단일 실행자·한국어 보고·비유 금지, AGENTS.md 0건 [실측 rg]), 머지 뒤 수정 main 직접 커밋 허용, `docs/FE/design-principles.md` 참조(3곳 0건 [실측 rg])와 969-983행 mock 문구, Test List 경계의 e2e, CI e2e 잡 / S 상태 문서 — README:113 xdist·경계 테스트 수(재측정), backlog 기준선 충돌(3행 4301·25행 4284 [문서])·#410·51행 "차이 0커밋", pr-log #410 롤링 / T 기술 기록 — python-style.md↔python-conventions.md 정본 충돌, test-suite-speed.md §6·66행, design-principles.md(#408 OPEN·줄 기준·`.empty-icon` 1개→9개 [실측 rg -l]), 줄 인용 드리프트(검토자 34건 [문서 techdocs-review]), draft-source-agent-discovery.md:5, i18n.md 배포 대기 문구, contract-guards.md 누락 가드. 열린 절 6개 [문서 위 기준선] 머리말 상태 문구 갱신(Edit).
- **55-3 추가(트랙 중 발견, 같은 유형 — 보고 후 같은 트랙에서 수정)**: F2 대상에 promote 오류 문단 2곳 [코드] 추가(`_archive_results_personal.html:122`·`personal_detail.html:121`, WED 발견) — 총 6곳 [코드] / F5 `draft_bulk.js` 검토 대기 탭 개별 판정 성공 시 결과 공지 누락 + `showEmptyState` 포커스·텍스트 순서(BIR 발견) / F6 `archive_search.js` 기록이 아예 없는 계정의 검색 live 문구가 화면 빈 상태 제목과 다름 / F7 `collection.js` 이름 미입력 오류 때 포커스 미이동(F6·F7은 WED·BIR 사후 판정에서 발견). 제외: collection `.form-status` 2곳 [코드](채우는 JS 0건 — 결함 아님), 활동 달력 날짜 빈 상태(결함 아님), 교환 수량 분기 포커스(다른 종류), 다른 행 요청 역순 완료 경합(기존 설계 잔존 위험). F5b 일괄 경로 공지: WED "무음" ↔ BIR "그대로" 충돌 → **그대로**(오케스트레이터 결정: 마지막 건 문장은 사실이고 공식 요약은 포커스 받는 `#bulk-approve-result`, 1건 일괄은 개선, 공유 함수에 무음 분기를 만들지 않음).
- **55-1 추가(같은 유형)**: `git -C . rm`·stage-all here-string 오인(훅 워커 발견), uv-only `python3.13`·`./manage.py`·`env`/`time` 접두(거버넌스 워커 발견). 남김: `git-commit-style-guard` 전역 옵션 미인식(ruff·인덱스 시험 기반이 필요해 트랙 규모 초과 — Known gaps 기록).
- **55-6 Gunicorn 접근 로그(사용자 지시 2026-11-12)**: `docker/entrypoint.sh`에 `--access-logfile -`·`--access-logformat '%(h)s %(t)s "%(m)s %(U)s" %(s)s %(b)s "%(a)s"'`. 계약 테스트 선례 `tests/core/test_entrypoint_contract.py:37`. `%(U)s`는 쿼리 문자열을 빼 검색어 등이 로그에 남지 않는다.

## 제외
훅을 보안 경계로 만드는 일(문자열 조합·`bash -c`·변수 치환은 수용된 공백) / 기록된 보류(F10 MFA·IP 보조 스로틀·백로그 F18 스태프 CSRF) / 운영 사용자 몫(백업 자동화·스케줄러 등록·`TRUSTED_PROXY_COUNT` 실측·운영 `EmailAddress` 감사) / Actions SHA 고정·베이스 이미지 digest(사용자 결정) / 디자인 트랙 51~54 / 상한 근접 파일 분할(가장 큰 `archive/services.py` 748줄 [실측 wc -l], 상한 800줄 [문서 coding-style]) / 과거 커밋 제목 길이 / 보관 파일 내용 정정.

## Domain Boundary / Coupling / Pythonic
의존 방향 변경 0건: B1·B2는 `archive` 안, B4는 `staff` 안, 훅 테스트는 `tests/core`에서 subprocess로만 실행(앱 임포트 없음). B2는 상속으로 중복 제거, 새 추상화 없음. B1은 기존 `update_collection_item`의 재조회 패턴을 따른다.

## Test List (코치 계약으로 확정 예정)
- T55-H1~H4 훅 계약(훅마다 1항목, 대상은 위 55-1의 훅 [문서]) — Red = 검토에서 찾은 형태만 실패, 기존 형태는 통과.
- T55-B1 낡은 인스턴스로 상태를 바꾸면 활동 기록 `from`이 DB 현재 상태 — Red = 메모리 값 기록.
- T55-B4 상한을 넘는 검색어는 `MAX_SEARCH_LENGTH`로 절단 — 이미-Green 고정, 뮤테이션 증거.
- B2는 기존 테스트 아래 리팩터(덮는 테스트는 코치 확인).

## AC
- AC1 T55-H1~H4 Green, 통과 형태 10건 차단·오탐 1건 해소 [실측 recheck.py 재실행], 못 막는 형태는 Known gaps에 기록.
- AC2 계획서 = 이 트랙 + 열린 절 6개, 보관 파일 40개 [계산], 재조립 diff 0, 보관 커밋 푸시.
- AC3 새 규약이 AGENTS.md·CLAUDE.md·메모리에서 같은 문장으로 읽힌다.
- AC4 F1~F4 브라우저 증거 + WED·BIR 사후 Conforms.
- AC5 B1 Red-Green, B2 회귀 Green, B3 마커로 `-m contract` 수집에 포함, B4 뮤테이션 증거.
- AC6 문서 지적마다 재측정 값으로 정정했거나 "재측정 결과 정확"을 Evidence에 기록.
- AC7 전체 회귀·check·마이그레이션·ruff·e2e 10건 [문서 README] 통과.

## Frontend Review Evidence
- 깊이 Standard: 빈 상태 행동 링크·폼 오류 알림·비동기 처리 뒤 툴바 상태(F4는 스태프 화면). WED·BIR 사전 출력 → FIE → Chrome DevTools 실측(링크 존재·`aria-live` 속성과 오류 표시·승인/반려 뒤 선택 수 표시·콘솔 오류) → WED·BIR 사후.

## 검증 명령
`uv run pytest -q <대상>`(Red-Green) → `uv run pytest -q -n auto` → `uv run pytest -q -m e2e tests/e2e` → `uv run python manage.py check` → `uv run python manage.py makemigrations --check --dry-run` → `uv run ruff check .` → `uv run ruff format --check .` → scratchpad `recheck.py`.

## 이연
없음(트랙 중 발견한 같은 유형 소규모 결함은 보고 뒤 이 트랙에서 수정).

## Evidence
- 55-2 보관: 닫힌 절 40개·5,673줄 → `docs/plan-archive/`, 재조립 SHA-256 `c3e0647d…` 일치 `[실측 scratchpad archive_move.py]`, 커밋 `d0b75213` 푸시. 계획서 956줄로 축소 `[실측 wc -l]`.
- 55-1 훅: Red-Green 훅별 — H4 3 failed→Green, H2 6→Green, H3 7→Green, H1 8→Green, 추가 2→Green, uv-only 추가 4→Green `[실측 uv run pytest tests/core/test_harness_hooks_contract.py]`; 계약 최종 85건 passed(중간 79건에서 uv-only 추가 6건) `[실측]`; 2026-11-11 통과 형태 10건 전부 차단·`git clean -nd` 허용 `[실측 recheck.py]`; timeout 초 단위 5·10·30 `[실측 json]`. 정정 기록: 오케스트레이터 브리프가 `perl -i.bak`을 신규로 잘못 분류(이미 차단), 훅 워커가 timeout을 ms로 오해해 1차 5000·10000·30000 기입 → 재지시로 정정.
- 55-4 백엔드: B1 Red 3 failed(`'planned' == 'missed'` 등) → Green; Green 뒤 기존 API 테스트가 PATCH 응답의 낡은 상태를 잡음(`assert 'planned' == 'visited'`) → 뷰가 반환값을 쓰도록 수정, `tests/archive` 981 passed. B2 리팩터 뒤 981 passed. B4 뮤테이션(절단 제거) 1 failed → 원복 1 passed. B3 `-m contract` 수집 2건 `[실측]`.
- 55-3 프론트 F1~F5: 측정 워커 Chrome DevTools 실측 전 항목 기대 일치(F5 live 대입 1회·MutationObserver 일치, 오프라인 실패 경로 포함), 오케스트레이터 F1·F2 렌더 재확인 `[실측 Django Client]`. WED·BIR 사후 F1~F5 **Conforms**. 실제 스크린리더 낭독은 미측정.
- 중간 전체 회귀(HEAD `abdf2aab` + 프론트 작업 트리): 4384 passed / 80.97초, check 0건, 마이그레이션 드리프트 없음, ruff check·format(461파일) 통과 `[실측]`.
- F6·F7·F5b: 측정 워커 실측 전 항목 기대 일치(F6 5개 화면 live = `.empty-title`, 컬렉션은 0건이면 검색창 미렌더로 해당 없음; F7 이름 칸 포커스; F5b 1건 일괄 결합 문장, 3건 일괄 요약 포커스), WED·BIR 사후 **Conforms**. WED 잔여 위험: 일부 성공 일괄에서 live의 마지막 성공 건 문장이 전체 성공처럼 들릴 수 있음.
- 55-6 접근 로그: 계약 테스트 Red(`--access-logfile -` 없음) → Green 2 passed, 셸 인자 분해로 형식 문자열 1개 인자 확인, 로컬 gunicorn 실제 로그 `127.0.0.1 [12/Nov/2026:19:56:18 +0900] "GET /health/" 404 12347 "Python-urllib/3.9"`·쿼리 미기록 `[실측]`. DOR 차단 사유(allauth 키가 경로에 있어 로그에 남음) → 사용자 결정 "지정 형식 그대로"(위험 수용, 2026-11-12), 런북 §9에 기록.
- 최종(HEAD `db9dfeff`, 원격 푸시 확인): `uv run pytest -q -n auto` 4391 passed / 57.84초, check 0건, 마이그레이션 드리프트 없음, ruff 통과; e2e 10 passed / 11.89초(로컬 Playwright 브라우저 미설치로 1차 10 errors → `uv run playwright install chromium` 후 통과) `[실측]`. QVL: AC1~AC6 충분, AC7은 위 두 결과로 충족.

