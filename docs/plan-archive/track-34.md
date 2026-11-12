# 트랙 34: 홈 히어로 아래 이벤트 달력 섹션 (2026-09-16) [v1 — PSO·DAR·TDD 코치·WED·BIR·QVL 사전 검토 반영, 인용은 오케스트레이터가 원문 대조, **사용자 승인 완료(2026-09-17 "승인", R1은 기본값=제거하지 않음)**]

> **출처**: 사용자 지시(2026-09-16) "홈 화면의 히어로 섹션 아래에 캘린더를 표출" + "반응형 웹앱 대응, 다크화면도 함께 구현". 디자인은 claude.ai/design 프로젝트 `cb1d6dcd` "Takulife index page mockups"의 `design_handoff_home_calendar/Home Calendar Section.dc.html`(보드 안 1b 채택) + README(DesignSync `get_file`로 읽음, 사본은 세션 스크래치패드 `design/`).
> **기준선** [실측 2026-09-16, main HEAD `ed95a91f`]: `uv run pytest -q` → **2905 passed / 10 deselected / 83.48초**. 로컬 DB에 2026-09와 겹치는 게시 행사 13건 [실측 `list_published_events_for_month({}, year=2026, month=9)`], 카테고리 6종 중 빈 문자열 `''` 1종 포함.
> **브랜치·PR**: main에서 `feat/home-event-calendar`. PR 1개, base main. 머지는 사용자 승인.

## 정정 기록 (검토 단계, 오케스트레이터 원문 대조)

1. 초안 Q4 "날짜 `n/j – n/j`, 단일일 `n/j`" → **폐기**(WED 정정): 달력 페이지는 다구간만 `n.d`–`n.d`를 보이고 단일일은 날짜 줄 자체를 생략한다 [코드 `templates/core/events/calendar.html:181-189`]. 장소도 `region_label · location_name` 4분기 [코드 `:190-198`]를 문자 그대로 복제한다.
2. WED "`.day-cell:focus-visible{outline-offset:-2px}`는 `event_calendar.css:171-174`에서 상속" → **사실 오류**: `event_calendar.css`는 홈에 로드되지 않는다 [코드 `templates/core/home.html:8-12` extra_css에 없음]. 그리드·오늘 배지·아젠다·모바일·포커스 규칙 전부 새 파일 `home_calendar.css`에 직접 쓴다(WED 명세의 나머지 서술과 일치).
3. 초안 S3 "`_events_by_date`를 `_helpers.py`로" → **변경**(DAR): 호출부 2곳이 모두 `web/views/events.py` 안이라 모듈-비공개 함수로 둔다 [코드]. `_helpers.py`는 파일 간 공유 전용 [문서 `docs/BE/web-views-package.md:11`]. 선례 `_active_filter_chips` [코드 `web/views/events.py:142-156`].
4. 초안 S6 앵커 `#home-calendar`(섹션 루트) → **변경**(WED·BIR 통합): 링크 프래그먼트는 아젠다 카드 `#home-calendar-agenda`(모바일 1열에서 클릭 목적지인 "그 날 일정"으로 바로 복귀). 섹션 루트 `id="home-calendar"`는 랜드마크로 유지. 앵커 대상에 `tabindex="-1"`(선례 [코드 `templates/core/archive/calendar.html:146`], 행사 달력 페이지는 없음 [코드 `templates/core/events/calendar.html:152`])과 `scroll-margin-top`(sticky 헤더 `--site-header-h: 4.3125rem` [코드 `static/css/components/site-chrome.css:30,34-36`], 저장소 내 `scroll-margin` 사용 0건 [실측 `rg`]).
5. 초안 HC-08/HC-09(web) → **unit 경계로 재분류**(코치): 순수 문자열 규칙을 HTTP로 증명하면 최고 비용 경계이고 DB 기본 정렬에 결합된다. 새 순수 함수를 직접 호출한다.
6. 초안 HC-14 "마크업 존재 단언" → **링크 계산값 검증으로 축소**(코치, 백로그 A4 정합): `id="home-calendar"` 존재는 브라우저 증거(WED/BIR)로, 백엔드 테스트는 `_extract_href` 선례 [코드 `tests/core/test_events_calendar_view.py:60-71`]처럼 href의 `month=`/`date=` 값만 컨텍스트와 대조.
7. QVL 갭 2건 반영 [문서 QVL 산출]: `date=`만 지정(HC-03 parametrize), 선택일 0건(HC-11·HC-14b parametrize). QVL 발견 — `event_calendar()`의 `month_grid` try/except 주석 [코드 `web/views/events.py:340-354`]은 현재 `core/calendar_grid.py:59-63`이 OverflowError를 셀 단위로 흡수해 예외를 전파하지 않으므로 **stale**(극단 월 무예외는 [코드 `tests/core/test_calendar_grid.py:150`, `tests/core/test_events_calendar_view.py:273`]이 증명). 홈에는 이 방어를 복제하지 않는다. 기존 코드 정리는 아래 R1(사용자 선택).
8. 시안 월 내비 히트타깃 38px [문서 README] → 44px(기존 동일 컴포넌트 [코드 `static/css/pages/event_calendar.css:51-56,67-72`], WED 결정). 시안 모바일 셀 `min-height 48px` [문서 보드 1c] → 3.25rem(52px) [코드 `event_calendar.css:460`] 기존값 채택(WED). 시안 당월 밖 숫자 `#a8afbb` → `var(--muted)` 상속 [코드 `static/css/components/calendar.css:72-74`], 규칙 추가 없음(WED).
9. 역할 충돌 정리: 선택일 0건 상태 — BIR은 카드 안 회복 링크 권고(Medium), WED는 "N개 모두 보기" 생략·섹션 헤더 "달력 전체 보기"로 충분. 정적 빈 상태는 WED 소유 → WED안 채택, BIR 권고는 잔여 위험으로 기록(헤더 링크가 상시 탈출로, BIR도 "완전한 막다른 상태 아님" 인정).

