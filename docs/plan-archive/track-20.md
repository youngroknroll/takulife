# 트랙 20: 드래프트 admin API 감사 기록 — H7 선택지 2 (2026-09-07)

> 배경: `docs/backlog.md` H7 — `/api/event-drafts/`(생성 POST·필드 수정 PATCH, 권한
> `IsAdminUser`=is_staff)는 `StaffActionLog` 밖이라 검수 화면에서 필드를 고친 뒤 승인하면
> "승인"만 남는다. 사용자 결정(2026-09-07): 선택지 2 — 액션 2종 사실 기록, 전후 스냅샷 보류.
> 사실 [실측 2026-09-07]: API 뷰 3개(`AdminEventDraftStatsView`·`AdminEventDraftListCreateView`·
> `AdminEventDraftDetailView`)가 `drafts/views.py` 전체(161줄 `wc -l`)이고 `config/urls.py:177`이
> `include("drafts.urls")`로 마운트(URL 이름 `event-drafts`·`event-draft-stats`·`event-draft-detail`,
> app_name 없음). 호출자는 `static/js/staff/draft.js:71`·`:156`뿐. `drafts.views`/`drafts.urls` 참조는
> `config/urls.py:177`·`tests/drafts/test_drafts_api.py:6`·`tests/core/test_architecture_boundaries.py:279`
> 3곳 [실측 rg]. `tests/drafts/test_drafts_api.py`는 30건(모듈 23 + 클래스 메서드 7) [실측 grep].
> 경계 가드 `tests/core/test_architecture_boundaries.py:362-374`가 drafts→staff 임포트를 금지한다.
> 계획서 v2 = v1을 DAR·TDD 코치·SRR 검토로 정정한 통합본. 브랜치 `feat/draft-api-audit`(main 091429b).

## 승인 범위

1. **코드 위치 A안(DAR)**: 뷰 3개를 `staff/views/draft_api.py`로 옮기고 `staff/api_urls.py`(app_name
   없음, URL 이름 3개 유지)를 `config/urls.py:177`에서 `include("staff.api_urls")`로 마운트.
   `drafts/views.py`·`drafts/urls.py`는 삭제(참조처 3곳뿐 [실측 rg]). `tests/drafts/test_drafts_api.py`는
   `tests/staff/test_staff_draft_api.py`로 이동(임포트 `staff.views.draft_api`), `tests/core/test_architecture_boundaries.py:640`
   허용 임포트 키를 새 경로로 갱신, `:279-282` `test_드래프트_뷰는_이벤트_모듈을_임포트하지_않는다`는
   대상 모듈이 사라지므로 삭제(오케스트레이터 발견, DAR 누락). OpenAPI 계약은 경로 기준이라 불변,
   `docs/BE/openapi-schema.md:9`의 위치 서술만 갱신. 근거: IsAdminUser 게이트 API는 검수 콘솔 관심사
   (`docs/BE/openapi-schema.md:9` "스태프 전용"), 승인·반려 뷰(`staff/views/drafts.py:228-238`)와 같은
   패턴. B안(신호)은 저장소 유일 시그널 용례(`archive/signals.py:33-45`, 베스트-에폭트)와 성격이 반대라 기각.
2. **서비스 분할(DAR, SRR Medium 해소)**: `create_draft_from_url`(`drafts/services.py:94-160`)을
   네트워크·추출 단계 `prepare_draft_from_url(*, source_url) -> DraftPayload`(`:96-136` 본문, DB 접근 0)와
   DB 단계 `persist_prepared_draft(*, payload, source_name="") -> EventDraft`(`:138-160` 본문, 내부 atomic·
   IntegrityError→`DraftCreationDuplicateError` 유지)로 나누고, 합성 함수 `create_draft_from_url`은 시그니처
   그대로 유지(호출자 `drafts/candidate_validation.py:287`·`discover_drafts.py:191` 무변경). `DraftPayload`는
   `DraftApprovalResult`(`:88-91`) 옆 frozen dataclass. 이유: `fetch_html` 타임아웃 5.0초×최대 4홉 = 20.0초
   [계산]가 DB 트랜잭션 안에 들어가면 안 된다(현재 `drafts/views.py:93`은 atomic 없이 호출).
