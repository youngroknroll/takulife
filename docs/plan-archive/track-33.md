# 트랙 33: 키워드 탐색 드래프트 국내·미종료 필터 (2026-09-15) [v2 — PSO·AIA·SRR·DAR·TDD 코치·QVL 검토 + 2차 범위(D8~D10) DAR·코치 델타 검토 반영, 인용은 오케스트레이터가 원문 대조, **사용자 승인 완료(2026-09-16 "승인, 진행해줘")**]

> **위치**: 트랙 30(키워드 탐색, PR #361 머지) 로컬 실기동(2026-09-15, 실행 13, 검색어 "하츠네 미쿠 팝업스토어")에서 드래프트 4건 중 3건이 부적합 [실측]: #71 도쿄 개최, #72 미국 BOOKOFF 개최(한국어 기사), #73 2023-05 종료. 소스 후보 5건 중 일본 집계 사이트 1건(collabo-cafe.com)이 `enabled=True`로 승격 [실측]. 이 트랙은 그 재발을 막는다.
> **기준선** [실측 2026-09-15, main HEAD `1c73f8c3`]: `uv run pytest -q` → **2826 passed / 10 deselected / 87.13초**. 착수가 이 커밋에서 시작하지 않으면 다시 잰다(Numbers In Documents).
> **브랜치·PR**: main에서 `feat/domestic-active-draft-filter`. PR 1개, base main.

## 사용자 결정 기록 (2026-09-15)

- D1 국내 개최 행사만 드래프트로 만든다. 지역 어휘(`core/vocab.py:38-50`, 8종 [코드])는 MVP로 고정 유지 — 국내인데 어휘 밖 지역은 region 빈 값 + 메모에 원 지역명(이미 `_check_region`이 수행, 아래 DF-00).
- D2 종료일(없으면 시작일)이 오늘보다 이전이면 제외. 날짜를 못 읽으면 제출.
- D3 러너와 서버 둘 다 적용.
- D4 같은 PR: 해외 소스 후보 제외, 완료 뷰 이벤트 수 0 저장 결함 수정.
- D5 개최지 신호가 없는(국내·해외 불확실) **행사는 제출**(PSO·AIA 권고 채택, SRR의 fail-closed 권고 기각).
- D6 국내·해외 불확실한 **소스 후보는 제외**(AIA 권고 — 소스 오판은 매 실행 반복 오염).
- D7 제외 건수는 **실행 기록(DB)에 저장**(PSO 권고 채택, DAR 이연안 기각). 화면 표시는 범위 밖.
- D8(2차) 후보가 있는 실행도 이벤트 결과를 상태에 반영한다 — 이번 트랙 포함.
- D9(2차) 서버 수집 경로(`discover_drafts` 명령과 후보 승격 시 초기 드래프트 생성)에도 필터 — **제목·본문에 한글이 없으면 제외**, **본문에 나온 가장 늦은 날짜가 오늘 이전이면 제외**, 날짜 없으면 제출. 근거: 서버 수집 드래프트 53건 중 한글 없음 20건이 전부 일본어 블로그·콜라보카페였고 코믹월드 공지 오탐 없음, 규칙 추출기 시작·종료일은 게시일이 섞여 "종료일(없으면 시작일)" 규칙은 15건을 잡지만 그중 12건이 날짜를 직접 심은 샘플이었다 [실측 2026-09-15 shell 집계].
- D10(2차) 로컬 DB의 해외 소스 #8(piapro 블로그)·#12(콜라보카페) 비활성화 — **완료** [실측 update 2건, enabled=False].
- 로컬 DB 드래프트 전체(57건 [실측]) 삭제는 사용자 결정 (c)이나 권한 분류기가 차단 — 사용자가 직접 실행. 백업 `pg_dump` 288,011바이트 [실측, 스크래치패드].

## 정정 기록 (검토 단계)

1. DAR "`FailureStage` 선택지 추가는 마이그레이션 불필요" → **기각**: choices는 마이그레이션 상태에 들어가 AlterField가 생긴다 [코드 선례 `drafts/migrations/0006_alter_sourcecandidate_failure_stage.py`].
2. DAR "목록형 소스 국내 판정은 sample_canary 뒤 서버 관측으로" → **기각**: 서버 결정론 지역 추출 `drafts/extraction.py:48-56` `_detect_region`은 서울·부산·인천 3개 문자열뿐이라 해외를 판정할 수 없다 [코드]. 러너 판정 필드를 서버가 스키마 단계에서 검사한다.
3. AIA 평가 골든셋 "#73 → 국내" → **정정**: #73은 渋谷(도쿄) 개최라 해외 [실측 실행 13 `extracted_location_name`].
4. AIA 평가 절차는 실행 13 드래프트를 DB에서 꺼내는 전제 → 드래프트 전체 삭제 후에는 스크래치패드 백업에서 복원 조회로 대체.
5. PSO "지역 어휘는 의도적 고정이라는 서술이 코드에 없다" → 사실(`core/vocab.py:219-223` 주석은 어휘가 늘어 왔다고 기록 [코드]). 고정은 2026-09-15 사용자 발언이 근거.
6. 오케스트레이터 신규 발견(보고 후 같은 트랙 수정, 2026-08-25 상시 결정): D4 수정으로 이벤트 수가 실제로 전달되면 `complete_run`의 후보 0건 분기(`drafts/discovery_runs.py:158-168` [코드])가 **실패 0건·생성 1건 이상인 정상 실행을 PARTIALLY_FAILED**로, **전부 정상 제외된 실행을 FAILED**로 산출한다(SRR Finding 1 + 오케스트레이터 확장). HTTP 완료 경로에서는 두 값이 늘 0으로 넘어가 이 분기의 이벤트 판정이 운영에서 한 번도 쓰이지 않았다 [코드 `drafts/runner_views.py:164-170`] — `complete_run` 서비스 함수 자체는 이벤트 수 파라미터 테스트가 있다 [코드 `tests/drafts/test_discovery_runs.py:308-361`, QVL 지적으로 표현 한정].
7. TDD 코치 발견: 러너 흐름은 탐색 단계의 `is_event`·`why_excluded`를 소비하지 않는다 [실측 `rg -n "why_excluded|is_event" local_runner/` → 프롬프트 문자열·해석 결과만]. 다른 종류(토큰 낭비·중복 판단)라 Deferred.

## Activated Roles / Not Activated

| 역할 | 활성 | 사유 |
|---|---|---|
| Product Scope Owner | ✅(완료) | 범위·수용 기준·열린 결정 산출 → D5~D7로 사용자 확정 |
| AI Automation Architect | ✅(완료) | 해석·탐색 프롬프트 출력 스키마 변경 |
| Security & Resilience Reviewer | ✅(완료) | 러너 제출 신뢰 경계·완료 뷰 입력 검증·"오늘" 시간대 |
| Domain Architecture Reviewer | ✅(완료) | 규칙 소유 위치·거부 관용구·복제 가드 |
| Backend TDD Coach | ✅ | Test List DF 확정·사이클 계약 |
| Backend & Integration Engineer | ✅ | 테스트·구현·문서 편집(오케스트레이터 단독 pytest 실행) |
| Quality Verification Lead | ✅ | 계획 검토 + 최종 증거 대조 |
| Deployment & Operations Reviewer | ❌ | 마이그레이션은 AddField(기본값 0)+choices AlterField로 잠금·데이터 이동 없음. 러너·서버 버전 불일치는 아래 호환 규칙으로 흡수. 배포 절차 변경 없음 |
| WED / BIR / Frontend Implementation Engineer | ❌ | 템플릿·CSS·JS 변경 없음(D7 화면 표시 범위 밖) |

## 승인 범위

**서버**
- S1 완료 뷰(`drafts/runner_views.py` `RunnerCompleteView`)가 `events_attempted`·`events_failed`·`events_excluded`를 읽어 `complete_run`에 전달. 키 없음 = 0(구버전 러너 호환). 정수가 아니거나 bool이면 400(SRR F2·F3).
- S2 `SourceDiscoveryRun.events_excluded`(PositiveSmallIntegerField, default 0) 추가, `complete_run`이 clamp 후 저장(D7).
- S3 `complete_run` 러너 성공 보고 분기의 상태 규칙을 후보 결과와 이벤트 결과의 결합으로 교정(정정 6 + D8). 러너 실패 보고 분기는 불변.
  - 후보 결과: 후보 없음=없음 / 전부 승격=정상 / 전부 실패=실패 / 혼합=부분.
  - 이벤트 결과: 시도 없음=없음 / 실패 없음=정상(생성 없음·전부 제외여도) / 실패 있음·생성 없음=실패 / 실패 있음·생성 있음=부분. 생성 수는 러너 보고가 아니라 `run.events`로 센다(기존 설계 유지 [코드 `drafts/models.py:137-138` 주석]).
  - 결합: 있는 결과가 없으면 SUCCEEDED, 모두 정상이면 SUCCEEDED, 모두 실패면 FAILED, 그 외 PARTIALLY_FAILED.
  - 기존 파라미터 테스트 4종(전_승격·혼합·전_실패·후보_없음_성공)과 `:309` 후보 없음·전부 실패는 결합 규칙에서도 기대값이 같다 [계산 표 대입].
- S4 `submit_agent_draft`(`drafts/agent_drafts.py:188` [코드])가 파싱 직후·잠금 A와 서버 재확인(네트워크) **이전**에 제외 판정(DAR): 종료일(없으면 시작일) < 오늘 → `ended`, `venue_country == "not_kr"` → `overseas`. 오늘 = `timezone.localdate()`(Asia/Seoul [코드 `config/settings.py:389`]), 테스트용 `today` 키워드 인자.
- S5 해석 페이로드 최상위 `venue_country`(`kr`|`not_kr`|`unclear`) — `_REQUIRED_KEYS`에 넣지 않는다. 없거나 enum 밖이면 `unclear`(AIA 호환 권고). 저장하지 않는다.
- S6 제외는 새 도메인 예외 `AgentDraftExcludedError(reason)` → 뷰가 **200 `{"status": "excluded", "reason": "ended"|"overseas"}`**로 매핑. 4xx가 아니므로 러너가 실패로 세지 않는다(SRR F1 해소). DAR의 반환 튜플 확장안은 기각 — `(draft, created)` 계약을 쓰는 기존 호출처·테스트(H8)를 흔들지 않고, 이 뷰가 이미 도메인 예외→응답 매핑 관용구를 쓰기 때문 [코드 `drafts/runner_views.py:188-198`].
- S7 소스 후보 페이로드 `source_country`(`kr`|`not_kr`|`unclear`). `submit_candidate`(목록형)·`register_account_source`(계정형) 모두 `kr`이 아니면(없음 포함, D6 fail-closed) 네트워크 전에 `FailureStage.NOT_DOMESTIC`("not_domestic")으로 FAILED 후보 저장, DraftSource 미생성.
- 마이그레이션 두 파일(코치): `0010` AddField `events_excluded`(DF-03 사이클), `0011` AlterField `failure_stage` choices(DF-11 사이클).
- S8(D9) 새 서비스 `create_collected_draft_from_url(*, source_url, source_name="", today=None)`(`drafts/services.py`): `prepare_draft_from_url` → 제외 판정 → 제외면 `DraftCreationExcludedError(reason)` → `persist_prepared_draft`. 판정 순수 함수는 `drafts/extraction.py`에 둔다 — 한글 검사(제목+본문), `latest_mentioned_date(text)`(기존 `_parse_date_candidates` 재사용, 가장 늦은 날짜). 사유 `non_korean`·`ended`. 오늘 = `timezone.localdate()`.
- S9(D9) `decide_and_create_candidate`(`drafts/candidate_intake.py:40-74` [코드])가 `DraftCreationExcludedError`를 skip_key `excluded_non_korean`·`excluded_ended`로 옮긴다(fetch 예산은 소비 — 실제로 가져왔으므로). 호출자 2곳이 새 함수를 넘긴다: `drafts/management/commands/discover_drafts.py:196`, `drafts/candidate_validation.py:305`(승격 시 초기 드래프트, 상한 `INITIAL_DRAFTS_PER_PROMOTED_SOURCE = 5` [코드 `:30`]). 명령 `_summarize`·`_report`에 두 건수 추가 — 스태프 「지금 수집」 메시지는 stdout 전 줄을 잇기 때문에 자동 반영된다 [코드 `staff/views/__init__.py:335-339`].
- 스태프가 URL로 직접 추가하는 경로(`staff/views/draft_api.py:98·112` [코드], prepare/persist 직접 호출)는 필터를 적용하지 않는다 — 사람이 고른 URL이다.

**러너**
- R1 해석 프롬프트(`local_runner/caption_interpreter.py:15-77` [코드])에 `venue_country` 출력과 지시: 본문 언어와 무관하게 실제 개최지로 판정, 본문의 도시·국가·지점명 신호만 사용, 신호 없으면 `unclear`(추측 금지). 근거 인용 필드는 추가하지 않는다(AIA).
- R2 `_local_precheck`가 enum 밖 `venue_country`를 `unclear`로 정규화.
- R3 순수 함수 `exclusion_reason(*, interpreted, today)` → `"ended"`|`"overseas"`|`None`(caption_interpreter.py). 문자 일치 parity 가드는 두지 않는다(DAR — 서버가 최종 게이트인 품질 규칙).
- R4 오늘 = `datetime.now(ZoneInfo("Asia/Seoul")).date()` — 해석 프롬프트의 오늘 날짜와 R3에 같은 값(SRR F4). 현재 `date.today()` [코드 `local_runner/exploration_flow.py:60`].
- R5 `run_exploration_flow`: R3가 제외면 제출하지 않고 `events_excluded`를 올린다(실패 아님). 서버가 `{"status": "excluded"}`로 응답해도 `events_excluded`를 올린다. 요약에 `events_excluded` 추가.
- R6 탐색 프롬프트(`local_runner/claude_code_adapter.py:83-130` [코드]) 소스 스키마에 `source_country` + "수집처가 주로 다루는 행사의 개최지" 기준 지시. 흐름은 `source_country != "kr"`인 소스를 제출하지 않는다(D6).
- R7 `RunnerClient.complete`·`_process_run`이 `events_excluded` 전송.

## 명시적 제외

- 지역 어휘 확장(제주 등), 해외 행사 별도 노출, 실행 화면에 제외 건수 표시(D7 화면 부분).
- 서버 지오코딩·유료 API·도메인 국적 추정(비용 제약 [메모리 cost-constraint]). 서버에 `DRAFT_LLM_EXTRACTION_ENABLED`로 게이트된 LLM 추출 경로가 있으나 기본 비활성 [코드 `config/settings.py:262`, QVL] — 이번 필터는 그 경로를 켜지 않는다.
- `create_draft_from_fields`(`drafts/services.py`)에 규칙 추가 — `web/promotion.py:75` [코드] 사용자 제보 승격과 서버 수집이 공유하는 저장 함수(DAR).
- 스태프 URL 직접 추가 경로 필터(S9 마지막 항목).
- 서버 수집 경로의 지역 탐지 기반 해외 판정 — 규칙 추출기 지역 탐지는 서울·부산·인천 문자열뿐이라 쓰지 않고 D9 한글 규칙만 쓴다 [코드 `drafts/extraction.py:48-56`].
- 기존 드래프트·소스 데이터 소급 정리(D10 로컬 비활성화는 완료).

## 수용 기준

1. 서버 API에 `venue_country="not_kr"` 또는 종료일이 어제인 이벤트를 직접 제출하면 200 `excluded`, EventDraft 증가 없음.
2. 종료일 = 오늘은 제출된다(경계). 날짜 둘 다 없음·날짜 형식 불량·`venue_country` 없음/`unclear`/대소문자 다른 값은 제출된다.
3. 국내 어휘 밖 지역은 region 빈 값 + 메모에 원값(기존 Green 유지).
4. `source_country`가 `kr`이 아닌 목록형·계정형 후보는 FAILED(`not_domestic`, 실패 문구 포함)이고 DraftSource가 생기지 않는다. 네트워크 호출 없음.
5. 완료 요청의 세 건수가 저장되고, 비정수·bool은 400.
6. 러너 성공 보고 실행의 상태는 S3 결합 규칙을 따른다. 특히 후보 전부 승격 + 이벤트 실패 있음·생성 없음 → PARTIALLY_FAILED, 후보 없음 + 이벤트 전부 제외(실패 없음) → SUCCEEDED.
7. 러너는 제외 판정 이벤트·비국내 소스를 제출하지 않고, 제외는 실패가 아닌 제외로 센다. 러너 프로세스 시간대가 UTC여도 오늘 판정이 KST 기준.
8. 실기동 재현(수동, 로컬 claude CLI): 같은 검색어 재실행에서 해외·종료 드래프트 없음, 콜라보카페류 소스 미승격, 실행 기록 `events_excluded`가 제외 건수와 일치.
9. 서버 수집(`discover_drafts`)에서 한글이 없는 문서와 본문의 가장 늦은 날짜가 어제인 문서는 드래프트가 생기지 않고, 명령 보고와 스태프 「지금 수집」 메시지에 사유별 제외 건수가 나온다. 미래 날짜가 하나라도 있거나 날짜가 없는 한글 문서는 생성된다.
10. 후보 승격 시 초기 드래프트 생성도 9와 같은 규칙을 따른다.
11. 스태프 URL 직접 추가는 한글 없는·지난 날짜 문서도 기존대로 생성된다.

## Domain Boundary and Dependency Direction

- 이벤트 제외 판정 소유 = `drafts.agent_drafts.submit_agent_draft`(러너 제출 전용 오케스트레이션). 소스 제외 = `drafts.candidate_validation`의 두 진입 함수. 실행 상태·건수 = `drafts.discovery_runs.complete_run`. HTTP 매핑 = `drafts.runner_views`.
- 서버 수집 필터 소유 = `drafts.services.create_collected_draft_from_url`(수집 전용 생성 서비스), 판정 순수 함수 = `drafts.extraction`, 결과 → skip 사유 매핑 = `drafts.candidate_intake`. 수집 명령·후보 승격은 이 함수를 넘기기만 한다.
- 새 의존 없음. `local_runner`는 계속 Django·서버 모듈 비의존(`tests/local_runner/test_local_runner_isolation.py` 유지). `tests/core/test_architecture_boundaries.py`의 candidate_validation·discovery_runs·candidate_intake 임포트 가드와 "candidate_validation에 `create_draft_from_fields` 문자열 금지" 가드 유지(새 함수 이름은 그 문자열을 포함하지 않는다).

## Coupling and Cohesion Review

- `parse_agent_draft_payload`는 "정정만 하는 파서" 계약 유지(DAR) — 제외는 그 밖(submit)에서.
- 제외 판정은 서버 `_exclusion_reason`, 러너 `exclusion_reason`, 서버 수집 판정 순수 함수로 한정. 짧은 날짜 비교 로직의 복제는 허용하고 공용 모듈·parity 가드는 신설하지 않는다.
- 제외 사유 enum은 러너 경로 `ended`·`overseas`, 서버 수집 경로 `non_korean`·`ended`만 — 확장 대비 추상화 없음.
- 기존 `create_draft_from_url`에 필터를 넣는 안은 기각: 한글 없는 픽스처로 이 함수를 직접 부르는 서비스 테스트 호출 19곳의 의미가 바뀐다 [실측 rg `create_draft_from_url\(` docstring 제외 — `test_drafts_services.py` 6·`test_drafts_services_llm_flag.py` 6·`test_draft_service_errors.py` 7; 초안의 "20곳"은 `test_drafts_services.py:382` docstring을 센 오류, DAR 정정]. 새 함수는 수집 호출자 2곳과 그 테스트의 monkeypatch 대상 문자열만 바꾼다.
- 전환 후 `create_draft_from_url`의 운영 코드 호출처는 없어진다 [계산 호출자 2곳 모두 전환, DAR rg 확인]. 그래도 **삭제하지 않는다** — fetch·추출 실패·LLM 플래그 분기·중복 매핑을 필터와 무관하게 고정하는 테스트 단위다(DAR). Deferred 참고.
- S3 결합 규칙은 `drafts/discovery_runs.py` 안 이름 붙은 순수 함수로 뽑는 것을 DAR이 권고하나 강제하지 않는다 — 코치의 Refactor 단계 재량. 새 파일·모듈 없음.
- 아키텍처 가드는 원문 텍스트 검사다: `candidate_validation.py`에는 주석에서도 `create_draft_from_fields` 문자열을 쓰지 않는다 [코드 `tests/core/test_architecture_boundaries.py:426-432`].

## Pythonic Code Design

- 도메인 예외 → 뷰 매핑은 기존 관용구(`EventLimitExceededError` 등) 복사.
- `today`는 키워드 인자(기본 None → 내부에서 계산)로 시간 주입 — 시계 고정 라이브러리 도입 없음(저장소 관행 `date.today() ± timedelta` [코드 코치 보고, `tests/staff/test_staff_event_inline_actions.py`]).
- 타입 검사는 `isinstance(v, int) and not isinstance(v, bool)`(선례 `drafts/agent_drafts.py:104-108` [코드]).

## TDD Checkpoints (Backend TDD Coach 계약 — 착수 시 코치가 순서·양식 재확정)

한 번에 하나. 표적 명령으로 Red 사유 확인 → 최소 Green → 관련 스위트. 실행·판정은 오케스트레이터 단독([메모리 pytest-single-runner-delegation]).

**사이클 순서(코치 확정, 2026-09-15)**: S1(DF-01·02) → S2 + 마이그레이션 `0010`(DF-03) → S3(DF-04·22) → [정비 커밋] 절대 날짜 픽스처 상대화 → S4(DF-05·06·07·08·09·23·24) → S5·S6(DF-10) → [정비 커밋] `source_country` 공유 픽스처 → S7 + 마이그레이션 `0011`(DF-11·12) → R1~R4(DF-13·14·15·21) → R5(DF-16·17, 요약 dict 단언 갱신 포함) → R6(DF-18·19) → R7(DF-20, 대역 시그니처 갱신 포함) → DF-25 → S8(DF-26a·26b·27) → S9(DF-28a·28b·29, monkeypatch 문자열 갱신 포함) → DF-30 회귀 확인.

**코치·검증 반영 규칙**
- 마이그레이션은 **두 파일**: `events_excluded` 컬럼은 DF-03 Green에서 바로 만들지 않으면 테스트 DB에 컬럼이 없어 `SourceDiscoveryRun`을 쓰는 테스트 전체가 깨진다(`pytest.ini`에 `--no-migrations` 없음 [코드]). `failure_stage` choices는 DF-11 Green에서 `0011`. 브랜치 미배포라 합칠 필요 없음.
- 정비 배치: 절대 날짜 상대화·`source_country` 공유 픽스처는 동작 변경 없는 독립 커밋(같은 테스트·같은 결과가 증거). `FAILURE_MESSAGES["not_domestic"]`은 DF-11 Green 안(프로덕션 변경은 실패 테스트 뒤). 요약 dict 단언(R5)·대역 `complete` 시그니처(R7)·monkeypatch 문자열(S9)은 그 변경을 일으키는 사이클의 Green 안.
- 한 parametrize에 여러 id를 미리 적어도 **id 하나씩** Red 확인 → 최소 Green → 다음 id.
- DF-04는 신규 하위 케이스 2개(실패 없음·생성 없음 → SUCCEEDED / 실패 없음·생성 있음 → SUCCEEDED)만 추가한다. "실패 있음·생성 있음 → PARTIALLY_FAILED"는 기존 `_setup_일부_생성`이 이미 고정 [코드 `tests/drafts/test_discovery_runs.py:318-331`] — 새로 쓰지 않는다. 기존 후보 없음 파라미터 3종(생성_0건·일부_생성·상한_초과_보고)은 결합 규칙에서도 기대값 불변 [코드 `:308-361` 대입].
- 가짜 Green 뮤테이션: DF-07 = "날짜 없으면 건너뜀" 분기를 지워 Red 확인 / DF-09 = 조건을 `!= "kr"`로 바꿔 Red 확인(D5 방어선) / DF-24 = **값은 `"NOT_KR"`·`" not_kr "`**(초안의 `"KR"`·`" kr "`는 어떤 정규화 버그로도 `not_kr`이 되지 않아 뮤테이션이 걸리지 않는다), `.strip().lower()` 정규화를 심어 Red 확인.
- DF-30은 새 테스트 불필요 — 스태프 URL 추가 테스트가 이미 한글 없는 픽스처("Sample Event")를 쓴다 [코드 `tests/staff/test_staff_draft_api.py:38`, `tests/staff/test_staff_draft_api_audit.py:35`]. 뮤테이션: 스태프 뷰 호출을 수집 전용 함수로 바꿔 Red 확인 후 복원.
- DF-26 분할: 26a `latest_mentioned_date`(첫 서버 수집 계약), 26b 한글 포함 판정. DF-28 분할: 28a `decide_and_create_candidate`의 제외 예외 → skip_key·예산 소비(unit, 콜러블 스텁), 28b 명령 보고 집계(domain). DF-27은 `fetch_html`만 스텁(`prepare_draft_from_url` 대역 금지).

서버 수집 첫 계약(코치 작성): DF-26a `본문에_날짜가_여러_개_있으면_가장_늦은_날짜를_반환한다` / Given 본문에 2026-09-10·2026-09-20 / Then `date(2026, 9, 20)` / Red 사유 = 함수 부재 ImportError / 최소 Green = `max(_parse_date_candidates(text), default=None)` / Refactoring allowed: No / `uv run pytest -q tests/drafts/test_draft_extraction.py -k 본문에_날짜가_여러_개_있으면_가장_늦은_날짜를_반환한다`.

| ID | 경계 | 파일(기존에 추가) | 핵심 행위 | Red 위험 |
|---|---|---|---|---|
| DF-00 | — | `tests/drafts/test_agent_drafts.py:123` [코드] | 국내 어휘 밖 지역 = 빈 값+원값 메모 | **이미 Green — 새 테스트 없음**(코치) |
| DF-01 | web | `tests/drafts/test_discovery_runner_api.py` | 완료 요청의 attempted 5·failed 2 [계산 코치 예시값]가 저장 | 0이 아닌 값 필수(가짜 Green 방지) |
| DF-02 | web | 같은 파일 | 비정수·bool 건수 → 400 | 문자열은 현재 500 [실측 `min('x', 20)` TypeError] |
| DF-03 | domain+web | `tests/drafts/test_discovery_runs.py`, runner_api | `events_excluded` 저장(마이그레이션 생성) | — |
| DF-04 | domain | `tests/drafts/test_discovery_runs.py` | 후보 없음·실패 없음·생성 없음 → SUCCEEDED / 실패 없음·생성 있음 → SUCCEEDED / 실패 있음·생성 있음 → PARTIALLY_FAILED | 기존 `:309` [코드] 전부 실패 → FAILED 유지 확인 |
| DF-05 | domain | `tests/drafts/test_agent_drafts.py` | 종료일 어제 → 제외, EventDraft 불변 | 부재 단언 → 뮤테이션 증거 |
| DF-06 | domain | 같은 파일 | 시작일만 있고 어제 → 제외 | — |
| DF-07 | domain | 같은 파일 | 종료일 오늘 / 날짜 없음 → 생성 | 날짜 없음은 이미 Green 가능 → 뮤테이션 |
| DF-08 | domain | 같은 파일 | `venue_country=not_kr` → 제외, 서버 재확인 fetch 미호출 | 뮤테이션 |
| DF-09 | domain | 같은 파일 | `venue_country` 없음·`unclear`·enum 밖 → 생성 | 이미 Green 가능 → 뮤테이션 |
| DF-10 | web | `tests/drafts/test_runner_draft_api.py` | 제외 → 200 `excluded`+reason | — |
| DF-11 | domain | `tests/drafts/test_candidate_validation.py` | 목록형 `source_country` kr 아님/없음 → FAILED `not_domestic`, fetch 미호출, DraftSource 없음 | 뮤테이션 |
| DF-12 | domain | 같은 파일 | 계정형 동일 | 뮤테이션 |
| DF-13 | unit | `tests/local_runner/test_caption_interpreter.py` | 해석 프롬프트에 `venue_country` 스키마·언어 무관 지시 | — |
| DF-14 | unit | 같은 파일 | `_local_precheck`가 enum 밖 → `unclear` | — |
| DF-15 | unit | 같은 파일 | `exclusion_reason` 표(ended·overseas·오늘 경계·날짜 없음·unclear) | — |
| DF-16 | unit | `tests/local_runner/test_exploration_flow.py` | 러너 제외 이벤트 미제출 + 요약 `events_excluded` | 대역 호출 기록 선확인 뮤테이션 |
| DF-17 | unit | 같은 파일 | 서버 `excluded` 응답 → excluded로 집계, failed 아님 | — |
| DF-18 | unit | 같은 파일 | `source_country != kr` 소스 미제출 | 뮤테이션 |
| DF-19 | unit | `tests/local_runner/test_claude_code_adapter.py` | 탐색 프롬프트 소스 스키마에 `source_country` | 기존 `ended` 지시 단언(이 테스트 파일 `:162` [코드] `for reason in ...`)은 재검증 대상 아님 |
| DF-20 | unit | `tests/local_runner/test_runner_loop.py` | 완료 보고에 `events_excluded` 전송(대역 없이 client 경유 계약 포함 — 트랙 30 교훈) | 기존 대역 complete 시그니처 갱신 [실측 rg `:77·195·269·317`] |
| DF-21 | unit | `tests/local_runner/test_exploration_flow.py` 또는 caption_interpreter | 오늘 = KST(프로세스 TZ=UTC에서도) | — |
| DF-22 | domain | `tests/drafts/test_discovery_runs.py` | S3 결합 규칙: 후보 전부 승격+이벤트 실패·생성 없음 → PARTIALLY_FAILED / 후보 전부 실패+이벤트 정상 → PARTIALLY_FAILED / 후보 전부 실패+이벤트 실패·생성 없음 → FAILED / 후보 혼합+이벤트 정상 → PARTIALLY_FAILED | 기존 파라미터 4종·`:309` [코드] 기대값 불변 확인 |
| DF-23 | domain | `tests/drafts/test_agent_drafts.py` | 날짜 형식 불량 → 제외하지 않고 생성 / 종료일만 있고 어제 → 제외 | — |
| DF-24 | domain | 같은 파일 | `venue_country` "NOT_KR"·" not_kr " → `unclear` 취급으로 생성(대소문자·공백 정규화 금지) | 이미 Green 가능 → 정규화 심기 뮤테이션 |
| DF-25 | unit | `tests/local_runner/test_exploration_flow.py` | 제출 응답에 `status`가 없거나 다른 값 → excluded로 세지 않는다 | — |
| DF-26 | unit | `tests/drafts/test_draft_extraction.py` | `latest_mentioned_date`(여러 날짜 중 최댓값·날짜 없음 None·무효 날짜 건너뜀), 한글 포함 판정 | — |
| DF-27 | domain | `tests/drafts/test_drafts_services.py` | `create_collected_draft_from_url`: 한글 없음 → `non_korean`, 가장 늦은 날짜 어제 → `ended`, 과거·미래 섞임·날짜 없음·오늘 → 생성 | 부재 단언 → 뮤테이션 |
| DF-28 | domain | `tests/drafts/test_discover_drafts_command.py` | `decide_and_create_candidate`가 제외 예외를 skip_key로 옮기고 fetch 예산을 소비, 명령 보고에 두 제외 건수 | — |
| DF-29 | domain | `tests/drafts/test_candidate_validation.py` | 후보 승격 시 초기 드래프트가 새 함수를 거쳐 제외 규칙 적용 | — |
| DF-30 | web | 기존 스태프 드래프트 URL 추가 테스트(착수 시 rg로 파일 확정) | 필터 미적용 — 새 테스트 없음, 기존 스위트 통과가 증거 | — |

## 기존 테스트 선행 정비 (QVL 반영)

- `tests/drafts/test_candidate_validation.py` 공유 픽스처 `_valid_payload`(`:69`)·`_account_payload`(`:880`)에 `"source_country": "kr"` 추가 — 두 픽스처 호출 31곳 [실측 rg, 정의 2줄 제외 — 초안 33은 정의 포함 오류, 코치 정정]. DF-11 사이클 첫 단계에서 먼저 반영하지 않으면 기존 후보 테스트 대부분이 `not_domestic`으로 먼저 실패한다.
- `drafts/candidate_validation.py` `FAILURE_MESSAGES`(`:42-51` [코드])에 `not_domestic` 문구 추가 — 없으면 `_save_failed_candidate`의 `FAILURE_MESSAGES[stage]`(`:134` [코드])가 KeyError.
- 절대 날짜 `2026-09-22` 픽스처를 오늘 기준 상대 날짜로 전환: `tests/drafts/test_agent_drafts.py:271-272·316-317`, `tests/drafts/test_runner_draft_api.py:71-72` [실측 rg]. S4 도입 전에는 통과하지만 도입 후 2026-09-23부터 제외돼 깨진다 — S4 사이클에서 먼저 전환.
- 러너 요약 dict 동등 단언 `tests/local_runner/test_exploration_flow.py:157·516` [실측 QVL 원문 확인]과 대역 `complete` 시그니처 `tests/local_runner/test_runner_loop.py:77·195·269·317` [실측 rg] — R5·R7 사이클에서 갱신.
- S9 호출자 전환에 따른 monkeypatch 대상 문자열 갱신: `tests/drafts/test_discover_drafts_command.py`(이름 등장 22줄), `tests/drafts/test_candidate_validation.py`(8줄) [실측 rg -c].

첫 계약(코치 작성): DF-01 `완료_요청이_보낸_시도_실패_건수가_실행에_그대로_저장된다` / Red 사유 = 뷰가 두 키를 읽지 않아 기본값 저장 / 최소 Green = 뷰가 두 값을 읽어 전달 / Refactoring allowed: No / `uv run pytest -q tests/drafts/test_discovery_runner_api.py -k 완료_요청이_보낸_시도_실패_건수가_실행에_그대로_저장된다`.

## 파일 목록

- 서버: `drafts/runner_views.py`, `drafts/discovery_runs.py`, `drafts/models.py`, `drafts/migrations/0010_*.py`·`0011_*.py`(생성), `drafts/agent_drafts.py`, `drafts/candidate_validation.py`, `drafts/services.py`, `drafts/extraction.py`, `drafts/candidate_intake.py`, `drafts/management/commands/discover_drafts.py`
- 테스트(서버 수집 추가분): `tests/drafts/test_draft_extraction.py`, `tests/drafts/test_drafts_services.py`, `tests/drafts/test_discover_drafts_command.py` — 모두 기존 파일
- 러너: `local_runner/caption_interpreter.py`, `local_runner/exploration_flow.py`, `local_runner/claude_code_adapter.py`, `local_runner/client.py`, `local_runner/runner.py`
- 테스트: 위 표의 기존 파일들(신규 파일 없음)
- 문서: `docs/BE/draft-source-agent-discovery.md`(제외 규칙·"오늘" KST·호환 규칙·상태 규칙), `docs/backlog.md`(현재 상태 한 줄)

## 검증 명령과 기대 증거

- 사이클별 표적 명령 Red→Green, 부재 단언 시나리오는 수정 되돌리기 뮤테이션 Red 확인.
- `uv run pytest -q tests/drafts tests/local_runner` → 실패 없음.
- `uv run python manage.py check` 이슈 없음, `uv run python manage.py makemigrations --check --dry-run` 무변경(0010·0011 생성 후).
- `uv run pytest -q` → 실패 없음, 증가분 = 신규 테스트 수 [계산] (착수 시 재측정 기준선 대비).
- 수동 실기동(수용 기준 8): 러너 토큰으로 서버·러너 기동 → 같은 검색어 실행 → 드래프트·후보·`events_excluded` 조회. 개발 DB 변경은 검증 후 원복 여부 사용자 확인.

## Evidence [실측 2026-09-16, 브랜치 `feat/domestic-active-draft-filter`]

- 전체 회귀 `uv run pytest -q` → **2900 passed / 10 deselected / 90.51초**(기준선 2826 대비 +74). `manage.py check` 이슈 0건, `makemigrations --check --dry-run` 무변경.
- 마이그레이션 2개: `0010_sourcediscoveryrun_events_excluded`(AddField), `0011_alter_sourcecandidate_failure_stage`(AlterField choices).
- 사이클마다 Red 사유 확인 후 최소 Green. 이미-Green 위험 시나리오(개최지 불확실 5종)는 뮤테이션으로 증거 확보 — 조건을 `!= "kr"`로 바꾸면 5건 실패, `.strip().lower()` 정규화를 넣으면 2건 실패, 복원 후 41 passed [실측].
- 계획과 다르게 드러난 것 3건: ① 러너가 빈 값·형식 불량 날짜를 보내면 저장 시점에 예외가 나던 기존 결함을 같은 사이클에서 정정(보고 후 수정) ② 소스 필터 초안이 국가 키 없음을 통과시켜 결정(D6)대로 좁힘 ③ 수집 함수 전환으로 기존 대역 25곳(명령 21·승격 4)이 실제 함수를 태워, 계획서 "선행 정비" 항목대로 대상만 이동 [실측 rg].
- 실기동 재현(수용 기준 8) [실측 2026-09-16 15:43~15:44, 실행 14, 검색어 "하츠네 미쿠 팝업스토어"]: 상태 `partially_failed`, 시도 8건·실패 4건·**제외 1건**. 드래프트 2건 모두 국내(서울 홍대 팝업)이고 해외·종료 건 0건. 승격 후보 3건은 전부 계정형이라 비활성 등록, 활성 소스는 `코믹월드 공지` 1개 그대로. 읽기 8건은 전부 HTTP 200이었고 실패 4건은 캡션·해석 실패(러너가 상태코드 외 원문을 남기지 않음), 나머지 1건은 해석이 "행사 아님"으로 판단해 실패·제외 어디에도 세지 않는 기존 경로 [코드 `local_runner/exploration_flow.py:153-154`].
- 실기동이 잡은 것: 개발 DB에 마이그레이션을 적용하지 않은 채 서버를 띄우면 `claim`이 500(`column drafts_sourcediscoveryrun.events_excluded does not exist`) [실측]. 테스트 DB는 매번 마이그레이션을 적용해 회귀에서는 드러나지 않는 종류다 — 배포 시 마이그레이션 선행이 필요하다.
- **재검토 후 재측정 [실측 2026-09-16 16:35]**: 전체 회귀 `uv run pytest -q` → **2905 passed / 10 deselected / 81.47초**(재검토 전 2900 대비 +5 = DF-02 파라미터 4케이스 + DF-21 1건 [계산], main 기준선 2826 대비 +79 [계산]). `manage.py check` 이슈 0건, `makemigrations --check --dry-run` 무변경. 뮤테이션: 완료 뷰 검사 루프에서 `events_excluded`를 빼면 그 필드 4케이스만 실패(8건 통과) / `_today_kst`를 `ZoneInfo("UTC")`로 바꾸면 KST 테스트 1건 실패, 둘 다 원복 후 `git diff --quiet` clean [실측]. 표적 스위트(편집 파일 + 아키텍처·격리·로깅 가드) 188 passed [실측]. 재검토 수정 커밋 3개(fix·test·docs) 푸시.
- **머지 완료 [실측 gh 2026-09-16 07:52Z]**: 사용자 "머지 승인" → PR #370 merge commit `ed95a91f`, 커밋 24개. main 재측정 `uv run pytest -q` → 2905 passed / 10 deselected / 84.29초 [실측], `check` 0 issues, `makemigrations --check` 무변경, main CI run 35070765683 success. `docs/pr-log.md` 롤링 + 백로그 행 머지 완료 반영은 docs PR(브랜치 `docs/pr-log-370`)로 올림 — 머지는 사용자 승인. 자동 deploy PR #371(main → production) 오픈 상태(사용자 결정).

## 커밋 계획

사이클별 커밋(테스트+구현) — 서버 S1~S7, 러너 R1~R7 의미 단위, 마이그레이션은 도입 사이클 커밋에 포함, 문서 커밋 별도. `git add -A` 금지(prompt_plan.md 미스테이징). 검증 후 커밋·푸시·PR 자동, 머지는 사용자 승인.

## 호환 규칙 (배포 순서 무관)

- 구 러너 → 신 서버: `venue_country` 없음 = `unclear`(제출), `events_excluded` 없음 = 기본값, **`source_country` 없음 = 소스 제외**(D6 fail-closed — 구 러너가 제출한 소스는 전부 FAILED. 러너는 사용자 본인 맥이라 같은 시점 갱신).
- 신 러너 → 구 서버: 서버가 모르는 키는 무시, 제외 판정은 러너가 이미 수행.

## 문서 대상 / 핸드오프

- `docs/BE/draft-source-agent-discovery.md`: Guardrail — 제외는 4xx가 아니라 200 excluded(러너 실패 집계 오염 방지), 국내 판정은 서버가 재검증할 수 없는 러너 필드(불확실=행사 제출·소스 제외 비대칭의 이유), "오늘"은 양쪽 KST, 러너 성공 보고 실행의 결합 상태 규칙.
- 같은 문서(서버 수집 절): 수집 전용 생성 함수만 한글·가장 늦은 날짜 필터를 적용하고 스태프 URL 직접 추가는 적용하지 않는 이유(사람이 고른 URL), 규칙 추출기의 시작·종료일은 게시일이 섞여 종료 판정에 쓰지 않는다는 실측 근거.
- `docs/backlog.md`: 현재 상태 한 줄.

## 재검토 기록 (머지 전, 2026-09-16 — 사용자 요청 "머지 전에 기능 재검토")

DAR·QVL·SRR·AIA·PSO 읽기 전용 검토 + 오케스트레이터 원문 대조(인용 행 번호 전부 일치 [실측 sed]). 차단 결함 없음. 같은 트랙에서 수정한 항목(2026-08-25 상시 결정):

1. 죽은 임포트 2곳 [실측 rg](`drafts/candidate_validation.py`, `drafts/management/commands/discover_drafts.py`)과 "monkeypatch 대상 테스트가 있어 남긴다"는 거짓 주석 — `rg -n "setattr\([^)]*create_draft_from_url"` 저장소 전체 0건 [실측]. 오케스트레이터 선행 발견, DAR 결함 확정 → 제거.
2. 함수 전환 때 이름만 남은 낡은 docstring 3곳 [실측 rg](위 명령 모듈 docstring, `tests/drafts/test_discover_drafts_command.py`, `tests/core/test_architecture_boundaries.py`) — QVL·DAR → 정정.
3. **절차 결함**: DF-21(오늘=KST) 테스트가 Test List에 Deferred 표기 없이 빠져 있었다(QVL 발견, R1~R4 사이클 커밋에 DF-21 없음 [실측 git log]) → 흐름 공개 경계 테스트 신설(가짜 `datetime.now`로 UTC 15:30 = KST 다음 날 0:30 순간을 고정).
4. DF-02 완료 뷰 400 파라미터에 `events_excluded` 누락(QVL) → 추가, 이미-Green이라 뮤테이션 증거.
5. 문서: `docs/backlog.md` 트랙 33 행이 "PR 미생성·실기동 미확인"으로 사실과 어긋남(PSO 결함, 오케스트레이터 선행 발견) → 정정. 두 경로 판정 축 비대칭(러너=개최지·종료일, 서버 수집=한글·가장 늦은 날짜)과 잔여 오탐·미탐이 문서에 없음(PSO 권고) → `docs/BE/draft-source-agent-discovery.md` 소절 추가. PR 본문에 소급 정리 없음·entrypoint 마이그레이션 선행 사실 추가.

검토했으나 결함 아님: `venue_country`·`source_country` 비문자열 타입은 `==`/`!=` 비교라 예외 없이 통과/제외(SRR) / 200 excluded 응답은 서버 enum만 노출(SRR) / 제외 판정이 SNS 무fetch·`validate_fetch_url` 이전(SRR) / 프롬프트 최상위 `venue_country` 위치 = 러너 정규화 = 서버 소비 지점(AIA) / `candidate_intake → services`는 기존 허용 방향(DAR) / `docker/entrypoint.sh`가 기본값(`RUN_DB_MIGRATIONS=true`)으로 기동마다 `migrate --noinput`을 gunicorn 앞에 실행하므로 PR 본문 "배포 시 주의"는 이미 절차로 덮인다 [코드] / 서버 수집 "가장 늦은 날짜" 규칙을 로컬 DB의 한글 포함 서버 수집 드래프트 33건에 대입하면 종료 제외 0건, 한글 형식(년월일) 날짜가 숫자 형식보다 늦은 건 0건 [실측 2026-09-16 shell] — `DATE_PATTERN`이 "년월일" 형식을 못 읽어 게시일이 늦은 날짜로 잡히는 오제외 위험은 현재 데이터에서는 관측되지 않음.

## Deferred

- 탐색 단계 `is_event`·`why_excluded` 미소비(정정 7) — 트리거: 해석 호출 비용 문제 실측.
- 운영 호출처가 없어진 `create_draft_from_url` 정리(DAR) — 트리거: 이 함수를 직접 겨냥하는 서비스 테스트가 모두 `create_collected_draft_from_url` 테스트로 흡수되는 시점.
- 계정형 소스의 국내 판정 서버 백스톱 부재(DAR) — 트리거: 해외 계정 등록 실사례.
- 국내 판정 원문 대조 앞단 필터(SRR 이연 강화) — 트리거: 판정 조작 의심 사례.
- 실행 화면 제외 건수 표시(D7 화면) — 트리거: 스태프 요청.
- (재검토 추가) 목록형 소스 국내 판정 서버 백스톱 부재(AIA — 계정형 항목과 대칭. 목록형은 승격 시 `enabled=True`라 오판 영향이 더 크다 [코드 `drafts/candidate_validation.py`]) — 트리거: 해외 목록형 소스 승격 실사례.
- (재검토 추가) 해석 프롬프트에 온라인 전용 행사의 `venue_country` 지시 없음(AIA) — 트리거: 온라인 행사 오제외 실사례.
- (재검토 추가) 탐색 프롬프트 `source_country` 판정 신호 문구 보강(AIA) — 트리거: 실기동에서 국내 목록형 소스가 unclear로 반복 누락.
- (재검토 추가) `EXCLUDED_REASON_TO_SKIP_KEY[exc.reason]` 기본값 부재(SRR, 현재 두 사유만 발생해 도달 불가) — 트리거: 새 제외 사유 추가.
- (재검토 추가) `events_excluded`를 `events_attempted` 상한으로 클램프(SRR — 지금은 `MAX_EVENTS_PER_RUN`까지만) — 트리거: D7 화면 표시 도입.
- (재검토 추가) 제출 뷰 2곳 [코드](`RunnerCandidateSubmitView`·`RunnerEventDraftSubmitView`)이 `SourceDiscoveryRun.DoesNotExist`를 잡지 않아 존재하지 않는 run_id에 500(SRR, 기존 결함 — 완료 뷰만 404). 제외 판정이 잠금 A 앞에 있어(S4 설계) 제외 페이로드는 같은 run_id·무효 임대에도 200이 돌아가는 비일관 포함 — 트리거: 러너 API 다음 트랙.
- (재검토 추가) 개최지·국적·날짜 필드 비문자열 타입 방어 테스트(SRR 권고, 코드는 안전) — 트리거: 러너 페이로드 스키마 변경.
- (재검토 추가) 서버 수집 `DATE_PATTERN`에 "년월일" 형식 미대응 — 현재 데이터 오제외 0건이라 보류 — 트리거: 한글 형식 날짜만 있는 페이지의 오제외 실사례.

---