## 사용자 결정 필요 항목

- **승인**: 아래 범위·수용 기준·Test List·파일 목록. PSO 판정: 새로 물을 제품 결정 없음(배치·반응형·다크는 사용자 직접 지시).
- **R1(선택)**: `event_calendar()`의 stale 주석+죽은 try/except [코드 `web/views/events.py:340-354`]를 이 트랙에서 제거할지. S3 리팩터로 같은 함수를 이미 건드린다. 기본값 = **제거하지 않음**(다른 종류 작업, 보고만).
- ~~**알림(질문 아님)**: 로그인 사용자 홈의 "내 컬렉션 현황" 패널이 한 섹션 아래로 내려간다(S4).~~ → **사용자 결정(2026-09-17)**: "내 컬렉션 현황은 달력 위에 있어야 해. 로그인한 사용자를 위해서 바로 알아봐야하니까." 스냅샷 include를 달력 앞으로 교환(PSO가 대안으로 적었던 배치). WED·BIR Light Conforms, 로그인 순서 hero → snapshot → calendar·비로그인 hero → calendar [실측 브라우저].

## Activated Roles / Not Activated

| 역할 | 활성 | 사유 |
|---|---|---|
| Product Scope Owner | ✅(완료) | 배치·범례·상한·복귀 규칙 승인, AC7 보강·AC8·AC9 추가 |
| Domain Architecture Reviewer | ✅(완료) | 조립 함수 위치·`_events_by_date` 배치·경계 판정, 이연 2건 [문서 DAR 산출] |
| Backend TDD Coach | ✅ | Test List 확정·첫 사이클 계약, Green 후 증거 검토 |
| Backend & Integration Engineer | ✅ | 뷰·테스트 편집(pytest 실행은 오케스트레이터 단독) |
| Web Experience Designer | ✅ | 사전 명세 완료·사후 판정 |
| Browser Interaction Reviewer | ✅ | 사전 기준 완료(깊이 High)·사후 판정 |
| Frontend Implementation Engineer | ✅ | 파셜·CSS·home.html 편집 |
| Quality Verification Lead | ✅ | 위험 매트릭스 완료·최종 증거 대조 |
| Security & Resilience Reviewer | ❌ | 공개 GET, 기존 검증 파서 재사용, 같은 파라미터가 `/events/calendar/`에 이미 공개 |
| Deployment & Operations Reviewer | ❌ | env·마이그레이션·배포 절차 변경 없음. 페이지 CSS는 셸 번들 밖 [코드 `tests/core/test_shell_css_bundle.py:13-30` `_SHELL_CSS_RELATIVE_PATHS`에 `pages/*`·`components/calendar.css` 없음] |
| AI Automation Architect | ❌ | LLM 없음 |

## 승인 범위

