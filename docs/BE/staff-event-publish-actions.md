# 이벤트 게시 액션(일괄 비공개·단건 목표 상태·검증) 가드레일

H2를 세 트랙으로 나눈 것 중 일괄(트랙 24)·단건(트랙 25) 목표 상태 설정과
검증 완료가 공유하는 불변식만 남긴다. 작업 일지가 아니다. 트랙 26(정렬·
기간·카테고리 필터)은 H2의 남은 한 조각으로 이 문서 범위 밖이다.

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
**정정(트랙 25)**: 툴바 마커(`#event-bulk-toolbar`)·빈 문단
(`#event-bulk-empty`)·결과 문단은 뷰 컨텍스트에 `event_rows`가 있으면
항상 `hidden` 속성으로 서버가 렌더하고, JS가 체크박스 존재 여부를 보고
노출을 결정한다(`templates/staff/events/list.html` [실측 grep]). 트랙
24 초판의 `has_published_rows` 불리언 분기(현재 페이지에 게시 행이 있을
때만 마커 자체를 렌더)는 폐기했다 — 그 분기로는 비공개 탭에서 인라인
"다시 게시"로 그 페이지에 처음 게시 행이 생기는 경우 담을 마커가
DOM에 없어 체크박스를 넣을 곳이 없었다(트랙 25 BIR 지적). 이제는
마커가 항상 존재하고 `hidden`만 토글되므로 재게시 직후에도 툴바가
나타날 수 있다. 선택은 현재 페이지·현재 필터에서만 유효하다 —
페이지·필터 전환은 새 문서 로드라 선택 상태가 자동으로 사라진다(별도
저장·복원 로직 없음).

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

## (j) 단건 목표 상태 엔드포인트

`POST /staff/events/<pk>/publish-status/`(`staff:event-publish-status`,
`staff/urls.py` [실측 grep]), `StaffEventPublishStatusView(APIView)`
(`staff/views/events_actions.py`), `permission_classes = [IsAdminUser]`.
본문 `{"publish_status": "draft" | "published"}` — (a)와 같은 **목표 상태
설정**이지 토글이 아니다. `Event.objects.select_for_update()` +
`get_object_or_404`(catch-all 없음, 단건이라 404 그대로 응답)로 잠근 뒤
읽는다. 이미 목표 상태면 (b)와 같은 멱등 분기로 `changed: false`·변경·
로그 없이 200. 응답은 항상 `{"id", "publish_status", "changed",
"quality_badges": [라벨...]}` — `quality_badges`는 서버가
`_event_quality_badges`로 계산해 돌려주므로 프론트가 배지 규칙을
복제하지 않는다. 재게시(`published`) 시 검증 예외는 `REPUBLISH_ERROR_
MESSAGES`(`(예외 클래스, 문구)` 순서 튜플, `staff/views/events.py`
[실측 grep], `_republish_error_message`가 `isinstance` 순회로 문구를
고른다 — 부모 `PublishEventError`가 마지막)로 `error_response(detail,
400)`(`core/errors.py`) 응답한다. 이 표는 PRG 토글 뷰
`staff_event_toggle_publish`의 except 사다리도 같이 쓴다 — 문구가
드리프트하면 두 경로가 동시에 깨진다. **`DuplicateOfficialUrlError`
분기는 문구 표에는 있어도 이 경로에서 실제로 도달할 수 없다** —
`official_url`이 DB 유일 제약이라, 충돌을 재현하려는 draft 이벤트를
같은 URL로 만드는 것 자체가 `IntegrityError`로 막힌다(테스트 시도 기록:
`tests/staff/test_staff_event_inline_actions.py` U8 케이스 목록 위 주석
[실측 grep]). 본문 값 오류(키 없음·목록에 없는 값·문자열 아님)는
`field_error_response("publish_status", ...)` 400.

## (k) 검증 완료 엔드포인트와 목록·수정 화면의 비대칭

