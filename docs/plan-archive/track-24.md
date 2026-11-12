# 트랙 24: 이벤트 일괄 비공개 설정 — H2 분할 1/3 (2026-09-09) [v2 — PSO·DAR·TDD 코치·SRR·WED·BIR 검토 반영]

> **검토 반영 요약(v1 → v2)** [문서 각 역할 산출, 인용 file:line 오케스트레이터 재확인 2026-09-09]
> - PSO: 분할 승인, ★1~★5 수용(★3은 조건부). **25·26 순서 뒤집음** — 인라인 단건 액션(원문·프론트 표 순서, 24와 같은 3화면
>   근거)이 필터·정렬(운영 기준 요구 없음, 종료 경고 칩이 이미 있음)보다 먼저 → 트랙 25 = 인라인 단건, 트랙 26 = 필터·정렬.
>   **핵심 발견**: 필터 목록에서 성공 행을 DOM에서만 지운 뒤 정적 페이저(`templates/core/partials/_pager.html:37·42` `?page=N`)로
>   다음 페이지를 누르면 서버 결과가 15칸 [코드] 밀려 항목을 건너뛴다 → ★6 결과 문단에 "이 페이지 새로고침" 링크(현재 URL) +
>   AC7 다페이지 순차 시나리오. 일괄 재게시 배제 동의. 상한 20 [코드] ≥ 페이지 15 [코드]라 전체 선택이 상한에 안 걸림 [계산].
> - DAR: 엔드포인트는 신규 파일이 아니라 **`staff/views/events.py`**(자원별 단일 파일 관례 — `drafts.py`가 단건·일괄을 함께 둠).
>   구조 검증은 `_helpers.py`에 `_validate_bulk_ids(ids, *, field_name, max_items)`로 일반화하고 `drafts.py` 두 호출부를 위임
>   (기존 일괄 테스트로 회귀 보증), 상수 `MAX_BULK_APPROVE_DRAFT_IDS`·`MAX_BULK_EVENT_IDS`는 분리 유지(값 20 우연 일치). **결함
>   위험**: 항목 루프에서 `get_object_or_404`를 쓰면 `Http404`가 catch-all에 삼켜져 "Not found." 계약이 깨진다 →
>   `Event.objects.select_for_update().get(pk=...)` + `except Event.DoesNotExist`. 이연 트리거: `events.py` 약 700줄 초과 시 분리.
> - SRR: 차단 없음. 되돌리기 비대칭(대량 비공개 ↔ 단건 재게시만) → ★4 확인 모달에 "되돌리려면 각 건을 개별적으로 다시 게시해야
>   합니다" 1문장. catch-all은 `logger.exception` + `event_id` 인자 + 분류 예외 뒤(선례 `drafts.py:343-350`). 멱등(이미 draft →
>   succeeded·무로그)은 감사 약화가 아니라 토글 재시도 결함 해소. Low: succeeded가 "실제 전환"과 "이미 그 상태"를 구분 안 함(이연).
> - WED: `<col>` 8개(선두 2rem) [계산], `.events-table` `min-width` 70.75 → 72.75rem [계산], 체크박스 셀은 항상 렌더·내용만
>   조건부(접근 이름 = 제목), bulkbar는 서버 `hidden` 렌더 + JS가 체크박스 존재 시 노출(드래프트 `initBulkToolbar` 선례), 버튼은
>   중립 `.staff-cta`(단건 화면 `edit.html:140` `--neutral` 선례, 되돌릴 수 있는 조작), 전체 탭 성공 시 배지 modifier
>   `--published → --draft`·경고 배지 제거·체크박스 셀 비움, 빈 페이지 전용 문구 `#event-bulk-empty`(서버 hidden 렌더), 실패
>   사유는 `events-tail-cell`에 `flex-wrap` + 전체 폭 문단, CSS는 drafts 값 복제(S6) + **`.staff-cta:disabled`는 drafts.css에만
>   있어 events.css 보강 필수** [실측 grep]. 표 하단 카운트 미갱신 수용.
> - BIR: ★5는 드래프트에 없던 **OR 이중 조건**(게시 탭 또는 경고 필터 → 행 제거 / 그 외 → 배지 갱신) — 세 경로 전부 브라우저
>   증거. 결과 문단 `tabindex="-1"` 필수, 재시도는 확인 모달 재통과(멱등이라 안전), Tab 순서 = 체크박스 → 같은 행 "수정" 링크.
>   `draft_bulk.js` 이식 제외 지점: 150-171(행/패널 조회)·173-190(live announce)·194-278(현재 행·빈 상태·J/K)·314-329(상태 라벨
>   맵)·359-380(패널 갱신)·495-546(행 판정)·601-648(`TakuQueue`) [실측 sed]. live region 없음 → 결과는 포커스 시에만 읽힘(문서 기록).
> - TDD 코치: B3 = parametrize 4건 + 상한 초과 별도, B6 별도 유지(계약), **B9(상수 리터럴 핀) 기각**, **B10 락 계약 추가**(선례
>   `tests/staff/test_staff_event_publish_delete_views.py:108-119` `FOR UPDATE` 캡처), L2·L3 짝 강제, 행 슬라이스 앵커는
>   `events-id-cell">{id}</td>`. 새 파일 `tests/staff/test_staff_event_bulk_unpublish.py` 타당.
> - 정정: ★0 순서(25↔26), v1 "신규 `event_bulk.py`" → `events.py`로.