### 포함
- S1 홈 컨텍스트 `home_calendar`(dict, 키 고정): `year`, `month`, `month_param`("YYYY-MM"), `weeks`(주당 7칸, 칸=`{date, in_month, today, selected, count, categories}`; `categories`=그날 겹치는 게시 행사 카테고리 슬러그를 **등장 순서로 중복 제거·빈 슬러그 제외·최대 4개** [문서 README]), `selected_date`, `selected_is_today`, `selected_rows`(`_attach_display(..., today=today, user=None)` 행 **최대 3건**, 2026-09-17 사용자 지시로 5→3 [문서 사용자 지시]), `selected_count`(전체 건수), `prev_month`/`next_month`("YYYY-MM"), `legend`(그 달에 등장한 카테고리 `{slug, label}`를 `core.vocab.CATEGORY` 순서로, 빈 슬러그 제외, 없으면 `[]`). 상수 `HOME_CALENDAR_AGENDA_LIMIT = 3`(README 원안 5 [문서]), `HOME_CALENDAR_DOT_LIMIT = 4` [문서 README]. 등장 순서의 출처는 `order_for_public_listing` [코드 `events/querysets.py:148`]이며 이 종속은 문서로만 기록한다(코치: unit 테스트가 입력 순서를 직접 통제).
- S2 `?month=YYYY-MM`·`?date=YYYY-MM-DD`: `_parse_calendar_month`/`_parse_calendar_date` [코드 `web/views/_helpers.py:84-122`] 재사용. 무효 값(형식·범위·표시 달 밖)은 **오류 패널 없이 이번 달·오늘로 복귀**(200). 월 라벨은 항상 실제 표시 달과 일치(BIR 최소 요구). 날짜별 전개는 시작일~종료일, 종료일 없으면 시작일 하루 [코드 `web/views/events.py:332-338`]. `month_grid` 호출을 try/except로 감싸지 않는다(정정 7).
- S3 `web/views/events.py`에 모듈-비공개 `_events_by_date(events)`(현 `:332-338` 이동)와 `_dedupe_category_slugs(slugs, *, limit)`(순수 함수, unit 테스트 대상), `_home_calendar_context(raw_month, raw_date, *, today)` 추가 [코드]. `event_calendar()`는 `_events_by_date`를 사용(행위 불변). `home()`은 `context["home_calendar"]`만 추가.
- S4 `templates/core/home.html`: 히어로 `</section>` 직후·`_home_collection_snapshot.html` include 앞에 `{% include "core/partials/_home_event_calendar.html" %}`. extra_css에 `css/components/calendar.css`, `css/pages/home_calendar.css` 링크 추가(home.css 뒤) [코드].
- S5 파셜 `templates/core/partials/_home_event_calendar.html`(신규) [문서 WED 명세]: `<section class="section" id="home-calendar">` + `.section-head`(eyebrow "이벤트 달력", `<h2>{{ month }}월, 놓치기 아까운 일정</h2>`, `.section-more` "달력 전체 보기 ›" → `/events/calendar/?month={{ month_param }}`) + `.home-cal` 2열. 좌 `.home-cal-grid`: `<nav class="calendar-month-nav" aria-label="월 이동">`(`<h3 class="calendar-month-label">` "YYYY · M월", 링크 3개 ‹ `aria-label="이전 달"` / "오늘" / › `aria-label="다음 달"`, href `?month=..#home-calendar-agenda`, "오늘"은 `/#home-calendar-agenda`) + `.month-grid.month-grid-head`(요일 7개) + `.month-grid.month-grid-body`(칸: `date` 있으면 `<a class="day-cell" href="?month=Y-m&date=Y-m-d#home-calendar-agenda" data-in-month data-today data-selected aria-label="{Y년 n월 j일 l}[, 이벤트 N개][, 오늘][, 선택한 날짜]" [aria-current="date"]>` 안에 `<span class="day-num">j</span>` + `{% if categories %}<span class="home-cal-dots" aria-hidden="true">` 점 `<span class="home-cal-dot" data-category="slug">`; `date` 없으면 `<span class="day-cell" data-void aria-hidden="true">` [코드 `_calendar_grid.html:34-66` 관례]) + `{% if legend %}` 범례(`.calendar-legend`/`.legend-item` + `.home-cal-dot[data-category]`, 마크업은 `templates/core/archive/calendar.html`의 범례 구조를 따른다). 우 `<div class="home-cal-agenda" id="home-calendar-agenda" tabindex="-1">`: `.date-detail-head`(`<h3>` "n월 j일" + `.date-detail-weekday` "l[ · 오늘]", `.date-detail-count` "N개"는 N≥1일 때) + 행이 있으면 `.agenda-rows` 안 `<article class="agenda-row" data-cat="slug">`(`.agenda-bar` / `.agenda-meta`: `{% if category_label %}.agenda-cat` · `.agenda-dot` · `.agenda-tone`(**`_event_compact_row.html:43-51`의 분기 문자 그대로**: 종료 / 오늘 종료 / D-N / 오늘 오픈 / 오픈 D-N / status_label) / `{% if work_title %}.agenda-work` / `<h3 class="agenda-title"><a href="/events/{id}/">` / 날짜·장소는 **`calendar.html:181-198` 분기 문자 그대로**) + `<a class="home-cal-agenda-more" href="/events/calendar/?month={month_param}&date={Y-m-d}#selected-date">이 날짜의 이벤트 N개 모두 보기 ›</a>`; 행이 없으면 `<p class="notice">이 날짜에는 등록된 이벤트가 없습니다.</p>`만(링크 생략). 찜 버튼·방문 상태 마커·`.agenda-end` 없음. 헤딩 위계 h1(히어로) → h2(섹션) → h3(월 라벨·아젠다 헤더) → h3(행 제목은 `calendar.html:180` 선례 유지).
- S6 CSS `static/css/pages/home_calendar.css`(신규, `home.css` 786줄 [실측]이 800줄 상한에 근접해 분리). 전부 `var(--…)`; 리터럴은 오늘 배지 글자 `#fff` 1곳 [코드 선례 `event_calendar.css:140`]만. 규칙(값은 README [문서]·`event_calendar.css` [코드]):
  - `.home-cal{display:grid;grid-template-columns:minmax(0,1fr) 23.75rem;gap:1.75rem;align-items:start}` [문서 README].
  - 월 내비(`.home-cal` 스코프): flex·space-between·`margin-bottom:.75rem`; `.calendar-month-label{margin:0;flex:none;white-space:nowrap;font-size:1.375rem;font-weight:300;letter-spacing:-.01em}`; `-sep{margin:0 .2em;color:var(--muted);font-weight:400}`; `-name{font-weight:400}`; `-glyph`/`-today`는 `event_calendar.css:51-82`와 같은 44px 박스(브랜드 잉크·hover underline) [코드].
  - 요일: `.month-grid-head{gap:1px;padding-inline:1px;margin-bottom:.375rem}`, `.month-grid-weekday{text-align:left;padding:0 .25rem;font-size:.625rem;font-weight:700;letter-spacing:.06em}`, `nth-child(7n+1)`=`--brand-ink`, `nth-child(7n)`=`--up-ink` [문서 README].
  - 본문: `.month-grid-body{gap:1px;background:var(--line);border:1px solid var(--line);border-radius:12px;overflow:hidden}`; `.day-cell{border:none;border-radius:0;min-height:4rem;padding:.4375rem .5rem;gap:.3125rem}`; `[data-in-month="false"]{background:var(--bg-card)}`; `[data-today="true"]{border:none;box-shadow:inset 0 -3px 0 var(--brand)}`; 선택 배경 `--brand-soft`·숫자 brand-ink는 `components/calendar.css:59-66` 상속(재정의 없음, 오늘=선택이면 중첩); `.day-num{display:inline-flex;align-items:center;justify-content:center;width:1.375rem;height:1.375rem;border-radius:999px;font-size:.75rem;font-weight:600}`; `[data-today="true"] .day-num{background:var(--brand);color:#fff}`; 일/토 숫자 색은 `event_calendar.css:161-167` 셀렉터 그대로; hover `.day-cell:not([data-selected="true"]):not([data-void]):hover{background:var(--bg-soft)}`; `.day-cell:focus,.day-cell:focus-visible{outline-offset:-2px}` [문서 README·코드].
  - 점: `.home-cal-dots{display:inline-flex;gap:3px;padding-left:.25rem}`; `.home-cal-dot{width:6px;height:6px;border-radius:50%;background:var(--brand)}` + `[data-category="<slug>"]{background:var(--cat-<slug>-ink)}` **7종 전부**(popup_store, collaboration_cafe, theater_bonus, goods_reservation, exhibition, fan_meeting, concert — `event_calendar.css:183-211`은 concert가 빠져 있다 [코드], 홈은 어휘 7종 [코드 `core/vocab.py:21-29`] 전부).
  - 범례: `.home-cal .calendar-legend{margin:.75rem 0 0;gap:1rem}`, `.legend-item{gap:.375rem}`, `.calendar-legend .home-cal-dot{width:8px;height:8px}` [문서 README].
  - 아젠다: `.home-cal-agenda{border:1px solid var(--line);border-radius:14px;background:var(--surface);padding:1.25rem 1.375rem 1rem;scroll-margin-top:calc(var(--site-header-h) + 1rem)}`; `.date-detail-head`/`-weekday`/`-count`와 `.agenda-row`(`--row-cat-ink` + `data-cat` 7종)/`-bar`/`-meta`/`-cat`/`-dot`/`-tone`/`-work`/`-title`(a inherit·focus-visible)/`-date`/`-place`는 `event_calendar.css:257-400` 값을 `.home-cal-agenda` 스코프로 복제하되 행 그리드 `4px minmax(0,1fr)`(2열), 행 `padding:.75rem .125rem`, 구분선 `--border-soft` [문서 README]; `.home-cal-agenda-more{display:block;padding:.75rem .125rem .375rem;font-size:.8125rem;font-weight:600;color:var(--brand-ink)}` + hover underline + focus-visible.
  - 반응형: `@media (max-width:56.25rem){.home-cal{grid-template-columns:minmax(0,1fr)}}`(WED: 히어로 53.75rem과 통일하지 않음). `@media (max-width:45rem)`: `event_calendar.css:438-480` 모바일 규칙과 같은 값 [코드](`.month-grid` gap 2px, head gap 2px·padding 0, body 배경·테두리·라운드·overflow 해제, `.day-cell{min-height:3.25rem;border:1px solid var(--line);border-radius:.5rem;align-items:center;justify-content:center;padding:.25rem .125rem}`, `[data-today="true"]{border:2px solid var(--brand);box-shadow:none}`, `.day-num{font-size:.625rem;width:1.25rem;height:1.25rem}`) + `.home-cal-dots{padding-left:0;justify-content:center;gap:2px}`, `.home-cal-dot{width:5px;height:5px}` [문서 README].
  - 새 transition·animation 없음(reduced-motion 추가 규칙 불필요, `components/calendar.css:216-220` 상속).
