# 트랙 35: 드래프트 실행 결과 기록·대시보드 표시 + 실기동 결함 수정 (2026-09-18, 사이트 로그 2단계) [v1 — PSO·DAR·SRR·AIA·TDD 코치·QVL·WED·BIR 사전 검토 통합, 인용은 오케스트레이터 원문 대조]

> **출처·승인**: 사용자 /goal(2026-09-18) "2->1->4 진행. 각 단계 마친 후 검토 필수. 결함 및 백로그 발생 시 수정 후 각 단계 pr" — 2단계 범위는 2026-09-17 사이트 로그 제안의 "드래프트 실행 기록에 결과 요약"이고, 목표 문구가 결함·백로그 즉시 수정을 요구하므로 2026-09-17 실기동 검토 결함(메모리 draft-live-run-2026-09-17)을 이 트랙에 포함한다. 사용자에게 멈춰 묻지 말라는 지시라 검토 역할 결정으로 확정한다.
> **기준선** [실측 2026-09-17, main `716fe90d`, 이후 main은 문서 커밋만]: 2927 passed / 10 deselected. 착수 전 재측정.
> **브랜치·PR**: main에서 `feat/draft-run-outcomes`. PR 1개(2단계), 머지는 사용자 승인.

## 역할 충돌 정리 (오케스트레이터)
1. 잘못된 `event_outcomes` 항목: 코치 초안 400 → **항목 단위 버림 + 200**(DAR·SRR). 근거: 완료 400이면 러너 `client.complete`가 예외를 내 `complete_run`이 실행되지 않고 실행이 CLAIMED로 남아 임대 1800초×최대 2회 [코드 `drafts/discovery_runs.py:16,19`] 동안 새 탐색이 막힌다. 최상위가 리스트가 아닐 때만 기존 필드처럼 400.
2. 건너뛴 항목 집계: 코치 "attempted 제외" → **attempted·excluded 둘 다 포함**(PSO, `events_excluded` 정의 [코드 `drafts/models.py:141`]와 일치, 차단 호스트 스킵이 attempted+failed에 들어가는 기존 패턴과 대칭 [코드 `local_runner/exploration_flow.py:109-114`]).
3. S5(X 읽기)·S7(재검증 생략): PSO "다른 종류라 제외" → **포함**. 사용자 목표가 결함·백로그 발생 시 수정을 요구한다.
4. 건너뛰기 자격: 초안 why_excluded 6종 전부 → **ended(코드가 날짜 재확인)·overseas(같은 출력에서 호스트가 not_kr 소스와 일치)만**(AIA, 트랙 33 D5 "불확실은 제출"). 되돌리기용 상수 1개.
5. robots 새 단계명: 초안 `robots_unreachable` → **`robots_fetch_failed`**(QVL, 기존 상수 [코드 `drafts/candidate_intake.py:14-17`]와 같은 어휘). S7 재사용 대상에서 제외(SRR — TLS·네트워크는 일시 오류).
6. `created` 표시: 러너 문자열 불신(PSO AC3) — 서버가 이 실행의 드래프트 source_url과 대조해 없으면 그 항목을 버린다. 대시보드 "행사 생성" 수는 계속 `run.events` 기준.

