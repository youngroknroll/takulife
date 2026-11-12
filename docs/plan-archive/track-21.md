# 트랙 21: 반려 드래프트 재오픈 — H5 (2026-09-08) [v2 — PSO·DAR·TDD 코치·SRR·DOR·WED·BIR 검토 반영]

> **검토 반영 요약(v1 → v2)** [문서 각 역할 산출, 인용 file:line은 오케스트레이터가 전수 재확인 2026-09-08]
> - PSO: ★1~★5 전부 수용(기본값 확정). 범위·AC·배제 이견 없음. AC5에 "재오픈된 대기 상태에서 승인·반려 버튼도
>   정상 렌더" 보강.
> - DAR: 가드 헬퍼는 (a) `_get_draft_for_update(draft_id, *, expected_status)` 매개변수화 채택, **기본값 없음**.
>   `reopen_draft`는 `select_for_update` 제약상 자체 `transaction.atomic()` 필수. `reviewed_by` 유지 타당. 뷰 파일
>   분리 불필요(`staff/views/drafts.py` 440줄 [실측 wc]). **결함 발견**: `EventDraftUpdateSerializer`가
>   `read_only_fields`를 통째로 재정의(`drafts/serializers.py:62-76`)하므로 `reopened_at`을 거기에도 넣지 않으면
>   PATCH 본문에 `reopened_at`이 오면 `update_draft`가 `DraftImmutableFieldError`(`drafts/services.py:281`)를 던지고
>   `staff/views/draft_api.py:178-183`은 그 예외를 안 잡아 500 회귀 → 승인 범위 4·Test List API1로 흡수. 문서에
>   "승인된 드래프트에 과거 반려 기록(rejected_at·rejection_reason)이 공존할 수 있다" 불변식 명문화.
> - SRR: 차단 없음, ★3 권한 대칭 수용. 추가 확인: GET → 405 테스트(V8), "이전 반려" 문단은 `|safe` 금지(SEC-AC3),
>   실패 경로 무로그 재확인(SEC-AC4). 빈도 제한·step-up은 기록된 사용자 보류라 재제안 없음.
> - DOR: 차단 없음. drafts 0007 기대 SQL = `ALTER TABLE "drafts_eventdraft" ADD COLUMN "reopened_at" timestamp with
>   time zone NULL;` 1문장, staff 0010 = `BEGIN;`/`COMMIT;`만. 롤백은 코드 우선(컬럼 잔존 무해). 배포 순서 문제 없음
>   (`docker/entrypoint.sh:4-8` migrate 후 기동).
> - WED: 버튼 라벨 "반려 재오픈", 무색 `.staff-cta.staff-cta-block`(ok=승인·danger-outline=반려 전용이라 배제), 기존
>   `.notice` 문단 유지, 안내·모달·이전 반려 문구 확정(승인 범위 5), 큐 배지 없음(★5), 현재 URL 재이동(★4), 신규 CSS
>   0줄 [계산].
> - BIR: **High** — `#draft-action-error`가 `{% if is_pending %}` 분기 안(`templates/core/drafts/detail.html:159`)에만
>   렌더돼 재오픈 오류가 화면에 안 보이고 포커스도 안 움직임 → 오류 문단을 분기 밖으로 끌어올린다. **Medium** —
>   `{% else %}`(`:162-164`)가 승인·반려를 묶으므로 반려 전용 분기 분리. `queue_shortcuts.js`는 목록에서만 로드
>   [실측 rg] → 상세 화면 무관. 사후 증거 목록은 Frontend Review Evidence 절.
> - TDD 코치: S2/S3·V4/V5·D2 파라미터화 병합, S6 → S6a/S6b 분리, S5·S6a·S6b는 이미-Green 핀(뮤테이션 증거 필수),
>   V7 패치 경로 `staff.views.StaffActionLog.objects.create`(선례 `tests/staff/test_staff_draft_actions.py:343-361`),
>   id 문자열 `not in` 단언 허용(선례 `tests/staff/test_staff_console.py:815`), 새 테스트 파일 없음.
> - **정정 기록(오케스트레이터 결함)**: 브리프에 적은 줄 번호 4곳이 틀렸다 — `_get_pending_draft_for_update` 217-226
>   → 실제 242-251, `StaffDraftRejectView` 343-370 → 348-377, 상세 반려 메타 32-46 → 34-47, 검수 판정 칼럼 140-165
>   → 135-166 [실측 grep]. 원인: 앞선 `sed -n` 창의 상대 위치를 절대 줄로 옮겨 적음. 규칙: 줄 번호는 `grep -n`
>   결과만 옮겨 적는다(Orchestrator Contract 4).