- S7 다크모드: 토큰 상속만. 확인 포인트 `--bg-card`·`--line`·`--brand`·`--brand-soft`·`--border-soft`·`--cat-*-ink` 다크값 [코드 `static/css/tokens.css:170-284`], `.notice` 다크 오버라이드 [코드 `static/css/components/cards.css:106`].
- S8 문서: `.docs/FE/2026-09-16-home-event-calendar.md`(FE 기술 기록: 두 리뷰어 사전 산출·사후 판정·브라우저 증거), `docs/backlog.md` 현재 상태 행(PR 시점), `docs/pr-log.md`(머지 시), `docs/BE/web-views-package.md:12` `events.py` 줄 수 갱신(DAR 권고, 456줄 [문서] → 현재 524줄 [실측 `wc -l`] → 구현 후 재측정).

### 제외
- 날짜 클릭 무새로고침 JS 전환(이연). 아젠다 찜 버튼·방문 상태 마커. 스태프 커스텀 카테고리 슬롯 색 이관(백로그 "남은 간극"). 홈 달력 필터 연동. `components/calendar.css`·`event_calendar.css`·`_calendar_grid.html`·`calendar.html` 수정 없음. 모델·마이그레이션·API·JS 신규 없음. 시안 모바일 보드의 하단 "M월 달력 전체 보기" 캡슐 버튼(섹션 헤더 링크로 대체). 스냅샷 `snapshot_active` 로직(F19) 무접촉.

## 수용 기준