> 배경: `docs/backlog.md` H2(P1, 제품 권고; WED는 P0로 봄) "이벤트 일괄 선택·일괄 게시 내리기, 목록 인라인 토글/검증,
> 정렬·기간·카테고리 필터". 사용자 지시(2026-09-09) "진행" → #347·#348 머지 뒤 H2 착수. **재측정 [실측 2026-09-09 shell]**:
> 이벤트 171건 전부 게시 상태, 그중 종료(`end_date < today`) 148건, 종료일 없는 게시 0건 — 운영 기준 "만료 행사 주 1회 정리"
> (`docs/event-operations-criteria.md:50-52`)를 지금 콘솔로 하려면 148건을 목록 → 수정 → 토글 3화면으로 하나씩 내려야 한다.
> 계약(2026-09-06): 일괄 내리기는 "비공개로 설정"이지 토글이 아니다 — 단건 토글 뷰 `staff_event_toggle_publish`
> (`staff/views/events.py:396-443` [실측 grep])는 읽은 상태를 반전하므로 응답 유실 뒤 재시도가 재게시한다. 선례: 드래프트 일괄
> 승인·반려 `StaffDraftBulkApproveView`·`StaffDraftBulkRejectView`(`staff/views/drafts.py`, 상한 `MAX_BULK_APPROVE_DRAFT_IDS = 20`
> [코드], `_validate_bulk_draft_ids`, 항목별 `transaction.atomic()` + 감사 로그, 응답 `{"succeeded": [...], "failed": [{"id",
> "reason"}]}` 항상 200), 큐 bulkbar 마크업(`templates/core/drafts/list.html:50-61`)·행별 실패 사유(`:118-123`)·JS
> `static/js/staff/draft_bulk.js`(649줄 [실측 wc], 선택 상태·`applyBulkResult`). 이벤트 목록(`templates/staff/events/list.html`
> 85줄 [실측 wc])은 JS를 로드하지 않고 `<col>` 7개 고정폭, 페이지 크기 `STAFF_EVENT_LISTING_PAGE_SIZE = 15`(`events/queries.py:184`
> [코드]). `unpublish_event`(`events/services.py:186`)는 검증 없이 `publish_status = DRAFT`만 저장(멱등 설정에 적합), 감사
> 액션 `EVENT_UNPUBLISH`는 이미 있음. 프론트 사전 검토 `.docs/FE/2026-09-06-staff-backoffice-frontend-review.md:40`·`:77-90`
> (WED H2 상세 명세)·`:157`(BIR — 목표 상태 지정 API·선택은 DOM 재질의로 초기화·"비공개로 설정" 문구). 기준선 [실측 2026-09-09
> main 6e4ccce] `uv run pytest -q` 2488 passed / 88.79초. **정정 기록(오케스트레이터 결함)**: pr-log·백로그 기준선 행에 결과
> 파일을 읽기 전 "76.84초"를 적어 docs PR #349를 열었다 → 실측 88.79초로 정정 커밋. 규칙: 숫자는 측정 출력을 읽은 뒤에만 옮긴다.
> 브랜치 `feat/event-bulk-unpublish`(main 6e4ccce).

## ★0 분할 (PSO 승인, 순서 정정)
H2를 세 트랙으로 나눈다 — 24 **일괄 비공개 설정**(체크박스·bulkbar·목표 상태 JSON 엔드포인트·행별 실패 사유), **25 인라인
단건 비공개/재게시/검증**(토글 뷰 JSON 분기 또는 별도 엔드포인트 — 24와 같은 3화면 근거, 원문 순서), **26 정렬·기간·카테고리
필터**(`_event_filter_query_pairs` 화이트리스트 확장, `list_query` 공유 템플릿 3개 — 종료 경고 칩 필터는 이미 있어 급하지 않음).
근거: 24만으로 종료 148건 정리 [실측]가 가능(가장 큰 운영 가치), 25·26은 각각 독립 PR. 한 트랙 = 한 PR 관례.

## 승인 범위 (★ = 사용자 미확인 가정 — PSO 판정 병기)

1. **엔드포인트** `POST /staff/events/bulk-unpublish/`(`staff:event-bulk-unpublish`, `StaffEventBulkUnpublishView(APIView)`,
   `IsAdminUser`, 본문 `{"event_ids": [int, ...]}`). ★1 **목표 상태 설정(set)**: 항목별 `transaction.atomic()` +
   `Event.objects.select_for_update()`; 게시 중이면 `unpublish_event` + `StaffActionLog(EVENT_UNPUBLISH, target_event)`, 이미
   비공개면 **변경·로그 없이 succeeded**(멱등 — 재시도가 재게시하지 않음), 없는 id는 failed `"Not found."`, 분류되지 않은 예외는
   failed `"Unexpected error."`(`logger.exception("bulk unpublish: unexpected error for event_id=%s", event_id)` — 분류 예외
   `Event.DoesNotExist` 뒤, 선례 `drafts.py:343-350`). 항목 조회는 **`Event.objects.select_for_update().get(pk=event_id)` +
   `except Event.DoesNotExist`**(`get_object_or_404` 금지 — Http404가 catch-all에 삼켜짐, DAR). 상한 20건 [코드 선례] — 상수
   `MAX_BULK_EVENT_IDS = 20`(`events.py` 소유, 드래프트 상수와 분리), 구조 검증은 `staff/views/_helpers.py`에
   `_validate_bulk_ids(ids, *, field_name, max_items)`로 일반화하고 `drafts.py`의 `_validate_bulk_draft_ids`는 이를 위임(메시지
   문자열 불변 — 기존 일괄 테스트 회귀로 보증). 응답은 항상 200(부분 실패 정상), 구조 오류만 400
   `field_error_response("event_ids", ...)`. 위치는 **`staff/views/events.py`**(540줄 [실측 wc] — 자원별 단일 파일 관례, DAR;
   분리 트리거 약 700줄), `staff/views/__init__.py` re-export, `staff/urls.py` 라우트 1개 [계산].
