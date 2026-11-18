# 트랙 38: 어댑터 얇게, 규칙은 내부 서비스로 (2026-09-18) [v1 — PSO·DAR·TDD 코치·SRR 사전 검토 통합, 오케스트레이터가 file:line 전부 재확인] · **상태(2026-11-12)**: PR 0 #380·PR 1 #382 머지(2026-09-19 `[실측 gh]`), 슬라이스 A·B·C는 미착수 `[문서 docs/backlog.md 트랙 38 행]`. · **폐기(2026-11-18)**: 미착수 슬라이스 A·B·C는 폐기한다 `[문서 사용자 지시 2026-11-18 "열린 트랙 폐기. 작업 혼동 가능성."]`. 머지된 PR 0·PR 1은 그대로 유효하다. 이 절은 실행 계획이 아니라 기록이다.

> **출처**: 사용자 지시(2026-09-18) "PR들 순차 머지 이후 어댑터는 얇게 유지하고 규칙을 내부 서비스로 넘기고 싶어." + 결정 4건 승인 [문서 채팅](머지 순서 / 결함 PR 선행 / D→A→B→C 슬라이스당 PR 1개 / local_runner 제외).
> **선행 완료**: #376 `8ee32d40` → #377 `0d4401b4` → #378 `4f45cd6e` 순차 머지 [실측 gh]. main 재측정 **3101 passed / 10 deselected / 91.08초**, check 0, makemigrations 변화 없음 [실측 4f45cd6e].
> **어댑터 정의**: HTTP 뷰·관리 명령·시리얼라이저·allauth 어댑터. `local_runner/`는 제외(별도 프로세스라 `drafts.*` 임포트 불가, 판별 규칙은 이미 서버 소유 [문서 docs/BE/draft-source-agent-discovery.md]).

## 역할 충돌·정정 정리
1. `_new_group_allowed` 이동 여부: SRR "이동 가능하되 호출자 전원이 거쳐야 하는 불변식" vs DAR "core.error_groups로 이동" → **이동(DAR)**, 단 docstring에 "무인증 쓰기 경로는 반드시 이 함수를 먼저 통과"를 못박는다(SRR 조건).
2. `core/client_error_views.py` 이동 범위: 코치 초안 규칙 4개 [문서 코치 보고](normalize_path·payload 검증·쿼터·식별자 조립) vs DAR·SRR "쿼터만" → **쿼터만(DAR)**. `normalize_path`는 백엔드 쪽도 어댑터가 출처별 location을 만드는 확립된 설계 [코드 core/logging.py:27-31], payload·origin·body 검사는 HTTP 개념(request.META, RequestDataTooBig)이라 경계에 남긴다.
3. 슬라이스 C 신규 모듈명: DAR 제안 `drafts/discovery_run.py`는 기존 `drafts/discovery_runs.py`(트랙 35 실행 상태)와 이름이 겹친다 [코드 ls drafts/] → **`drafts/listing_discovery.py`**(목록형 소스 수집 오케스트레이션).
4. PSO "어댑터 종류당 PR 1개" vs DAR "대상 도메인당 슬라이스" → DAR 분할 채택(각 슬라이스가 한 어댑터 종류·한 도메인 안에 머물러 둘 다 만족).