> 배경: `docs/backlog.md` H5(P1, 결함·빈도 낮음) — 승인·반려·수정이 전부 pending 전용
> (`drafts/services.py` `_get_pending_draft_for_update`, DraftStateError)이고 `source_url`이
> unique(`drafts/models.py`)라 반려는 영구 폐기, 복구 경로는 shell뿐. 사용자 지시(2026-09-08)
> "남은 H절 항목 진행" → P1 중 결함인 H5부터. 착수 순서 근거: H4(SLA 지표)의 설계 확정 항목
> "재오픈 후 대기 시간의 기산점"이 이 트랙의 결정을 소비하므로 H5 → H4 순.
> 사실 [실측 2026-09-08]: `rg -n "reopen|재오픈" --type py --type html --type js` 결과는 이미지
> 검증 코드(`events/image_validation.py:79`·`tests/events/test_image_validation.py`)뿐, 드래프트 재오픈
> 구현 0건. 반려 서비스 `reject_draft`(`drafts/services.py:336-352`)는 `review_status·reviewed_by·
> rejected_at·rejection_reason·updated_at` 5필드를 저장한다 [코드]. `StaffActionLog.action`
> `max_length=16` [코드 `staff/models.py`], `"draft_reopen"`은 12자 [계산 `python3 -c "print(len(...))"`].
> 최신 마이그레이션: drafts 0006, staff 0009 [실측 ls]. 프론트 사전 검토 원문:
> `.docs/FE/2026-09-06-staff-backoffice-frontend-review.md:43`(WED)·`:160`(BIR) — 재오픈 버튼은
> `templates/core/drafts/detail.html` judge-actions(`:154-159`), JS는 `static/js/staff/draft.js`
> `bindApproveButton`(`:178-240`) 구조 재사용, 확인 대화상자 필수, 기산점은 설계 시 확정.
> 브랜치 `feat/draft-reopen`(main e41ed3d). 기준선 [실측 2026-09-08 main e41ed3d] `uv run pytest -q`
> 2440 passed / 68.77초.

## 승인 범위 (★ = 사용자 미확인 가정 — PSO 판정 병기)

1. **서비스** `reopen_draft(*, draft_id)`(`drafts/services.py`): REJECTED → PENDING, `reopened_at=now()`,
   `update_fields=["review_status", "reopened_at", "updated_at"]`. ★1 마지막 반려 기록(`reviewed_by`·
   `rejected_at`·`rejection_reason`)은 **지우지 않는다** — 재검수자가 왜 반려됐는지 봐야 하고, 감사 로그는
   사유를 담지 않는다. 상태 가드 헬퍼는 `_get_pending_draft_for_update`(`drafts/services.py:242`)를
   `_get_draft_for_update(draft_id, *, expected_status)`로 매개변수화(**기본값 없음**, 호출처 3곳 [실측 grep]
   `:293`·`:305`·`:338`은 `expected_status=EventDraft.ReviewStatus.PENDING` 명시) — DAR 채택. `reopen_draft`는
   기존 세 서비스처럼 `with transaction.atomic():`로 가드 호출을 감싼다(`select_for_update`는 atomic 밖 금지).

