# 이벤트 일괄 비공개 설정(`event-bulk-unpublish`) 가드레일

트랙 24(H2 분할 1/3)로 붙인 `POST /staff/events/bulk-unpublish/`가 지키는
경계만 남긴다. 작업 일지가 아니다. 트랙 25(인라인 단건 비공개/재게시/검증)·
트랙 26(정렬·기간·카테고리 필터)은 H2의 남은 두 조각으로 이 문서 범위 밖이다.

## 배경

운영 기준 "만료 행사 처리"(`docs/event-operations-criteria.md:50-52`)는 종료된
행사를 주 1회 스태프 콘솔에서 정리하라고만 정하고 수단은 정하지 않았다.
재측정 [실측 2026-09-09 shell]: 이벤트 171건 전부 게시 상태, 그중 종료
(`end_date < today`) 148건. 트랙 24 이전에는 단건 토글 뷰
`staff_event_toggle_publish`(`staff/views/events.py:411`)만 있어 148건을
목록 → 수정 → 토글 3화면으로 하나씩 내려야 했다. 이 토글은 **읽은 상태를
반전**하므로, 비공개 처리가 성공한 뒤 응답만 유실되면 재시도가 그 행사를
다시 게시해 버린다. 이번 엔드포인트는 반전이 아니라 "비공개로 설정"이라는
**목표 상태 지정**이라 같은 요청을 몇 번 반복해도 안전하다.

## 엔드포인트 계약

- `POST /staff/events/bulk-unpublish/`(`staff:event-bulk-unpublish`,
  `staff/urls.py:58-62` [실측 grep]), `StaffEventBulkUnpublishView(APIView)`
  (`staff/views/events.py:561`), `permission_classes = [IsAdminUser]`.
- 요청 본문 `{"event_ids": [int, ...]}`. 구조 오류(비객체·빈 목록·비정수·bool
  포함·상한 초과)는 `field_error_response("event_ids", ...)`로 400 —
  드래프트 일괄 뷰와 같은 패턴(`core/errors.py`).
- 정상 요청은 항상 200 `{"succeeded": [id, ...], "failed": [{"id": id,
  "reason": "..."}]}`. 부분 실패가 정상 케이스라 전체 요청을 400으로 막지
  않는다.
- 고정 `reason` 문구는 두 가지뿐이다: 존재하지 않는 id는 `"Not found."`,
  분류되지 않은 예외는 `"Unexpected error."`.

## (a) 목표 상태 설정이다 — 토글이 아니다

`_unpublish_one`(`staff/views/events.py:595`)은 대상이 게시 중이면
`unpublish_event(event=event)`를 호출하고, 그 외(이미 비공개)에는 아무것도
바꾸지 않는다. "현재 상태를 뒤집는" 연산이 아니라 "draft로 만든다"는
목표만 있어, 같은 id로 몇 번을 다시 보내도 결과가 같다(멱등, 아래 (b)).

## (b) 멱등 — 이미 비공개인 항목은 변경·로그 없이 succeeded

이미 `publish_status == draft`인 이벤트는 `unpublish_event`도 호출하지
않고 `StaffActionLog`도 남기지 않은 채 `succeeded`에 포함된다. 같은
`event_ids` 목록으로 두 번째 요청을 보내도 응답의 `succeeded`는 동일하고
로그는 첫 요청분만 남는다 — 응답 유실 후 재시도가 안전한 이유가 이 분기다.

## (c) 상한 20건과 구조 검증 공용화

`MAX_BULK_EVENT_IDS = 20`(`staff/views/events.py:558` [코드]) — 드래프트
일괄 승인 상한 `MAX_BULK_APPROVE_DRAFT_IDS`(`staff/views/drafts.py:266`)와
값은 같지만 우연이며 상수는 분리 유지한다. 구조 검사는
`staff/views/_helpers.py:40` `_validate_bulk_ids(ids, *, field_name,
max_items)`로 일반화했고, `staff/views/drafts.py:269`의
`_validate_bulk_draft_ids`는 이 함수에 위임한다(호출부 2곳·시그니처·오류
메시지 문자열 불변 — 기존 드래프트 일괄 승인·반려 테스트가 회귀를
보증한다). 400은 이 구조 검사에서만 나온다 — 상한 초과도 항목을 하나도
처리하기 전에 걸러진다.