## 승인 범위 (PR 5개 [계산], 순서 고정, 각 PR = 커밋은 규칙당 1개)
- **PR 0 결함(행동 변경, Red-Green)** — 승인 전 체크 드리프트. `staff/views/drafts.py:64-98 _draft_preapproval_checks`는 실제 검증기 `events/services.py:42-75 _validate_publish_fields`(approve_draft → create_published_event → 검증 [코드 drafts/services.py:358-363, events/services.py:104])에 있는 **기간 역전(start>end)·제목=공식URL(끝 슬래시 무시)** 두 검사가 없다 [코드]. 해법: `events/services.py`에 검증기 바로 옆 dry-run 판정 함수 `publish_field_checks(*, title, official_url, start_date, end_date, category, region, existing_queryset) -> list[{key,label,passed}]`(검증기와 같은 순서, 예외 대신 전 항목 판정). 뷰는 초안 필드를 넘겨 결과를 그대로 컨텍스트에 싣는 얇은 어댑터로(템플릿 `templates/core/drafts/detail.html:158-163`은 label·passed만 렌더 [코드], 변경 없음; 기존 테스트 `tests/staff/test_staff_draft_views.py:606-621`의 5키 전수 단언은 새 키 2개를 포함하도록 갱신 — 행동 변경의 의도된 Red [코드]). 새 key: `period`, `title_not_url`. 드리프트 재발 방지 핀 = 계약 테스트(실패 사례 7종 [코드 검증기 raise 7곳] parametrize: 각 실패 체크 key ↔ 검증기가 던지는 예외 짝).
- **PR 1 슬라이스 D** — `core/client_error_views.py:27,93-101` `NEW_GROUP_HOURLY_LIMIT`·`_new_group_allowed` → `core/error_groups.py` `frontend_new_group_allowed(fingerprint)`(+ 상수). 뷰의 `from core.models import ErrorGroup` 제거. 기존 테스트 monkeypatch 대상 2곳만 경로 갱신 허용(`tests/core/test_client_error_report.py:319, 375` [코드]). `docs/BE/error-groups.md`의 뷰 행번호 인용(:27, :93-101 [코드]) 갱신.
- **PR 2 슬라이스 A** — `staff/views/events.py:69-95` `QUALITY_WARNING_LABELS`·`_event_quality_badges` → `events/queries.py`(`QUALITY_WARNING_KEYS:178`·`published_quality_warnings:151` 옆 [코드], 공개 이름 `event_quality_badges`). 임포트 갱신 `staff/views/events_actions.py:27`, `staff/views/__init__.py:53` [코드]. `docs/BE/staff-event-publish-actions.md:150,190` 위치 언급 갱신 [코드 rg]. 대시보드 문구 수동 동기화 주석은 그대로 옮긴다.
- **PR 3 슬라이스 B** — `staff/views/_helpers.py:60-93` `_build_source_rows` → `drafts/queries.py` `draft_source_health_rows(sources)`(소비처 `staff/views/__init__.py:38,267`, `staff/views/sources.py:11,22` [코드 rg]); `staff/views/drafts.py:48-61` `_draft_warning_badges` → `drafts/queries.py` `draft_warning_badges(draft)`(소비처 `:114` [코드 rg]). `settings.DRAFT_SOURCE_STALE_HOURS` 참조가 함께 이동. `tests/staff/test_staff_draft_sources_view.py:3` docstring 언급만 갱신.
- **PR 4 슬라이스 C** — `drafts/management/commands/discover_drafts.py`(234행 [실측 awk])의 `_ListingOutcome`·`_mark_source_checked`·`_process_listing`·`_process_candidates`·`_summarize`·`INTER_REQUEST_DELAY_SECONDS` → 신규 `drafts/listing_discovery.py` `run_listing_discovery(*, stderr) -> stats dict`. 명령은 플래그 확인(`DRAFT_DISCOVERY_ENABLED`, 활성 소스 없음 문구)·호출·stdout 출력만. stderr 주입은 기존 `candidate_intake` 관행대로 유지(행동 불변). 사설 함수를 직접 임포트하는 테스트 0건 [실측 rg].

## 제외 (전부 이 트랙 밖)
행동 변경(PR 0 제외)·URL/응답/CLI stdout 계약 변경·프론트(템플릿/CSS/JS)·새 베이스 클래스·범용 서비스/배지/RateLimiter 프레임워크·새 앱·`local_runner/*`·러너 API 뷰(`drafts/runner_views.py`는 이미 얇음, 예외→상태코드 매핑은 경계 통제)·`archive/serializers.py` 교차필드 검증·queryset 스코핑(표현 경계)·`core/logging.py` DatabaseError 분기·`accounts/adapters.py`·URL 안전/SNS 호스트 패리티 파일(`local_runner/url_safety.py`, `local_runner/page_fetch.py`, `drafts/candidate_validation.py` 호스트 목록)·`staff_draft_discovery_run`의 stdout 텍스트 파싱 결합(이연, 트리거: PR 4 뒤 구조화 반환값 필요 시)·기록된 보류 `staff/views/events.py` 필터 헬퍼 분리(아래 트랙 26 Deferred, 현재 802행 [실측 awk]).

## 수용 기준 (PSO)
AC1 옮긴 어댑터 함수 본문에 상한·분류·자격 판정 분기가 없다(도메인 호출 + 응답/출력 조립만). AC2 옮긴 규칙마다 어댑터를 거치지 않는 도메인 직접 호출 테스트가 하나 이상 [계산]. AC3 이동 전 테스트가 무수정(monkeypatch 경로·docstring 예외)으로 전부 통과, URL·응답 코드·본문·stdout 불변. AC4 `makemigrations --check --dry-run` 변화 없음(드리프트가 하나라도 나오면 범위 초과 신호, 정지 [계산]). AC5 슬라이스마다 PR 하나 [계산].

