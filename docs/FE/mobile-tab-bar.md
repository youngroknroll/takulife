# 모바일 하단 탭 바 — 가드레일

이 문서는 **가드레일만** 담는다. 2026-11-15 트랙 56에서 모바일(45rem 이하) 주 내비를 ☰ 메뉴에서 화면 하단 고정 탭 바로 바꿨다(사용자 지시 "모바일에서 메뉴는 하단으로 이동. 클릭하기 쉽도록").

## 현재 구성

- 주 내비는 헤더 마크업 안 `#primary-nav` 하나다(`templates/core/partials/_site_header.html`, `templates/500.html`). 두 번째 `<nav>`는 없다. 45rem 이하에서만 CSS가 `position: fixed; bottom: 0`으로 화면 하단에 옮긴다(`static/css/components/site-chrome.css`의 45rem 미디어 쿼리). 그래서 데스크톱과 모바일의 탭 순서가 같다(건너뛰기 → 로고 → 주 내비 4개 → 계정 → 본문).
- 탭 바 높이는 `--site-tabbar-h`(칸 3.5rem + 위 경계선 1px + 안전 영역) 하나로 정한다. 이 변수는 45rem 이하 블록에서만 정의되므로 넓은 화면에서는 `var(--site-tabbar-h, 0px)`가 0이다.
- 현재 섹션 링크는 `class="active"`와 `aria-current="page"`를 함께 가진다(`tests/core/test_site_header_nav.py`가 바이트 문자열로 고정).

## 가드레일

**G1 `.site-header`(와 주 내비의 다른 조상)에 45rem 이하에서 `backdrop-filter`·`transform`·`filter`·`perspective`·`will-change: transform`을 두지 않는다.** 이 속성이 있으면 `position: fixed` 자손의 기준 상자가 뷰포트가 아니라 그 조상이 되어 탭 바가 화면 하단이 아니라 헤더 아래에 붙는다. 데스크톱 헤더의 흐림은 45rem 이하에서 `backdrop-filter: none`으로 끈다.

**G2 화면 하단에 고정되는 새 요소는 탭 바 위에 쌓는다.** 규칙 두 줄을 같이 쓴다:
- 요소: `bottom: var(--site-tabbar-h, 0px);`
- 문서 끝 여백: `body:has(<그 요소>) { padding-bottom: calc(<요소 높이 rem> + var(--site-tabbar-h, 0px)); }` — 빠지면 끝까지 스크롤해도 푸터 마지막 줄이 요소 뒤에 남는다. JS가 `hidden`으로 숨기는 요소는 `:has(<요소>:not([hidden]))`.
기존 11곳 예: `static/css/pages/event_detail.css`(`.mobile-cta`), `archive_collection_detail.css`(`.collection-detail-actions`) 등.

**G3 토스트처럼 화면 아래에 뜨는 알림은 `max(env(safe-area-inset-bottom), var(--site-tabbar-h, 0px))`만큼 올린다.** 헤더가 `position: sticky; z-index: 50`이라 그 안의 탭 바는 페이지 수준 50으로 그려져, z-index 50 미만의 요소를 덮는다(`static/css/components/toast.css`).

**G4 탭 바 라벨에 `white-space: nowrap`·`word-break: keep-all`을 주지 않는다.** ja "マイアクティビティ"는 80px 칸에서 두 줄로 접혀야 넘치지 않는다 `[실측 Chrome DevTools 2026-11-15, 320px 4개 언어 칸 80×56px 넘침 0]`.

**G5 탭 바 배경은 불투명(`--surface`)이다.** 반투명 크롬색(`--chrome-glass-cta`)이면 뒤로 지나가는 큰 제목이 라벨 뒤에 비친다.

## 알려진 공백

- iOS 실기기에서 `env(safe-area-inset-bottom)` 값은 확인하지 못했다. `templates/base.html`의 viewport meta에 `viewport-fit=cover`가 없다 — 기존 하단 고정 바 11곳과 같은 조건이다.
