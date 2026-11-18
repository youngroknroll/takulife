# 홈 이벤트 달력 섹션 — 기술 기록

기준일: 2026-09-17 · 트랙 34
대상: `templates/core/partials/_home_event_calendar.html`,
`static/css/pages/home_calendar.css`, `templates/core/home.html`,
`web/views/events.py`(`_home_calendar_context` 등 컨텍스트 조립),
연쇄 수정된 `static/css/pages/event_calendar.css`·
`templates/core/events/calendar.html`

이 문서는 **가드레일만** 담는다. 다음 작업자가 모르면 같은 실수를 반복할 것들이다.

## Current fact

- 위치: 히어로 다음, 로그인 사용자는 `_home_collection_snapshot.html` 다음
  (스냅샷이 먼저), 비로그인은 스냅샷이 렌더되지 않아 히어로 바로 다음
  [코드 `templates/core/home.html:111,113`].
- 파일: 파셜 1개(`_home_event_calendar.html`), CSS 1개(`home_calendar.css`),
  뷰 헬퍼(`_home_calendar_context`·`_events_by_date`·`_dedupe_category_slugs`,
  `web/views/events.py` 모듈-비공개).
- 컨텍스트 키 계약 `home_calendar`(dict): `year`, `month`, `month_param`
  ("YYYY-MM"), `weeks`(주×7칸, 칸=`{date, in_month, today, selected, count,
  categories}`), `selected_date`, `selected_is_today`, `selected_rows`
  (`_attach_display` 결과, 최대 3건), `selected_count`, `prev_month`/
  `next_month`("YYYY-MM"), `legend`(`[{slug, label}]`).
- 앵커 규칙: 월내비·날짜 칸은 `#home-calendar-agenda`로 돌아오고, "이 날짜의
  이벤트 N개 모두 보기" 링크는 `/events/calendar/?month=…&date=…#selected-date`
  (행사 달력)로 이동한다 [코드 `templates/core/partials/_home_event_calendar.html:169`].
  섹션 루트 `id="home-calendar"`는 랜드마크일 뿐 앵커 대상이 아니다.

## Decision

- 반응형 경계 `56.25rem`에서 2열 → 1열, `45rem`에서 모바일 셀 규칙 적용
  (히어로 `53.75rem`과 통일하지 않음, WED 결정).
- 월내비 히트타깃 44px(시안 38px 채택하지 않음) — `event_calendar.css`
  기존 컴포넌트와 통일.
- 채움 칸(당월 밖)은 카테고리 점을 찍지 않고 글자색만 `--ink-2`로 구분한다
  (트랙 58 이후 배경은 당월 칸과 같은 `--surface`다 `[코드 calendar.css:30-40,54-56]`.
  이력: 트랙 34에는 배경을 `--bg-card`로 구분했다)
  (채움 칸은 표시 달과 겹치는 행사만 알고 있어 점이 불완전하고, 디자인
  시안도 채움 칸에 점을 그리지 않는다(HC-16)).
