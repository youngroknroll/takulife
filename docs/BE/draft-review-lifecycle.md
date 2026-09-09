# 드래프트 검수 생애주기와 재오픈(`reopen_draft`) 가드레일

트랙 21(H5)로 붙인 반려 드래프트 재오픈이 지키는 경계만 남긴다. 작업 일지가 아니다.
트랙 22(H4 검수 SLA 지표)의 (i)~(k)도 담는다. 트랙 23(H3 유입 경로)의
(l)도 담는다.

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

예외 — 0008(`origin`)은 NOT NULL이고 정방향 마이그레이션이 DB 기본값을
제거하므로(sqlmigrate: `ADD COLUMN "origin" varchar(20) DEFAULT 'collected'
NOT NULL;` 뒤 `ALTER COLUMN "origin" DROP DEFAULT;` [실측 `manage.py
sqlmigrate drafts 0008`]) 코드만 되돌리면 구코드의 드래프트 INSERT가 NOT
NULL 위반으로 실패한다 — 롤백은 `manage.py migrate drafts 0007`(DROP
COLUMN) 역방향을 코드 롤백과 함께 실행한다(DOR).

## (h) `EventDraftUpdateSerializer`는 `reopened_at`을 읽기 전용으로 막는다

`EventDraftUpdateSerializer.Meta.read_only_fields`(`drafts/serializers.py`)에
`reopened_at`을 빠뜨리면 PATCH 본문에 실려 온 `reopened_at`이 `update_draft`
까지 내려가 `DraftImmutableFieldError`를 던지고, 그 예외를 잡지 않는
`staff/views/draft_api.py`가 500으로 응답한다. 이 계약은
`tests/staff/test_staff_draft_api.py`의
`test_수정_요청_본문의_reopened_at은_무시되고_500이_나지_않는다`가 고정한다.

## (i) 검수 SLA 지표는 드래프트 필드로만 집계한다 — 반려율·평균 처리 정의

`drafts/queries.py`의 `draft_review_sla(*, days=7, now=None)`(`:34`)
[실측 `grep -n`]: 최장 대기 = 검토 대기 중 기산점(`reopened_at` or
`created_at`) 최솟값 기준 `now − 기산점`. 평균 처리·반려율 = 창
`[now − 7일, now)`에 결정된 드래프트(현재 상태가 approved면 `approved_at`,
rejected면 `rejected_at`)의 `결정 시각 − 기산점` 평균과 반려 비율.
사용자 미확인 기본값(PSO 수용, 2026-09-08): ★1 집계 원천은 감사 로그가
아니라 드래프트 필드다 — 반려 → 재오픈 → 승인은 승인 1건으로만 센다
(과거 반려 기록이 남아 있어도 `review_status`가 approved이기 때문이다,
위 (f) 참조). ★2 창은 7일이고 직전 창 대비 증감은 넣지 않는다. ★3 반려
사유 분포는 이 지표에서 빠지고 H10(사유 템플릿) 뒤로 이연한다.

## (j) 결정 시각이 없는 옛 승인·반려 건은 SLA 창에 들어오지 않는다

0002 마이그레이션이 `approved_at`·`rejected_at`을 데이터 이관 없이
추가해서 그 이전에 결정된 건은 두 필드가 모두 None이다. `draft_review_sla`의
`Case` 결정 시각 표현식이 이 경우 NULL이 되므로 창 필터
(`decided_at__gte`/`decided_at__lt`)에서 자동으로 빠진다 — 로컬 DB에서는
승인 4건·반려 4건 전부 이 경로였다 [실측 2026-09-08 shell]. 핀 테스트는
`tests/drafts/test_drafts_queries.py::TestDraftReviewSla::test_결정_시각이_없는_레거시_승인_반려_건은_창_집계에서_제외된다`
(`:201`) [실측 `grep -n`].

## (k) 표시 규칙 — 값 없음은 하이픈, 단위는 48시간 기준

`staff/views/__init__.py`의 `_build_review_sla_cards`(`:170`)와
`_format_duration`(`:162`) [실측 `grep -n`]: `value`는 표시용 문자열이거나
None이다 — 정수 0을 그대로 넘기면 템플릿의 `is not None` 분기가 아니라
진위값 분기로 오판할 위험이 있어 문자열로만 넘긴다. 시간 단위는
`total_seconds()/3600`이 48 미만이면 "시간", 이상이면 "일"로 바꾸고,
반려율은 정수 %로 반올림한다. 값이 없으면 카드는 `-`를 보여준다(콘솔
전역 `default:"-"` 관례를 따른다). 값 없음 노트는 카드 컨테이너 안
자식이라 스크린리더 접근 가능 이름에 포함된다. `decided_at`의 `Case`
필터는 인덱스를 타지 못한다 — 건수가 수만 규모에 이르면 부분 인덱스를
검토한다(이연).

## (l) 유입 경로 origin — 사용자 제보만 user_report, source_name과 다른 축

`EventDraft.Origin`(`drafts/models.py`, `collected`/`user_report`, 기본값
`collected`)은 드래프트가 어떻게 만들어졌는지만 구분한다. 값을 정하는 곳은
`create_draft_from_fields(origin=...)` 호출자뿐이며, 제보 경로
`web/promotion.py`의 `promote_personal_entry`(`:83`)만 `origin=user_report`를
넘기고 [실측 `grep -n`], 자동 수집(`create_draft_from_url`)과 스태프의 URL
직접 생성(admin API)은 인자를 생략해 기본값 `collected`를 그대로 쓴다.
`source_name`은 승인 시 이벤트로 복사돼 소비자에게 "N 제공"으로 노출되는
출처 이름이라 `origin`과는 다른 축이고, 유입 경로 구분 표시에 쓰지 않는다.

제보는 드래프트 id를 `PersonalEntry`에 남기지 않아 과거 제보 드래프트를
역추적할 수 없으므로 백필하지 않았다. 따라서 0008 이전 행은 실제 유입
경로와 무관하게 전부 collected로 표시되며, 이는 알려진 오표시다.

표시: 큐 표·인스펙터 배지 "제보"(`queue-origin-badge`, 상태 칩과 별도
클래스 — `draft_bulk.js`가 상태 칩을 클래스·`data-draft-status-chip`으로
갱신하므로 셀렉터가 겹치면 안 된다), 상세 상단바 "공식 제보 · " 접두. API는
읽기 전용(`EventDraftSerializer`·`EventDraftUpdateSerializer` 양쪽
`read_only_fields` — 트랙 21 `reopened_at` 선례). 라벨 계약은
`tests/drafts/test_draft_labels.py`가 `drafts/labels.py`의
`ORIGIN_LABELS` 키와 `EventDraft.Origin.values`를 맞춰 고정한다.

사용자 미확인 기본값(PSO 수용 2026-09-09): 값은 둘만 두고(세분화 없음),
유입 경로 필터·통계는 만들지 않으며, 기존 드래프트 백필도 하지 않는다.