## 승인 범위
- S1 러너 행사별 결과 `{url, outcome, reason}` + 행사당 INFO 로그 1줄(outcome·reason·host, 본문 금지, 영문 ASCII·lazy %). outcome: created·duplicate·excluded·failed·skipped. reason: skipped=known_url·agent_ended·agent_overseas / failed=host_blocked·blocked·fetch_empty·interpret_error·no_title·submit_error / excluded=overseas·ended·server_overseas·server_ended / created·duplicate=빈 값.
- S1b 흐름 도중 일반 예외가 나면 그때까지의 결과를 실패 완료 보고에 싣는다(임대 상실 409는 보고하지 않음 — 다른 곳이 이미 가져간 실행). `_ALLOWED_FAILURE_KINDS`에 러너가 실제 보내는 `exploration_error` 추가(SRR 발견 기존 결함 [코드 `drafts/discovery_runs.py:22`, `local_runner/runner.py:91`]).
- S1c (기준선 실기동 발견, 2026-09-18 실행 16) 행사 하나의 읽기 예외가 실행 전체를 죽였다: `exploration_error`로 실패, events_attempted 5 [실측] 중 결과 4건만 기록, 5번째 항목은 요청 전송 전 예외(그 뒤 httpx 요청 로그 0건 [실측]), 예외 종류 로그 0건 [실측]. 원인 [코드 `local_runner/exploration_flow.py:156-162`]: `fetch_text`에서 `BlockedResponseError`만 잡는다. 수정: 읽기 단계의 예상된 예외(httpx.HTTPError·InvalidFetchUrlError·UnsafeFetchUrlError·ResponseTooLargeError·EmptyExtractionError·OSError)는 그 항목만 failed·`fetch_error`로 기록하고 계속, WARNING 1줄(예외 클래스명·host). 러너 `_process_run`의 두 실패 경로는 원인 예외 클래스명을 WARNING으로 남긴다(본문 금지). 서버 허용목록 failed에 `fetch_error` 추가(TR-22가 강제).
- S2 완료 API `event_outcomes`(선택 키, 옛 러너 호환). 검증은 `complete_run` 쪽 헬퍼(DAR), 뷰는 리스트 타입만. 항목: dict, url http(s)·`sanitize_text` 적용·200자 이하, outcome·reason 허용목록, created는 실행 드래프트와 대조, 최대 20건(초과분 절단) [코드 `drafts/agent_drafts.py:55`]. 저장 `SourceDiscoveryRun.event_outcomes` JSONField(default=list). 허용목록 러너·서버 일치 계약 테스트.
- S3 러너 건너뛰기: 탐색 항목의 `why_excluded=="ended"`이고 탐색이 준 `end_date`(ISO)가 오늘(KST)보다 이전이면 skipped·agent_ended, `why_excluded=="overseas"`이고 URL 호스트가 같은 출력의 `source_country=="not_kr"` 소스 호스트와 같으면 skipped·agent_overseas. 그 외는 기존 경로(fail-open). 상수 `SKIPPABLE_AGENT_REASONS`.
- S4 탐색 프롬프트: `today`(KST ISO) 인자, 국내(대한민국) 개최만 is_event=true, why_excluded에 overseas 추가(스니펫의 도시·국가 신호로만, 없으면 빈 값), 이벤트 스키마에 `end_date`(YYYY-MM-DD, 모르면 빈 값). `_today_kst`는 러너 공용 위치로 이동, runner가 today 전달.
- S5 X 게시물 읽기: x.com·twitter.com의 `/<handle>/status/<숫자 id>`만 `cdn.syndication.twimg.com/tweet-result`(고정 호스트, id 숫자 검증, `validate_fetch_url`, 타임아웃 15초·응답 1,000,000바이트 상한 [코드 `local_runner/page_fetch.py:25-27`])로 읽어 본문 반환, 실패·비게시물 URL은 None. 인스타 경로 무변경.
- S6 소스 후보 robots 실패 분리: `RobotsCheckResult.reason`이 fetch 실패면 새 `FailureStage.ROBOTS_FETCH_FAILED`("robots.txt를 가져오지 못했다(네트워크·인증서 오류)"), 불허는 기존 ROBOTS. 마이그레이션 AlterField.
- S7 최근 결정적 실패 재사용: 같은 URL이 7일 안에 robots·sample_mismatch·listing_extraction·not_domestic·url_safety로 실패했으면 네트워크 없이 같은 단계로 새 실패 행 생성(Unique(run,url) 유지, 상한 재검사 기존 패턴 재사용 [코드 `drafts/candidate_validation.py:139-168`]). robots_fetch_failed·fetch·sample_canary는 제외. **착수 중 정정(오케스트레이터 원문 대조)**: url_safety는 DNS 조회 실패(OSError)도 같은 단계로 기록돼 일시 오류가 섞이고 [코드 `drafts/candidate_validation.py:203-207`], not_domestic은 네트워크가 없는 payload 필드 검사라 재사용 이득이 없고 다음 제출의 교정값을 덮는다 → 둘 다 재사용 대상에서 뺀다(robots·sample_mismatch·listing_extraction 3종).
- S8 대시보드 탐색 표: "승격/실패"→"후보 승격/후보 실패", "행사 생성/행사 제외/행사 실패" 추가(생성=`run.events` 수, 제외·실패=저장 건수, 옛 실행은 결과 목록이 비면 "-"), 마지막 열 상세 버튼(네이티브 button, 다음 형제 `<tr hidden>` 단일 td colspan=열 수, aria-expanded·aria-controls, 행마다 고유 이름, 선례 `static/js/staff/draft.js:329-352`). 상세 목록은 `<ul>`로 호스트+경로(쿼리 제거, 링크 아님, overflow-wrap 줄바꿈)·결과 배지(생성됨 ok / 중복·제외·건너뜀 disabled / 실패 error)·사유 한국어 라벨(모르는 값은 "알 수 없음"). 쿼리 함수가 표시용 필드를 계산, 쿼리 수 고정 테스트.
- S8 추가(착수 중 발견, 같은 종류): 후보 실패 단계 라벨 체인에 `not_domestic` 분기가 없어 빈 칸으로 보인다 [코드 `templates/staff/dashboard.html:277`]. S6 `robots_fetch_failed` 라벨과 함께 채운다.
- S9 문서: `docs/BE/draft-source-agent-discovery.md` 트랙 35 절(FailureStage 개수 정정 포함), backlog 행.