`POST /staff/events/<pk>/verified/`(`staff:event-verified`),
`StaffEventVerifiedView(APIView)`(`staff/views/events_actions.py`).
본문 없음, `get_object_or_404` + `transaction.atomic()` 안에서
`mark_event_verified` + `EVENT_VERIFY` 로그. 응답 200 `{"id",
"verified_at"(ISO), "quality_badges"}`. `verified_at`을 되돌리는
서비스가 없어 **검증 완료는 되돌릴 수 없다** — 그래서 목록 인라인
검증 버튼만 확인 모달을 거친다(비공개·재게시는 반대 버튼으로 즉시
되돌릴 수 있어 모달이 없다). **의도된 비대칭**: 수정 화면 검증 카드
(`templates/staff/events/edit.html`)는 게시 상태 조건이 없어 비공개
이벤트에도 노출되지만, 목록 인라인 검증 버튼은 게시 행에만 둔다 —
검증은 "공개 정보의 재확인"이라는 의미라 비공개 상태에서 목록에서
확인할 이유가 적다는 판단(PSO). 수정 화면 쪽은 이번 트랙 범위 밖이라
그대로 둔다.

## (l) 행 배지 `needs_reverification`은 쿼리 없는 모델 메서드

`Event.needs_reverification(self, *, today)`(`events/models.py`
[실측 grep])는 순수 술어다 — `events/queries.py`의
`_needs_reverification_qs`(`F`/`ExpressionWrapper` 기반 쿼리셋)와 같은
규칙(시작일 7일 전 ≤ today ≤ 종료일, 두 날짜 모두 있음, `verified_at`이
없거나 그 날짜가 기준일보다 이전)이지만 쿼리를 새로 던지지 않는다.
목록 페이지 한 장에 최대 `STAFF_EVENT_LISTING_PAGE_SIZE`(15건 [코드])
행이 있어, 행마다 `.exists()`를 다시 물으면 N+1이 되기 때문이다.
`_event_quality_badges`(`staff/views/events.py`)가 이 메서드를 호출해
`ended_still_published` 바로 다음 위치에 라벨 "시작 임박, 미확인"을
추가한다(두 경고는 상호 배타 — 종료된 행사는 재확인 대상이 아니다).
메서드와 쿼리셋의 동등성은 도메인 테스트(`tests/events/
test_event_quality_warnings.py` E1)가 경계 픽스처로 고정한다 — 웹
계층 테스트(B1)는 HTTP 응답으로만 확인하고 쿼리셋을 직접 임포트하지
않는다(`tests/staff/test_staff_events_views.py`는 서비스·쿼리 계층
임포트 금지 가드 대상, `tests/core/test_architecture_boundaries.py`
[실측]).

## (m) 목록 행 인라인 액션 UI 규칙