## (d) 항목별 트랜잭션·락, `get_object_or_404` 금지

각 id는 `with transaction.atomic():`(`staff/views/events.py:605` 부근) 안에서
`Event.objects.select_for_update().get(pk=event_id)` → `except
Event.DoesNotExist`(`:615`) → catch-all `except Exception:`(`:621`
`logger.exception`) 순으로 처리한다. `get_object_or_404`는 쓰지 않는다 —
그걸 쓰면 내부에서 던지는 `Http404`가 바깥 catch-all에 걸려
`"Not found."` 대신 `"Unexpected error."`로 뭉개진다(구현 중 뮤테이션
M4로 실측 확인 — B7이 실패). 트랜잭션이 항목 단위라 한 항목이 실패해도
그 항목의 변경분만 롤백되고 나머지 항목 처리는 계속된다.

## (e) 감사: 성공(실제 전환) 항목만 건별 로그, 실패·멱등은 무로그

`unpublish_event`가 실제로 실행된 항목만 `StaffActionLog.objects.create(
action=StaffActionLog.Action.EVENT_UNPUBLISH, target_event=event, actor=...,
ip_address=..., user_agent=...)`를 같은 트랜잭션 안에서 남긴다. 로그
기록이 실패하면(예: `IntegrityError`) 그 항목의 상태 변경도 함께
롤백되고 `catch-all`이 `"Unexpected error."`로 보고한다 — 나머지 항목
처리는 막지 않는다. 이미 비공개였던 항목(멱등)과 실패 항목은 로그를
남기지 않는다.

## (f) 목록 UI: 체크박스·마커 렌더 조건

게시 행(`publish_status == published`)에만 선택 체크박스를 렌더한다.
`#event-bulk-toolbar`·`#event-bulk-empty` 두 마커는 뷰 컨텍스트의
불리언 `has_published_rows`(현재 페이지 `event_rows` 기준 `any`,
`staff/views/events.py:144`)가 참일 때만 서버가 렌더한다
(`templates/staff/events/list.html:34`·`:106`). 처음 설계였던
`{% if event_rows %}`(승인 범위 2 원문)는 필터 없이 그 페이지에 비공개
행만 있는 경우를 거르지 못해 `has_published_rows`로 대체했다(정정,
AC5 "게시 행이 있는 페이지에만"과 일치시킴). 바 자체는 서버가 `hidden`
속성으로 렌더하고 `event_bulk.js`가 체크박스 존재를 확인한 뒤 노출한다.
선택은 현재 페이지·현재 필터에서만 유효하다 — 페이지·필터 전환은 새
문서 로드라 선택 상태가 자동으로 사라진다(별도 저장·복원 로직 없음).

## (g) 성공 반영의 OR 조건과 "이 페이지 새로고침" 링크

성공한 항목의 화면 반영은 두 갈래다: **게시 탭 또는 경고 필터가 걸려
있으면** 그 필터에 더는 속하지 않으므로 행을 DOM에서 제거하고, **전체
탭·경고 없음이면** 배지를 `--published → --draft`로 바꾸고 경고 배지·
체크박스 셀을 비운다. 행이 제거되는 경로에서는 결과 문단에 "이 페이지
새로고침" 링크(`location.href`)를 붙인다 — 목록은 정적 페이저
(`?page=N`)라 서버가 페이지당 15건(`STAFF_EVENT_LISTING_PAGE_SIZE`,
`events/queries.py:184` [코드])을 오프셋으로 자르므로, DOM에서만 행을
지운 채 "다음" 버튼을 누르면 서버 계산 오프셋이 그대로 적용돼 방금
지워진 만큼의 항목을 건너뛴다. 링크로 같은 URL을 다시 불러오면 서버가
새로 페이지를 계산해 건너뜀이 사라진다.

## (h) 수용된 한계

- live region이 없다 — 결과·오류 문단은 `tabindex="-1"` + `focus()`로만
  스크린리더에 읽힌다(포커스 이동 시에만).