2. **목록 화면**(`templates/staff/events/list.html`, WED 사양): ★2 `<col style="width:2rem">`를 맨 앞에 추가 → `<col>` 8개
   [계산], `.events-table` `min-width` 70.75rem → 72.75rem [계산](1024px는 이미 가로 스크롤 대상 — 신규 회귀 아님). 헤더
   `<th scope="col"><span class="sr-only">선택</span></th>`. 바디 `<td>`는 항상 렌더, 내용은 `publish_status == "published"`일 때만:
   `<label class="sr-only" for="event-select-{{ id }}">{{ title|default:"(제목 없음)" }} 선택</label><input type="checkbox"
   id="event-select-{{ id }}" class="event-select-checkbox" data-event-select data-event-id="{{ id }}">`. 표에
   `data-selected-publish-status="{{ selected_publish_status }}" data-selected-warning="{{ selected_warning }}"`. bulkbar는
   `.events-toolbar` 뒤·`.events-table-wrap` 앞, `{% if event_rows %}` 안, **서버는 항상 `hidden`으로 렌더**하고 JS가 체크박스가
   있을 때 노출: `<div class="events-bulkbar" id="event-bulk-toolbar" hidden><label class="events-select-all"
   for="event-select-all"><input type="checkbox" id="event-select-all"><span class="sr-only">전체 선택</span></label><span
   class="mono" id="event-bulk-selected-count">0건 선택</span><button type="button" id="event-bulk-unpublish-btn"
   class="staff-cta" disabled>선택 항목 비공개로 설정</button><p id="event-bulk-result" class="mono events-bulk-result"
   tabindex="-1"></p><p id="event-bulk-error" class="events-inline-error" tabindex="-1" hidden></p></div>`. 빈 페이지 문단
   `<p class="events-empty" id="event-bulk-empty" tabindex="-1" hidden>이 페이지의 이벤트를 모두 처리했습니다. 새로고침하면 갱신된
   목록을 볼 수 있습니다.</p>`를 `.events-table-wrap` 형제로 서버 렌더. "경고 / 작업" 셀에 `data-bulk-fail-reason-host` +
   `<p class="events-inline-error" data-bulk-fail-reason hidden></p>`. ★3 선택은 현재 페이지·현재 필터에서만 유효, 페이지·필터
   전환은 새 문서 로드라 자동 초기화. 화면 하단에 `<script defer src="{% static 'js/staff/event_bulk.js' %}">`(기존 목록은 JS 없음).
3. **JS** 신규 `static/js/staff/event_bulk.js`(`draft_bulk.js` 42-108 선택 상태·396-432 결과 반영·434-494 버튼 바인딩 구조만
   이식; BIR 제외 지점 150-278·314-329·359-380·495-546·601-648은 옮기지 않음; `draft_bulk.js` 무변경): 개별/전체 3상태, 카운터,
   버튼 활성 조건, `initBulkToolbar`(체크박스 존재 시 `hidden` 해제). 확인 모달 ★4 **"선택한 N건을 비공개로 설정합니다. 되돌리려면
   각 건을 개별적으로 다시 게시해야 합니다. 진행할까요?"**(SRR). `TakuAPI.post("/staff/events/bulk-unpublish/", {event_ids})` →
   ★5 성공 항목: `data-selected-publish-status === "published"` **또는** `data-selected-warning`이 비어 있지 않으면 행 제거(그
   필터에 더는 속하지 않음), 그 외(전체 탭·경고 없음)는 `events-status-badge--published → --draft`·텍스트 "비공개", 경고 배지
   제거, 체크박스 셀 비움. 실패 항목: 행 `data-bulk-fail-reason`에 사유 표시. 결과 문단: "N건 모두 비공개 완료." / "성공/전체건
   비공개 완료. 처리되지 않은 항목은 행에서 사유를 확인하세요." + ★6 행이 제거된 경우 **"이 페이지 새로고침"** 링크(`location.href`,
   PSO 발견 — 정적 페이저로 다음 페이지를 누르면 항목을 건너뜀) → `resultEl.focus()`. 마지막 대상 행이 제거되면
   `.events-table-wrap` hidden + `#event-bulk-empty` 노출·포커스. 403은 `CSRF_OR_SESSION_MSG`, 그 외 `formatError` → 오류 문단
   포커스, 버튼 복구(재시도는 모달 재통과, 서버 멱등). 표 하단 "N–M / total" 미갱신. 단축키 없음. live region 없음(결과는 포커스
   시 읽힘 — 문서 기록).