## 역할
Activated: PSO(완료)·DAR(완료 + PR별 사후 리뷰)·TDD 코치(PR별 계약)·BIE(구현)·QVL(PR별 최종)·SRR(PR 1 필수, PR 4 조건부 — robots/fetch 오케스트레이션 이동). Not activated: WED·BIR·FIE(템플릿·CSS·JS 변경 없음 [계산]), AI Automation Architect(LLM 범위 없음), DOR(배포·설정·마이그레이션 변경 없음).

## Domain Boundary / Coupling / Pythonic
의존 방향 변화 없음: staff → events/drafts(기존), core.client_error_views → core.error_groups(기존), 명령 → drafts(기존). 역방향(core→drafts, drafts/events→staff) 이동은 없다 [문서 DAR 보고]. 결합: staff 뷰 소비처(슬라이스 A 임포트 2곳 + 정의 1곳, 슬라이스 B 소비처 3곳 [코드 rg])가 각자 알던 판정을 도메인 모듈 하나로 모아 중복 정의 제거, 뷰의 `ErrorGroup` 직접 참조 제거. 응집: 이동 대상 전부 그 도메인이 이미 소유한 동종 함수 옆에 붙는다. 설계: 기존 `*/queries.py`·`*/services.py`·`core/error_groups.py`에 함수 추가만, 신규 파일은 `drafts/listing_discovery.py` 하나 [계산], 클래스·프레임워크 없음.

## Test List (TDD 코치 방법: 새 Red = 새 위치 ImportError, 증거 = 옛 테스트 무수정 Green + 도메인 테스트 신설 + 뮤테이션 1회, 총 13건 [계산])
| ID | PR | 경계 | 요지 |
|---|---|---|---|
| TA-01 | 0 | unit | `publish_field_checks`: 시작일>종료일이면 `period` 실패, 나머지 통과 (첫 테스트) |
| TA-02 | 0 | unit | 제목이 공식 URL과 같으면(끝 슬래시 무시) `title_not_url` 실패 |
| TA-03 | 0 | contract | 실패 사례 7종 parametrize: 실패한 체크 key ↔ `_validate_publish_fields`가 던지는 예외 짝(드리프트 핀) |
| TA-04 | 0 | web | 인스펙터가 기간 역전 초안에 실패 배지를 보여준다(`tests/staff/test_staff_draft_views.py` B2 옆) |
| TA-05 | 1 | domain | `frontend_new_group_allowed`: 상한 초과 새 지문 거부, 기존 지문 갱신 허용, 상한 미만 새 지문 허용 |
| TA-06 | 1 | web(기존) | `tests/core/test_client_error_report.py` 전부 Green(monkeypatch 경로 2곳만 갱신) |
| TA-07 | 2 | unit | `event_quality_badges` 경고 5종 parametrize + 경고 없음 |
| TA-08 | 2 | web(기존) | `tests/staff/test_staff_console.py`·이벤트 액션·이벤트 뷰 테스트 Green |
| TA-09 | 3 | unit | `draft_source_health_rows` 우선순위 disabled>error>stale>ok 4사례 + 비활성은 stale 아님 |
| TA-10 | 3 | unit | `draft_warning_badges` 제목/지역/기간 3종 + 없음 |
| TA-11 | 3 | web(기존) | `tests/staff/test_staff_draft_sources_view.py`·대시보드·초안 목록 테스트 Green |
| TA-12 | 4 | domain | `run_listing_discovery` 반환 통계가 기존 stdout 요약 값과 같다(기존 명령 테스트 시나리오 1개를 도메인 경계로 복제) |
| TA-13 | 4 | contract(기존) | `tests/drafts/test_discover_drafts_command.py` 전부 Green(stdout·stderr 문자열 불변) |

## 검증 (PR마다)
사이클 `uv run pytest -q <파일>` → 뮤테이션 1회(PYTHONDONTWRITEBYTECODE=1, 커밋에 남기지 않음) → 관련 기존 테스트 파일 무수정 Green → 전체 `uv run pytest -q`·`manage.py check`·`makemigrations --check --dry-run`(변화 없음). diff 리뷰로 AC1 확인. 문서 대상: PR 1 `docs/BE/error-groups.md`, PR 2 `docs/BE/staff-event-publish-actions.md`, PR 0·3·4 `docs/backlog.md` 행 갱신. 브랜치: PR 0 `fix/draft-preapproval-checks`, PR 1 `refactor/error-group-quota`, PR 2 `refactor/event-quality-badges`, PR 3 `refactor/draft-badges-health`, PR 4 `refactor/listing-discovery`.