버튼 3종(`data-row-action="verify"|"unpublish"|"republish"`)을 모든
게시/비공개 행에 항상 렌더하고 해당 없는 것만 `hidden`으로 토글한다
(`templates/staff/events/list.html` [실측 grep]) — 노드를 교체하면
포커스가 유실되므로 항상 존재하는 버튼의 `hidden`만 바꾼다(BIR).
검증 라벨은 `verified_at` 유무로 "검증 완료"/"다시 검증"(수정 화면과
같은 문구). 성공 반영은 세 액션 모두 같은 OR 규칙을 쓴다: **비공개**는
게시 탭이거나 경고 필터가 걸려 있으면 행 제거, 그 외는 배지만 갱신;
**재게시**는 비공개 탭이면 행 제거; **검증**은 경고 필터가
`needs_reverification`이면 행 제거. 요청 중에는 같은 행의 체크박스와
다른 버튼을 잠근다. **BIR 사후 판정 반영**: 잠긴 행에는 `is-row-locked`
표식(class)을 두고, `event_row_actions.js`의 `pageshow`(`event.
persisted`) 리스너가 bfcache 복귀 시 이 표식이 붙은 행만 찾아 풀어준다
— `api.js`의 공용 pageshow 핸들러는 `.is-loading` 버튼만 복구해,
plain `disabled`로 잠근 체크박스·형제 버튼까지는 못 풀어주기 때문이다
(안 풀면 뒤로 가기로 돌아온 행이 영구히 잠긴다). live region(`#event-
live`) 기록은 포커스 이동과 같은 틱을 피하려고 100ms 뒤로 미뤄
쓴다(`window.setTimeout`) — 같은 틱에 쓰면 스크린리더가 갱신을 놓칠
수 있다. 개별 체크박스 `change`는 표(`.events-table`)에
이벤트 위임으로 붙이고(리스너 재부착 없음), 재게시로 체크박스가 새로
생기면 `window.TakuEventBulk.refreshToolbar()`(`static/js/staff/
event_bulk.js` [실측 grep], 재계산 전용·인자·반환 없음·툴바 부재
no-op)만 불러 카운터·툴바 노출을 다시 맞춘다. 행 오류 문단은
`<p data-row-error tabindex="-1" hidden>`(호스트 `data-row-error-host`)
로 개명해 일괄·단건이 셀렉터를 공유한다. live region
`<p id="event-live" aria-live="polite">`(`templates/staff/events/
list.html` [실측 grep])에는 성공·실패 결과 문구를 항상 기록한다 —
결과 문단(`#event-bulk-result`) 자체는 행이 제거될 때만 액션별 동사로
갱신한다(행이 남으면 무갱신). **결함 수정(브라우저 검증)**: 결과
문단은 툴바(`#event-bulk-toolbar`) 안에 있어, 체크박스가 0개라 툴바가
`hidden`인 페이지(예: 비공개 탭)에서는 `showResult`(`static/js/staff/
event_row_actions.js` [실측 grep])가 텍스트·링크를 쓰기 전에 먼저
툴바의 `hidden`을 해제한다 — 그렇지 않으면 문단이 화면에 보이지도
않고 뒤이은 `focus()`도 걸리지 않는다. 같은 이유로, 일괄 비공개가
성공해 행이 남는 경로(`event_bulk.js`의 `applySucceededEvent` [실측
grep])도 그 행의 검증·비공개 버튼을 `hidden`으로, 다시 게시 버튼을
노출로 토글한다 — 일괄 처리와 단건 인라인 처리가 같은 버튼 상태
규칙을 따르게 맞춘 것이다.

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

`tests/staff/test_staff_event_inline_actions.py`(트랙 25, 이름은
`grep -n "^def test_" tests/staff/test_staff_event_inline_actions.py`
[실측]로 확인):

| 이름(앞부분) | 검증 |
|---|---|
| U1 `test_익명_사용자는_이벤트_목표_게시_상태_설정을_할_수_없다` | 403 |
| U2 `test_일반_사용자는_이벤트_목표_게시_상태_설정을_할_수_없다` | 403 |
| U3 `test_publish_status_경로에_GET으로_접근하면_허용되지_않는다` | 405, 상태 불변 |
| U9 `test_존재하지_않는_이벤트_id로_게시_상태_설정을_요청하면_404가_된다` | 404 |
| U4 `test_publish_status_값이_유효하지_않으면_...` | 400, parametrize 3건, `publish_status` 필드 오류 |
| U5 `test_게시된_이벤트를_publish_status_draft로_설정하면_...` | 200, draft 전환 + 로그 1건(actor·ip·UA) |
| U6 `test_이미_목표_게시_상태인_이벤트는_변경과_로그_없이_changed_false를_응답한다` | parametrize 이미_비공개/이미_게시 |
| U7 `test_초안_이벤트를_publish_status_published로_설정하면_...` | 200, 서버 계산 `quality_badges`(종료 이벤트 리터럴) |
| U8 `test_재게시_불변식을_위반한_초안_이벤트는_...` | 400, parametrize 5종(문구 리터럴, "공식_URL_중복"은 (j) 참고로 제외) |
| U10 `test_publish_status_설정은_대상_행을_잠그고_읽는다` | `FOR UPDATE` 쿼리 캡처 |
| V1a `test_익명_사용자는_이벤트_검증_완료_처리를_할_수_없다` | 403 |
| V1b `test_일반_사용자는_이벤트_검증_완료_처리를_할_수_없다` | 403 |
| V1c `test_verified_경로에_GET으로_접근하면_허용되지_않는다` | 405 |
| V3 `test_존재하지_않는_이벤트_id로_검증_완료를_요청하면_404가_된다` | 404 |
| V2 `test_스태프가_재확인_대상_이벤트를_검증_완료_처리하면_...` | 200, `verified_at` 기록 + `quality_badges == []` |