4. **CSS**(`static/css/staff/pages/events.css`, WED): `.events-bulkbar`·`.events-select-all`·`.events-bulk-result`·
   `.events-inline-error`를 drafts.css `.queue-bulkbar`(`:254-268`)·`.queue-select-all`·`.queue-bulk-result`·`.queue-inline-error`
   (`:135-143`)와 같은 값으로 복제(S6 페이지별 분리), `.events-bulkbar .staff-cta:disabled { opacity: 0.6; cursor: default; }`
   (drafts.css `:86`에만 있어 이벤트 페이지엔 미적용 — 보강), `.events-tail-cell { flex-wrap: wrap; }` + `.events-inline-error {
   flex: 1 0 100%; }`, `.events-table` `min-width: 72.75rem`. 약 30줄 [계산], `--c-*`만, transition·animation 없음.
5. **문서**: `docs/BE/staff-event-bulk-unpublish.md` 신설(가드레일: 목표 상태·멱등·상한·항목별 원자성·선택 범위·감사 규칙),
   `docs/event-operations-criteria.md:50-52` 만료 처리 문장에 콘솔 일괄 비공개 1줄, `docs/operations-runbook.md` 스태프 콘솔
   절에 절차 1줄, 백로그 H2 행에 분할·24 완료 표기, pr-log(머지 시).

## 배제 (범위 밖 — 25·26으로)
- 정렬·기간·카테고리 필터(25), 인라인 단건 토글·검증·재게시(26), 일괄 재게시(검증 실패 처리가 얽힘 — 요구 없음), 페이지·필터
  간 선택 유지, 단축키, 표 하단 카운트 갱신, 삭제 일괄 처리.

## 수용 기준
- AC1 게시 이벤트 N건 POST → 전부 succeeded, 각각 draft, `EVENT_UNPUBLISH` 로그 N건(actor·target_event), 200.
- AC2 이미 비공개 이벤트 포함 → 그 항목은 succeeded이되 변경·로그 없음(멱등). 같은 요청 재전송 → 결과 동일, 로그 추가 없음.
- AC3 없는 id → failed "Not found.", 나머지는 정상 처리(항목별 격리). 한 항목의 로그 저장 실패 → 그 항목만 롤백(draft 아님·로그
  없음), 나머지 succeeded.
- AC4 구조 오류(빈 목록·목록 아님·정수 아님·bool·21건 이상 [계산 상한+1]) → 400, 변경 없음. 익명·일반 사용자 → 403.
- AC5 목록: 게시 행에만 체크박스(비공개 행은 빈 `<td>`), bulkbar는 서버 `hidden` 렌더(마커 `id="event-bulk-toolbar"`)·게시 행이
  있는 페이지에만 마크업 존재(`{% if event_rows %}` 안), `<col>` 8개 [계산], 표 `data-selected-publish-status`, 실패 사유 호스트
  셀, 빈 페이지 문단 `#event-bulk-empty` hidden 렌더.
- AC6 회귀·check 통과, 마이그레이션 없음(`makemigrations --check` 변경 없음). 드래프트 일괄 테스트(검증 함수 위임 후) 불변 통과.
- SEC-AC1 catch-all은 `logger.exception` + event_id, 분류 예외 뒤. SEC-AC2 응답에 예외 문자열 없음. SEC-AC3 확인 모달에 되돌리기
  문장 렌더.
- AC7 브라우저(High, 1440px): (1) 경고 필터 `?warning=ended_still_published`에서 2건 선택 → 카운터 "2건 선택" → 확인 모달(포커스
  "아니오"·Tab 순환·Escape 취소) → "예" → POST 1건 [계산] → 두 행 제거·결과 문단 포커스·"이 페이지 새로고침" 링크 → 링크로 재로드
  → 다음 항목이 밀려 올라와 보임(다페이지 순차, PSO ★6) (2) 전체 탭·경고 없음에서 1건 → 행 유지·배지 "비공개"·경고 배지 소거·
  체크박스 제거 (3) 전체 탭 + 경고 필터에서 1건 → 행 제거(OR 조건 나머지 절반) (4) 실패 경로(삭제된 id) → 행 사유·"N/M건" 문구
  (5) 403 강제(세션 만료) → 오류 문단 포커스·버튼 복구·모달 재통과로 재전송 성공 (6) 키보드 전용(체크박스 Space → Tab → 같은 행
  "수정" 링크 → … → 버튼 Enter → 모달) (7) 페이지의 게시 행 전부 처리 → 표 hidden·빈 문단 포커스 (8) 페이지·필터 전환 후
  선택 0·버튼 disabled (9) 콘솔 오류 없음. 임시 데이터·캡처 삭제.

## Activated Roles / Not Activated (확정 — 6역할 사전 검토 완료 2026-09-09)
- Activated: PSO(★0 분할·★1~★5), DAR(엔드포인트 위치·검증 공용화·서비스 재사용), Backend TDD Coach, SRR(대량 상태 변경 엔드포인트
  — 상한·권한·CSRF·멱등), WED·BIR(bulkbar·비동기 부분 실패 UI, depth **High**: 비동기 상태·크로스 페이지 패턴), BIE·FIE, QVL.