## 사후 기록 (PR별로 오케스트레이터가 기입)
- **PR 0 = #380** (`fix/draft-preapproval-checks`, 커밋 fe428344·88bd4c3f, 2026-09-18) — 코치 계약대로 진행. Red: 새 테스트 파일 collection error(ImportError) → 최소 Green 9 passed. TA-01 첫 실행 `Database access not allowed` → 마커 unit→domain+django_db(코치 예견). TA-03 official_url_missing 실제 실패 key {official_url, official_url_unique}(기존 미리보기와 같은 연쇄 표시) → 기대값 정정. 뮤테이션 2회: 기간 검사 `and False` → 2 failed / 7 passed(TA-01·TA-03[period_reversed]만), rstrip 제거 → 1 failed / 8 passed(TA-02만), 원복 9 passed [실측]. 첫 시도(부등호 반전)는 정상 날짜까지 깨뜨려 9 failed — 판별력 없어 폐기. 웹: 옛 뷰(stash)+새 테스트 2 failed / 2 passed, 새 뷰 59 passed. 전체 3111 passed / 10 deselected / 89.78초(main 3101 → +10 = 신규 테스트 수와 일치 [계산]), check 0건, makemigrations 변화 없음 [실측 88bd4c3f]. CI 5잡 pass [실측 gh]. DAR: 결함 0, AC1·의존 방향 충족, 권고 1(URL 결측 시 unique 동반 실패는 기존 동작). QVL: **Complete with residual risk** — 잔여 = backlog 행 미갱신(#379와 충돌 회피로 머지 후 롤링 docs PR에서 처리), 인스펙터 표시 순서가 title 우선 → official_url 우선(검증기 순서, 스태프 내부 화면). **머지 완료 `6ddc7def`(2026-09-19, 사용자)**. 롤링 docs PR #381 오픈.
- **PR 1 = #382** (`refactor/error-group-quota`, 커밋 2862540a 이동·e877ff3f 문서, 2026-09-19) — 코치 계약(별칭 대신 새 이름 임포트, monkeypatch 경로 2곳 갱신은 오케스트레이터 결정). Red: `ImportError: frontend_new_group_allowed` → 이동 후 두 파일 57 passed. 뮤테이션 `<=`→`<`: 3 failed / 54 passed(EG-36·EG-37 신규 + EG-20 기존, EG-38 기존 지문 경로 Green), 원복 57 passed [실측]. 전체 3114 passed / 10 deselected / 96.36초(main e4e0338f 3111 → +3 [계산]), check 0건, makemigrations 변화 없음 [실측 2862540a]. 뷰에서 `ErrorGroup`·`cache`·`timezone` 임포트 제거, 본문·캐시 키 동일(diff 확인). `docs/BE/error-groups.md` 행번호 인용 18곳 재실측 갱신 + 가드레일 문장. DAR 결함 0 / SRR 결함 0(권고: 게이트를 코드로 강제하는 래퍼 — 이연, 트리거: 세 번째 무인증 쓰기 경로) / QVL Complete with residual risk(문서 최종본 확인 = 완료). CI: 4잡 pass, **의존성 감사만 fail — anyio 4.13.0 신규 GHSA 2건(fix 4.14.2), docs PR #381도 동일 실패 → 환경 요인**, 별도 build PR **#383**(uv.lock 변경 3줄 [실측 git diff --stat], anyio 4.13.0→4.14.2만, CI 5잡 pass [실측 gh], DOR 차단 없음, 로컬 pip-audit(Python 3.12) No known vulnerabilities [실측]) 머지 `bcd7e4db` → #381·#382 브랜치에 main 머지해 게이트 재통과(5잡 pass [실측 gh]) → **#381 `504f0c8d`, #382 `0c7cb3a0` 머지 완료(2026-09-19, 사용자 승인)**. main 재측정 3114 passed / 10 deselected / 126.66초, check 0건, makemigrations 변화 없음 [실측 0c7cb3a0]. DOR 권고(런북에 외부 어드바이저리 감사 실패 절차 기록)는 사용자 미결.
