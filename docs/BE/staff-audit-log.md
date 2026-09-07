# 드래프트 admin API 감사 로그(`draft_create`·`draft_update`) 가드레일

트랙 20(H7 선택지 2)으로 `/api/event-drafts/`(POST·PATCH)에 붙인 감사 기록이
지키는 경계만 남긴다. 작업 일지가 아니다.

## (a) 감사 로그는 staff 소유 — admin API도 staff로 이동했다

`drafts`는 `staff`를 임포트하지 않는 경계 가드(`tests/core/test_architecture_boundaries.py`)가
있어서, 감사가 필요한 admin API(`AdminEventDraftListCreateView`·
`AdminEventDraftDetailView`)는 `staff/views/draft_api.py`로 옮겨 staff가
직접 소유한다(`staff/api_urls.py`, URL 이름 `event-drafts`·`event-draft-detail`
불변). 승인·반려 뷰(`staff/views/drafts.py`)와 같은 패턴이다.

## (b) 네트워크 fetch는 DB 트랜잭션 밖 — 그래서 서비스를 나눴다

`drafts/services.py`의 `create_draft_from_url`을 `prepare_draft_from_url`
(`:111`, 네트워크·추출, DB 접근 0)과 `persist_prepared_draft`(`:176`, DB 저장 +
`IntegrityError`→`DraftCreationDuplicateError`, 내부 `transaction.atomic()`)로
나눴다. `staff/views/draft_api.py`의 `create()`(`:85`)는 `prepare_draft_from_url`을
트랜잭션 밖에서 먼저 호출하고, 성공하면 `with transaction.atomic():` 블록
(`:111`) 안에서 `persist_prepared_draft` + `StaffActionLog.objects.create(...)`
(`:113`)를 함께 실행한다. `update()`(`:163`)도 같은 패턴으로 `with
transaction.atomic():`(`:169`) 안에서 `update_draft` + 로그 기록을 묶는다.
`fetch_html`이 최대 4홉·홉당 5.0초 [코드]로 DB 커넥션을 오래 붙잡지 않게
막는 경계다.

## (c) 실패 경로는 무로그 — 승인·반려 선례와 동일

`create()`의 fetch/추출 예외군(`DraftCreationUnsafeUrlError` 등)은
`persist`+로그 블록 진입 전에 반환되므로 로그가 없다. `DraftCreationDuplicateError`는
`persist_prepared_draft` 내부 atomic에서 발생해 그 저장 자체가 롤백되므로
로그도 없다. `update()`의 `DraftStateError`·`DraftVocabError`도 `update_draft`
호출 시점에 나서 로그 블록에 도달하지 않는다. 로그 기록(`StaffActionLog.objects.create`)
자체가 실패하면(예: DB 오류) `with transaction.atomic()` 블록 전체가 롤백돼
드래프트 생성·수정도 함께 사라진다 — 감사 기록 실패를 조용히 무시하지 않는다.

## (d) 비감사 경로 3곳 — 러너·비스태프 호출은 이 로그를 남기지 않는다

`create_draft_from_url`(합성 함수, `:202`)·`create_draft_from_fields`를 admin
API가 아닌 다른 곳에서 부르면 `StaffActionLog`가 남지 않는다. 이 로그는
"스태프가 admin API를 통해 조작했다"는 사실만 기록하지, 드래프트 생성 자체를
추적하지 않는다.

- `drafts/candidate_validation.py:287` — 후보 URL 자동 검증 러너가 제출.
- `drafts/management/commands/discover_drafts.py:191` — 관리 명령이 소스를 크롤링해
  자동 생성(actor 없음).
- `web/promotion.py:74` — 일반 사용자가 개인 기록을 공식 제보로 승격. 스태프
  행동이 아니다.

셋 다 별도 시스템 감사 항목으로 이연됐고(트랙 20 계획서 "배제"), 이번
변경으로 로그가 추가되지 않는다.

## (e) 전후 값 없음·대상 소실 시 추적 한계

`draft_create`·`draft_update` 로그는 `target_draft` FK만 남기고 변경 전/후
필드 값은 남기지 않는다(H12(b) 보류). `target_draft`는
`on_delete=models.SET_NULL`이라 드래프트가 삭제되면 로그는 남아도 어떤
드래프트였는지 더는 알 수 없다.
