# 트랙 25: 이벤트 목록 인라인 단건 비공개·재게시·검증 — H2 분할 2/3 (2026-09-09) [v2 — PSO·DAR·SRR·TDD 코치·WED·BIR 검토 반영]

> **검토 반영 요약(v1 → v2)** [문서 각 역할 산출, 인용 file:line 오케스트레이터 rg/sed 재확인 2026-09-09]
> - PSO: 조건부 승인. ★1·★2·★3·★4·★6·★7·★9 승인, ★5는 BIR 브라우저 증거 조건부. **정정**: 수정 화면 검증 카드는 게시 상태 조건이
>   없어(`edit.html:102-121` [실측 sed] `{% if event.verified_at %}`만 분기) 비공개 이벤트도 검증 가능 → ★4는 인라인 목록과 수정
>   화면의 의도된 비대칭으로 문서에 명시. 이연 절에 "수정 화면 토글은 재시도-반전 결함을 그대로 가진다"를 명시. 운영 기준 문서에
>   재검증 절차 정의가 없음(`docs/event-operations-criteria.md` §3은 만료 처리·소스 변경 확인만) → 미해결 제품 결정으로 백로그에 기록.
>   AC7에 "비공개 행 검증 버튼 없음" 확인 추가. 백로그 상단 회귀 표 갱신은 PR #352(오픈)가 담당.
> - DAR: 조건부 승인. 엔드포인트는 (a) 목표 상태 APIView 2개(드래프트 단건 `draft-approve/reject/reopen` 관례, `staff/urls.py:38-52`
>   [실측]). PRG 뷰 JSON 분기·경로 3개 기각. 문구 표는 `(예외 클래스, 문구)` **순서 튜플 + isinstance 순회**(부모 폴백 보존),
>   위치는 `staff/views/events.py`(도메인 계층에 UI 문구 금지). **★9 정정**: 쿼리셋(`F`/`ExpressionWrapper`)은 인스턴스 술어와 코드
>   공유 불가 — 행마다 `.exists()` 재조회는 N+1(페이지 15건 [코드])이라 **금지**, `Event.needs_reverification(self, *, today)` 모델
>   메서드로 추출(events 소유, staff가 호출). **파일 크기**: `events.py` 625줄 [실측 wc] + 추가분 약 100~135줄 [계산] ≈ 725~760줄
>   [계산] > 분리 트리거 700줄 [문서 트랙 24] → 신규 APIView 2개는 **`staff/views/events_actions.py`** 신설(`__init__.py` 재노출
>   관례 `staff/views/__init__.py:37-52` [실측]). 문서는 같은 파일을 쓰되 파일명을 `docs/BE/staff-event-publish-actions.md`로
>   `git mv`하고 범위 문장 갱신(참조 `docs/backlog.md`·`docs/operations-runbook.md` [실측 rg]). 테스트 배치: `test_*_views.py`는
>   서비스·쿼리 계층 임포트 금지 가드(`tests/core/test_architecture_boundaries.py:710` [실측]) → 규칙 동등성은 `tests/events/`에.
> - SRR: 차단 없음. **Medium**: "검증 완료"는 되돌릴 수 없음(`verified_at`을 None으로 되돌리는 서비스 0건 [실측 rg]) → 검증 버튼만
>   확인 모달. SEC-AC3 `textContent`만(`static/js/staff/*.js` innerHTML 0건 [실측 rg]), SEC-AC4 검증 확인 여부를 문서에 기록.
>   문구 튜플 순서 보장 테스트 권고 → U8 parametrize가 담당.
> - TDD 코치: **정정** ① "기존 토글 테스트가 문구 회귀를 보증"은 거짓 — 6개 문구를 단언하는 테스트 0건 [실측 rg] → P1로 기존 테스트에
>   메시지 단언 추가. ② 토글 뷰 except 절은 7개(`events.py:441-453` [실측]), 도달 가능한 예외는 6종. ③ AC2 "이미 published" 멱등
>   누락 → U6 parametrize. Test List 확정(아래), 목록 테스트 ID는 R1~R3(L1~L3는 트랙 24가 사용 중).
> - WED: **정정** 경고 배지 최대는 5개가 아니라 4개 [계산 — `needs_reverification`은 `ended_still_published`·`missing_dates`와
>   상호 배타], 행당 동시 버튼은 최대 2개 [코드]. DOM 순서 배지 → 검증 → 비공개/다시 게시 → 수정 → 오류 문단(수정 화면 rail 순서와
>   동일), 열 폭 조정 불필요(`flex-wrap` 기존). `.events-row-btn`은 `.events-rail-btn--neutral/--accent` 값 복제(`#fff` 리터럴은
>   저장소 관례). 오류 문단은 `data-row-error`(호스트 `data-row-error-host`)로 개명해 일괄·단건 공유. **검증 성공 시 경고 필터가
>   `needs_reverification`이면 행 제거**(OR 규칙 통일 — v1 공백). 결과 문단은 행이 제거될 때만 "1건 비공개/게시/검증 완료." + 링크.
> - BIR: **High 3건** ① 행 오류 문단에 `tabindex="-1"` 없음(`list.html:93` [실측 sed]) → 추가 ② `rebind()` 재실행은 상시 버튼에 리스너
>   중복 → 체크박스 `change`는 표에 **이벤트 위임**, 노출 훅은 재계산 전용 `refreshToolbar()` ③ 게시 행 0건 페이지는 툴바 마커가
>   렌더되지 않아(`list.html:34` `has_published_rows`) 재게시로 생긴 체크박스를 담을 그릇이 없음 → **★10 트랙 24 (f) 정정**: 마커·빈
>   문단·결과 문단은 `event_rows`가 있으면 항상 `hidden` 렌더, JS가 체크박스 존재 시 노출(초기·재게시 후 모두). Medium ④ 검증
>   모달(SRR과 동일) ⑤ 버튼 교체 시 포커스 유실(`draft_bulk.js:372-379` 실증) → **버튼 3종을 항상 렌더하고 `hidden`만 토글**, 교체
>   뒤 새로 보이는 버튼에 명시적 `focus()`. **정정**: 트랙 24 BIR "스태프 템플릿 live region 0건"은 `templates/staff/`만 본 결과 —
>   `templates/core/drafts/list.html:135` `queue-inspector-live`가 있음 [실측 rg] → 이번 트랙에 live region 도입. 이식 선례는
>   `draft.js:178`이 아니라 `draft_bulk.js:495` `bindQueueRowJudgement`·`:331` `applySucceededDraft`·`:185` `announceOutcome`
>   [실측 rg]. AC7에 (10)~(15) 추가.