2. **모델** `EventDraft.reopened_at = DateTimeField(null=True, blank=True)` → drafts 0007(ADD COLUMN NULL,
   데이터 마이그레이션 없음, Postgres 즉시). ★2 **H4 기산점 결정(기록)**: 대기 시간 시작 = `reopened_at`이
   있으면 그 값, 없으면 `created_at`. 재반려 후 재오픈은 `reopened_at`을 덮어쓴다(최근 재오픈 1회만 보존).

3. **감사** `StaffActionLog.Action.DRAFT_REOPEN = "draft_reopen"`, `ACTION_LABELS["draft_reopen"] = "반려 재오픈"`,
   staff 0010(AlterField choices, SQL 없음). 기록은 뷰의 `with transaction.atomic():` 안에서 서비스 호출과
   묶는다(승인·반려 선례). 실패 경로(404·400·403)는 무로그.

4. **엔드포인트** `POST /staff/drafts/<int:draft_id>/reopen/`(`staff:draft-reopen`,
   `StaffDraftReopenView(APIView)`, `staff/views/drafts.py`). ★3 권한은 `IsAdminUser`(=is_staff) — 반려와
   같은 신뢰 수준의 역방향 조작이라 반려와 대칭. 오류: 404 `"Not found."`, 400 `"Only rejected drafts can be
   reopened."`(`core.errors.error_response`), GET → 405(APIView 기본). 응답 200 `EventDraftSerializer`(fields·
   read_only_fields에 `reopened_at` 추가 — `/api/event-drafts/` 응답에도 같은 필드가 노출됨, `/api/schema/` 계약은
   필드 추가에 무관) **+ `EventDraftUpdateSerializer.Meta.read_only_fields`에도 `reopened_at` 추가**(DAR 결함:
   빠지면 PATCH 본문의 `reopened_at`이 `update_draft`까지 내려가 500). `staff/views/__init__.py` re-export,
   `staff/urls.py` 라우트 1개 추가 [계산].