## 제외
오류 묶음(1단계)·보존 정리(4단계), 탐색 원출력 전문 저장, 같은 이름·팬메이드 등 주관 사유 건너뛰기, 캡션 경로 응답 상한(기존 결함 — SRR 이연), DNS 리바인딩 TOCTOU(이연), 새로고침 후 펼침 상태 유지.

## 역할
PSO·DAR·SRR·AIA(완료) / TDD 코치·Backend Eng·Frontend Eng·QVL·WED·BIR 활성. DOR 미활성: AddField JSONField default·choices AlterField, 소형 테이블, 배포 절차 무변경.

## Test List (코치 초안을 결정에 맞춰 조정, 총 37건 [계산])
| ID | 경계 | 요지 |
|---|---|---|
| TR-01~11 | unit/contract | S1: known_url / host_blocked / blocked / fetch_empty / interpret_error / no_title / excluded overseas·ended / submit_error / server_overseas·server_ended / created·duplicate / 로그 계약(본문 없음) |
| TR-12 | unit | S1b: 흐름 예외 시 부분 결과가 실패 완료 보고에 실린다 |
| TR-13 | domain | S1b: failure_kind exploration_error가 요약에 남는다 |
| TR-14~19 | web/domain | S2: 저장 / 옛 러너 빈 목록 / 잘못된 항목 버림·200·상태 정상 / 20건 절단 / 제어문자 제거 / 실행에 없는 created 버림 |
| TR-20~21 | contract/unit | S2: RunnerClient.complete가 httpx 본문에 싣는다 / _process_run이 싣는다 |
| TR-22 | contract | S2: 러너 outcome·reason 허용목록 = 서버 허용목록 |
| TR-23~26 | unit | S3: 지난 ended 건너뜀 / not_kr 소스 호스트 overseas 건너뜀 / 그 외 why_excluded는 기존 경로(핀·뮤테이션) / 건너뜀은 attempted·excluded 포함 |
| TR-27~28 | unit | S4: 프롬프트 today·국내 규칙·overseas·end_date / runner가 today 전달 |
| TR-29~32 | unit/contract | S5: status URL은 tweet-result 본문 / 실패는 None / 비게시물 URL은 요청 없이 None / 응답 상한 초과는 None |
| TR-33 | domain | S6: robots fetch 실패는 robots_fetch_failed, 불허는 robots |
| TR-34~36 | domain | S7: 7일 내 결정적 실패는 네트워크 없이 같은 단계 / 7일 지난 실패는 재검증(핀) / robots_fetch_failed는 재사용 안 함 |
| TR-37 | domain | S8: recent_discovery_runs가 결과별 건수·표시 행 계산, 쿼리 수 고정 |
| TR-38 | unit | S1c: 읽기의 예상된 예외(종류별 parametrize)는 그 항목만 failed·fetch_error, 다음 항목 계속 처리 |
| TR-39 | unit | S1c: _process_run 실패 경로가 원인 예외 클래스명을 WARNING으로 남긴다 |
(S1c 추가로 총 39건 [계산])
기존 테스트 `tests/local_runner/test_exploration_flow.py:164,543`의 요약 dict 전체 비교는 계약 변경에 따른 의도된 갱신(QVL) [코드].

## 검증
- 사이클: `uv run pytest -q <대상 파일>` Red → Green. 슬라이스: `uv run pytest -q tests/local_runner tests/drafts tests/staff`. 전체: `uv run pytest -q`, `check`, `makemigrations --check --dry-run`.
- 실기동(AIA 평가): S1·S2 완료 후 "치이카와 팝업스토어" 기준 실행 1회(결과 목록이 기준선) → S3~S5 완료 후 같은 검색어 1회. 대조: 결과·사유 분포, 읽기·해석 호출 수 감소가 건너뜀 수와 일치, 건너뛴 항목 전수 URL 확인(오제외 0), 소요 시간.
- 브라우저(S8): 1280·1024 × 라이트·다크, 펼치기 키보드·aria-expanded, 가로 오버플로, 콘솔 0.

## 이연(Deferred)
- event_outcomes 별도 모델 승격(DAR) — 트리거: 실행 간 URL 실패 조회 요구.
- 주관 사유(same_name 등) 건너뛰기 평가셋(AIA) — 트리거: 누적 실행 여러 번 뒤 에이전트 사유와 서버 판정 일치율 확보 [문서 AIA 권고 3~5회].
- 캡션 경로 응답 크기 상한·DNS 리바인딩(SRR).

---