- AC1 `GET /`(파라미터 없음): 이번 달 격자·오늘 선택 — 컨텍스트(HC-01·01b) + 렌더(브라우저).
- AC2 `?month=`로 다른 달은 1일 선택, `?date=`(month 동반·단독) 지정 가능, 무효 값은 이번 달·오늘로 복귀(200, 오류 UI 없음) — HC-02·03·04.
- AC3 기간 행사 시작~종료 모든 칸 반영, 종료일 없으면 시작일 하루, 초안 제외 — HC-06·10.
- AC4 칸 카테고리 중복 제거·빈 슬러그 제외·최대 4개 [문서 README], 범례는 그 달 등장 카테고리만 어휘 순서 — HC-08·09·13.
- AC5 선택일 행 최대 3건 [문서 2026-09-17 사용자 지시 "달력 폼 밑에 여백이 많이 생기기 때문", README 원안 5건]·전체 건수 별도·0건이면 빈 행·빈 상태 문구·"모두 보기" 링크 생략 — HC-11·14b + 브라우저.
- AC6 이전/다음 달 값 연도 경계 통과 — HC-12(극단 월 무예외는 기존 테스트가 담당, 재중복 없음).
- AC7 로그인 여부와 무관하게 섹션 렌더(PSO). 브라우저: 1280×900·900×900(56.25rem 경계 ±1px)·390×844 × light/dark에서 시안 일치, 가로 오버플로 0(`scrollWidth <= innerWidth`), 키보드 순서 월내비 3개 → 날짜 칸(void 제외) → 아젠다 링크 [문서 BIR], 포커스 링 가시(`outline-offset:-2px`), 셀 클릭 후 `location.hash === "#home-calendar-agenda"`·`document.activeElement`가 그 카드·카드 top ≥ 헤더 높이 69px [계산 4.3125rem×16], 콘솔 오류 0.
- AC8 로그인 홈 섹션 순서 hero → home-calendar → snapshot-panel → 카테고리 → 이번 주 → 마감 임박 → 새 이벤트(브라우저 DOM 확인, PSO).
- AC9 빈 카테고리 행사는 count·아젠다에는 포함되고 점·범례에서만 제외(HC-09 count 단언 + 브라우저 회색 바 확인, PSO).
- AC10 선택일 행에 `_attach_display` 표시 필드(status_slug·status_label·category_slug·category_label·dday) 존재 — HC-15.

## Domain Boundary and Dependency Direction (DAR)

새 도메인 없음. `events` 공개 조회 경계(발행·월 겹침·정렬)와 `core.calendar_grid`·`core.vocab`에 대한 기존 web→core 단방향 의존만 재사용. `_home_calendar_context`·`_events_by_date`·`_dedupe_category_slugs`는 `web/views/events.py` 모듈-비공개(공개 행사 열람 그룹 파일-당-피처 구조 [문서 `docs/BE/web-views-package.md:12`]). 점·행 상한·빈 슬러그 제외·범례 정렬은 도메인 불변식이 아닌 표시 규칙이라 web 소유. 날짜별 전개는 기존 뷰 배치를 넓히지 않고 재사용(해소는 이연). 애플리케이션 서비스·트랜잭션 경계 해당 없음(읽기 전용). 금지 방향(`core.calendar_grid`→`events`/`archive` AST 가드 [코드 `tests/core/test_calendar_grid.py:120`], `web`→`staff`) 무접촉.

## Coupling and Cohesion Review (DAR)

1. 결합: 늘지 않는다. 날짜 전개 로직 이중 구현 위험 제거, 월 겹침·정렬·파서 재사용으로 규칙 지점 1곳 유지. 숨은 결합 1건(카테고리 등장 순서 ↔ `_ordered_by_default_state` [코드 `events/querysets.py:119`])은 S1에 문서화, unit 테스트는 입력 순서를 직접 통제.
2. 응집: 표시 규칙은 web, 도메인 규칙은 events/core에 유지. 통과.

## Pythonic Code Design

`_home_calendar_context`는 파서 → 조회 → `_events_by_date` → `month_grid` → 칸 dict 조립 → `_attach_display` 순의 명시적 데이터 흐름, 함수 50줄 이내 목표 [문서 사용자 전역 지침](초과 시 칸 조립을 `_home_calendar_weeks(grid, events_by_date, *, today, selected_date)`로 분리). 상수 2개 [문서 README]는 매직넘버 제거용, 확장 포인트 없음. 컨텍스트는 dict 1개(`home_calendar`)로 네임스페이스.

## Test List (코치 확정 + QVL 갭 반영, 총 15건 [계산], 파일 `tests/events/test_home_calendar.py`, `pytestmark = pytest.mark.web`, unit 항목은 `@pytest.mark.unit`)

오늘 고정은 `patch("web.views.events.timezone.localdate", return_value=date(2026, 9, 16))` [코드 `tests/events/test_home_view.py:80` 관례]. 행사 생성은 `make_event` [코드 `tests/conftest.py:95`].