> 배경: 백로그 H2 분할(트랙 24 계획 ★0, PSO 판정) 두 번째 조각. 사용자 지시(2026-09-09) "다음 진행". 트랙 24(PR #350 머지,
> main 73a7539)로 일괄 비공개 설정은 끝났지만 **단건 재게시·검증은 여전히 목록 → 수정 → 버튼 3화면**이다(`templates/staff/events/
> edit.html:102-146` 검증·게시 상태 rail 카드 [실측 rg]). 재측정 [실측 2026-09-09 shell]: 이벤트 171건 전부 게시, 비공개 0건, 종료
> 게시 148건, "시작 임박, 미확인"(`_needs_reverification_qs`, `events/queries.py:100-121`) 6건, `verified_at` NULL 171건(검증
> 이력 0). 기존 단건 뷰는 전부 PRG(redirect + messages): 토글 `staff_event_toggle_publish`(`staff/views/events.py:411-461`,
> **읽은 상태를 반전**), 검증 `staff_event_verify`(`:463-490`), 삭제 `:492-`. 프론트 사전 검토(`.docs/FE/2026-09-06-staff-
> backoffice-frontend-review.md:85`)가 확정한 계약: "fetch는 redirect를 따라가 HTML을 받으므로 JSON 분기 또는 별도 JSON 엔드포인트
> 필요". `TakuAPI.post`는 `content-type`이 JSON일 때만 `data`를 채운다(`static/js/shared/api.js:48` `parseResponse`). 목록 행에는
> 검증 상태 표시가 없고, 품질 배지 `_event_quality_badges`(`events.py:64-79`)에 `needs_reverification` 라벨(`:60` "시작 임박,
> 미확인")이 없어 **그 필터로 좁혀도 행에 이유가 안 보인다** [코드]. 선례: 트랙 24 `StaffEventBulkUnpublishView`(`events.py:561-`)
> 목표 상태 설정·항목별 atomic·`event_bulk.js`(288줄 [실측 wc]) 결과 반영 OR 조건, 드래프트 단건 판정 `draft.js:178`
> `bindApproveButton`(askConfirm → setLoading → post → 상태 갱신 → `successEl.focus()`). 파일 크기 [실측 wc]: `staff/views/
> events.py` 625줄(DAR 분리 트리거 약 700줄 [문서 트랙 24]), `list.html` 117줄. 기준선 [실측 2026-09-09 main 73a7539]
> `uv run pytest -q` 2506 passed / 76.22초. 브랜치 `feat/event-inline-actions`(main 73a7539).

## 승인 범위 (★ = 사용자 미확인 가정 — 검토 역할 판정 병기)

1. **JSON 단건 엔드포인트 2개** — 신규 파일 **`staff/views/events_actions.py`**(DAR: 분리 트리거 초과 예상), `APIView` +
   `permission_classes = [IsAdminUser]`(선례 `StaffEventBulkUnpublishView` `events.py:561-` [실측]), `staff/views/__init__.py`
   재노출, `staff/urls.py` 라우트 2개. `_event_quality_badges`·`REPUBLISH_ERROR_MESSAGES`는 `.events`에서 임포트(방향
   events_actions → events 단방향).
   - ★1(PSO·DAR 승인) `POST /staff/events/<pk>/publish-status/`(`staff:event-publish-status`) 본문 `{"publish_status": "draft" |
     "published"}` — **목표 상태 설정**. `transaction.atomic()` + `Event.objects.select_for_update()` + `get_object_or_404`(단건 404
     정상, catch-all 없음). 이미 목표 상태면 변경·로그 없이 200 `changed: false`(양방향). `draft` → `unpublish_event` +
     `EVENT_UNPUBLISH` 로그, `published` → `republish_event` + `EVENT_REPUBLISH` 로그(같은 트랜잭션). 재게시 검증 예외(도달 가능
     6종, except 절 7개 `events.py:441-453` [실측 TDD 코치])는 `error_response(detail, 400)`(`core/errors.py`)로 기존 토글 뷰 문구
     그대로. 문구 표는 **`staff/views/events.py`**에 `REPUBLISH_ERROR_MESSAGES = ((MissingOfficialUrlError, "..."), ...,
     (PublishEventError, "..."))` 순서 튜플 + `isinstance` 순회(부모 폴백 보존, DAR) — PRG 토글 뷰의 except 사다리를 이 표로
     치환(문구 불변, **P1로 기존 토글 테스트에 메시지 단언을 추가해야 회귀 보증이 성립** — TDD 코치 정정). 본문 값 오류는
     `field_error_response("publish_status", ...)` 400. 응답 200 `{"id", "publish_status", "changed", "quality_badges": [라벨...]}`
     (`quality_badges`는 서버 계산 — DAR 승인, 드래프트 단건 뷰가 serializer 데이터를 돌려주는 선례와 동형).
   - ★2(승인) `POST /staff/events/<pk>/verified/`(`staff:event-verified`) 본문 없음 — `get_object_or_404` + `transaction.atomic()`
     안에서 `mark_event_verified` + `EVENT_VERIFY` 로그. 응답 200 `{"id", "verified_at"(ISO), "quality_badges"}`. 기존 PRG 뷰
     `staff_event_verify`·수정 화면 폼은 무변경. **★4 비대칭 명시**: 수정 화면 검증 카드는 비공개 이벤트에도 노출되지만 목록 인라인
     검증 버튼은 게시 행에만 둔다(의도된 축소 — 검증은 공개 정보의 재확인).
2. ★3(승인) **행 배지 보강** — `events/models.py`에 **`Event.needs_reverification(self, *, today)`** 순수 술어 메서드(★9 DAR
   정정: 규칙 = 시작일 7일 전 ≤ today ≤ 종료일, 두 날짜 모두 있음, `verified_at`이 없거나 그 날짜가 기준일보다 이전 —
   `_needs_reverification_qs` `events/queries.py:113-121` [코드]와 동일 의미, **행마다 쿼리 재실행 금지**). `_event_quality_badges`
   (`staff/views/events.py:64-79` [실측])가 이 메서드를 호출해 `QUALITY_WARNING_LABELS["needs_reverification"]`를
   `ended_still_published` 다음 위치에 추가(WED — 시간축 조건 인접, 두 라벨은 상호 배타). 쿼리셋과의 동등성은 `tests/events/`
   도메인 테스트(E1)로, 웹 계층은 HTTP로만 확인(B1).
3. **목록 행 인라인 액션**(`templates/staff/events/list.html` 꼬리 셀, WED 순서): 배지 → `data-row-action="verify"` 버튼 → 
   `"unpublish"` 또는 `"republish"` 버튼 → "수정" 링크 → 행 오류 문단. **버튼 3종을 모든 행에 항상 렌더하고 해당 없는 것은
   `hidden`**(BIR 포커스 규칙: 노드 교체 금지): 게시 행은 verify+unpublish 노출·republish hidden, 비공개 행은 republish 노출·
   verify·unpublish hidden. 검증 라벨은 `verified_at` 유무로 "검증 완료"/"다시 검증"(수정 화면 `edit.html:117-119` [실측] 문구와
   동일), 행에 `data-verified="1|0"`. 행 오류 문단은 `<p class="events-inline-error" data-row-error tabindex="-1" hidden>`(개명 +
   `tabindex` 추가, 호스트 `data-row-error-host`; `event_bulk.js:151` [실측] 셀렉터와 L1·L3 테스트 셀렉터 함께 수정). ★10 **툴바
   마커·`#event-bulk-empty`·결과 문단은 `{% if event_rows %}`면 항상 `hidden` 렌더**(트랙 24 (f) 정정 — 재게시로 게시 행이 생기는
   페이지를 지원), `has_published_rows` 컨텍스트와 그 분기 제거, L2·L2b는 "마커는 있되 `hidden`"으로 재작성(T1). live region
   `<p id="event-live" class="sr-only" aria-live="polite"></p>` 1개(BIR — 선례 `templates/core/drafts/list.html:135` [실측]).
4. **JS** 신규 `static/js/staff/event_row_actions.js`(이식 선례 `draft_bulk.js:495` `bindQueueRowJudgement`·`:331`
   `applySucceededDraft`·`:185` `announceOutcome` [실측]; `draft_bulk.js`·`draft.js` 무변경): 버튼 클릭 → ★5(PSO 조건부·SRR·BIR)
   **비공개·다시 게시는 확인 모달 없음**(수정 화면 토글 선례 `events.py:412-413` [실측], 반대 버튼 즉시 노출로 되돌리기), **검증
   완료·다시 검증은 확인 모달**(되돌릴 수 없음 — 문구 "이 이벤트의 공식 정보를 다시 확인했나요? 검증 완료로 기록되며 되돌릴 수
   없습니다.") → 요청 중 **같은 행의 체크박스·다른 버튼 disabled**(BIR 1) + `setLoading` → `TakuAPI.post` → 성공 반영(OR 규칙 통일):
   (a) 비공개: `data-selected-publish-status === "published"` 또는 `data-selected-warning` 비어 있지 않음 → 행 제거, 그 외 배지
   `--draft` "비공개"·경고 배지를 응답 `quality_badges`로 다시 그림·체크박스 제거·verify·unpublish hidden·republish 노출 후 `focus()`
   (b) 재게시: `data-selected-publish-status === "draft"` → 행 제거, 그 외 배지 `--published` "게시"·경고 배지 응답값·체크박스 셀에
   체크박스 생성(`label` sr-only + `input`, 서버 마크업과 동일)·republish hidden·unpublish·verify 노출(라벨은 `data-verified`)·
   unpublish에 `focus()` (c) 검증: `data-selected-warning === "needs_reverification"` → 행 제거(WED 통일), 그 외 라벨 "다시 검증"·
   `data-verified="1"`·경고 배지 응답값·포커스 유지. 행 제거 뒤 `#event-bulk-result`에 "1건 비공개 완료." / "1건 게시 완료." /
   "1건 검증 완료." + " 이 페이지 새로고침" 링크 → `focus()`; 행이 남으면 결과 문단 무갱신(WED). 남은 행 0이면 표 hidden +
   `#event-bulk-empty` 포커스(트랙 24와 동일). live region에는 성공·실패 결과 문구를 항상 기록(제목 + 결과). 실패: 400 `detail` → 행
   오류 문단 표시·`focus()`, 403 → `CSRF_OR_SESSION_MSG`(행 오류 문단), 404 → "이미 삭제된 이벤트입니다." 행 오류 문단에 표시 후
   행 제거·결과 문단 포커스, 그 외 `formatError`. 항상 `setLoading(false)`·행 잠금 해제를 DOM 변경보다 먼저. `textContent`만
   (SEC-AC3). ★7 정정: `event_bulk.js`는 (i) 개별 체크박스 `change`를 **`.events-table`에 이벤트 위임**(`bindIndividualCheckboxes`
   제거), (ii) `window.TakuEventBulk = { refreshToolbar }` 노출 — 체크박스 존재 시 툴바 `hidden` 해제 + `updateToolbarState()`,
   리스너 재부착 없음, 툴바 부재 시 no-op, (iii) `applyFailedEvent`·`applyBulkResult` 셀렉터 `[data-row-error]`, (iv) 일괄 결과
   문구를 live region에도 기록. 초기화도 `refreshToolbar` 경로를 재사용.
5. **CSS**(`static/css/staff/pages/events.css`, WED 사양): `.events-row-btn { min-height: 1.5rem; padding: 0 0.5rem;
   border-radius: 0.25rem; font-size: 0.71875rem; font-weight: 700; border: 1px solid var(--c-line); background: var(--c-panel);
   color: var(--c-text); }`(`.events-rail-btn--neutral` `:565-569` [실측] 값 복제), `.events-row-btn--accent`(`.events-rail-btn--
   accent` `:559-563` [실측] 값 복제, `#fff` 리터럴은 저장소 관례), `:disabled { opacity: 0.6; cursor: default; }`, `.is-loading
   { opacity: 0.75; }`, transition 없음. `.events-edit-link`의 `margin-left: auto`는 유지(버튼이 앞에 와도 "수정"은 오른쪽 끝).
   약 30줄 [계산].
6. **문서**: `git mv docs/BE/staff-event-bulk-unpublish.md docs/BE/staff-event-publish-actions.md`(★8 DAR 조건부) — 제목·범위
   문장을 "일괄·단건 목표 상태 설정과 검증" 공통 불변식으로 다시 쓰고 (j) 단건 목표 상태 엔드포인트 (k) 검증 엔드포인트·확인 모달·
   비대칭 (l) 행 액션 UI 규칙(버튼 상시 렌더·hidden, OR 규칙, 위임·`refreshToolbar`, live region) (m) 트랙 24 (f) 정정(마커 상시
   렌더) 절 추가, 테스트 대응표 갱신. 참조 갱신 `docs/backlog.md`·`docs/operations-runbook.md`. 백로그 H2 항목 트랙 25 완료 표기 +
   PSO 미해결 제품 결정(재검증 절차 정의 부재) 1줄, 운영 런북 절차 1줄. 이연 절에 수정 화면 토글의 재시도-반전 결함 잔존 명시.

## 배제 (범위 밖)
- 정렬·기간·카테고리 필터(트랙 26), 일괄 재게시·일괄 검증, 수정 화면 PRG 폼의 목표 상태화(**이연 — 같은 재시도-반전 결함이 수정
  화면에 그대로 남는다**, PSO 조건), 삭제 인라인화(2단계 확인 절차라 목록에 넣지 않음), 단축키, 검증 이력 표시(`verified_at` 시각을
  행에 노출하는 것은 열 추가라 배제 — 버튼 라벨 "다시 검증"으로만 드러냄), 재검증 운영 절차 정의(사용자 결정 — 백로그 기록).

## 수용 기준
- AC1 `publish-status` `draft`: 게시 → draft, `EVENT_UNPUBLISH` 로그 1건(actor·ip·UA), 200 `changed: true`, `quality_badges: []`.
  이미 draft → 200 `changed: false`, 로그 0건.
- AC2 `publish-status` `published`: draft → published, `EVENT_REPUBLISH` 로그 1건, `quality_badges`는 서버 계산값(종료 이벤트면
  "종료됐지만 게시 중" 포함). 재게시 검증 예외는 도달 가능한 5종 각각 → 400 `detail` = 토글 뷰 문구 리터럴, 상태·로그 무변경
  (**정정**: 6종 중 `DuplicateOfficialUrlError`는 `official_url` DB 유일 제약으로 재게시 경로에서 도달 불가 — Red 기록 참조).
  이미 published → `changed: false`, 로그 0건.
- AC3 `verified`: 재확인 대상 이벤트에 `verified_at` 설정 + `EVENT_VERIFY` 로그 1건, 응답 `verified_at` ISO, `quality_badges`에서
  "시작 임박, 미확인" 제거(`[]`). 없는 id 404.
- AC4 권한: 두 엔드포인트 모두 익명·일반 사용자 403, GET 405, 없는 id 404, 본문 값 오류 400 `publish_status` 필드 오류. PRG 토글
  뷰의 문구는 P1 단언으로 고정(상수 공유 뒤 드리프트 방지).
- AC5 목록: 게시 행은 `verify`·`unpublish` 버튼 노출·`republish` hidden, 비공개 행은 `republish` 노출·나머지 hidden, 검증 라벨은
  `verified_at` 유무로 "검증 완료"/"다시 검증", ★3 조건을 만족하는 게시 행에 "시작 임박, 미확인" 배지(같은 픽스처로 대시보드 카운트도
  1건 [계산]), 행 오류 문단 `data-row-error` + `tabindex="-1"`, 툴바 마커·빈 문단이 게시 행 없는 페이지에도 `hidden`으로 존재,
  live region 존재, `event_row_actions.js` 로드.
- AC6 회귀·check 통과, 마이그레이션 없음(모델 메서드만 추가), 기존 토글·검증·삭제 테스트(`tests/staff/test_staff_event_publish_
  delete_views.py` 303줄, `test_staff_event_verify_view.py` 67줄 [실측 wc]) P1·T1 외 불변 통과, `Event.needs_reverification`과
  `_needs_reverification_qs` 동등성 도메인 테스트(E1), 구현 후 `wc -l staff/views/events.py` 재실측 기록.
- SEC-AC1 응답에 예외 문자열·스택 없음(문구 표만). SEC-AC2 두 엔드포인트 `IsAdminUser`. SEC-AC3 JS는 `textContent`만. SEC-AC4 검증
  확인 모달 렌더(문구 포함).
- AC7 브라우저(High, 1440px): (1) 게시 탭 "비공개" → 행 제거·결과 문단 "1건 비공개 완료." + 새로고침 링크·포커스 (2) 전체 탭
  "비공개" → 배지 "비공개"·경고 배지 소거·체크박스 제거·republish 버튼 노출·포커스 그 버튼·결과 문단 무갱신, 이어서 "다시 게시" →
  배지 "게시"·경고 배지 복원·체크박스 생성·전체 선택이 그 행을 셈·unpublish 버튼 포커스 (3) 비공개 탭 "다시 게시" → 행 제거 (4)
  제목 없는 비공개 이벤트 "다시 게시" → 행 오류 문단에 토글 문구·`activeElement`가 그 문단·상태 유지 (5) 403 강제 → 오류·버튼 복구·
  재시도 성공 (6) "검증 완료" → 확인 모달(포커스 "아니오"·Escape 취소) → "예" → 라벨 "다시 검증"·"시작 임박, 미확인" 배지 소거·DB
  `verified_at`·로그 1건 (7) 키보드: 체크박스 → 검증 → 비공개 → "수정" 순 Tab, Enter/Space 동작 (8) 체크된 행 인라인 비공개 →
  카운터 감소 (9) 콘솔 오류 0건 (10) 게시 행 0건 페이지(비공개 탭 또는 검색)에서 "다시 게시" → 전체 탭이면 체크박스 생성과 툴바 노출
  (11) 서로 다른 두 행 연속 재게시 뒤 일괄 비공개 1회 클릭 → POST 정확히 1회 (12) (4)의 포커스를 `activeElement`로 확인 (13) 검증
  버튼 Enter 연타 → 모달이 가로막아 로그 1건 (14) 비공개 행에 검증 버튼 미노출 (15) 경고 필터 `needs_reverification`에서 검증 → 행
  제거. 임시 데이터·캡처 삭제.

## Activated Roles / Not Activated (확정 — 6역할 사전 검토 완료 2026-09-09)
- Activated: PSO, DAR, Backend TDD Coach, SRR, WED·BIR(depth High), BIE·FIE, QVL.
- Not Activated: DOR(마이그레이션·설정 변경 없음), AI Automation Architect.

## Domain Boundary and Dependency Direction
- events 소유: `unpublish_event`·`republish_event`·`mark_event_verified`(무변경), 신규 `Event.needs_reverification(self, *,
  today)`(불변식·규칙은 모델 소유 — DAR). staff 소유: 엔드포인트(`events_actions.py`)·감사·배지 라벨·오류 문구 표·표시. 방향
  staff → events, events_actions → events(같은 패키지, 단방향). 금지: events → staff, 행마다 쿼리셋 재실행.

## Coupling and Cohesion Review
- 재게시 오류 문구 표를 PRG 토글 뷰와 JSON 뷰가 단일 출처로 공유. 인라인 JS와 일괄 JS는 `refreshToolbar` 훅 하나 + 공유 셀렉터
  (`[data-row-error]`, `#event-bulk-result`, `#event-live`)로만 결합, 리스너 재부착 없음. 응답의 `quality_badges`로 프론트가 배지
  규칙을 복제하지 않는다.

## Pythonic Code Design
- 예외 → 문구 매핑은 `(클래스, 문구)` 순서 튜플을 `isinstance`로 순회(부모 `PublishEventError`가 마지막) — dict + `type(exc)`는
  미래의 하위 예외 폴백을 잃는다. `Event.needs_reverification`은 인자 `today`를 받는 순수 메서드(시간 의존 숨기지 않음).

## Test List (TDD 코치 확정 + DAR 배치 조정) [문서 코치 산출]
- `tests/staff/test_staff_event_inline_actions.py` 신규(`pytest.mark.web`, `publish_status_url()`·`verified_url()` 헬퍼): U1
  `test_익명_사용자는_이벤트_목표_게시_상태_설정을_할_수_없다`(Red NoReverseMatch) / U2 `test_일반_사용자는_이벤트_목표_게시_
  상태_설정을_할_수_없다`(이미-Green → 뮤테이션 `permission_classes = []`) / U3 `test_publish_status_경로에_GET으로_접근하면_
  허용되지_않는다`(이미-Green → 임시 `get` 추가 뮤테이션) / U9 `test_존재하지_않는_이벤트_id로_게시_상태_설정을_요청하면_404가_
  된다` / U4 `test_publish_status_값이_유효하지_않으면_이벤트_게시_상태_설정을_거부한다`(parametrize 키_없음/목록에_없는_값/
  문자열이_아닌_값 → 400·무변경) / U5 `test_게시된_이벤트를_publish_status_draft로_설정하면_비공개로_전환되고_감사_로그가_
  남는다` / U6 `test_이미_목표_게시_상태인_이벤트는_변경과_로그_없이_changed_false를_응답한다`(parametrize 이미_비공개/이미_게시;
  뮤테이션: 멱등 분기 제거 → 로그 1) / U7 `test_초안_이벤트를_publish_status_published로_설정하면_게시되고_서버가_계산한_품질_
  배지를_응답한다`(종료 이벤트 → `["종료됐지만 게시 중"]` 리터럴) / U8 `test_재게시_불변식을_위반한_초안_이벤트는_publish_status_
  published_설정이_거부되고_토글_뷰와_같은_문구를_응답한다`(parametrize 6종 — 공식_URL_없음/제목_없음/공식_URL_중복/기간_역전/
  카테고리_무효/지역_무효, 문구는 리터럴) / U10 `test_publish_status_설정은_대상_행을_잠그고_읽는다` / V1a `test_익명_사용자는_
  이벤트_검증_완료_처리를_할_수_없다` / V1b 일반 사용자(이미-Green) / V1c GET 405(이미-Green) / V3 `test_존재하지_않는_이벤트_id로_
  검증_완료를_요청하면_404가_된다` / V2 `test_스태프가_재확인_대상_이벤트를_검증_완료_처리하면_검증_시각이_기록되고_시작_임박_
  배지가_사라진다`(Given 재확인 대상 → `quality_badges == []`).
- `tests/staff/test_staff_events_views.py` 추가(HTTP만 — 서비스·쿼리 임포트 금지 가드): B1 `test_시작_임박_미확인_배지는_행_표시와_
  대시보드_카운트가_같은_이벤트에_대해_일치한다`(경계 픽스처 `start_date=today+7·end_date=today·verified_at=None` 양성 + 명백한
  음성 1건, 목록 행 배지 + `/staff/dashboard/` 컨텍스트 카운트 1) / R1 `test_게시_행에는_비공개와_검증_버튼이_노출되고_비공개_행에는_
  다시_게시_버튼만_노출된다`(hidden 속성 기준) / R2 `test_검증_이력이_없는_게시_행은_검증_완료_라벨이고_이미_검증된_게시_행은_다시_
  검증_라벨이다`(parametrize) / R3 `test_이벤트_목록에_행_인라인_액션_스크립트와_live_region이_로드된다` / T1 L2·L2b 재작성: 게시
  행 없는 페이지에도 `id="event-bulk-toolbar"`·`id="event-bulk-empty"`가 `hidden`으로 존재(★10), L1·L3 셀렉터 `data-row-error`.
- `tests/events/test_event_quality_warnings.py` 추가: E1 `test_needs_reverification_메서드는_재확인_대상_쿼리셋과_같은_판정을_
  한다`(경계 4종 [코드 기존 테스트 `:431-520`]과 동일 픽스처로 메서드 결과 == 쿼리셋 포함 여부).
- P1 기존 `tests/staff/test_staff_event_publish_delete_views.py:95` 테스트에 `messages` 문구 단언 추가("제목이 없어 다시 게시할 수
  없습니다.").
- 이미-Green 핀은 뮤테이션으로 증거화(트랙 24 방식).

## 구현 순서 (슬라이스별 커밋, pytest 실행·판정은 오케스트레이터 단독)
1. 도메인: `Event.needs_reverification` + E1(Red → Green) → 배지 B1 → 커밋 `feat(events): 재확인 대상 판정 메서드와 목록 배지`
2. 엔드포인트: U1 스켈레톤 → U2·U3 뮤테이션 → U9 → U4 → U5 → U6 → U7 → U8 → U10 → V1a~V3 → V2 + 문구 표 치환 + P1 → 커밋
   `feat(staff): 이벤트 단건 목표 게시 상태·검증 JSON 엔드포인트`
3. 목록 템플릿·CSS·JS(T1·R1~R3 + `event_bulk.js` 위임·`refreshToolbar`·live region + 브라우저 High) → 커밋 `feat(staff): 이벤트
   목록 인라인 비공개·재게시·검증`
4. 문서(rename + (j)~(m) + 백로그 + 런북) → 커밋 `docs: 이벤트 게시 액션 가드레일 통합과 H2 트랙 25 기록`

## 검증 명령과 기대 증거
- `uv run pytest -q tests/staff/test_staff_event_inline_actions.py tests/staff/test_staff_events_views.py tests/staff/
  test_staff_event_publish_delete_views.py tests/staff/test_staff_event_verify_view.py tests/events/test_event_quality_warnings.py`,
  전체 회귀(기준선 2506 [실측]), `check`, `makemigrations --check`(변경 없음), `wc -l staff/views/events.py staff/views/
  events_actions.py`. 브라우저 AC7 (1)~(15).
- **Red 기록 [실측 2026-09-09, 4파일]**: 38 failed / 76 passed (4.84초). 사유: NoReverseMatch `event-publish-status` 17건·
  `event-verified` 5건, `AttributeError: 'Event' object has no attribute 'needs_reverification'` 7건(E1 parametrize), 마크업 단언
  실패(R1·R2·R3·B1·L2·L2b·L3 — 버튼 태그 None, `data-row-error-host`·`event_row_actions.js`·`시작 임박, 미확인` 부재). **발견**:
  U8의 `공식_URL_중복` 케이스는 Given 자체가 `events_event_official_url_key` 유일 제약 IntegrityError로 만들어지지 않는다 —
  `official_url`이 DB 유일이라 재게시 경로에서 `DuplicateOfficialUrlError`는 도달 불가(토글 뷰의 같은 except 분기도 죽은 방어) →
  U8은 5종 parametrize로 조정하고 문구 표에는 그 항목을 유지(문서에 도달 불가 기록). P1 추가 단언은 Green(문구 그대로).
- **슬라이스 1·2 Green [실측 2026-09-09]**: 인라인 액션·품질 경고·토글/검증/삭제·일괄 테스트 5파일 112 passed(4.92초). 구현 위치
  [실측 grep]: `events/models.py:38` `needs_reverification`(`timezone.localtime(verified_at).date()` 기준 — 쿼리셋 `__date`와 같은
  현재 타임존), `staff/views/events.py:75` 배지 추가·`:408` `REPUBLISH_ERROR_MESSAGES`·`:419` `_republish_error_message`·`:459`
  토글 뷰 except 치환, `staff/views/events_actions.py:30` `StaffEventPublishStatusView`·`:81` `StaffEventVerifiedView`, `staff/
  urls.py:64-72`. 파일 크기 [실측 wc]: `events.py` 633줄(트리거 700줄 미만), `events_actions.py` 109줄. `check` 이상 없음·
  `makemigrations --check` 변경 없음 [실측]. **뮤테이션 5건 전부 Red → 원복 `cmp` 일치 [실측]**: M1 `permission_classes = []`(2곳)
  → U1·U2·V1a·V1b 4 failed / M2 `get` 추가(2곳) → U3·V1c 2 failed / M3 `changed = True` → U6 2 failed / M4 `select_for_update`
  제거 → U10 1 failed / M5 문구 표 "제목이 없어…" 변경 → P1 1 failed + U8[제목_없음] 1 failed(4 passed). 커밋 `ddfaa6b feat(staff):
  이벤트 단건 목표 게시 상태·검증 JSON 엔드포인트와 재확인 배지`(구현 순서 1·2를 한 커밋으로 — `events.py` 헝크가 두 슬라이스에
  걸쳐 있어 분리 불가, 정정 기록).

## Frontend Review Evidence [문서 WED·BIR 사전 산출 2026-09-09]
- 검토 깊이: **High**(양측 동의) — 비동기 상태·OR 분기·포커스 종착·두 스크립트 결합.
- WED 사전 수용 기준 10항 [문서]: (1) 게시 행 DOM 순서 배지 → 검증 → 비공개 → 수정 (2) 비공개 행은 다시 게시 → 수정, 검증 버튼
  hidden (3) `.events-row-btn`/`--accent`가 rail 버튼 값과 동일 (4) `:disabled` 0.6·`.is-loading` 0.75·transition 없음 (5) 검증
  라벨이 `edit.html`과 동일 문자열 (6) 오류 문단 `data-row-error`를 일괄·단건이 공유 (7) 세 액션 동일 OR 규칙(검증은
  `needs_reverification` 필터에서 행 제거) (8) 재게시로 생긴 체크박스가 카운터·전체 선택에 반영 (9) 결과 문단은 행 제거 시에만
  액션별 동사 (10) 배지 4개 + 버튼 2개 + 수정 링크가 15rem 셀에서 2줄 이내·헤더 미가림.
- BIR 사전 기준 10항 [문서]: (1) 요청 중 같은 행 체크박스·버튼 잠금 (2) 노드 교체 금지·hidden 토글·새로 보이는 버튼 명시 focus
  (3) 위임 + `refreshToolbar()`(인자·반환 없음, 툴바 부재 no-op) (4) 체크박스 제거 직후 재계산 (5) 검증만 확인 모달 (6) 오류 문단
  `tabindex="-1"`, 403/404/400 회복 경로 (7) DOM 순서 = Tab 순서 (8) live region 도입 (9) 속성 변경만이라 pageshow 복구 무영향
  (10) AC7 (10)~(13) 시나리오.
- **슬라이스 3 Green [실측 2026-09-09]**: 마크업 테스트 19 passed(3.26초, `_button_tag`를 닫는 태그까지 캡처하도록 고친 뒤 — FIE가
  R2를 맞추려 넣었던 `title` 속성 중복은 되돌림, 정정 기록). 트랙 6파일 131 passed(5.71초). 커밋 `4e14622 feat(staff): 이벤트 목록
  인라인 비공개·재게시·검증`(**정정**: `git mv`로 스테이지된 문서 rename(내용 변경 0줄)이 이 커밋에 함께 들어감 — 문서 내용은 별도
  docs 커밋).
- **브라우저 증거 [실측 2026-09-09, Chrome DevTools MCP 1440×900, 임시 계정 id 90·임시 이벤트 565~572 `[T25 임시]`, 목데이터 무변경
  (실 게시 171건 유지)]**: 초기 상태 — 게시 행에 검증·비공개 노출·재게시 hidden, F1에 "시작 임박, 미확인" 배지(★3), 오류 문단
  `tabindex="-1"`, live region `aria-live="polite"`, 버튼 높이 24px·글자 11.5px, 배지 있는 행 47px(2줄)·없는 행 34px, 가로 스크롤
  없음(scrollWidth = clientWidth 1192px). (1) 게시 탭 "비공개"(565) → 행 제거·"1건 비공개 완료. 이 페이지 새로고침"·결과 문단
  포커스·live "T25-A1 비공개 완료"·POST 1건 200. (2) 전체 탭 "비공개"(566) → 배지 "비공개"·경고 배지 0·체크박스 제거·republish
  노출·포커스 republish·결과 문단 무갱신 → "다시 게시" → 배지 "게시"·체크박스 생성(label "… 선택")·전체 선택이 1건으로 셈·unpublish
  포커스·오류 hidden. (3) 비공개 탭 "다시 게시"(567) → 행 제거·결과 문단. (4)·(12) 제목 없는 568 "다시 게시" → 400 "제목이 없어
  다시 게시할 수 없습니다." 행 오류 문단 표시·`activeElement` = 그 문단·상태 유지·버튼 복구. (5) csrftoken 삭제 → 403 → CSRF 문구·
  포커스·버튼·체크박스 복구 → 쿠키 재발급 뒤 재시도 성공. (6)·(13) 570 검증 버튼에 Enter ×2 → 모달 열림 → 기본 "아니오"가 눌려
  취소·변경 0·포커스 복귀 → Enter → Tab → Enter → 라벨 "다시 검증"·`data-verified=1`·배지 소거·포커스 유지·DB `verified_at`·
  `EVENT_VERIFY` 로그 1건. (15) `?warning=needs_reverification`에서 572 검증 → 행 제거·결과 문단 포커스·실 행 6건 무변경. (7) Tab
  순서 체크박스 → 검증 → 비공개 → "수정"(hidden 재게시 건너뜀). (8) 체크된 571 인라인 비공개 → "0건 선택"·버튼 disabled. (11) 569·
  565 연속 재게시 뒤 두 행 선택 → 일괄 비공개 1회 클릭 → 네트워크 POST 정확히 1건(`bulk-unpublish`)·둘 다 "비공개". (10) `?q=T25-A`
  전체 탭(게시 행 0, 툴바 hidden)에서 재게시 → 체크박스 생성·툴바 노출·전체 선택 활성·1건 카운트. (14) 비공개 행 검증·비공개 버튼
  hidden. (9) 콘솔 error/warn/issue 0건. 감사 로그 16건(재게시 7·비공개 7·검증 2), 실패 시도는 무로그. 임시 데이터 삭제(이벤트 8·
  로그 16·계정 행 2), 캡처 파일 0.
  **결함 2건 → 같은 트랙 수정(FIE)**: (a) 비공개 탭처럼 툴바가 hidden인 페이지에서 행 제거 시 결과 문단이 hidden 툴바 안에 있어
  보이지 않고 `focus()` 실패 → `showResult`가 툴바를 먼저 노출(재검증: 툴바 노출·결과 텍스트·마지막 행이면 빈 문단 포커스). (b) 전체
  탭 일괄 비공개 성공 뒤 행 인라인 버튼이 갱신되지 않아 비공개 행에 "검증·비공개"가 남고 "다시 게시"가 hidden → `applySucceededEvent`
  배지 경로에서 버튼 토글(재검증: 565 일괄 비공개 뒤 republish만 노출). **미재현 관찰 1건**: G1 마지막 행 제거 직후 한 번
  `activeElement`가 body였으나 같은 경로를 focus 로그로 재실행하니 결과 문단 → 빈 문단 순으로 정상 이동(원인 미확정, 기록만).
  **픽스처 교훈**: 임시 이벤트의 `category`·`region`을 표시값("expo"·"서울")으로 넣어 재게시 검증 400이 두 번 났다 — 어휘 슬러그
  (`popup_store`·`seoul`)로 만들어야 한다(코드 결함 아님, 400 경로가 정상 동작한 부수 증거).
- **문서·회귀 [실측 2026-09-09]**: 문서 커밋 `627b3cf docs: 이벤트 게시 액션 가드레일을 통합하고 H2 트랙 25를 기록한다`(rename 내용
  + (f) 정정 + (j)~(m) + 백로그·런북). 전체 회귀(627b3cf) `uv run pytest -q` 2540 passed / 70.70초(기준선 2506 + 신규 34 [계산]),
  `check` 이상 없음, `makemigrations --check` 변경 없음, `wc -l` `events.py` 633줄·`events_actions.py` 109줄.
- **WED 사후 판정 [문서 2026-09-09]: 승인(Conforms)** — 사전 기준 10항 전부 충족(인용 `list.html:34`·`:95`, `events.css:349-351`,
  `event_bulk.js:115`·`:141-149`, `title=` 0건 — 오케스트레이터 sed/rg 재확인 [실측]). 편차 3건 수용: `title` 되돌림, `showResult`의
  툴바 노출(**Low**: 비공개 탭에서 결과 문단과 함께 "0건 선택"·disabled 버튼이 강조색 바로 드러남 — 결과·오류 문단을 바 밖으로
  분리하는 개선을 이연), 일괄 성공 경로 버튼 토글(AC5 불변식 유지에 필요). Blocking/High/Medium 없음.
- **BIR 사후 판정 [문서 2026-09-09]: 조건부 승인(Deviates → 수정 후 재확인)** — 사전 기준 10항 중 8항 Conforms. **High** (h)
  bfcache 복귀: `setRowLocked`가 체크박스·형제 버튼을 plain `disabled`로 잠그는데 `api.js` `pageshow` 핸들러는 `.is-loading`만 복구 →
  요청 중 이탈 뒤 복귀하면 그 행 컨트롤이 영구 잠금(사전 기준 9 "속성 변경만이라 무영향"은 틀림 — 정정). **Medium** (g) 비제거
  성공 분기에서 `focus()`와 live region 갱신이 같은 틱 → 스크린리더가 결과 문구를 놓칠 수 있음. **Low** (e) 404 분기의 행 오류 문단
  기록은 행과 함께 사라져 죽은 코드(계획 4항 지시 자체의 오류 — 정정). Low(절차) 브라우저 증거가 1440px 단일 뷰포트 — 스태프 콘솔은
  1024px 미만을 차단하는 데스크톱 전용 셸이라 모바일 증거는 대상 아님(기록). (f) 미재현 관찰: `handleRowRemoval` 이후 경로에 포커스
  탈취 코드 없음 확인, 추정 원인은 `setRowLocked(true)`가 포커스된 버튼을 disable하는 브라우저 동작(미확정). 저장소 전역 권고:
  `visit_create.js`·`visit_edit.js`의 같은 잠금-업로드 패턴도 pageshow 공백 가능성(이연). → FIE에 High·Medium·Low(e) 3건 수정 지시.
- **BIR 결함 3건 수정·재검증 [실측 2026-09-09]**: 커밋 `f40e6b0 fix(staff): 행 액션 잠금의 bfcache 복구와 live region 타이밍을
  보강한다` — `setRowLocked`가 행에 `is-row-locked`를 토글하고 파일 끝 `pageshow`(`persisted`) 리스너가 잠긴 행을 전부 풀어줌,
  `announce`는 `setTimeout` 100ms 뒤 기록, 404 분기 죽은 코드 3줄 제거. 브라우저 재검증(임시 이벤트 573·계정 id 91, 이후 삭제·
  실 게시 171건 유지): "비공개" 클릭 직후 같은 틱에 행 클래스·체크박스·버튼 3종 전부 disabled(잠금) → 합성
  `PageTransitionEvent("pageshow", {persisted: true})` 디스패치 → 전부 해제·클래스 제거 → 응답 도착 뒤 배지 "비공개"·republish
  포커스·live "T25-H1 비공개 완료"(지연 기록). 콘솔 오류 0건. 마크업 테스트 19 passed·`node --check` 통과.
- **최종 회귀 [실측 2026-09-09, f40e6b0]** `uv run pytest -q` 2540 passed / 87.76초. 문서 커밋 `dbea714`((m) 절에 `is-row-locked`·
  pageshow 복구·live 100ms 지연 기록).
- **QVL [문서 2026-09-09]: 조건부** — AC1·AC4·AC5·SEC-AC1~4·회귀 위험 (a)~(e) 코드 대조 충족, U8 5종 Given이 `_validate_publish_fields`
  검사 순서와 1:1 격리됨 확인, E1은 7종 parametrize(계획 문구 "경계 4종"보다 넓음), `events.py` 633줄·`events_actions.py` 109줄 일치.
  조건 3건: ① **BIR 재확인 verdict 부재**(Dual Review Gate — f40e6b0 뒤 BIR 자신의 Conforms 필요) → BIR에 재확인 요청 ② Low: 비공개
  이벤트에 `verified/` 호출 테스트 0건 → V4 추가 지시(종료된 비공개 이벤트 → `quality_badges []`, 뮤테이션은 `is_published` 가드
  제거) ③ Low: AC2 "6종" 문구 → "도달 가능 5종"으로 정정(위 AC2). 숫자 드리프트: 계획의 `test_staff_event_publish_delete_views.py`
  303줄은 P1 추가 전 값(현재 309줄 [실측 QVL grep]). 신선 실행은 오케스트레이터 실측(f40e6b0 2540 passed / 87.76초)으로 충족.
- **QVL 조건 해소 [실측 2026-09-09]**: ② V4 `test_비공개_이벤트를_검증_완료_처리하면_기록은_남지만_품질_배지는_빈_목록이다`
  (`tests/staff/test_staff_event_inline_actions.py:403`) — 파일 23 passed(4.12초, 이미-Green) → 뮤테이션 M6 검증 뷰의 `is_published`
  가드 제거 → 1 failed → 원복 `cmp` 일치. 커밋 `aa872c3 test(staff): 비공개 이벤트 검증 완료 응답의 빈 품질 배지를 핀한다`. ③ AC2
  문구 정정 완료. `check` 이상 없음·`makemigrations --check` 변경 없음(HEAD 재실행). ① **BIR 재확인 [문서 2026-09-09]: Conforms** —
  pageshow 리스너 2개(`api.js:345` `.is-loading` / `event_row_actions.js:390` `.is-row-locked`)는 `persisted`만 검사하고 셀렉터가 달라
  충돌 없음(리스너 다중 등록은 저장소 관례), `is-row-locked`는 `.then` 첫 줄에서 조건 없이 해제(`TakuAPI.post`는 fetch 예외도
  `{ok:false}`로 흡수해 `.then` 미호출 경로 없음), 100ms 지연은 포커스 이동(t=0)과 채널·시점이 분리돼 문제 없음, 404 경로 피드백은
  결과 문단 + live 두 채널 유지. 잔여(신규 아님): 100ms 안에 다른 행 액션이 연달아 오면 live 문구가 덮임(단일 live region 한계, 이연).
  → Dual Review Gate 충족(WED Conforms · BIR Conforms). **QVL 조건 3건 전부 해소 → 완료.**

## 이연
- WED Low: `#event-bulk-result`·`#event-bulk-error`를 `.events-bulkbar` 강조 컨테이너 밖으로 분리(툴바 없는 페이지의 단건 결과가
  일괄 UI 없이 보이게) — 다음 소규모 트랙.
- 수정 화면 PRG 토글의 목표 상태화 — **같은 재시도-반전 결함이 수정 화면에 잔존**(PSO 조건 명시), 일괄 재게시·검증, 검증 시각 열,
  `StaffEventBulkUnpublishView`의 `events_actions.py` 이동(순수 이동, 다음 트랙에서 함께 검토), 재검증 운영 절차 정의(사용자 결정),
  트랙 26 필터.

## 문서 대상·핸드오프 조건
- `docs/BE/staff-event-publish-actions.md`(rename + (j)~(m)), 백로그 H2 항목·미해결 제품 결정, 런북 절차 한 줄, pr-log(머지 시).

---