`tests/staff/test_staff_events_views.py`(그 파일 뒷부분, HTTP만·서비스·
쿼리 계층 임포트 금지):

| 이름(앞부분) | 검증 |
|---|---|
| B1 `test_시작_임박_미확인_배지는_행_표시와_대시보드_카운트가_같은_이벤트에_대해_일치한다` | 배지 표시와 대시보드 카운트 일치(경계 픽스처) |
| R1 `test_게시_행에는_비공개와_검증_버튼이_노출되고_비공개_행에는_다시_게시_버튼만_노출된다` | 버튼 3종 `hidden` 유무 |
| R2 `test_검증_이력이_없는_게시_행은_검증_완료_라벨이고_이미_검증된_게시_행은_다시_검증_라벨이다` | parametrize 미검증/기검증 |
| R3 `test_이벤트_목록에_행_인라인_액션_스크립트와_live_region이_로드된다` | 스크립트 태그 + `#event-live` |
| L1 `test_게시_행에만_일괄_선택_체크박스가_있고_비공개_행에는_없다` | 체크박스 유/무, `<col>` 8개(변경 없음) |
| L3 `test_게시_행이_있으면_일괄_선택_바와_실패_사유_표시_영역이_있다` | 마커 존재, `data-row-error-host`·`tabindex="-1"`(개명 반영) |
| T1(구 L2) `test_게시_행이_없는_페이지에도_일괄_선택_바가_숨김_상태로_렌더된다` | `?publish_status=draft`, 마커는 존재하되 `hidden`((f) 정정 반영) |
| T1(구 L2b) `test_필터_없이도_게시_행이_없는_페이지에_일괄_선택_바가_숨김_상태로_렌더된다` | 필터 없이도 마커는 존재하되 `hidden` |

`tests/events/test_event_quality_warnings.py`:

| 이름(앞부분) | 검증 |
|---|---|
| E1 `test_needs_reverification_메서드는_재확인_대상_쿼리셋과_같은_판정을_한다` | 경계 픽스처로 모델 메서드 == 쿼리셋 `.exists()` |

`tests/staff/test_staff_event_publish_delete_views.py`(P1, 기존 테스트
`:95` 부근에 단언 추가): 제목 없는 초안 재게시 토글 거부 시
`messages` 컨텍스트에 "제목이 없어 다시 게시할 수 없습니다." 문구가
그대로 포함되는지 고정 — PRG 뷰와 JSON 뷰가 `REPUBLISH_ERROR_MESSAGES`를
공유하므로 문구 드리프트를 이 테스트가 잡는다.

## 이연

트랙 26(정렬·기간·카테고리 필터), 수정 화면 PRG 토글의 목표 상태화
(**같은 재시도-반전 결함이 수정 화면에 그대로 남아 있다** — 이번
트랙은 목록 인라인만 목표 상태로 바꿨다), `StaffEventBulkUnpublishView`
(트랙 24)를 `staff/views/events_actions.py`로 옮기는 순수 이동(다음
트랙에서 함께 검토), 일괄 재게시, 페이지·필터 간 선택 유지, 단축키,
`event_bulk.js`/`event_row_actions.js` 선택·판정 로직과
`draft_bulk.js` 공용 모듈화(두 번째 사용처가 더 생긴 시점에 추출
검토), succeeded의 "실제 전환/이미 그 상태" 구분, `staff/views/
events.py` 인터페이스별 분리(트리거 약 700줄 [문서 DAR]), **재검증
("검증 완료") 운영 절차 정의 — `docs/event-operations-criteria.md`에
아직 없음, 사용자 결정 필요**(백로그에도 기록).