- Not Activated: DOR(마이그레이션·설정·프로세스 변경 없음), AI Automation Architect.

## Domain Boundary and Dependency Direction
- events 소유: `unpublish_event`(무변경). staff 소유: 엔드포인트·검증·감사·표시. 방향 staff → events. 드래프트 일괄 뷰와
  구조를 공유하되 자원이 다르므로 상수·검증 함수 공용화는 DAR 판단(`staff/views/_helpers.py` 후보).

## Test List (TDD 코치 확정) [문서 코치 산출]
- 엔드포인트(`tests/staff/test_staff_event_bulk_unpublish.py` 신규, `test_staff_bulk_approve.py` 스타일, `bulk_unpublish_url()`):
  B1 `test_익명_사용자는_이벤트_일괄_비공개_설정을_할_수_없다`(403; Red NoReverseMatch) / B2 `test_일반_사용자는_이벤트_일괄_비공개_
  설정을_할_수_없다`(403 — 스켈레톤 뒤 이미-Green: 뮤테이션 `AllowAny`로 Red 확인) / B3 `test_요청_구조가_잘못되면_이벤트_일괄_
  비공개_설정을_거부한다`(parametrize ids 빈_목록/리스트가_아닌_본문/정수가_아닌_원소/불리언_원소 → 400·로그 0) / B3-cap
  `test_event_ids_개수가_상한을_초과하면_일괄_비공개_설정_요청을_거부하고_아무것도_변경하지_않는다`(게시 21건 [계산] → 400·전부
  published·로그 0) / B4 `test_게시_중인_이벤트_여러_건을_일괄_비공개로_설정하면_모두_draft가_되고_건별로_감사_로그가_남는다`
  (2건·actor·target_event·ip·UA) / B5 `test_이미_비공개인_이벤트가_섞여도_해당_건은_변경과_로그_없이_성공으로_보고된다` / B6
  `test_같은_이벤트_ID_목록으로_두_번_요청해도_두_번째_요청은_상태와_로그를_추가로_바꾸지_않는다`(계약; B5 분기로 조기 Green 가능
  → 뮤테이션: 멱등 분기 제거 → 로그 2건 Red) / B7 `test_존재하지_않는_이벤트_id는_전체_요청을_실패시키지_않고_건별_실패로_보고된다`
  ("Not found." + 나머지 성공·로그 1) / B8 `test_한_항목의_감사_로그_기록이_예기치_못한_오류로_실패해도_나머지_항목_처리는_계속된다`
  (3건 중 가운데 IntegrityError → 그 건 published 유지·로그 2건, 선례 `test_staff_bulk_approve.py:294`) / B10 `test_일괄_비공개_
  설정은_대상_행을_잠그고_읽는다`(`CaptureQueriesContext`에 `FOR UPDATE`, 선례 `test_staff_event_publish_delete_views.py:108-119`).
  B9(상수 리터럴 핀)는 기각 — B3-cap이 행동으로 증명.
- 드래프트 회귀: `_validate_bulk_ids` 위임 후 `tests/staff/test_staff_bulk_approve.py`·`test_staff_bulk_reject.py` 불변 통과.
- 목록(`tests/staff/test_staff_events_views.py`): L1 `test_게시_행에만_일괄_선택_체크박스가_있고_비공개_행에는_없다`(행 슬라이스 =
  `events-id-cell">{id}</td>` 인덱스에서 `rfind("<tr")`~`find("</tr>")`, 앵커 `data-event-select` 양성+음성; `<col` 8개 [계산]
  단언 포함) / L3 `test_게시_행이_있으면_일괄_선택_바와_실패_사유_표시_영역이_있다`(`id="event-bulk-toolbar"`·`data-selected-
  publish-status`·`data-bulk-fail-reason-host`·`id="event-bulk-empty"`) / L2 `test_게시_행이_없는_페이지에는_일괄_선택_바가_없다`
  (`?publish_status=draft`, L3와 짝 — L3 Green 뒤에만 의미). 뮤테이션: 체크박스 조건 제거 → L1 음성 Red.

## 구현 순서 (슬라이스별 커밋, pytest 실행·판정은 오케스트레이터 단독)
운영 방식은 트랙 21~23과 같다(테스트 먼저 → Red 기록 → 최소 구현 → Green → 조기 Green 뮤테이션 → 커밋).
1. 엔드포인트(B1~B10): B1 스켈레톤(URL·뷰·`IsAdminUser`) → B2 뮤테이션 → `_validate_bulk_ids` 일반화(드래프트 위임, 회귀) →
   B3·B3-cap → B4 → B5·B6 → B7 → B8 → B10 → 커밋 `feat(staff): 이벤트 일괄 비공개 설정 엔드포인트`
2. 목록 템플릿·CSS·JS(L1~L3 + 브라우저 High) → 커밋 `feat(staff): 이벤트 목록 일괄 선택과 비공개 설정`
3. 문서 → 커밋 `docs: 이벤트 일괄 비공개 가드레일과 H2 분할 기록`

## 검증 명령과 기대 증거
- `uv run pytest -q tests/staff/test_staff_event_bulk_unpublish.py tests/staff/test_staff_events_views.py`, 전체 회귀(기준선
  main 재측정값), `manage.py check`, `makemigrations --check`(변경 없음). 브라우저 AC7.