| ID | 경계 | 행위 | Given | When | Then | Test name | Expected Red |
|---|---|---|---|---|---|---|---|
| HC-01 | web | 파라미터 없이 홈을 열면 이번 달·오늘이 기본 | today=2026-09-16, 행사 없음 | GET / | `home_calendar.year==2026`, `month==9`, `selected_date==date(2026,9,16)` | `test_파라미터_없이_홈을_열면_컨텍스트에_이번_달과_오늘이_기본으로_담긴다` | `home_calendar` 키 없어 KeyError |
| HC-01b | web | 오늘 칸에 today·selected 플래그 | 동일 | GET / | weeks 각 주 7칸 [문서 코치], 9/16 칸 `today`·`selected` True, `month_param=="2026-09"`, `selected_is_today` True | `test_파라미터_없이_홈을_열면_오늘_칸에_오늘과_선택_플래그가_모두_참으로_담긴다` | weeks 미생성 |
| HC-02 | web | month로 다른 달이면 1일 선택 | today=2026-09-16 | GET /?month=2026-11 | `selected_date==date(2026,11,1)`, 격자에 11/1·11/30 포함, `selected_is_today` False | `test_month_파라미터로_다른_달을_열면_그_달_1일이_선택된다` | `?month=` 미처리 |
| HC-03 | web | date로 날짜 지정(parametrize ids: 월과_함께/날짜만) | today=2026-09-16 | GET /?month=2026-09&date=2026-09-20 · GET /?date=2026-09-20 | `selected_date==date(2026,9,20)`, 그 칸 selected True | `test_date_파라미터로_날짜를_지정하면_그_날짜가_선택된다` | `?date=` 미처리 |
| HC-04 | web | 무효 month/date는 조용히 복귀(parametrize ids: 잘못된_월_형식/표시_월_밖_날짜) | today=2026-09-16 | GET /?month=2026-13 · GET /?month=2026-10&date=2026-09-20 | 200, `year==2026`·`month==9`·`selected_date==오늘`, 본문에 "요청한 날짜를 확인할 수 없어요" 없음 | `test_잘못된_month_또는_date_값은_오류_없이_이번_달_오늘로_되돌아간다` | 무효 분기 없음 |
| HC-12 | web | 이전·다음 달 값 연도 경계 | | GET /?month=2026-12 | `prev_month=="2026-11"`, `next_month=="2027-01"` | `test_이전_다음_달_값은_연도_경계를_넘어간다` | 미계산 |
| HC-06 | web | 기간 전개(parametrize ids: 종료일_있음/종료일_없음) | 9/10~9/12 popup_store 1건 · 9/10 end=None 1건 | GET / | 10·11·12일 count 1·categories ["popup_store"], 13일 0 · 10일 1, 11일 0 | `test_기간_행사는_시작일부터_종료일까지_날짜_칸에_반영되고_종료일이_없으면_시작일만_반영된다` | 이벤트 미조회로 전부 0 |
| (S3) | 리팩터 | HC-06 Green 직후 `_events_by_date` 추출, `tests/events/test_home_calendar.py` + `tests/core/test_events_calendar_view.py` 동시 Green 확인 | | | | | |
| HC-08 | unit | 같은 카테고리 중복은 하나 | `["popup_store","popup_store"]` | `_dedupe_category_slugs(slugs, limit=4)` | `["popup_store"]` | `test_같은_카테고리가_중복이면_하나로_합쳐진다` | 함수 부재 |
| HC-09 | unit | 5종 이상은 4종, 빈 슬러그 제외, 등장 순서 유지 | `["", "a","b","c","d","e"]`형 6개 [문서 README 상한] | 동일 | 길이 4, `""` 없음, 앞 4개 순서 | `test_카테고리가_다섯_종_이상이면_최대_네_종만_남고_빈_슬러그는_제외된다` | 상한·제외 없음 |
| HC-10 | web | 초안 제외(전제 고정 — HC-06 이후 추가 구현 없이 Green 가능, 보고 시 명시) | 오늘 DRAFT 1건 | GET / | 오늘 칸 count 0, `selected_rows==[]` | `test_초안_행사는_홈_달력에_나타나지_않는다` | 구현 전 KeyError |
| HC-11 | web | 선택일 행 상한·전체 건수(parametrize ids: 네_건_상한/행사_없음, 2026-09-17 상한 5→3 변경) | 오늘 겹침 4건 [문서 상한+1] · 0건 | GET / | len 3·count 4 · len 0·count 0 | `test_선택한_날짜의_행사는_최대_세_건까지_담기고_전체_건수는_따로_담긴다` | 상한 없음 |
| HC-15 | web | 선택일 행에 파생 표시값 | 오늘 1건(category popup_store) | GET / | 행에 `status_slug`·`status_label`·`category_slug=="popup_store"`·`category_label=="팝업스토어"`·`dday` 키 | `test_선택일_행은_행사의_파생_표시값을_담는다` | `_attach_display` 미경유 |
| HC-13 | web | 범례는 등장 카테고리만 어휘 순 | exhibition 1건·popup_store 1건·category "" 1건 | GET / | `legend==[{"slug":"popup_store","label":"팝업스토어"},{"slug":"exhibition","label":"전시"}]` | `test_범례는_표시_달에_실제로_있는_카테고리만_어휘_순서로_담는다` | legend 미구현 |
| HC-14a | web | "달력 전체 보기" 링크가 표시 달로 | today 고정 | GET /?month=2026-11 | `_extract_href`형 추출로 href == `/events/calendar/?month=2026-11` | `test_홈_응답의_달력_전체_보기_링크는_표시_달로_이동한다` | 파셜 미포함 |
| HC-14b | web | "모두 보기" 링크에 선택일(parametrize ids: 행사_있음/행사_없음) | 9/20 1건 · 0건, GET /?date=2026-09-20 | | 있음: href에 `month=2026-09`·`date=2026-09-20`·`#selected-date` · 없음: 링크 부재 | `test_홈_응답의_모두_보기_링크는_선택한_날짜를_담는다` | 파셜 미포함 |
| HC-16 | web | (구현 중 추가 — 브라우저 검증 발견) 채움 칸에는 건수·카테고리를 담지 않는다 | 8/28~9/3 popup_store 1건 | GET / | 8/31 칸 in_month False·count 0·categories [], 9/1 칸 count 1 | `test_이번_달_밖_채움_칸에는_행사_건수와_카테고리를_담지_않는다` | 8/31 count 1 |
| HC-17 | web | (구현 중 추가 — 코치 지적: AC9 근거 HC-09는 건수를 다루지 않음) 빈 카테고리 행사는 건수·아젠다에 남고 점·범례에서 빠진다 | 오늘 category "" 1건 | GET / | 오늘 칸 count 1·categories [], selected_count 1, 행 제목 일치, legend [] | `test_카테고리가_없는_행사는_건수와_아젠다에는_남고_점과_범례에서는_빠진다` | 첫 실행 Green → 뮤테이션 Red |