3. **액션·라벨·마이그레이션**: `Action.DRAFT_CREATE="draft_create"`·`DRAFT_UPDATE="draft_update"`(각 12자
   [코드], `max_length=16`), `ACTION_LABELS` "드래프트 생성"·"드래프트 수정", 0009(AlterField choices, SQL 없음).
   순서 고정(TDD 코치): Action 추가 → 라벨·마이그레이션 계약 테스트 Red 확인 → 라벨·`makemigrations` → Green.
4. **기록 규칙**: 생성 = `prepare`(트랜잭션 밖) → 기능 꺼짐·fetch 실패군은 기존 매핑대로 응답 → `with atomic():
   persist + StaffActionLog(DRAFT_CREATE, target_draft)`, 중복은 atomic 밖에서 `field_error_response`.
   수정 = `with atomic(): update_draft + StaffActionLog(DRAFT_UPDATE, target_draft)`. 실패 경로는 전부 무로그.
   메타데이터 `_staff_action_metadata(request)`. 전후 값 없음(H12(b) 보류). 응답 코드·본문·URL 불변.
5. **문서**: `docs/BE/staff-audit-log.md` 신설 — 가드레일만: (a) 감사 로그는 staff 소유, 도메인 앱은 staff를
   임포트 못 하므로 감사가 필요한 admin API는 staff가 소유 (b) 네트워크 fetch는 DB 트랜잭션 밖 (c) 실패 경로
   무로그(승인·반려 선례) (d) 비감사 경로 3곳 명시 — 러너 제출 `drafts/candidate_validation.py:287`·
   `discover_drafts.py:191`(actor 없음)·`web/promotion.py:74`(일반 사용자, 스태프 행동 아님) [실측 rg]
   (e) 전후 값 없음·`target_draft` SET_NULL 시 추적 한계. `docs/BE/openapi-schema.md` 위치 문구, 백로그 H7 완료,
   pr-log(머지 시).

## 배제
- 전후 스냅샷(H12(b)), 실패 시도 감사(unsafe·중복 반복 — SRR 이연), 러너·관리 명령 경로 시스템 감사(별도 항목),
  승인·반려 로그 변경, 프론트·CSS, 감사 보존 정책.

## 수용 기준
- AC1 생성 성공 POST → `draft_create` 로그 1건(target_draft = 응답 id, actor = 요청자), 응답 201 불변.
- AC2 PATCH 성공 → `draft_update` 로그 1건, 응답 200 불변. 같은 드래프트 두 번 수정 → 로그 2건.
- AC3 실패 경로(기능 꺼짐 403·unsafe·중복·비HTML·초과·추출 없음·fetch 503·pending 아님·vocab) 전부 로그 0건, 응답 불변.
- AC4 로그 저장 실패 시 생성 롤백(드래프트 미존재)·수정 롤백(필드 원복), 500.
- AC5 URL 이름·경로·응답 스키마 불변: 이동한 API 테스트 30건 [실측] 통과, `/api/schema/` 계약 통과.
- AC6 경계 가드·라벨 계약·마이그레이션 계약·서명 규약 가드 통과, 전체 회귀 통과.
- AC7 감사 로그 화면에 두 액션이 한국어 라벨·드래프트 대상으로 보인다.
- SEC-AC1 생성 경로에서 `fetch_html` 실행 중 열린 DB 트랜잭션이 없다(`transaction=True` 테스트에서 가짜 fetch가
  `connection.in_atomic_block is False`를 관찰).
- SEC-AC2 `prepare_draft_from_url`은 `DraftCreationDuplicateError`를 절대 내지 않고, `persist_prepared_draft`만 낸다.

## Activated Roles / Not Activated [문서 3역할 검토 결과 2026-09-07]
- Activated: DAR(A안·분할 결정), Backend TDD Coach(Test List S1~S10), SRR(Medium 1건 → 분할로 해소, 문서 항목 (d)),
  BIE, QVL. Not activated: PSO(사용자 승인), WED·BIR(프론트 무변경), DOR(choices-only 마이그레이션, 0008 선례), AI.