- 표 하단 "N–M / total" 카운트는 갱신하지 않는다.
- 부분 실패 시 실패한 행의 체크박스는 선택 상태를 유지한다 — 재시도는
  확인 모달을 다시 통과해야 하며, 서버가 멱등이라 재전송은 안전하다.
- succeeded는 "실제로 전환됐다"와 "이미 그 상태였다"를 구분하지 않는다
  (SRR Low, 이연).

## (i) CSS: `.events-bulkbar`는 `min-height`

`.events-bulkbar`(`static/css/staff/pages/events.css:274` 부근)는
고정 `height`가 아니라 `min-height: 2.25rem`을 쓴다 — 고정 높이였다면
403 실패처럼 바 전체 폭을 차지하는 오류 문단이 바 밖으로 넘쳐 아래 표
헤더에 가려지는 결함이 브라우저 실측으로 발견됐다. 같은 값을 쓰는
드래프트 큐의 `.queue-bulkbar`는 오류 문단이 전체 폭이 아니라 이
증상이 나타나지 않아 그쪽은 고치지 않았다(보고만). 같은 수정에서 결과
문단의 "이 페이지 새로고침" 링크에 밑줄(`.events-bulk-result a`,
`:297-298`)을 더했다 — 색만으로는 구분이 어려웠다.

## 테스트 대응표

`tests/staff/test_staff_event_bulk_unpublish.py`:

| 이름(앞부분) | 검증 |
|---|---|
| `test_익명_사용자는_이벤트_일괄_비공개_설정을_할_수_없다` | 403 |
| `test_일반_사용자는_이벤트_일괄_비공개_설정을_할_수_없다` | 403 |
| `test_요청_구조가_잘못되면_이벤트_일괄_비공개_설정을_거부한다` | 400, parametrize 4건 |
| `test_event_ids_개수가_상한을_초과하면_...` | 400, 21건, 전부 published 유지 |
| `test_게시_중인_이벤트_여러_건을_일괄_비공개로_설정하면_...` | 200, draft 전환 + 로그 2건 |
| `test_이미_비공개인_이벤트가_섞여도_...` | 멱등 — succeeded, 로그는 게시분만 |
| `test_같은_이벤트_ID_목록으로_두_번_요청해도_...` | 재요청 로그 미증가 |
| `test_같은_이벤트_id가_중복된_목록은_두_번째_항목을_멱등_분기로_처리한다` | 한 요청 안 중복 id — 둘 다 succeeded, 로그 1건 |
| `test_존재하지_않는_이벤트_id는_...` | `"Not found."`, 나머지 성공 |
| `test_한_항목의_감사_로그_기록이_예기치_못한_오류로_실패해도_...` | `"Unexpected error."`, 나머지 성공 |
| `test_일괄_비공개_설정은_대상_행을_잠그고_읽는다` | `FOR UPDATE` 쿼리 캡처 |

`tests/staff/test_staff_events_views.py`(그 파일 뒷부분에 추가):

| 이름(앞부분) | 검증 |
|---|---|
| `test_게시_행에만_일괄_선택_체크박스가_있고_비공개_행에는_없다` | 체크박스 유/무, `<col>` 8개 |
| `test_게시_행이_있으면_일괄_선택_바와_실패_사유_표시_영역이_있다` | 마커 존재 |
| `test_게시_행이_없는_페이지에는_일괄_선택_바가_없다` | `?publish_status=draft`, 마커 부재 |
| `test_필터_없이도_게시_행이_없는_페이지에는_일괄_선택_바가_없다` | 필터 없이도 마커 부재 |

## 이연

트랙 25(인라인 단건 비공개/재게시/검증), 트랙 26(정렬·기간·카테고리
필터), 일괄 재게시, 페이지·필터 간 선택 유지, 단축키, `event_bulk.js`
선택 로직과 `draft_bulk.js` 공용 모듈화(두 번째 사용처가 더 생긴 시점에
추출 검토), succeeded의 "실제 전환/이미 그 상태" 구분, 이벤트 목록 live
region, `staff/views/events.py` 인터페이스별 분리(트리거 약 700줄 [문서 DAR]).