- **Red 기록 [실측 2026-09-09, 두 파일]**: 15 failed / 11 passed (3.36초). 사유: NoReverseMatch `event-bulk-unpublish` 12건
  (B1·B2·B3×4·B4·B5·B6·B7·B8·B10), ImportError `MAX_BULK_EVENT_IDS` 1건(B3-cap), 마크업 부재 2건(L1 `data-event-select`,
  L3 `id="event-bulk-toolbar"`). L2는 사전 Green(이미-Green 핀 — L3 Green 뒤 뮤테이션으로 의미 확인 예정).
- **슬라이스 1 Green [실측 2026-09-09]**: `test_staff_event_bulk_unpublish.py` + 드래프트 일괄 승인·반려 회귀 = 35 passed(4.21초).
  BIE `manage.py check` 이상 없음·`makemigrations --check` 변경 없음 [문서 BIE, 오케스트레이터 재실행은 회귀 단계에서].
  구현 위치 [실측 grep]: `_helpers.py:40` `_validate_bulk_ids`, `drafts.py:269` 위임, `events.py:551` 상수·`:554` 뷰·`:588`
  `_unpublish_one`(`:598` `select_for_update().get`, `:608` `DoesNotExist`, `:614` `logger.exception`), `urls.py:59-61`.
  **뮤테이션 5건 전부 Red → 원복 `cmp` 일치 [실측]**: M1 `permission_classes = []` → B1·B2 2 failed / M2 멱등 분기 `if True:` →
  B5·B6 2 failed(로그 추가) / M3 `select_for_update()` 제거 → B10 1 failed / M4 `get_object_or_404` 사용 → B7 1 failed
  ("Unexpected error." ≠ "Not found." — DAR 결함 위험 핀 확인) / M5 항목별 `atomic` 제거 → B8 1 failed.
  커밋: `3bbcb46 refactor(staff): 일괄 id 구조 검사를 _validate_bulk_ids로 공용화한다`, `f86c1a7 feat(staff): 이벤트 일괄 비공개
  설정 엔드포인트`(구현 순서의 단일 커밋을 리팩터/기능 2개로 분리 — 커밋 단위 규약).
- **슬라이스 2 Green [실측 2026-09-09]**: `test_staff_events_views.py` 14 passed(3.20초). 중간 발견 2건을 같은 슬라이스에서 수정:
  (a) L1 정규식 `<col`이 `<colgroup>`까지 세어 9 ≠ 8 — 원래 템플릿도 `<col` 7 + `<colgroup` 1 = 8이라 Red 때 우연히 통과한
  테스트 결함 → `r"<col[\s>]"` [코드 `tests/staff/test_staff_events_views.py:182`]. (b) FIE가 L2를 맞추려 템플릿에
  `selected_publish_status != "draft"` 조건을 걸었으나 필터 없이 비공개 행만 있는 페이지를 못 거름(AC5 "게시 행이 있는 페이지에만"
  과 불일치) → 뷰 컨텍스트 `has_published_rows`(현재 페이지 `event_rows` 기준 `any`, `staff/views/events.py:144`·`:169`) +
  템플릿 `{% if has_published_rows %}` 2곳(`list.html:34`·`:106`) + L2b `test_필터_없이도_게시_행이_없는_페이지에는_일괄_선택_바가_
  없다`(`:213`). 승인 범위 2의 "`{% if event_rows %}` 안" 문구는 이 뷰 불리언으로 대체(정정). **뮤테이션 2건 Red → 원복 `cmp`
  일치 [실측]**: MT1 체크박스 조건 `{% if 1 %}` → L1 1 failed / MT2 `has_published_rows = bool(event_rows)` → L2·L2b 2 failed.
  커밋 `00b319d feat(staff): 이벤트 목록 일괄 선택과 비공개 설정`. 브라우저 AC7·WED/BIR 사후·QVL은 아래에 이어서 기록.

## Frontend Review Evidence [문서 WED·BIR 사전 산출 2026-09-09]
- 검토 깊이: **High**(WED·BIR 동의) — 비동기 부분 실패 UI·OR 이중 조건 분기·행 제거/갱신·빈 페이지 전환·`draft_bulk.js` 구조 축소.
- WED 사전 사양: 승인 범위 2·4에 통합. 수용 기준 9항 [문서]: (1) `<col>` 8개·선두 2rem·min-width 72.75rem (2) 게시 행만 체크박스,
  비공개 행 `<td>` 존재 (3) bulkbar 서버 hidden·JS 노출 (4) 버튼 `.staff-cta` 무색 (5) 전체 탭 성공 = modifier 교체 + 경고 배지
  제거 + 체크박스 셀 비움, 게시 탭/경고 필터 = `<tr>` 제거 (6) 하단 카운트 미갱신 (7) 빈 페이지 = 표 hidden + `#event-bulk-empty`
  (8) 실패 사유 문단이 `events-tail-cell` 자식, flex-wrap 새 줄 (9) `.staff-cta:disabled` 규칙 추가.
- BIR 사전 기준 [문서]: (1) 선택은 DOM 재질의로 페이지 전환 시 자동 초기화, 카운터 0·버튼 disabled (2) 요청 중 `setLoading` 중복
  방지 (3) ★5 세 경로(게시 탭 / 전체+경고 / 전체·경고 없음) 각각 증거 (4) 결과·오류 문단 `tabindex="-1"` + `focus()` (5) 재시도 =
  확인 모달 재통과 (6) Tab 순서 체크박스 → 같은 행 "수정" 링크 (7) `draft_bulk.js` 제외 지점 준수 (8) live region 없음 → 결과는
  포커스 시 읽힘(문서 기록).
