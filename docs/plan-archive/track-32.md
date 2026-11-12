# 트랙 32: DB 락·트랜잭션 검수 결함 수정 (2026-09-14) [v1 — 검수 4역할(DAR·SRR·DOR·QVL) + TDD 코치 반영, **사용자 승인 완료(2026-09-14 "승인")**]

> **위치**: 2026-09-14 검토 전용 검수("DB 락과 트랜잭션 검수")가 실측으로 확정한 결함을 고치는 트랙. 검수 결과·정정 기록은 메모리 `db-lock-transaction-audit-2026-09-14`가 정본이며 아래는 계획에 필요한 부분만 옮겼다.
> **기준선** [실측 2026-09-14, 브랜치 `fix/db-lock-transaction-audit` HEAD `6da333a0`]: `uv run pytest -q` → **2816 passed / 10 deselected / 85.40초**, `check` 0 issues, `makemigrations --check --dry-run` 무변경.
> **브랜치·PR**: `core/categories.py`가 `origin/main`에 없으므로(카테고리 어휘 PR #365 미머지 [실측 `git cat-file -e`]) 현재 HEAD(`fix/site-wide-interaction-audit`, PR #366) 위에 스택한다. PR base는 `fix/site-wide-interaction-audit`, #366 머지 후 main으로 재지정.

## 정정 기록 (검수 단계)

오케스트레이터 오류 [계산 4건]과 검토 역할 오류 [계산 4건]을 남긴다 — 본문은 정정된 값을 쓴다.

1. 브리프 "운영 DB=Render Postgres" → **Supabase Session pooler** [문서 `docs/deploy-runbook.md:18-25`].
2. "감사 로그 FK 선삽입 → FOR UPDATE 교착" 단언 **철회**: Django FK는 `DEFERRABLE INITIALLY DEFERRED`라 FOR KEY SHARE가 커밋 시점에 잡힌다 [실측 `pg_constraint` staff_staffactionlog FK 5건 중 5건 condeferred]. 2커넥션 실측은 교착 없이 늦은 쪽 `Event.DoesNotExist`.
3. 세이브포인트 부재 시 예외는 PG InternalError가 아니라 `Model.save()`의 mark_for_rollback_on_error → `TransactionManagementError` [실측]; 마지막 문장이면 예외 없이 세이브포인트 롤백 [실측].
4. `core/categories.py` 인용 행 52-59 → **55-62** [코드].
5. DAR·DOR가 교착을 "성립"으로 유지 → 실측으로 기각. QVL "update_collection_item은 이미지 저장 아님" → 실측(spy) 기각. SRR "상태 PATCH는 기록된 결정" → 해당 가드레일은 순서·위치 보류이지 원자성 보류가 아니라 결함 유지. TDD 코치 "`staff_event_delete` def 663행" → **665행** [실측 `rg -n`].

## Activated Roles / Not Activated

| 역할 | 활성 | 사유 |
|---|---|---|
| Backend TDD Coach | ✅ | 백엔드 동작 변경 — Test List 9건 [계산] 확정, 첫 계약 H1-a |
| Backend & Integration Engineer | ✅ | 테스트·구현·문서 편집 |
| Quality Verification Lead | ✅ | 최종 증거 대조(검수 단계 산출 계승) |
| Domain Architecture Reviewer | ✅(검수 단계 완료) | 트랜잭션 경계·세이브포인트 규율·감사 로그 계약 판정 산출 완료, 구현 후 재검토는 QVL에 위임 |
| Security & Resilience Reviewer | ✅(검수 단계 완료) | 수용 기준 4건 산출 완료 |
| Deployment & Operations Reviewer | ✅(검수 단계 완료) | 관측 공백·타임아웃 부재 판정 완료, 이 트랙은 설정·마이그레이션 변경 0건 |
| Product Scope Owner | ❌ | 사용자가 결함 목록을 승인, 제품 판단 없음. 스로틀 한도 30/minute은 create 스코프와 같은 근거의 기본값(가정) |
| Web Experience Designer / Browser Interaction Reviewer / Frontend Implementation Engineer | ❌ | 템플릿·CSS·JS 변경 0건 |
| AI Automation Architect | ❌ | LLM 범위 0건 |

## 승인 범위 — 결함 7건 [계산]

| ID | 위치 [코드] | 결함(실측 재현) | 최소 수정 |
|---|---|---|---|
| H1 | `core/categories.py:55-62` | 재획득 분기가 `category.save()` IntegrityError를 세이브포인트 없이 삼킴. 생성/재게시/승인 경로는 다음 쿼리 `TransactionManagementError` 500·전체 롤백; 삭제 경로(`staff/services.py:56-72`)는 예외 없이 이벤트 잔존 + EVENT_DELETE 로그만 커밋 | 재획득 두 줄만 `with transaction.atomic():`로 감싼다(관용구 `core/analytics.py:94`, `staff/views/categories.py:129`) |
| H2' | `staff/views/events.py:665-722` | 동시 삭제 늦은 쪽이 `delete_event`의 `select_for_update().get()`에서 `Event.DoesNotExist` → 미포착 500 | atomic 첫 문장에서 `get_object_or_404(Event.objects.select_for_update(), pk=pk)`로 잠근 뒤 로그 → `delete_event`(`:607-610` toggle 관용구) → 늦은 쪽 404 |
| H3 | `archive/services.py:207·249·273` | `mark_visited`·`mark_missed`·`revert_to_planned`가 atomic 없이 save → `_record_activity` | 세 함수의 save~`_record_activity`만 `transaction.atomic()`으로 감싼다. `record_event` 순서·위치 불변(가드레일 `docs/BE/visit-completion-concurrency.md` Guardrail) |
| H4 | `staff/views/discovery.py:76·87` | `create_run`과 감사 로그가 별도 autocommit | 두 호출을 하나의 `with transaction.atomic():`로. except 분기 불변 |
| H8 | `drafts/agent_drafts.py:207-218`, `drafts/runner_views.py:189-199` | `DraftCreationDuplicateError` 미포착 → 러너에 500 | `submit_agent_draft`에서 잡아 기존 행 재조회 후 `(existing, False)` 반환(뷰 불변) |
| H7 | `staff/views/home_categories.py:21·40-41` | HomeConfig 락 없는 전체 save → 마지막 쓰기 승리 | POST atomic 안 `HomeConfig.objects.select_for_update().get(pk=config.pk)` 재조회 후 저장(`staff/views/categories.py:241-247` 관용구) |
| T1 | `archive/views.py:681`, `config/settings.py:584-593` | `CollectionItemDetailView` PATCH·DELETE 스로틀 없음(POST는 30/minute) | `throttle_scope = "collection_item_update"` + `get_throttles`(PATCH·DELETE만), `DEFAULT_THROTTLE_RATES`에 `"collection_item_update": "30/minute"` |

함께 고치는 문서 수치: `README.md:133` "select_for_update 9개 파일"은 낡은 값 — 호출 파일 **10개** [실측 `rg -n 'select_for_update\(' --glob '!tests/**'` 주석 제외]. 같은 커밋에서 원문을 사전 측정 기록으로 남기고 정정한다(AGENTS.md Numbers In Documents).

## 명시적 제외

- **H5** 사진 업로드·컬렉션 이미지 교체의 저장소 쓰기가 FOR UPDATE 안에서 실행 [실측 spy 2건] — 멱등 토큰·상한 계약이 그 락에 의존하므로 유지. 이연 트리거: S3 지연으로 인한 락 대기 타임아웃 실측.
- **H6** 가입 atomic이 SMTP 발송 포함 — 기록된 결정 [문서 `docs/BE/account-identity.md` (g)].
- `lock_timeout`·`statement_timeout`(prompt_plan.md 트랙 12 이연), `DB_CONN_MAX_AGE`(트랙 17 보류), S3Boto3Storage botocore 타임아웃(DOR 이연), 교착·락 대기 관측 지표(DOR 이연), Supabase `deadlock_timeout` 실측(사용자 액션).
- 스크래치패드의 2스레드 실경쟁 재현(`time.sleep` 동기화)은 정식 스위트에 편입하지 않는다(코치 기각 — 플레이키 위험) [문서 코치 보고].

## Domain Boundary and Dependency Direction

DAR 판정 계승. 방향 위반 **없음** [실측 검수]. 각 앱은 자기 소유 테이블만 잠그고(archive→자기 4테이블, accounts→User, drafts→자기 3테이블), staff는 Event·Category·User를 조율 계층으로 잠그며, web/promotion은 PersonalEntry를 잠근 채 drafts에 삽입만 한다. 서로 다른 두 자원의 역순 잠금 경로 0건. 이번 수정은 소유 계층을 옮기지 않는다: H1은 core 내부, H3는 archive 서비스 내부, H2'·H4·H7은 staff 뷰 내부, H8은 drafts 서비스 내부, T1은 archive 뷰 + settings.

## Coupling and Cohesion Review

세이브포인트 규율: `except IntegrityError` 18곳 중 이탈 1곳(H1) [실측 rg]. 감사 로그 "같은 atomic" 계약: `StaffActionLog.objects.create` 22곳 중 의도되지 않은 이탈 1곳(H4), 의도된 예외 1곳(`staff/views/__init__.py:328` finally 항상-로그) [실측]. 새 헬퍼·데코레이터·추상화 0건 — 기존 관용구 복사만.

## Pythonic Code Design

- 세이브포인트는 `with transaction.atomic():` 컨텍스트 매니저, 락은 `select_for_update()` 후 같은 인스턴스 사용 — 저장소 관용구 그대로.
- H8은 예외를 서비스 경계 안에서 정규화해 뷰가 이미 가진 `created=False` 응답 경로에 합류(DAR 권고).
- H2'는 두 문장의 순서 교환 + 잠금 조회로 해결하며 새 예외 처리 분기를 만들지 않는다.

## TDD Checkpoints (Backend TDD Coach 계약)

한 번에 하나. 순서 H1-a → H1-b → H2' → H3 → H4 → H8 → H7 → T1. 각 사이클: 표적 명령(Red 사유 확인) → 최소 Green → 관련 스위트. 리팩터링은 코치 허용 시에만. 실행은 오케스트레이터 단독(메모리 `pytest-single-runner-delegation`).

| ID | 파일(기존에 추가) [코드 코치 보고] | 테스트명 | 예상 Red 사유 |
|---|---|---|---|
| H1-a | `tests/core/test_category_palette_lifecycle.py` | `test_카테고리_슬롯_재획득이_충돌해도_뒤이은_감사로그_기록이_성공한다` | 바깥 atomic이 needs_rollback → 다음 쓰기 `TransactionManagementError` |
| H1-b | 같은 파일 | `test_삭제_경로에서_슬롯_재획득이_충돌해도_이벤트_삭제와_감사로그가_함께_커밋된다` | 세이브포인트 조용한 롤백으로 이벤트 잔존. H1-a Green 후 이미 Green이면 뮤테이션(수정 되돌리기)으로 Red 확인 |
| H2' | `tests/staff/test_staff_event_publish_delete_views.py` | `test_삭제_확인_POST_직전에_이벤트가_사라지면_500_대신_404를_응답한다` | `delete_event` 호출 직전 행 삭제 monkeypatch → `Event.DoesNotExist` 전파 |
| H3 | `tests/archive/test_activity_log_orchestration.py` | `test_상태_전환_중_활동_기록_삽입이_실패하면_상태_변경도_함께_롤백된다`(parametrize 방문·놓침·예정 복귀) | `_record_activity` raise 후 상태가 이미 바뀌어 있음 |
| H4 | `tests/staff/test_staff_source_discovery_request_view.py` | `test_탐색_요청_감사로그_삽입이_실패하면_실행_생성도_함께_실패한다` | run 1건 생성됨 |
| H8 | `tests/drafts/test_agent_drafts.py` | `test_경쟁으로_기존_행을_놓친_제출은_예외_대신_기존_드래프트를_반환한다` | `EventDraft.objects.filter` 빈 결과 monkeypatch → `DraftCreationDuplicateError` 전파 |
| H7 | `tests/staff/test_staff_home_categories_view.py` | `test_홈_카테고리_저장_POST는_대상_행을_잠그고_읽는다` | `CaptureQueriesContext`에 `FOR UPDATE` 0건 |
| T1 | `tests/archive/test_collection_items_api.py` | `test_컬렉션_항목_수정_삭제_요청이_설정된_한도를_초과하면_429로_제한된다` | PATCH 30회 후 DELETE가 204 [코드 스로틀 한도] |

첫 계약(H1-a): Behavior=슬롯 재획득 경합 실패 후에도 같은 트랜잭션의 감사 로그 기록이 커밋 / Red 사유=위 표 / Green 경계=`core/categories.py` 재획득 두 줄 감싸기, 다른 파일 불변 / Refactoring allowed: No / 명령 `uv run pytest -q tests/core/test_category_palette_lifecycle.py::test_카테고리_슬롯_재획득이_충돌해도_뒤이은_감사로그_기록이_성공한다`.

기각(코치) [문서 코치 보고]: 호출 횟수·인자 단언, `transaction.atomic` 목킹, 스크래치 2스레드 실경쟁 테스트 편입.

## 회귀 명령 범위 [계산 결함별]

- H1: `tests/core/test_category_palette_lifecycle.py tests/core/test_category_model.py tests/core/test_category_seed_migration.py tests/core/test_category_token_contract.py tests/staff/test_staff_category_views.py tests/events/test_events_services.py tests/staff/test_staff_event_publish_delete_views.py tests/staff/test_staff_event_services.py tests/drafts/test_drafts_services.py`
- H2': H1 목록 + `tests/staff/test_staff_action_log.py`
- H3: `tests/archive/test_activity_log_orchestration.py tests/archive/test_visit_record_status_orchestration.py tests/archive/test_archive_missed_status.py tests/archive/test_archive_services_analytics.py tests/archive/test_user_event_status_api.py`
- H4: `tests/staff/test_staff_source_discovery_request_view.py` / H8: `tests/drafts/test_agent_drafts.py tests/drafts/test_runner_draft_api.py` / H7: `tests/staff/test_staff_home_categories_view.py` / T1: `tests/archive/test_collection_items_api.py tests/archive/test_promotion_api.py`
- 마무리: `uv run python manage.py check`, `uv run python manage.py makemigrations --check --dry-run`, `uv run pytest -q`(기준선 2816 passed 대비 증가분 = 신규 테스트 수 [계산]).

## 커밋 계획

결함마다 커밋 1개(테스트+구현, 혼자 Green·revert 가능), 문서 커밋 1개, README 수치 정정 커밋 1개 [계산 9개]. `git add -A` 금지 — 명시 스테이징(prompt_plan.md 미스테이징). 검증 후 커밋·푸시·PR 자동, 머지는 사용자 승인.

## 문서 대상과 핸드오프 조건

- `docs/BE/category-vocabulary.md` "팔레트 슬롯" 절: 재획득 분기 세이브포인트 가드레일(왜 없으면 바깥 트랜잭션이 오염되는지, 삭제 경로의 조용한 불일치 사례).
- `docs/BE/visit-completion-concurrency.md` Guardrail: 상태 전환 3함수의 원자성(순서·위치 보류는 유지, atomic 추가만) [코드 archive/services.py].
- `docs/BE/staff-event-publish-actions.md` (d) 옆: 삭제 뷰가 잠금 조회를 로그보다 먼저 한다는 계약. 감사 로그 "같은 atomic" 계약의 의도된 예외(`staff/views/__init__.py:328`)를 `staff/views/_helpers.py` docstring에 한 줄로 명문화.
- `docs/BE/draft-source-agent-discovery.md` "함정과 실측": 러너 제출의 중복 정규화(H8)·탐색 요청 감사 로그 원자성(H4).
- `docs/backlog.md` F5(스로틀) 행에 `collection_item_update` 추가, 현재 상태 절 갱신.

## Deferred

- H5 근본 해법(스토리지 쓰기를 행 락 밖으로) — 트리거: S3 지연 실측.
- 교착·락 대기 관측(pg_stat_activity 기반)·Supabase `deadlock_timeout` 확인 — 사용자 액션·트랙 17과 병행 여부 사용자 결정.
- 마이그레이션 롤백 금지 목록이 런북 2곳에 분산(DOR) [문서 DOR 보고] — 문서 소유 역할 판단.

## Evidence [실측 2026-09-14, PR #367 `fix/db-lock-transaction-audit` → base `fix/site-wide-interaction-audit`]

- 사이클 8회(H1-a·H1-b·H2'·H3·H4·H8·H7·T1) 전부 Red 사유 확인 후 최소 Green. H1은 수정 되돌리기 뮤테이션으로 2 failed → 복원 2 passed. 신규 테스트 10건 [계산 1+1+1+3+1+1+1+1].
- 전체 회귀 `uv run pytest -q` → **2826 passed / 10 deselected / 85.11초**(기준선 2816 대비 +10 = 신규 테스트 수). `check` 0 issues, `makemigrations --check --dry-run` 무변경.
- 커밋 9개 [실측 git log]: 결함 7(`7721ca12` H1, `095c271e` H2', `f92055fd` H3, `dda9ac1f` H4, `0fdece9e` H7, `2e7607e3` H8, `a3cc5a65` T1) + 문서 `8a7e1bab` + README `8af14597`.
- 구현 중 정정 [계산 2건]: README 지시 "select_for_update 10개 파일"은 H7 반영 전 값 → 엔지니어 재측정 **11개** 채택 [실측 rg]; README의 `transaction.atomic` 51곳(2026-09-09)도 낡아 `with transaction.atomic(` 62곳 [실측]으로 같은 커밋에서 정정. 문서 검토에서 "재획득=기존 소유자 슬롯 해제" 오기 1곳을 오케스트레이터가 직접 고침.
- 미완: 머지(사용자 승인), #366 머지 후 base 재지정, `docs/pr-log.md` 롤링(머지 시).

---