**실행 결과** [실측, 이 세션]: 사이클 전부 기대 사유로 Red → Green. 첫 실행 Green 3건(HC-10, HC-14b[행사_없음], HC-17)은 임시 뮤테이션으로 Red 확인 후 원복(미커밋). HC-10은 코치 지적으로 `selected_rows == []` 단언을 뒤늦게 추가. 신규 테스트 22건 [실측 `--collect-only`], 전체 회귀 2927 passed / 10 deselected / 98.60초 [실측 HEAD `03a76e3a`], 기준선 대비 +22건 [계산].

실행 순서: HC-01 → 01b → 02 → 03 → 04 → 12 → 06 → (S3 리팩터) → 08 → 09 → 10 → 11 → 15 → 13 → 14a → 14b(14a/b는 파셜·include 완성 후).

첫 사이클 계약(코치 원문 [문서 코치 산출]): Scenario HC-01 / Given today 고정·행사 없음 / When `Client().get("/")` / Then 최상위 스칼라 3개(year·month·selected_date) / boundary web / DB·HTTP: HTTP 필요, `django_db` 표시 / Expected Red: `resp.context["home_calendar"]` KeyError / Minimum Green: `home()`에 `{"year","month","selected_date"}`만 담은 dict 추가 / Refactoring allowed: No / `uv run pytest -q tests/events/test_home_calendar.py::test_파라미터_없이_홈을_열면_컨텍스트에_이번_달과_오늘이_기본으로_담긴다`.

## Frontend Review Evidence

- 검토 깊이: **High** [문서 BIR·WED 사전 산출](BIR: sticky 헤더 기하 + 저장소 공용 "월 이동/날짜 셀 앵커" 패턴 2곳 교차 + 히어로 로테이터 재초기화 상호작용). WED는 Standard 제안했으나 높은 쪽 채택.
- WED 사전 명세(완료, 요지 S5~S7에 반영): 뼈대 클래스 재사용·새 클래스 `.home-cal*`, 앵커 2개, 문자 그대로 복제 대상 2곳(`_event_compact_row.html:43-51`, `calendar.html:181-198`), 56.25rem, 당월 밖 색 상속, 44px 히트박스, 0건 링크 생략, 범례 0건 숨김, 오늘=선택 중첩 허용. Conforms 기준: 구현 수용 기준 11항 전부 스크린샷·DOM 증거, 새 CSS 리터럴 hex `#fff` 1곳 외 0(diff 확인).
- BIR 사전 기준(완료): (1) 앵커 대상 `tabindex="-1"`; (2) `scroll-margin-top`; (3) 스킵 링크 `#content`와 충돌 없음; (4) 전체 재요청에 따른 로테이터 재초기화는 허용; (5) 키보드 순서 월내비 3 → 날짜 칸(void 제외) → 아젠다 행 제목 링크 → 모두 보기; (6) `outline-offset:-2px`; (7) 38px vs 44px는 정보(폐기 규칙); (8) 새 애니메이션 없음; (9) 모바일 셀 44px 이상; (10) 채움 칸 `span[data-void][aria-hidden]`, 링크 없음. 사전 발견: High 1(포커스 미이동 → tabindex로 해소), Med-High 1(헤더 클리핑 → scroll-margin으로 해소), Med 1(0건 회복 링크 → 정정 9로 잔여 위험 기록), 정보 1.
- 계획된 브라우저 증거: AC7·AC8·AC9 항목 + WED 상태별 (a) 기본 진입 (b) 다른 달 (c) 오늘≠선택 (d) 선택일 0건 (e) 5종 이상 날(4개 캡) (f) 빈 슬러그 행 회색 바. 측정 스크립트: `document.documentElement.scrollWidth <= innerWidth`, Tab마다 `document.activeElement` 로깅, 클릭 후 `location.hash`·`activeElement`·`getBoundingClientRect().top`, `.day-cell:focus` computed `outline-offset`. 캡처는 스크래치패드에 두고 검증 후 삭제.
- 사후 판정 [문서 각 역할 산출, 2026-09-17]: WED **Conforms**(수용 기준 11항 전부) / BIR **Conforms**(A1~A10 전부, 결함 0건) / QVL: 3건 상한 변경 전 코드 기준으로 "미완료"(선행 조건 5개) → 오케스트레이터가 조건 1·2(Green, 전체 회귀 2927 passed)·3(3건 상한 뒤 1280·901 뷰포트 × 라이트·다크 재측정: 아젠다 3행, 카드 517px·달력 영역 435px, 오버플로 0, 콘솔 0건 [실측])·4(이 표 HC-16·17 등재, 콘서트 항목 정정)·5(PR 본문 공개)를 충족.
- 사후 발견·수정 [실측 브라우저]: 채움 칸 점(HC-16, `de11c742`), 채움 칸 배경 `--bg-card` 누락·아젠다 포커스 링(`8e846529`), 행사 달력 `#selected-date` 포커스·콘서트 색(`ab38a5e2`). 사용자 지시로 아젠다 상한 5→3(`03a76e3a`).