- 계획된 브라우저 증거: AC7 (1)~(9).
- **브라우저 증거 [실측 2026-09-09, Chrome DevTools MCP, 1440×900, 임시 계정 id 89·임시 이벤트 554~564 `[T24 임시]` 접두, 목데이터
  무변경(실 게시 171건 유지)]**:
  (1) 게시 탭+경고 필터 `?publish_status=published&warning=ended_still_published` — bulkbar 노출·버튼 disabled·`<col>` 8개·
  `min-width` 1164px(=72.75rem)·가로 스크롤 없음(scrollWidth = clientWidth 1192px). 554·555 클릭 → "2건 선택"·전체 선택
  indeterminate → 버튼 → 모달 문구 SRR 문장 포함·포커스 "아니오" → Tab "예" → Tab "아니오"(순환) → Escape → 오버레이 hidden·포커스
  버튼 복귀·선택 유지·POST 0건 → 버튼 → Tab → Enter → POST 1건 200 → 두 행 제거(15→13)·"2건 모두 비공개 완료. 이 페이지 새로고침"
  링크(href = 현재 URL)·결과 문단 포커스·카운터 0·버튼 disabled·하단 "1–15 / 153" 미갱신(수용). DB: 554·555 draft, EVENT_UNPUBLISH
  2건(ip 127.0.0.1). 링크 클릭 재로드 → 행 559·558·557·210·…·182·181(뒤 항목 2건이 밀려 올라옴)·"1–15 / 151"·선택 0.
  (2) 전체 탭·경고 없음 `?q=T24-B` — 556 → 행 유지·배지 `--draft` "비공개"·체크박스 셀 비움·체크박스 0·전체 선택 disabled·결과
  "1건 모두 비공개 완료."(링크 없음)·포커스 결과.
  (3) 전체 탭+경고 필터 `?warning=ended_still_published` — 557 → 행 제거(15→14)·링크 있음·포커스 결과.
  (4) 실패 경로 `?q=T24-D` — 전체 선택 2건 → 558을 shell로 삭제 → 확인 → 558 행 유지·`data-bulk-fail-reason` "Not found." 표시(꼬리 셀
  둘째 줄 224px/240px, 체크 유지·"게시" 유지) / 559 배지 "비공개"·경고 배지 1→0·체크박스 제거 → 결과 "1/2건 비공개 완료. 처리되지
  않은 항목은 행에서 사유를 확인하세요."(링크 없음)·카운터 "1건 선택"·버튼 활성(재시도 가능).
  (5) 403 `?q=T24-E` — 계정 `is_staff=False` 뒤 확인 → POST 403 → `#event-bulk-error` CSRF_OR_SESSION_MSG·포커스 오류 문단·버튼
  복구(disabled false)·체크 유지 → `is_staff=True` 복구 → 버튼 → 모달 재통과 → POST 200 → 오류 hidden·"1건 모두 비공개 완료."·
  배지 "비공개". 네트워크: 403 → 200 순 2건.
  (6) 키보드 전용 `?publish_status=published&q=T24-G` — 전체 선택에서 Tab → 행 체크박스(비활성 버튼·tabindex -1 문단 건너뜀) →
  Space → "1건 선택"·버튼 활성 → Tab → 같은 행 "수정" 링크 → Shift+Tab ×2 → 버튼 → Enter → 모달 포커스 "아니오" → Tab → Enter
  → 행 제거.
  (7) 빈 페이지 — (6)의 단일 행 제거와 `?publish_status=published&q=T24-F` 전체 선택 3건 확인 모두 → 행 0·`.events-table-wrap`
  hidden·`#event-bulk-empty` 노출·포커스·결과 "3건 모두 비공개 완료. 이 페이지 새로고침".
  (8) F 페이지 전체 선택 3건 → `?q=T24-F`로 전환 → 체크 0·"0건 선택"·버튼 disabled·전체 선택 해제.
  (9) 콘솔 error/warn/issue 0건(보존 메시지 포함). DB 최종: 임시 10건 전부 draft(558 삭제), 감사 로그 10건(actor 89), 실 게시 171건.
  **결함 2건 → 같은 트랙 수정(FIE, events.css)**: (a) 결과 문단의 "이 페이지 새로고침" 링크 `text-decoration: none`·색 동일 → 링크
  구분 불가 → `.events-bulk-result a` 밑줄. (b) `.events-bulkbar` `height: 2.25rem` 고정 → 403 오류 문단(전체 폭)이 바 밖으로
  넘쳐 표 헤더에 가려짐(바 36px vs scrollHeight 78px [실측]) → `min-height` + 오류 문단 하단 여백. drafts.css `.queue-bulkbar`도
  `height` 고정이지만 오류 문단이 전체 폭이 아니라 같은 증상이 나타나지 않아 무변경(보고만).
  **수정 재검증 [실측 2026-09-09, `ignoreCache` 재로드]**: (b) csrftoken 쿠키 제거 뒤 확인 → 403 → 바 높이 86px(scrollHeight 84px)·
  오류 문단 bottom 179px < 바 bottom 186px < 표 top 208px(가려짐 없음)·한 줄 상태 바 36px 유지. (a) 링크 computed
  `text-decoration-line: underline`·offset 2px. 커밋 `143ffae fix(staff): 일괄 바 오류 문단 넘침과 결과 링크 구분을 보강한다`.