## Domain Boundary and Dependency Direction
- `staff → drafts(models·services·serializers·queries)` 기존 방향(`staff/views/drafts.py:24-36`). `drafts`는 staff를
  임포트하지 않음(가드 유지). drafts는 `EventDraft` 상태 전이·불변식을 계속 소유, staff는 감사 taxonomy와
  admin API 표면을 소유. 새 불변식: draft_create/draft_update 로그는 대응 상태 전이와 같은 트랜잭션에서만 성공.

## Test List (TDD 코치 확정 + SRR 반영) [문서 코치 검토 결과]
파일: `tests/staff/test_staff_draft_api.py`(이동한 30건 + 신규), `tests/drafts/test_drafts_services.py`(분할 계약),
확장 `tests/staff/test_staff_audit_log_view.py`, 재사용 `tests/staff/test_staff_action_labels.py`·`tests/core/test_migrations_in_sync.py`.
- S0 이동 회귀: 이동만 한 상태에서 30건 Green(URL 이름 불변 증거).
- S8/S9(이미 Green 핀): Action 2종 추가 → 라벨 계약·마이그레이션 계약 Red → 라벨·0009 → Green.
- S1 `관리자가_url로_드래프트_생성에_성공하면_draft_create_감사_로그가_한_건_남는다`(201, count 1, target_draft=응답 id, actor).
- S2 `관리자가_검토_대기중인_드래프트를_patch로_수정하면_draft_update_감사_로그가_한_건_남는다`.
- S3 `같은_드래프트를_두_번_patch로_수정하면_draft_update_로그가_두_건_남는다`.
- S4/S5 기존 실패 테스트에 `StaffActionLog.objects.count() == 0` 단언 추가(이름 끝 `_로그도_남지_않는다`; 이미 Green — 회귀 안전망).
- S6 `생성_성공_후_감사_로그_기록이_실패하면_드래프트_생성이_통째로_롤백된다`(monkeypatch `staff.models.StaffActionLog.objects.create`, 500, 드래프트 미존재).
- S7 `patch_성공_후_감사_로그_기록이_실패하면_드래프트_수정이_통째로_롤백된다`.
- S10 `감사_로그_화면에_드래프트_생성_수정_행동이_한국어_라벨과_드래프트_대상으로_보인다`(이미 Green 기대, AC7 증거).
- S11(SRR, contract, `django_db(transaction=True)`) `드래프트_생성의_원본_fetch는_db_트랜잭션_밖에서_실행된다` — 가짜 `fetch_html`이 `connection.in_atomic_block`을 기록.
- S12(domain, 분할 계약) `prepare_draft_from_url은_중복_source_url이어도_예외_없이_페이로드를_돌려준다` / `persist_prepared_draft는_중복_source_url에_DraftCreationDuplicateError를_낸다` / `create_draft_from_url은_분할_전과_같은_드래프트를_만든다`.

## 구현 순서 (pytest 실행·판정은 오케스트레이터 단독) [문서 이 계획서]
1. BIE 1차: 이동(A안)·`Action` 2종 추가·신규 테스트 전부 작성(라벨·마이그레이션·분할·로그는 미구현) →
   오케스트레이터: 이동한 API 테스트 30건 Green, 이미-Green 핀 2건 Red, 신규 Red 사유 확인 → 커밋(이동만 분리 커밋).
2. BIE 2차: 라벨·0009·서비스 분할·로그 기록 → Green·뮤테이션(로그 생성 제거, atomic 제거) → 커밋.
3. 문서 → 전체 회귀 → PR.

## 검증 명령
`uv run pytest -q tests/staff/test_staff_draft_api.py tests/drafts/test_drafts_services.py tests/staff/test_staff_audit_log_view.py tests/staff/test_staff_action_labels.py tests/core/test_migrations_in_sync.py tests/core/test_architecture_boundaries.py tests/core/test_openapi_schema.py tests/core/test_service_signature_conventions.py` → passed; `uv run pytest -q`; `makemigrations --check --dry-run`; `manage.py check`.

---