- 선택일 행이 0건이면 "모두 보기" 링크를 생략한다(섹션 헤더 "달력 전체
  보기"가 상시 탈출로).
- 아젠다 표출 상한은 최대 3건(2026-09-17 사용자 지시로 5→3, 사유: 2열에서
  달력 아래 빈 여백). 상한 상수(`HOME_CALENDAR_AGENDA_LIMIT`)는 백엔드가
  같은 시점에 5→3으로 바꾼다 — 이 문서와 컨텍스트 계약 수치를 반드시
  함께 맞춘다.
- 당월 밖 날짜 숫자색은 공용 컴포넌트(`components/calendar.css`)의 `--ink-2`
  (`[코드 calendar.css:54-56]`, 이력: 트랙 34에는 `--muted`)를 그대로 쓴다 — 새 규칙을 추가하지 않는다.
- 아젠다 행의 tone·날짜·장소 분기는 새로 만들지 않고 기존 템플릿의 분기를
  문자 그대로 복제한다(`_event_compact_row.html`의 status_slug 5분기,
  `events/calendar.html`의 날짜·장소 4분기).
- 로그인 사용자는 컬렉션 현황을 먼저 봐야 한다는 사용자 지시(2026-09-17)로
  스냅샷을 달력 위에 둔다.

## Guardrail

**G1** 홈은 `event_calendar.css`를 로드하지 않는다
[코드 `templates/core/home.html:8-13` extra_css에 없음]. 그리드·요일·아젠다
재정의가 `home_calendar.css`에 그대로 복제돼 있고 전부 `.home-cal`/
`.home-cal-agenda`로 스코프돼 있다. 한쪽 파일만 고치면 홈과
`/events/calendar/`가 어긋난다 — 달력 스킨을 바꿀 때는 두 파일을 함께
확인해야 한다.

**G2** 새 CSS의 색은 전부 `var(--…)` 토큰이다. 지금 `tokens.css` 밖 색 리터럴은
0줄이다 `[실측 ac1_count 2026-11-17, 스태프·dist 제외]`(이력: 트랙 34에는 오늘 배지 글자
`#fff` 1곳이 있었고 트랙 58이 지웠다). 새 리터럴 hex를 추가하면 토큰 밖 색이 생긴다.

**G3** 날짜 이동으로 도착하는 앵커 대상은 세 규칙이 항상 짝으로 붙는다:
`tabindex="-1"`(키보드 포커스 이동) + `scroll-margin-top: calc(var(--site-header-h)
+ 1rem)`(sticky 헤더에 가리지 않게) + `:focus{outline:none}`(직접 탭하는
컨트롤이 아니므로 파란 기본 링을 끈다). 세 달력(홈·행사·활동) 모두 세
짝을 쓴다 — 활동 달력(`static/css/pages/archive_calendar.css`
`.date-detail-section`)에는 2026-10-27에 `scroll-margin-top`을 보완했다.
홈 `#home-calendar-agenda` [코드 `home_calendar.css`
`.home-cal-agenda`], 행사 달력 `#selected-date` [코드 `event_calendar.css`
`.date-detail-section`, `templates/core/events/calendar.html:172`]. 새 앵커 대상을 만들 때 세 짝 중
하나라도 빠뜨리면 리뷰에서 재발한다(트랙 34에서 행사 달력 쪽
`tabindex`·`scroll-margin-top`·`:focus` 3종이 모두 빠져 있던 것을 이번에
채웠다).

**G4** 카테고리 점 색 규칙은 어휘 7종 전부(popup_store, collaboration_cafe,
theater_bonus, goods_reservation, exhibition, fan_meeting, concert)를
쓴다. 지금은 `data-category` 속성이 `--dot-<slug>`(`tokens.css:20-26`)를 고른다
`[코드 calendar.css:129-142(`.day-item-cat`·`.day-mobile-dot`), home_calendar.css:111-146(`.home-cal-dot`)]`.
속성이 없거나 미지정 슬러그의 점은 기본색 `--ink-2`다 `[코드 calendar.css:118-127, home_calendar.css:111-118]`.
아젠다에는 바가 없고 카테고리 글자 `--ink-2`와 `currentColor` 점이다
`[코드 event_calendar.css:147-158, home_calendar.css:238-248]`.
이력: 트랙 34 이전에는 `event_calendar.css`에 concert 색이 빠져 점이 `--brand`, 아젠다 바가
`--muted`로 폴백했고 트랙 34가 두 파일 모두 concert를 채웠다. 새 카테고리 색 규칙을 추가할 때는
`core/vocab.py`의 어휘 수와 항상 대조한다.

**G5** 채움 칸(칸에 `date`가 있지만 `in_month=false`)은 여전히 `<a>` 링크로
렌더된다 — 다른 달로 이동하는 정상 인터랙션이다. `date=None`인 극단 칸(연도
경계를 메우는 자리)만 `data-void`가 붙은 비링크 `<span>`이다. 이 둘을
혼동해 채움 칸을 링크 없이 렌더하면 "다른 달 날짜 클릭" 동작이 사라진다.

## Known gap

- 선택일이 0건일 때 아젠다 카드 안에는 회복 링크가 없다(BIR 권고,
  Medium). 섹션 헤더 "달력 전체 보기 ›"가 상시 탈출로라 완전한 막다른
  상태는 아니라고 판단해 잔여 위험으로만 기록한다.
- 새로고침(같은 URL, 프래그먼트 포함) 시 포커스는 앵커 대상이 아니라
  `BODY`로 간다 — 브라우저의 스크롤 위치 복원 동작이며 이 트랙에서
  손댈 대상이 아니다.
- 스태프가 만든 커스텀 카테고리는 이 화면들에 슬러그별 규칙이 없어
  점은 기본색 `--ink-2`로 표시된다(트랙 58 이후 값. 이력: 트랙 34에는 점 `--brand`·바 `--muted`
  였다. 백로그 "남은 간극", 이 트랙 범위 밖).
- `.agenda-*` 스킨이 `event_calendar.css`와 `home_calendar.css` 두 곳에
  존재한다(계산 2곳). 세 번째 소비처가 생기면 `components/agenda.css`로
  추출을 검토한다(현재는 3회 규칙 미충족).

## Evidence

브라우저 실측 [문서 오케스트레이터 산출, 스크래치패드
`track34-browser-evidence.md`, Chrome DevTools MCP, dev 서버, 2026-09-17]:

- 뷰포트 경계: 901×900에서 2열(445px/380px), 900×900에서 1열(852px) —
  56.25rem 경계 ±1px 확인.
- 390×844(DPR3): 날짜 칸 49.4×52px, 카테고리 점 5px, 월내비 글리프
  히트박스 44×44px.
- 앵커 이동: 클릭 후 카드 top 85px, 헤더 하단 69px(4.3125rem×16 [계산])
  이상이라 가려지지 않음.
- 이력(트랙 34 시점 측정): 아래 다크모드 줄의 `--cat-*-ink`·`--muted`·`--bg-card`와 다크 값은
  트랙 56(다크 삭제)·트랙 58(토큰 정리)에서 삭제됐다. 지금 값은 `docs/FE/design-principles.md`가 정본이다.
- 다크모드 [실측 `getComputedStyle`]: `--cat-popup_store-ink` 라이트
  rgb(126,34,206)=#7e22ce, 다크 rgb(177,126,220)=#b17edc가 격자 점·범례
  점·아젠다 바·카테고리명 4곳에서 일치. 채움 칸 숫자색은 라이트
  rgb(91,100,114)·다크 rgb(162,169,185) = `--muted`. 채움 칸 배경은 라이트
  rgb(251,251,252)/다크 rgb(46,50,62) = 둘 다 `--bg-card`.
- 쿼리: 비로그인 홈 GET 전후 비교로 달력 컨텍스트 추가분 +1건 [계산].
- 새 CSS 리터럴 hex: `#fff` 1곳(오늘 배지)만 [실측 `rg`].
- 테스트: 신규 테스트 22건 `[실측 --collect-only 2026-09-17]`(2026-10-27
  현재 파일 수집 23건 `[실측 uv run pytest --collect-only -q tests/events/test_home_calendar.py]`).
  전체 회귀
  **2927 passed / 10 deselected** [실측 `uv run pytest -q`, HEAD
  `03a76e3a`], 기준선 main **2905 passed** [실측].
- 레이아웃: 아젠다 3건 상한 적용 후 1280px 기준 아젠다 카드 517px·달력
  영역 435px(차이 81px) [실측].