5. **화면**(`templates/core/drafts/detail.html`·`static/js/staff/draft.js`, WED 사양 + BIR 기준 확정):
   - 검수 판정 칼럼(`:135-166`) 분기를 `{% if is_pending %}` / `{% elif draft.review_status == "rejected" %}` /
     `{% else %}`(승인)로 나눈다(BIR Medium). 반려 분기 = 기존 `.notice` 문단("반려됨 상태입니다. 승인/반려는
     검토 대기 상태에서만 가능합니다") **유지** + 그 아래 `<div class="review-judge-actions">` 안에
     `<button id="draft-reopen-btn" class="staff-cta staff-cta-block" type="button" data-draft-id="{{ draft.id }}">반려 재오픈</button>`
     + `.review-judge-note` 문단: "공식 URL은 중복 등록이 불가능해 반려된 드래프트는 새로 만들 수 없습니다.
     재오픈하면 검토 대기로 돌아가 이 화면에서 수정·승인·반려를 다시 진행할 수 있습니다." 승인 분기 = 기존
     `.notice` 문단 그대로. 버튼 색은 무색 기본(`.staff-cta` `static/css/staff/shell.css:266`) — ok(승인)·
     danger-outline(반려) 판정색 배제.
   - `<p id="draft-action-error" class="queue-inline-error" tabindex="-1" hidden></p>`는 세 분기 **밖**(칼럼 body
     끝)으로 끌어올린다(BIR High — 현재 `:159`가 대기 분기 안에만 있어 반려 상태에서 `showError`의 null 가드에
     걸려 오류가 안 보인다). `#draft-approve-success`는 대기 분기 안 유지.
   - 재오픈된 대기 상세(뷰 컨텍스트 `was_reopened = draft.reopened_at is not None`, `is_pending`일 때만 의미):
     대기 분기 **맨 앞**(`.review-checks` `:139` 이전, DOM 순서상 판정 버튼보다 먼저 읽힘)에 기존 `:34-46` 패턴
     재사용: `<p class="notice">이 드래프트는 반려에서 재오픈되었습니다. 이전 반려 기록은 아래와 같습니다.</p>`
     + `<p class="meta">검토자: {{ draft.reviewed_by.email|default:"-" }} · 반려 시각: {{ draft.rejected_at|date:"Y.m.d H:i" }} · 반려 사유: {{ draft.rejection_reason|default:"(사유 없음)" }}</p>`
     (`|safe` 금지 — SEC-AC3). 상단바 메타·큐 목록에는 재오픈 시각·배지를 넣지 않는다(★5 WED 확정).
   - JS `bindReopenButton`(`bindRejectButton` `:244-285` 구조): `askConfirm("반려를 취소하고 검토 대기로 되돌릴까요?
     재검수에서 다시 반려할 수 있습니다.")` → 취소 시 즉시 return → `setLoading(btn, true)` → `TakuAPI.post("/staff/drafts/"
     + id + "/reopen/", {})` → 성공 시 ★4 `commitAndNavigate(btn, window.location.href)`(**`.is-loading` 유지** —
     `bindEditForm` `:170-176` 선례, bfcache `pageshow` 강제 이동 조건) / 403은 `setLoading(false)` + `CSRF_OR_SESSION_MSG`
     / 그 외 `formatError` → `showError(errorEl)`(포커스 이동). `DOMContentLoaded`에 `bindReopenButton()` 등록.
   - 신규 CSS 없음 [계산 0줄]. `.review-col-body`(`static/css/staff/pages/drafts.css:675`) flex gap이 간격 처리.

6. **문서**: `docs/BE/draft-review-lifecycle.md` 신설(가드레일만: (a) 상태값은 기존 셋 그대로 [코드
   `ReviewStatus`], 재오픈은 PENDING 복귀 (b) 마지막 반려 기록 유지 규칙 (c) `reopened_at` = SLA 기산점, H4가
   소비 (d) 감사 `draft_reopen`·실패 무로그 (e) `source_url` unique라 재생성 불가 → 재오픈이 유일한 복구 경로,
   shell 불필요 (f) **승인된 드래프트에 과거 반려 기록(`rejected_at`·`rejection_reason`)이 공존할 수 있다**(반려 →
   재오픈 → 승인 경로, DAR) (g) 마이그레이션 롤백은 코드 우선(컬럼 잔존 무해, DOR)), `docs/event-operations-criteria.md:72`
   전이 문장에 재오픈 1줄, 백로그 H5 항목 완료 + H4 항목에 ★2 기산점 링크, pr-log(머지 시).

## 배제 (범위 밖)
- 신규 상태값(`reopened`) 추가, 반려 이력 다중 보관 모델, 승인 취소(approved → pending: 게시 이벤트 회수와
  얽혀 별도 항목), 일괄 재오픈, 큐 목록·인스펙터에서의 인라인 재오픈, H4 지표 자체(다음 트랙), H10 반려 사유
  템플릿, 감사 보존 정책(H12(b)).

## 수용 기준
- AC1 반려 드래프트 재오픈 POST → 200, `review_status=pending`, `reopened_at` 기록, `reviewed_by·rejected_at·
  rejection_reason` 유지, 감사 로그 `draft_reopen` 1건 [계산](actor=요청자, target_draft=대상).
- AC2 대기·승인 상태 → 400, 로그 0건 [계산], 필드 불변. 없는 id → 404. 익명·일반 사용자 → 403(로그 없음).
- AC3 로그 저장 실패 → 재오픈 롤백(rejected 유지·`reopened_at` None), 응답 500.
- AC4 재오픈된 드래프트는 기존 수정·승인·반려를 그대로 탄다(pending 가드 자동 통과); 재반려 후 재오픈은
  `reopened_at` 갱신.
- AC5 상세 화면: 반려 상태에서만 재오픈 버튼 렌더, 재오픈된 대기 상태에서 이전 반려 기록 문단 + 승인·반려 버튼
  정상 렌더, 승인·미재오픈 대기 상태에는 버튼·문단 둘 다 없음. `#draft-action-error`는 세 상태 모두 렌더.
- SEC-AC1 GET `/staff/drafts/<id>/reopen/` → 405. SEC-AC3 이전 반려 문단에 `|safe` 없음(diff 확인). SEC-AC4 400·403·404
  경로에서 로그 건수 불변.
- AC6 감사 로그 화면에 "반려 재오픈" 칩·라벨 노출(라벨 계약 테스트), 마이그레이션 동기화·서명 규약·경계 가드
  통과, 전체 회귀 통과.
- AC7 브라우저(Chrome DevTools MCP): 반려 상세 → 재오픈 클릭 → 확인 모달 → 재이동 → 검토 대기 UI·이전 반려
  기록·감사 로그 행 확인, 콘솔 오류 없음. 임시 계정·캡처는 검증 후 삭제.

## Activated Roles / Not Activated (확정 — 7역할 사전 검토 완료 2026-09-08)
- Activated: PSO(★1~★5 판정·수용 기준), DAR(가드 헬퍼 매개변수화·필드 소유·의존 방향), Backend TDD Coach
  (Test List 확정), SRR(권한 대칭·남용·롤백), DOR(마이그레이션 drafts 0007·staff 0010 — 경량), WED·BIR(프론트
  사전·사후 검토), BIE·FIE(구현), QVL(증거 매핑).
- Not Activated: AI Automation Architect(LLM 무관).

## Domain Boundary and Dependency Direction
- drafts 소유: 모델 필드·`reopen_draft`·상태 가드. staff 소유: 뷰·URL·감사 액션·라벨. 방향 staff → drafts만
  (`tests/core/test_architecture_boundaries.py` 가드). events 무관 — 반려는 이벤트를 만들지 않았으므로 되돌릴
  게 없다. 서비스는 키워드 전용 인자(`tests/core/test_service_signature_conventions.py`).

## Test List (TDD 코치 확정, DAR·SRR 추가 반영) [문서 코치 산출]
새 테스트 파일 없음. 이름은 한국어 행동 중심(`test_...한다`), Given-When-Then 한 줄 주석. `reopen_draft`는 테스트
함수 안 로컬 임포트(모듈 상단 임포트면 파일 전체가 수집 오류).
- 서비스(`tests/drafts/test_drafts_services.py`):
  S1 `test_반려된_드래프트를_재오픈하면_대기_상태로_바뀌고_이전_반려_기록은_유지된다` — Red: ImportError(`reopen_draft`
  없음) → 구현 후 컬럼 부재 ProgrammingError → 마이그레이션 0007 후 Green.
  S2/S3 `test_대기나_승인_상태의_드래프트는_재오픈할_수_없다`(parametrize pending/approved) — DraftStateError.
  S4 `test_존재하지_않는_드래프트는_재오픈할_수_없다` — DraftNotFoundError.
  S5 `test_재반려_후_다시_재오픈하면_재오픈_시각이_갱신된다` — **이미-Green 핀**: 뮤테이션 = `reopen_draft`의
  `timezone.now()`를 기존 값 유지로 바꿔 Red 확인 후 원복.
  S6a `test_재오픈된_드래프트는_update_draft로_수정할_수_있다` / S6b `..._approve_draft로_승인할_수_있다` —
  **이미-Green 핀**: 뮤테이션 = `review_status = PENDING` 대입 제거 → DraftStateError로 Red 확인 후 원복.
- 뷰(`tests/staff/test_staff_draft_actions.py`, `draft_reopen_url` 헬퍼 추가):
  라벨 계약(기존 `test_모든_스태프_행동에_한국어_표시_라벨이_있다`) — Action 추가 직후 Red → 라벨 추가로 Green.
  V1 `test_반려된_드래프트를_재오픈하면_대기_상태로_바뀌고_감사_로그가_한_건_남는다`(AC1, 응답에 `reopened_at`,
  REMOTE_ADDR·UA 메타). V2 `test_익명_사용자는_드래프트를_재오픈할_수_없다`(403). V3 `test_일반_사용자는_드래프트를_
  재오픈할_수_없다`(403). V4/V5 `test_대기나_승인_상태의_드래프트는_재오픈이_거부되고_로그도_남지_않는다`(parametrize,
  400·로그 없음). V6 `test_존재하지_않는_드래프트는_재오픈할_수_없고_로그도_남지_않는다`(404). V7 `test_감사_
  로그_기록이_실패하면_재오픈_전체가_롤백된다` — `monkeypatch.setattr("staff.views.StaffActionLog.objects.create", ...)`
  IntegrityError(선례 `:343-361`) → 500, rejected 유지, `reopened_at` None, 로그 없음. V8 `test_재오픈_엔드포인트는_
  GET을_허용하지_않는다`(405, SRR). 초기 Red는 전부 NoReverseMatch(`staff:draft-reopen` 미등록).
- admin API(`tests/staff/test_staff_draft_api.py`): API1 `test_수정_요청_본문의_reopened_at은_무시되고_500이_나지_않는다`
  — PATCH `{"extracted_title": ..., "reopened_at": "2026-01-01T00:00:00Z"}` → 200, `reopened_at` None 유지(DAR 결함
  핀; Red = `EventDraftUpdateSerializer.read_only_fields` 누락 시 500).
- 상세 화면(`tests/staff/test_staff_draft_views.py`): D1 `test_반려_상세에는_재오픈_버튼이_보인다`(`'id="draft-reopen-btn"'
  in body`). D2 `test_대기나_승인_상세에는_재오픈_버튼이_보이지_않는다`(parametrize, `not in` — id 앵커 허용 선례
  `tests/staff/test_staff_console.py:815`; D1 최소 Green(무조건 렌더) 뒤 D2가 분기를 강제). D3 `test_재오픈된_대기_
  상세에는_이전_반려_사유가_보인다`(고유 사유 문자열 in body). D4 `test_반려_상세에도_판정_오류_문단이_렌더된다`
  (`'id="draft-action-error"' in body`, BIR High 핀).
- 계약: 마이그레이션 동기화·서명 규약·경계 가드는 기존 테스트가 자동 검증.

## 구현 순서 (슬라이스별 커밋, pytest 실행·판정은 오케스트레이터 단독)
운영 방식: 슬라이스마다 BIE/FIE가 **테스트만 먼저** 쓰고 → 오케스트레이터가 실행해 각 테스트의 Red 사유를 기록 →
같은 에이전트가 코치 순서대로 최소 구현 → 오케스트레이터가 Green 판정 → 이미-Green 핀은 오케스트레이터가 직접
뮤테이션(임시 편집 → Red 확인 → 원복) → 슬라이스 파일 전체 회귀 → 커밋. 슬라이스 2의 Action·라벨·0010은 라벨 계약
테스트 Red를 먼저 본다(트랙 20 선례).
1. 서비스: 모델 필드(마이그레이션은 S1 Red 확인 뒤 `makemigrations drafts`) + `_get_draft_for_update` 매개변수화 +
   `reopen_draft`(S1~S6b) → 커밋 `feat(drafts): 반려 드래프트 재오픈 서비스와 reopened_at`
2. 뷰: Action·라벨·0010 → URL·`StaffDraftReopenView`·serializer(`EventDraftSerializer`·`EventDraftUpdateSerializer`)
   (V1~V8, API1) → 커밋 `feat(staff): 재오픈 엔드포인트와 감사 기록`
3. 화면: 템플릿·JS(D1~D4) + 브라우저 검증(AC7) → 커밋 `feat(staff): 드래프트 상세 재오픈 버튼`
4. 문서 → 커밋 `docs: 드래프트 검수 생애주기 가드레일과 H5 종결`

## 검증 명령과 기대 증거
- `uv run pytest -q tests/drafts/test_drafts_services.py tests/staff/test_staff_draft_actions.py tests/staff/test_staff_draft_views.py`
- `uv run pytest -q` 전체(기준선 [실측 2026-09-08 main e41ed3d] 2440 passed / 68.77초), `uv run python manage.py
  makemigrations --check --dry-run`(변경 없음), `uv run python manage.py check`(이슈 없음), `uv run python manage.py
  sqlmigrate drafts 0007`(기대: `ALTER TABLE "drafts_eventdraft" ADD COLUMN "reopened_at" timestamp with time zone NULL;`
  1문장), `sqlmigrate staff 0010`(기대: `BEGIN;`·`COMMIT;` 외 DDL 없음).
- 브라우저: AC7 + 아래 BIR 증거 목록.

## Frontend Review Evidence [문서 WED·BIR 사전 산출 2026-09-08]
- 검토 깊이: **Standard**(WED·BIR 동의) — 버튼 하나·기존 확인 모달 재사용·상태별 문단 분기. 신규 컴포넌트 없음.
- WED 사전 사양: 승인 범위 5에 통합(버튼 라벨·색·위치, `.notice` 유지, 안내·모달·이전 반려 문구, 큐 배지 없음,
  재이동 방식, CSS 0줄 [계산]). 정보 위계: 이전 반려 기록 → 승인 전 체크 → 반려 사유 → 판정 버튼.
- BIR 사전 기준: (1) 오류 문단은 반려 분기에도 렌더되고 `focus()` 가능(High 해소 선행) (2) 반려 전용 분기 분리
  (3) 성공 시 `commitAndNavigate` + `.is-loading` 유지 + `data-committed-redirect`(bfcache 이중 재오픈 방지)
  (4) 이전 반려 문단은 `.review-checks` 이전 DOM 위치. 확인 모달 트랩·포커스 복귀·기본 "아니오"는
  `confirm-modal.js` 재사용이라 신규 검증 불필요. 권고(결함 아님): 안내 문단을 `aria-describedby`로 버튼에 연결.
- 계획된 브라우저 증거(BIR 목록): 반려 상세 스냅샷(버튼·안내·`#draft-action-error` 존재) → 클릭 → 모달 스냅샷
  (포커스 "아니오", Tab 순환) → "예" → Network에 `POST .../reopen/` 1건 [계산] → 콘솔 오류·경고 없음 → 재이동 후
  스냅샷(이전 반려 문단이 판정 버튼보다 앞, 재오픈 버튼 소멸, 승인·반려 버튼 노출) → 실패 경로 강제 재현(403 또는
  400: 오류 문단 표시 + `document.activeElement` 확인) → 키보드 전용 패스(Tab → Enter → 모달 Tab+Enter).
- **수집된 브라우저 증거** [실측 2026-09-08, Chrome DevTools MCP, 로컬 runserver, 임시 스태프 계정 → 검증 후 삭제]:
  (1) 반려 상세(드래프트 51): 검수 판정 칼럼 = 상태 문단 → "반려 재오픈" 버튼(`staff-cta staff-cta-block`, tabIndex 0) →
  안내 문단; `#draft-action-error` 존재(hidden, tabindex -1, 버튼 뒤). 콘솔 오류·경고 없음. 캡처 `track21-01`.
  (2) 클릭 → `role="dialog"` 모달, 초기 포커스 "아니오", Tab → "예" → Tab → "아니오"(트랩 순환). 캡처 `track21-02`.
  (3) "예" → 네트워크 `POST /staff/drafts/51/reopen/` 200 1건 [실측] → `GET /staff/drafts/51/` 재이동. 재이동 후 이전 반려
  문단이 `.review-checks`·승인 버튼보다 앞(`compareDocumentPosition`), 재오픈 버튼 소멸, 승인·반려 버튼 노출, 편집 필드 활성,
  `#draft-action-error` 존재. DB: pending·`reopened_at` 기록·`reviewed_by`·사유 유지, 감사 로그 `draft_reopen`(actor·IP·UA) 1건
  [실측 shell]. 캡처 `track21-03`.
  (4) 오류 경로(드래프트 52, 페이지 로드 뒤 DB를 pending으로 바꿔 400 유도) 키보드만: 버튼 focus → Enter → 모달("아니오") → Tab
  ("예") → Enter → `POST .../52/reopen/` 400 1건 → 오류 문단 표시 "Only rejected drafts can be reopened." + `activeElement` =
  오류 문단, 버튼 `.is-loading` 해제·활성, 모달 래퍼 hidden. 콘솔: 브라우저의 400 리소스 로그 1건(JS 예외 없음). DB·로그 무변경.
  캡처 `track21-04`.
  (5) 감사 로그 화면 `?action=draft_reopen`: 칩 "반려 재오픈" 활성, 행 1건(시각·라벨·대상 URL·행위자). 콘솔 없음. 캡처 `track21-05`.
  미수행: 403 실제 재현·bfcache 뒤로가기·네트워크 스로틀(기존 `api.js` 처리 재사용, 코드 검토로 대체 — BIR 사후 판정 참조).
- **WED 사후 판정: Conforms** [문서 WED 산출 2026-09-08] — 버튼 라벨·색·위치, `.notice` 유지, 안내·모달 문구, 이전 반려
  기록 마크업·위치(`.review-checks` 앞, `|safe` 없음), 큐 배지 없음, 재이동 방식, `#draft-action-error` 3분기 렌더 전부 코드·캡처
  일치. 잔여 확인 요청 1건(CSS diff 0줄)은 오케스트레이터가 `git diff main...HEAD --stat -- static/css` = 0줄 [실측]로 종결.
  서술 정정: 캡처 4는 "화면은 반려 상태로 렌더된 채 DB만 pending으로 바꾼" 상태다(위 (4) 문장과 같은 뜻, 표현만 보강).
- **BIR 사후 판정: Conforms** [문서 BIR 산출 2026-09-08] — 사전 기준 (1)~(4) 전부 충족(오류 문단 분기 밖 1회 렌더·`focus()`,
  반려 전용 분기, `commitAndNavigate`가 `data-committed-redirect`를 자동 부여, 이전 반려 문단 DOM 순서). 저장소 전수 대조:
  `list.html` 인스펙터의 `data-role="draft-action-error"`는 액션 버튼과 같은 조건 안이라 같은 결함 아님. 미수행(403 실제 재현·
  bfcache 뒤로가기·스로틀)은 기존 `api.js` 경로 재사용이라 잔여 위험 Low, QVL 판정에 명시.
- **QVL 완료 판정: 완료** [문서 QVL 산출 2026-09-08] — AC1~AC7·SEC-AC1·3·4 전항 Passed(테스트 이름·줄 매핑), 프론트
  이중 판정 둘 다 Conforms 확인, 도메인 경계·서명 규약·CSS 0줄·문서 실체 확인. 잔여 위험 Low 4건: 403·bfcache·스로틀 브라우저
  미수행(기존 `api.js` 재사용), `reviewed_by` None 렌더는 기존 `|default:"-"` 패턴 이월(전용 테스트 없음), 동시 재오픈/재반려는
  `select_for_update` 구조 방어(전용 테스트 없음, 승인·반려와 동일 수준), QVL 자체는 회귀 재실행 불가(오케스트레이터 실측에
  의존 → 머지 직전 `uv run pytest -q` 1회 재실행 권고). 캡처 5장·임시 계정·임시 드래프트·감사 로그 행은 검증 후 삭제 [실측].

## 이연 (Deferred Refactoring Note 포함)
- H4 SLA 지표(다음 트랙 — ★2 기산점 소비). 승인 취소. 반려 이력 다중 보관. 큐 목록 인라인 재오픈. H10 사유 템플릿.

## 문서 대상·핸드오프 조건
- `docs/BE/draft-review-lifecycle.md`(신설, 가드레일 a~e), `docs/event-operations-criteria.md` 전이 문장,
  `docs/backlog.md` H5 항목 완료 + ★2 기산점 결정 기록(H4 항목에 링크), pr-log(머지 시). 계획서 v2는 검토 반영
  후 이 절을 갱신.

---