- **회귀 [실측 2026-09-09, 143ffae]**: `uv run pytest -q` 2505 passed / 95.88초(기준선 2488 + 신규 17 = 2505 [계산]) ·
  `manage.py check` 이상 없음 · `makemigrations --check` 변경 없음.
- **WED 사후 판정 [문서 2026-09-09]: 승인(조건 없음)** — 사전 기준 9항 전부 충족(인용 `events.css:110`·`:276`·`:297-300`·`:317-320`,
  `list.html:34`·`:41`·`:106`, `event_bulk.js`에 `.events-table-foot-range` 참조 0건 — 오케스트레이터 sed/grep 재확인 [실측]).
  편차 (i) `has_published_rows`는 AC5를 더 엄격히 만족하는 조건이라 수용, (ii) `min-height`·링크 밑줄(색 단독 구분 회피)·오류 문단
  하단 여백 수용. 추가 결함 없음.
- **BIR 사후 판정 [문서 2026-09-09]: 승인(Conforms)** — 사전 기준 8항 전부 충족(중복 클릭 방지 `api.js:314` `button.disabled`,
  모달 트랩·Escape `confirm-modal.js:100-123`, 포커스 종착 `event_bulk.js:189`·`:200`·`:253`, 제외 지점 미이식 — 오케스트레이터
  sed 재확인 [실측]). Blocking/High/Medium 없음. Low/정보 3건(전부 저장소 전역 관례, 트랙 국지 아님): `table` 참조 바인딩 시점 캡처
  (`event_bulk.js:214`, 선례 `draft_bulk.js:441`), 카운터·결과 문단 `aria-live` 없음(스태프 템플릿 전역 0건 [실측 grep]), 체크박스
  네이티브 크기. 제품 권고 2건 → 이연 절에 기록.
- **QVL [문서 2026-09-09]: 조건부 완료** — AC1~AC5·SEC-AC1~3·회귀 위험 (a)~(d) 코드·테스트 대조 충족(인용 `events.py:604`·`:608`,
  `__init__.py:29`, CI `ci.yml` Postgres — 오케스트레이터 sed/grep 재확인 [실측]). 조건 = 오케스트레이터의 신선한 재실행·재관찰:
  AC6 수치와 AC7은 이 세션에서 오케스트레이터가 직접 실행·관찰한 값(위 기록)이며, docs 커밋 2a79822는 코드 무변경(`git diff --stat
  143ffae HEAD` = docs 4파일만 [실측]), `check`·`makemigrations --check` 2a79822에서 재실행 이상 없음 [실측]. Postgres 의존(B10)은
  기존 선례와 같은 환경 의존(로컬 `.env`·CI 모두 Postgres). 커버리지 공백 1건(중복 id `[5, 5]`) → 같은 트랙에서 B11 추가(아래).
- **B11 [실측 2026-09-09]** `test_같은_이벤트_id가_중복된_목록은_두_번째_항목을_멱등_분기로_처리한다`(`tests/staff/test_staff_event_bulk_
  unpublish.py:180`): 파일 14 passed(2.76초, 이미-Green) → 뮤테이션 M6 멱등 분기 `if True:` → `assert 2 == 1`(로그 2건) Red → 원복
  `cmp` 일치. 커밋 `f49b34e test(staff): 중복 id 목록의 일괄 비공개 설정을 멱등 분기로 핀한다`. **최종 회귀 [실측 f49b34e]**
  `uv run pytest -q` 2506 passed / 69.79초(기준선 2488 + 18 [계산]). 임시 데이터 삭제 확인: 이벤트 10건·로그 11건·계정 행 2건 삭제,
  잔여 이벤트 171건·게시 171건(목데이터 무변경) [실측]. 캡처 파일 없음(스크린샷은 인라인만).

## 이연
- 트랙 25(인라인 단건 비공개/재게시/검증), 트랙 26(정렬·기간·카테고리 필터), 일괄 재게시, 선택 유지, 단축키, JS 선택 로직 공용
  모듈화(`draft_bulk.js`와 중복 — 두 번째 사용처가 생긴 시점에 추출 검토), succeeded의 "실제 전환/이미 그 상태" 구분(SRR Low),
  이벤트 목록 live region(BIR 정보), `events.py` 인터페이스별 분리(트리거 약 700줄 [문서 DAR]).
- BIR 사후 제품 권고 2건(결함 아님): 드래프트·이벤트 bulk 툴바를 함께 손대는 트랙(25·26)에서 카운터·결과 문단 `aria-live="polite"`
  도입 검토; 빈 페이지 전환 뒤 "0건 선택" disabled 컨트롤과 결과 문단이 같은 바에 남는 화면의 다듬기(WED 재량).

## 문서 대상·핸드오프 조건
- `docs/BE/staff-event-bulk-unpublish.md`, 운영 기준·런북 1줄씩, 백로그 H2 분할 표기, pr-log(머지 시).

---

