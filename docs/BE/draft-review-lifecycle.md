# 드래프트 검수 생애주기와 재오픈(`reopen_draft`) 가드레일

트랙 21(H5)로 붙인 반려 드래프트 재오픈이 지키는 경계만 남긴다. 작업 일지가 아니다.

## (a) 상태값은 그대로다 — 재오픈은 신규 상태가 아니라 PENDING 복귀다

`EventDraft.ReviewStatus`는 `pending`/`approved`/`rejected` 3상태 그대로다
[코드]. 재오픈은 `rejected → pending` 전이일 뿐 새 상태값을 만들지 않는다.
전이 함수는 `drafts/services.py`의 `approve_draft`(`:303`)·`reject_draft`
(`:336`)·`reopen_draft`(`:355`) 셋뿐이고 [실측 `grep -n`], 셋 다 공통
상태 가드 `_get_draft_for_update(draft_id, *, expected_status)`(`:242`,
기본값 없음, `select_for_update` 사용)를 거친다.

## (b) 재오픈은 반려 기록을 지우지 않는다

`reopen_draft`는 `review_status`·`reopened_at`만 갱신하고 `reviewed_by`·
`rejected_at`·`rejection_reason`은 건드리지 않는다. 재검수자가 왜 반려됐는지
봐야 하고, 감사 로그(아래 (d))는 사유를 담지 않기 때문이다. 상세 화면은
이 기록을 뷰 컨텍스트 `was_reopened`(`staff/views/drafts.py`
`event_draft_detail`)로 판단해 "이전 반려 기록" 문단으로 보여준다
(`templates/core/drafts/detail.html`).

## (c) `reopened_at`은 최근 1회만 보존한다 — H4 기산점이 이 값을 쓴다

재반려 후 다시 재오픈하면 `reopened_at`을 덮어써 직전 값은 남지 않는다.
H4(검수 SLA 지표)의 대기 시작 기산점 결정(사용자 결정 ★2, 2026-09-08,
PSO 기본값 수용): `reopened_at`이 있으면 그 값, 없으면 `created_at`을
기산점으로 쓴다.

## (d) 감사: `draft_reopen`은 승인·반려와 같은 트랜잭션·로그 규칙을 따른다

`StaffActionLog.Action.DRAFT_REOPEN`("반려 재오픈")은
`staff/views/drafts.py`의 `StaffDraftReopenView.post`(`:390`) 안
`transaction.atomic()`에서 `reopen_draft` 호출과 함께 기록된다. 로그 기록
자체가 실패하면 재오픈도 함께 롤백된다(승인·반려 선례, `docs/BE/staff-audit-log.md`
(c)와 동일한 무로그 규칙). 400(`DraftStateError`)·403(권한 없음)·404
(`DraftNotFoundError`) 실패 경로는 로그를 남기지 않는다. `draft_create`·
`draft_update`도 같은 무로그 규칙을 따른다(`docs/BE/staff-audit-log.md` (c)).

## (e) `source_url` unique라 재오픈이 유일한 복구 경로다

`EventDraft.source_url`은 unique 제약이라 반려된 드래프트와 같은 URL로 새
드래프트를 만들 수 없다. 그래서 반려 복구는 `POST /staff/drafts/<id>/reopen/`
(`IsAdminUser`, `staff:draft-reopen`)뿐이고, 이 경로가 생기기 전까지 유일한
복구 수단이던 `manage.py shell` 조작이 더는 필요 없다.

## (f) 승인된 드래프트에 과거 반려 기록이 공존할 수 있다

반려 → 재오픈 → 승인 경로를 거치면, 승인된(`approved`) 드래프트에도
`rejected_at`·`rejection_reason`(과거 반려 기록)이 남아 있을 수 있다.
상태별 화면 분기는 이 잔존 필드가 아니라 `review_status` 값만 본다 — 잔존
필드를 상태 판단에 쓰면 승인된 드래프트가 반려 문단으로 잘못 렌더된다.

## (g) 마이그레이션은 경량이고 롤백은 코드 우선이다

drafts 0007은 `ALTER TABLE "drafts_eventdraft" ADD COLUMN "reopened_at"
timestamp with time zone NULL;` 1문장이다 [실측 `manage.py sqlmigrate drafts 0007`].
staff 0010은 `Action` choices만 바꾸는 `AlterField`라 실행 SQL이 없다
(`-- (no-op)`) [실측 `manage.py sqlmigrate staff 0010`]. 롤백은 코드 우선
정책을 따른다 — 컬럼이 남아 있어도 구코드가 참조하지 않으므로 무해하다.

## (h) `EventDraftUpdateSerializer`는 `reopened_at`을 읽기 전용으로 막는다

`EventDraftUpdateSerializer.Meta.read_only_fields`(`drafts/serializers.py`)에
`reopened_at`을 빠뜨리면 PATCH 본문에 실려 온 `reopened_at`이 `update_draft`
까지 내려가 `DraftImmutableFieldError`를 던지고, 그 예외를 잡지 않는
`staff/views/draft_api.py`가 500으로 응답한다. 이 계약은
`tests/staff/test_staff_draft_api.py`의
`test_수정_요청_본문의_reopened_at은_무시되고_500이_나지_않는다`가 고정한다.