## 파일·구현 단계

1. 브랜치 `feat/home-event-calendar`. 백엔드 사이클 HC-01~HC-15(Backend & Integration Engineer 편집, 오케스트레이터가 사이클마다 Red·Green 실행). S3 리팩터는 HC-06 Green 직후.
2. 프론트: `_home_event_calendar.html`, `home.html`, `home_calendar.css`(Frontend Implementation Engineer, WED·BIR 사전 산출 준수). 완료 후 HC-14a/b Red→Green.
3. 오케스트레이터 브라우저 검증(dev 서버 + Chrome DevTools MCP) → WED·BIR 사후 판정 → 코치 Green 증거 검토 → QVL 완료 판정.
4. 문서 S8 → 커밋(의미 단위: 테스트+뷰 / 리팩터 / 파셜+CSS / 문서) → 푸시 → PR.

## 검증 명령·기대 증거

- 사이클: `uv run pytest -q tests/events/test_home_calendar.py::<name>` Red(기대 사유) → Green.
- 슬라이스(QVL 확장): `uv run pytest -q tests/events tests/core/test_events_calendar_view.py tests/core/test_head_meta.py tests/core/test_static_reference_guard.py tests/core/test_shell_css_bundle.py tests/core/test_calendar_grid.py tests/web/test_sitemaps.py`
- 전체: `uv run pytest -q`(기대 2905+신규 passed [계산], 0 failed) / `uv run python manage.py check`(0 issues) / `uv run python manage.py makemigrations --check --dry-run`(변경 없음).
- 쿼리 증가분: `django_assert_num_queries` 또는 `CaptureQueriesContext`로 홈 GET 전후 차이 실측 후 보고([계산] +1 예상, 테스트로 고정하지는 않음 — 기존 `home()`에 쿼리 예산 테스트 없음).
- 브라우저: 위 Frontend Review Evidence.

## 이연·발견

- Deferred Refactoring Note(DAR) 1: 날짜별 전개 규칙을 `events/queries.py` 또는 `EventQuerySet`으로 이관 — 트리거: 세 번째 호출부 또는 DB 없는 단위 테스트 요구. 관련 테스트 `tests/core/test_events_calendar_view.py`, `tests/events/test_home_calendar.py`.
- Deferred Refactoring Note(DAR) 2: `web/views/events.py` 크기(현재 524줄 [실측]) — 트리거: 700줄 초과 또는 대형 조립 함수 3번째 추가 시 서브모듈 분리.
- Deferred Refactoring Note(오케스트레이터): `.agenda-*` 규칙이 `event_calendar.css`와 `home_calendar.css` 2곳 [계산]에 존재 — 트리거: 세 번째 소비처 등장 시 `components/agenda.css`로 추출(현재 2곳, 3회 규칙 미충족).
- 발견(정정 7): `event_calendar()` stale 주석+죽은 try/except [코드 `web/views/events.py:340-354`] — R1 사용자 선택.
- 발견(코드): `event_calendar.css:183-211`·`:298-320`에 concert 카테고리 색 규칙 없음 → 달력 페이지에서 콘서트 점·바가 `--brand`/`--muted` 폴백. 계획 시점엔 "보고만, 백로그 후보"였으나 **구현 중 사후 리뷰(BIR)가 같은 페이지의 `#selected-date` tabindex 누락을 함께 확인해, 사용자 상시 결정(2026-08-25 같은 유형 소규모 결함은 같은 트랙에서 수정)에 따라 커밋 `ab38a5e2`에서 두 건 모두 수정 완료** — 계획 제외 목록의 `event_calendar.css`·`calendar.html` 무수정 원칙을 이 두 건만큼 확장했다(PR 본문에 명시).
- 발견(문서): `docs/BE/web-views-package.md:12` `events.py` 줄 수 stale(S8에서 갱신).
- 이연(초안 제외 목록): JS 무새로고침 전환, 찜 버튼, 슬롯 색 이관.

## 문서 대상·핸드오프

- `.docs/FE/2026-09-16-home-event-calendar.md` [문서 계획]: Current fact(섹션 위치·앵커 2개·컨텍스트 계약), Decision(56.25rem·44px·0건 링크 생략·당월 밖 색 상속), Guardrail(리터럴 hex 금지·`event_calendar.css` 미로드이므로 규칙 복제 필요·`tabindex=-1`+`scroll-margin-top` 쌍), Known gap(concert 색·0건 회복 링크 잔여), Evidence(브라우저 측정치).
- `docs/backlog.md` 현재 상태 표에 트랙 34 항목 추가. `docs/pr-log.md`는 머지 시.

---

