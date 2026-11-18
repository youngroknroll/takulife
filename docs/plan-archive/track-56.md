# 트랙 56: 다크 모드 전면 삭제 — 라이트만 남긴다 (2026-11-15) [v2 — WED·BIR·TDD 코치·QVL 사전 검토 반영, **사용자 승인 2026-11-15 "오케이 진행하도록."(D1~D8 기본값 포함)** · 사용자 지시 2026-11-15 "다크모드는 전면 삭제. 라이트모드만 생성."(시안) → "오케이 적용하도록"(운영 사이트·디자인 문서까지) [문서 사용자 지시]] · **PR #418 머지 완료(2026-11-16T18:35:35Z, merge commit `149ca3d9`, 사용자 직접 머지 "자체 머지 하였음.") `[실측 gh]`**

> **기준선** `[코드 main 22b51350 작업 트리, rg 2026-11-15]`: 다크 모드는 템플릿 4개(`templates/base.html`, `templates/500.html`, `templates/core/partials/_site_header.html`, `templates/staff/base_staff.html`), CSS 6개(`static/css/tokens.css`, `static/css/base.css`, `static/css/components/cards.css`, `static/css/components/site-chrome.css`, `static/css/staff/tokens.css`, `static/css/staff/base.css`), JS 1개(`static/js/shared/theme.js` 86줄), 백엔드 1곳(`core/categories.py` PALETTE·UNASSIGNED_PALETTE의 `dark_soft`/`dark_ink` 13쌍), 스태프 카테고리 템플릿 2개, 테스트 3개, 번역 파일 3개에 걸쳐 있다. `static/css/dist/shell.css`는 git 무시 빌드 산출물이고 `docker/entrypoint.sh:10`이 매 기동 때 다시 만든다 `[코드]`.

## 결정(기본값 — 사용자 승인 대상)

- D1 스태프 콘솔도 포함한다. 근거: 지시가 "전면"이고, `theme.js`를 공개·스태프가 함께 읽는다 `[코드 base.html:124, base_staff.html:83]`. 트랙 50의 "스태프 콘솔 제외"는 디자인 시스템 적용 범위 결정이라 이 트랙과 별개다.
- D2 링크 밑줄은 계속 항상 켠다. 근거 문장만 바꾼다: 라이트 링크/본문 대비 3.42:1은 3:1 하한에 여유가 작고, 색 하나로만 링크를 구분하지 않는다(원칙 3) `[문서 design-principles.md:217]`.
- D3 `static/css/tokens.css:3`의 `color-scheme: light`는 유지한다. OS가 다크여도 폼 컨트롤·스크롤바가 라이트로 그려진다. 스태프 `static/css/staff/base.css:14-16`의 `html { color-scheme: light dark; }`는 지운다(스태프 `tokens.css:8`의 `:root { color-scheme: light }`가 이미 이긴다 `[코드]`).
- D4 헤더는 테마 버튼 자리만 빠지고 나머지 DOM 순서(메뉴 → 로고 → 주 내비 → 계정)는 그대로다.
- D5 방문자 브라우저에 남은 localStorage `takulife-theme` 값은 지우는 코드를 넣지 않는다. 읽는 코드가 사라지므로 아무 효과가 없다.
- D6 날짜가 붙은 과거 검증 기록("라이트·다크 실측" 문장: `docs/FE/auth-editorial.md:192`, `account-settings-editorial.md:161`, `frontend-residual-sweep.md:18`, `event-typography-editorial.md:62,113`, `home-event-calendar.md:118-122`(2026-09-17 트랙 34 Evidence), `docs/BE/error-groups.md:223`, `docs/BE/i18n.md:591`, `docs/backlog.md` F13 행, `docs/pr-log.md`)은 당시 사실이라 고치지 않는다 `[코드 rg -i '다크|dark' docs]`. `event-typography-editorial.md:173`의 "theme.js 관례와 동일 패턴"도 당시 검증 공백 기록이라 그대로 둔다(다크 문장이 아님 — WED 사전 결함 3 정정). 현재 규칙을 말하는 문장만 고친다.
- D7 스태프 카테고리 편집 화면의 "라이트" 라벨(`edit.html:60`)은 짝이 사라지면 구분 기능이 없으므로 지운다(WED 사전 권고 1 채택). 구현 중 정정: 라벨을 비우면 카드가 soft 배경만 보여 ink 색을 볼 수 없어서, 같은 자리에 카테고리 이름(`{{ category.label }}`)을 ink 색으로 남기고 `.cat-palette-card-label` 규칙은 유지한다(오케스트레이터 2026-11-15, WED 사후 판정 대상).
- D8 모바일 열린 메뉴에서 주 내비가 DOM상 계정 영역보다 앞인데 화면에는 뒤에 그려지는 탭 순서 불일치(`site-chrome.css:99-104,112-115` `[코드]`)는 테마 버튼과 무관한 기존 결함이라 이 트랙에서 고치지 않는다(BIR 사전 결함 D2). 사후 측정에서 재현돼도 이 트랙의 회귀로 보지 않는다.

## 범위

포함:
1. 공개 셸: `base.html` 첫 페인트 테마 스크립트와 주석(:16-36) 및 `theme.js` 로드(:124) 삭제, `_site_header.html`·`500.html`의 테마 버튼과 `theme_toggle_label` 번역 변수 삭제, `static/js/shared/theme.js` 파일 삭제.
2. 스태프 셸: `base_staff.html` 주석·첫 페인트 스크립트(:17-39)와 `theme.js` 로드(:83) 삭제, `static/css/staff/tokens.css` 다크 블록(:44-79) 삭제, D3의 `html` 규칙 삭제, 카테고리 다크 견본 삭제(`templates/staff/categories/edit.html:62-64` 다크 카드, D7의 "라이트" 라벨 :60, `list.html:66` 다크 견본)와 그에 딸린 CSS(`static/css/staff/pages/categories.css`): `.cat-palette-preview`의 `grid-template-columns: 1fr 1fr`(:470)를 `1fr`로 바꾸고 같은 값이 된 모바일 덮어쓰기(:605-607)를 지운다 — 안 바꾸면 74.9375rem 초과 폭에서 카드가 절반만 차고 오른쪽이 빈다(WED 사전 결함 1) `[코드]`. `.cat-palette-card-label`(:483-486)은 D7 정정에 따라 유지. `.cat-swatch-pair`(:153, `inline-flex`)는 자식이 하나여도 레이아웃 영향이 없어 둔다 `[코드]`.
3. 공개 CSS: `tokens.css` 다크 블록(:164-284)과 반투명 크롬 주석의 다크 언급(:56-57), `base.css` `.site-message-info` 다크 규칙과 주석(:76-84), `components/cards.css`의 다크 규칙 3개와 각 주석(:103-108, :145-149, :228-231), `components/site-chrome.css` 테마 토글 절(:392 주석부터 `/* ── account menu` 직전까지) `[코드]`. 다크를 전제로 한 주석도 같은 유형이라 함께 고친다(QVL 사전 위험 2, 오케스트레이터 `rg -n -i '다크|dark'` 재확인 `[코드]`): `tokens.css:17-18`(강조 쌍 "다크에서 묻힌다"), `:35-36`(teal 라이트/다크 값), `:145-146`(시리즈 색 라이트/다크 명도), `pages/archive_calendar.css:484-489`(`.activity-page` 접두사 이유 = cards.css 다크 재정의 — 선택자는 그대로 두고 주석만), `components/toast.css:14-17`(다크모드 자동 반전), `components/search.css:31`(다크 5.74:1), `staff/pages/categories.css:467`(절 제목 "라이트·다크 두 칩"), `staff/tokens.css:5`(출처 "라이트/다크 팔레트").
4. 백엔드: `core/categories.py` PALETTE 12슬롯과 UNASSIGNED_PALETTE에서 `dark_soft`/`dark_ink` 키 삭제 `[코드 rg -c '"dark_soft"' = 13]`, `palette_hex_for` 독스트링(:204-205) "hex 4종"·"항상 4키를 보장한다" → 2종·2키, 팔레트 주석(:158-159) "라이트·다크 모두 WCAG AA" → 라이트만.
5. 테스트: `tests/core/test_category_token_contract.py:48-78`(슬롯 토큰이 정확히 1번, light 값과 일치, 독스트링 "[실측] 현재 48개 토큰"(:60) → 24개 `[계산 python3 -c "print(12*2)"]`), `tests/staff/test_staff_category_views.py:471-481`(키 집합 = `{light_soft, light_ink}`, 이름 `…hex_4개가_내려온다` → `…hex_2개가_내려온다`), `tests/core/test_ui_korean_literal_guard.py:131`(`shared/theme.js` 항목 삭제, `_EXPECTED_JS_FILE_COUNT` 26 → 25 `[코드 :152]`). :448·:464의 UNASSIGNED_PALETTE 비교는 객체 자체와 비교하므로 수정 불필요 `[코드 TDD 코치 확인]`.
6. 번역: `locale/{en,ja,zh_Hans}/LC_MESSAGES/django.po`의 msgid "다크모드 전환" 항목 삭제(djangojs.po에는 없음 `[실측 QVL rg]`). `.mo`는 커밋하지 않는다 `[문서 docs/BE/i18n.md:24]`. 같은 줄의 "언어당 메시지는 django 643건"은 삭제 뒤 `msgfmt --statistics`로 다시 세어 고친다 `[문서 i18n.md:24, 재측정 대상]`.
7. 문서: `docs/FE/design-principles.md` — 원칙 3 근거(:50), ⑤ 표의 "라이트·다크 쌍" 열(:112-125), "라이트·다크 쌍 규칙" 절(:129-136)을 라이트 전용 규칙으로, ⑩(a) 표의 다크 열(:203-224), ⑫에 2026-11-15 결정 추가, ⑬-7(다크 `:visited`) 해소 표시, ⑬-1(:363)은 "테마 버튼이 사라져 이 항목은 대상이 없다"로만 적고 모바일 열린 메뉴의 내비/계정 탭 순서 불일치(BIR 사전 결함 D2, 테마 버튼과 무관한 기존 결함 `[코드 site-chrome.css:99-104,112-115]`)가 해소됐다고 쓰지 않는다. ⑫ 2026-11-03 "라이트·다크 모두 무채색 바탕"(:350)은 이력이라 그대로 두고 새 결정이 대체함을 적는다. 줄별 처리표는 WED 사전 명세(아래 Frontend Review Evidence)를 따른다 — ③ 브랜드 레드 행(:66)의 다크 값 삭제와 `tokens.css` 인용 줄 번호 재측정, ⑩(a) 다크 열 삭제로 바뀌는 파생 숫자(:217 대비, :234 점 대비 조합 수)는 python으로 다시 세어 `[계산]`을 붙인다, :170 "다크 터미널"(레퍼런스 이름)은 유지. `docs/FE/home-event-calendar.md` G2 근거(:62-64 "다크모드가 깨진다")를 "토큰 밖 색이 생긴다"로. `docs/backlog.md`에 트랙 56 행.

제외: 토큰 재정립(트랙 B)·A4 화면 적용(트랙 D), D5·D6, `static/css/dist/`(빌드 산출물), 반투명 크롬·그림자 등 라이트 값 정리.

## AC

- AC1 OS 다크(DevTools emulate dark) + localStorage `takulife-theme=dark`인 상태에서 공개 홈·이벤트 목록·달력·상세·컬렉션·500과 스태프 홈·카테고리 목록·편집이 라이트 토큰으로 그려진다(`--bg` 계산값 = 라이트 값), `<html>`에 `data-theme` 속성이 없다.
- AC2 헤더에 테마 버튼이 없고 320·375·1440px에서 가로 넘침 0, 메뉴 토글·계정 메뉴 동작, 콘솔 오류 0, 탭 순서 = 건너뛰기 → 메뉴(모바일) → 로고 → 주 내비 → 계정.
- AC3 `rg -n 'data-theme|theme-toggle|theme\.js|takulife-theme|prefers-color-scheme|TakuTheme' templates static/js static/css core staff web tests --glob '!static/css/dist/**'` 0건, `rg -n 'dark_soft|dark_ink' --glob '*.py' --glob '*.html'` 0건, 보강판 `rg -n -i '다크|dark' static/css static/js templates core staff web --glob '!static/css/dist/**'` 0건(QVL 사전 지적 — 한글 "다크" 주석은 첫 패턴이 못 잡는다). 예외 한 줄: `tokens.css:145` 시리즈 색 주석이 기존 측정의 출처를 "당시 다크 포함"으로 밝히는 문장이라 남긴다 `[코드]`(새 숫자를 지어내지 않기 위해).
- AC4 팔레트 계약: tokens.css 슬롯 토큰이 각각 정확히 1번 정의되고 PALETTE light 값과 같다. 스태프 카테고리 뷰 `palette_hex` 키 = `{light_soft, light_ink}`.
- AC5 django.po 3개 `[코드 git ls-files locale]`에 "다크모드 전환" 0건, `uv run python manage.py compilemessages --ignore .venv` 성공.
- AC6 `uv run pytest -q -n auto` 통과, `uv run ruff check .`·`uv run ruff format --check .`·`uv run python manage.py check`·`makemigrations --check --dry-run` 통과, 헤더를 바꾸므로 e2e `uv run pytest -q -m e2e tests/e2e`도 실행.
- AC7 design-principles.md에 현재 규칙으로서의 다크 언급 0(결정 이력 문장과 :170 레퍼런스 이름 "다크 터미널" 제외), ⑫에 사용자 원문 인용, 파생 숫자는 `[계산]` 재태깅.
- AC8 스태프 카테고리 편집 화면이 1280·1440px에서 팔레트 미리보기가 한 열로 전체 폭을 채우고 빈 칸이 없다, 목록 화면 견본이 하나만 보인다(WED 사전 결함 1).
- AC9 `ko`·`en`·`ja`·`zh-hans` 언어로 공개 헤더를 한 번씩 렌더해 콘솔 오류 0, 테마 버튼 없음(QVL 사전 제안 `[코드 locale 언어 목록]`).

## 범위 추가 — 모바일 하단 고정 탭 바 (2026-11-15) [문서 사용자 지시]

사용자 지시: "모바일에서 메뉴는 하단으로 이동. 클릭하기 쉽도록. 그리고 pr을 올리고" → 질문 답변 "하단 고정 탭 바"(☰ 버튼 없이 4칸 항상 보임), "#418에 함께 넣기". D8(모바일 열린 메뉴 탭 순서 차이)은 ☰ 메뉴가 사라지면서 이 범위가 대신 다룬다.

기준선 `[코드 rg 2026-11-15]`: 모바일(≤45rem)은 `.nav-menu-toggle`(☰, `static/js/shared/nav_menu.js`)이 `#primary-nav`를 헤더 아래 둘째 줄로 펼친다(`site-chrome.css` 45rem 미디어 쿼리 `.site-nav{order:3}`·`[data-expanded="false"]{display:none}`). `.site-header`에 `backdrop-filter`가 있다 — `position: fixed` 자손의 기준 상자가 뷰포트가 아니라 헤더가 된다. 모바일에서 화면 아래에 고정되는 액션 바가 공개 페이지 CSS 11곳에 있다(`event_detail.css:381` `.mobile-cta`, `archive.css:1017`, `archive_collection.css:1330`, `archive_collection_detail.css:413`, `archive_collection_edit.css:379`, `archive_personal_create.css:398`, `archive_personal_edit.css:186`, `archive_personal_detail.css:422`, `archive_visit_create.css:400`, `archive_visit_edit.css:421`, `archive_visit_detail.css:466`), 대부분 `env(safe-area-inset-bottom)`을 쓴다. 내비 라벨 중 가장 긴 것은 ja "マイアクティビティ"다 `[코드 locale/ja/LC_MESSAGES/django.po:396-397]`.

포함(세부는 WED·BIR 사전 출력으로 확정, 위치는 위 기준선 `[코드]`):
8. 45rem 이하에서 `#primary-nav`를 화면 하단 고정 4칸 탭 바로 보이고 ☰ 버튼·`nav_menu.js`·관련 CSS를 없앤다(`templates/core/partials/_site_header.html`, `templates/500.html`, `templates/base.html` 스크립트 태그, `static/css/components/site-chrome.css`, `tests/core/test_ui_korean_literal_guard.py` 목록·개수). 본문·푸터가 탭 바에 가리지 않게 하단 여백, 기존 하단 고정 액션 바 11곳과의 배치(탭 바 위로 올리기 또는 해당 화면에서 탭 바 숨기기), 현재 쪽 표시에 `aria-current="page"`. 45rem 초과 데스크톱 헤더는 그대로.

추가 AC `[코드 기준선 높이는 위 착수 전 기준선 실측]`:
- AC10 320·375px에서 탭 바 4칸이 화면 하단에 고정되고 각 칸 높이 44px 이상, 스크롤해도 위치 유지, 가로 넘침 0, 마지막 본문·푸터가 탭 바에 가리지 않는다. ko·en·ja·zh-hans 라벨이 칸 밖으로 넘치지 않는다.
- AC11 하단 고정 액션 바가 있는 화면에서 액션 바와 탭 바가 겹치지 않는다(WED가 정한 방식대로).
- AC12 1440px 데스크톱 헤더는 기준선과 같다(높이 69px, 탭 순서 동일). 모바일 탭 순서와 현재 쪽 표시(`aria-current`)가 BIR 기준을 충족한다. `nav_menu.js` 참조 0건, `uv run pytest -q -n auto`·e2e 통과.

탭 바 사전 출력과 통합 결정(2026-11-15, 오케스트레이터가 file:line 재확인 `[코드]`):
- WED 사전 명세: `#primary-nav`는 헤더 DOM 자리 그대로 두고 ≤45rem에서만 `.site-header`의 `backdrop-filter`를 끄고 `position: fixed; bottom: 0` 4칸 균등 탭 바로 보인다(DOM 이동·두 번째 nav는 기각 — 데스크톱 탭 순서 보존, 랜드마크 중복 방지). 높이 변수 `--site-tabbar-h: calc(3.5rem + env(safe-area-inset-bottom))`(지정값, ≤45rem 블록에서만 정의, 나머지 폭은 `var(--site-tabbar-h, 0px)`가 0). 라벨은 아이콘 없이 텍스트, `white-space: nowrap`·`word-break: keep-all` 금지(ja "マイアクティビティ" 두 줄 허용), 현재 쪽 표시는 ≤45rem에서 칸 위쪽 줄. ☰(`.nav-menu-toggle`·`.nav-menu-icon`·`[data-expanded="false"]` 규칙, 마크업, `nav_menu.js`) 삭제. 하단 고정 액션 바 11곳은 화면별 분기 없이 전부 "탭 바 위로": 바의 `bottom: 0` → `bottom: var(--site-tabbar-h, 0px)`, 짝 wrapper `padding-bottom: Nrem` → `calc(Nrem + var(--site-tabbar-h, 0px))`(event_detail ≤60rem·archive ≤53.75rem도 같은 식으로 새 미디어 쿼리 없이). `body` ≤45rem `padding-bottom: var(--site-tabbar-h)`. 결함 1(`aria-current` 신규)·2(기준 상자 해법)·3(브레이크포인트 차이)·4(`--site-header-h` 소비 5곳 특정) 반영.
- BIR 사전 기준: (1) 탭 바 조상에 `backdrop-filter`·`transform`·`filter`가 계산값으로 없다 (2) 탭 바 `getBoundingClientRect().bottom` = `innerHeight`, 스크롤 전후 같음 (3) 칸 높이 ≥ 44px (4) 4개 언어 320px에서 칸마다 `scrollWidth <= clientWidth` (5) 액션 바 11곳 화면에서 탭 바와 사각형이 겹치지 않음, 액션 바 없는 화면은 푸터 마지막 줄과 겹치지 않음 (6) Tab으로 마지막 포커스 가능 요소까지 갔을 때 탭 바·액션 바에 가리지 않음(WCAG 2.2 SC 2.4.11) (7) 건너뛰기 다음 Tab 순서에서 주 내비 4개가 본문보다 먼저 (8) 현재 섹션 `<a>`에만 `aria-current="page"` (9) 토스트와 탭 바가 겹치지 않음 (10) 콘솔 0·`nav_menu` 참조 0 (11) 1440 헤더 69px·탭 순서 불변 (12) `tests/core/test_site_header_nav.py`(정확한 바이트 문자열 `class="active"` 비교 :21-26)를 갱신하고 회귀·e2e 통과 (13) iOS 실기기 안전 영역은 DevTools로 대체 불가 — Unverified.
- 통합 판단: ① 기준 상자는 WED 해법 채택(BIR 기준 (1)을 계산값으로 확인). ② WED의 "토스트 수정 불필요"는 기각 — `.site-header`가 `position: sticky; z-index: 50`이라 쌓임 맥락을 만들어 그 안의 탭 바는 페이지 수준 50으로 그려지고 토스트(40, `toast.css:10`)를 덮는다 `[코드 site-chrome.css:33-38]`. 토스트 `bottom`을 `calc(1rem + max(env(safe-area-inset-bottom), var(--site-tabbar-h, 0px)))`로 올린다(BIR (9)). ③ 포커스 가림 방지로 ≤45rem `html { scroll-padding-bottom: var(--site-tabbar-h) }` 추가(BIR (6)). ④ `aria-current="page"`는 `test_site_header_nav.py` 기대값을 먼저 바꿔 Red → 템플릿 수정 Green(TDD T4). ⑤ 라벨 글자 크기는 0.75rem(12px) — "클릭하기 쉽도록" 지시에 맞춰 WED 예시 11px보다 한 단계 크게, ja 두 줄이 칸 안에 드는지 실측. ⑥ `viewport-fit=cover`는 추가하지 않는다(기존 11곳과 같은 조건, iOS 실기기 확인은 Unverified로 보고). ⑦ BIR의 "nav를 헤더 밖으로" 대안은 ①로 대체.

탭 바 구현·검증 `[실측 2026-11-15, 커밋 83f424e8, DEBUG=false 새 번들, Chrome DevTools 터치 에뮬레이션, 로그인 사용자]`:
- T4 Red: `test_site_header_nav.py` 4건이 `aria-current="page"` 없는 바이트 문자열로 실패(기대한 이유) → 템플릿 수정 뒤 Green(영향 3파일 11 passed). 전체 `uv run pytest -q -n auto` 4483 passed / 50.87초, e2e 10 passed, ruff·check 통과.
- 320·375px, 11개 화면(`/`, `/events/`, `/events/53/`, `/collection/`, `/collection/242/`·`/edit/`·`/new/`, `/archive/`, `/archive/visits/18/`·`/edit/`, `/archive/visits/new/`): 탭 바 583~640px = innerHeight 640, 스크롤 뒤 같음, 조상 `backdrop-filter`·`transform`·`filter` 0, 칸 4개 모두 56px, 라벨 넘침 0, `aria-current`는 현재 섹션 하나, 토스트 526~568px로 탭 바 위, 가로 넘침 0. 액션 바 6개 화면에서 바 518~583px로 탭 바와 겹침 0, 마지막 포커스 가능 요소 가림 0, 끝까지 스크롤했을 때 푸터 마지막 링크 가림 0.
- 측정 중 고친 것: ① 탭 바 실제 높이 57px(칸 56 + 위 경계선 1)라 액션 바와 1px 겹침 → 변수에 1px 포함 ② 액션 바 화면에서 푸터 마지막 링크가 바 뒤에 남음(문서 끝에서 44~45px, 바 65px — 변경 전에도 같던 기존 결함, 같은 유형이라 이 트랙에서) → 11개 파일에 `body:has(바)` 하단 여백 ③ 탭 바 배경 `--chrome-glass-cta`(투명도 4%)로 뒤로 지나가는 큰 제목이 라벨 뒤에 비침(스크린샷) → `--surface` 불투명.
- 4개 언어 320px: ko·en·ja·zh-hans 칸 모두 80×56px, 넘침 0(ja "マイアクティビティ"·en "My activity" 포함). 1440px: 헤더 69px, 내비 `position: static`, `backdrop-filter` 유지 — 기준선과 같다.
- 탭 순서 375·1440 동일: 건너뛰기 → takulife → 홈 → 이벤트 → 컬렉션 → 내 활동 → 계정 메뉴 → 본문. 콘솔 오류·경고 0. 500 페이지(오프라인 렌더) 375px: 탭 바 683~740 = innerHeight 740, 칸 56px, 넘침 0.
- Unverified: iOS 실기기 안전 영역(`env(safe-area-inset-bottom)`, `viewport-fit=cover` 없음 — 기존 11곳과 같은 조건).
- 사후 판정(2026-11-15): WED **Conforms**(측정 중 고친 세 가지를 명세 목적에 맞는 보강으로 수용, 가드레일 문서 권고 → `docs/FE/mobile-tab-bar.md` 커밋 `0298efd5`). BIR **Conforms**, 공백 2건 — ① 액션 바 11곳 중 개인 기록 3화면과 조건부 `.mobile-cta`(이벤트 상세·내 활동)가 실측에 없었다 → 추가 실측 `[실측 Chrome DevTools 2026-11-15, 사용자 48, 320·375px, 900px 스크롤 뒤]`: `/archive/personal/new/`·`/archive/personal/194/`·`/edit/`·`/events/53/`·`/archive/`·`/archive/personal/` 모두 바 518~583px·탭 바 583~640px 겹침 0, 포커스 가림 0, 푸터 가림 0, 넘침 0 ② `.topbar-auth` z-index 주석이 옛 구조(내비 줄바꿈) 설명 → 정정. 권고(결함 아님): `scroll-padding-bottom`에 액션 바 높이까지 넣는 공유 변수 — 실측에서 가림 0이라 채택하지 않음.
- QVL 판정(2026-11-15): AC10·AC11 충족, Dual Review Gate 충족, 코드 결함 0. AC12는 HEAD 기준 재실행이 없어 미완료로 판정 → 오케스트레이터가 HEAD `465e8fdf`(직전 커밋 = `site-chrome.css` 주석 2줄 `[실측 git show --stat]`)에서 재실행 `[실측 2026-11-15]`: `uv run pytest -q -n auto` 4483 passed / 45.89초, `uv run pytest -q -m e2e tests/e2e` 10 passed / 10.47초, ruff check 통과·format 465개 파일 변경 없음, `manage.py check` 이슈 0, makemigrations 변경 없음 → 탭 바 범위 완료. 남은 Unverified = iOS 실기기 안전 영역(사용자 보고).

## Activated Roles

- Web Experience Designer: 헤더 배치·스태프 카테고리 견본·디자인 문서 개정 명세.
- Browser Interaction Reviewer: 첫 페인트, OS 다크·남은 localStorage 상호작용, 헤더 탭 순서·포커스, bfcache.
- Frontend Implementation Engineer: 템플릿·CSS·JS·FE 문서 편집.
- Backend TDD Coach: 팔레트 계약 테스트 3개 `[코드 범위 5]`의 Red-Green 순서.
- Backend & Integration Engineer: `core/categories.py`·테스트·`.po`·backlog 편집.
- Quality Verification Lead: AC ↔ 증거 대응, 완료 판정.

Not Activated:
- Product Scope Owner: 범위는 사용자가 "전면 삭제"·"적용"으로 정했다. 남은 선택은 D1~D8 기본값으로 계획서 승인 때 확인한다.
- Domain Architecture Reviewer: 의존 방향 변화 없음(core PALETTE를 staff가 읽는 기존 방향 그대로, 키만 줄어듦).
- Security & Resilience Reviewer: 신뢰 경계 변화 없음. localStorage 읽기가 사라질 뿐이다.
- Deployment & Operations Reviewer: 환경 변수·마이그레이션·기동 절차 변화 없음(`entrypoint.sh`의 번들 단계 그대로).
- AI Automation Architect: 해당 없음.

## Frontend Review Evidence

- 깊이: High — 모든 페이지의 헤더·첫 페인트·스태프 셸을 함께 바꾸는 사이트 전역 패턴 변경.
- WED 사전 명세(2026-11-15, 오케스트레이터가 file:line 재확인 `[코드]`): 헤더는 마크업만 지우면 된다 — `.site-header-inner`는 flex + gap이고 `.theme-toggle`에는 order·auto-margin이 없으며, 배치 규칙은 `.topbar-auth{margin-left:auto}`(site-chrome.css:99-104)와 45rem 이하 `.site-nav{order:3}`(:106-115)뿐이라 빈칸이 안 생긴다. 스태프 편집 화면은 그리드 1열화 필요(범위 2). 문서 줄별 처리: :50·:136 새 근거 문장(D2), :66 다크 값 절 삭제 + `tokens.css` 인용 재측정, :112 표 열 삭제, :129 절 제목 "색 토큰 규칙", :131·:133 규칙 삭제, :132 "두 토큰 블록" → "토큰 블록", :170 유지, :203-224 다크 값·대비 삭제와 파생 숫자 재계산, :350 이력 유지 + ⑫ 2026-11-15 항목에 대체 관계 명시, ⑬-1·⑬-7 해소 표시(⑬-1은 범위 7의 제한 문구대로). 결함 1(그리드)·2(D6 목록)·3(:173 분류)·4(파생 숫자) 전부 v2에 반영.
- BIR 사전 기준(2026-11-15): 삭제 대상 밖에서 `TakuTheme`·`data-theme`·토글 DOM 위치에 기대는 JS·템플릿·e2e 0건 `[코드 rg]`, 오류 큐 스크립트와 테마 스크립트는 상태 공유 없음. 측정 기준: (1) emulate dark + `localStorage.setItem('takulife-theme','dark')` 후 하드 리로드, (2) `--bg` 계산값이 공개 `#f5f6f8`·스태프 `--c-bg` `#eef0f4`, (3) `data-theme` 속성 null, (4) `<html>` 계산 `color-scheme` = light, (5) Network에 `theme.js` 요청 자체가 없음(404면 태그 삭제 누락), (6) 콘솔 0, (7) Tab 순회 순서 기록(320·375는 메뉴 연 상태도, D8은 참고 기록), (8) `.site-header` 높이를 **구현 전에 먼저** 재고 구현 뒤와 비교 — `--site-header-h`(site-chrome.css:30, 고정값)에 기대는 sticky 오프셋이 있다, (9) bfcache 뒤로가기 뒤 콘솔 0·`data-theme` 없음, (10) 번들 `shell.css`가 새로 만들어진 것인지 확인. 결함 D1(⑬-1 서술)은 범위 7에, D2는 D8로 반영.
- 계획한 브라우저 증거: AC1·AC2·AC8·AC9와 BIR 기준 (1)~(10)(Chrome DevTools, `DEBUG=false` + `collectstatic` + `bundle_shell_css`로 운영과 같은 번들).
- 착수 전 기준선 `[실측 Chrome DevTools 2026-11-15, main 22b51350, DEBUG=false + bundle_shell_css + collectstatic, 로그인 슈퍼유저, srcdoc iframe 폭별]`: 공개 `.site-header` 높이 320·375px = 65px, 1440px = 69px(`--site-header-h` 4.3125rem과 같음), `/`·`/events/`·`/events/calendar/`·`/collection/` 동일, 가로 넘침 0, 테마 버튼 1개. 스태프 `/staff/`·`/staff/categories/`는 `.site-header`가 없다. OS 다크에서 `data-theme="dark"`.
- Red `[실측 uv run pytest 2026-11-15, 2 failed]`: T1 `AssertionError: [('cat-slot-0-soft', ['#f3e8ff', '#342442'], '#f3e8ff'), …]`(슬롯 속성이 라이트·다크 두 번 정의 — 기대한 이유), T2 `Extra items in the left set: 'dark_ink' 'dark_soft'`(기대한 이유). 두 테스트를 함께 Red로 만든 뒤 함께 Green으로 만들었다 — 코치 계약의 한 번에 하나 원칙에서 벗어난 묶음이며 각 Red 이유는 따로 기록했다.
- ⑩(a) :234 "점 대비 14조합"은 라이트 점 7색 × 바탕·표면 2면이다 `[계산 python 2026-11-15: 최저 3.77:1]` — WED 사전 명세의 "7조합으로 수정"은 틀린 주장이라 채택하지 않는다.
- Green·검증 `[실측 2026-11-15, 브랜치 refactor/remove-dark-mode]`: 영향 테스트 3파일 36 passed, T1 뮤테이션(`--cat-slot-0-soft` 중복 정의 → Red, 복원 → Green), `uv run pytest -q -n auto` 4483 passed / 51.14초, ruff check·format(465 files) 통과, `manage.py check` 0 issues, makemigrations 변경 없음, e2e 10 passed / 12.49초, `compilemessages --ignore .venv` 성공·언어당 django 642·djangojs 69(msgfmt). AC3 rg 세 패턴 0건(예외 `tokens.css:145` 한 줄).
- 브라우저 `[실측 Chrome DevTools 2026-11-15, DEBUG=false 새 번들(shell.css의 data-theme 0건), emulate dark + localStorage takulife-theme=dark, 로그인 슈퍼유저]`: AC1 공개 `/`·`/events/`·`/events/calendar/`·`/events/53/`·`/collection/`과 스태프 `/staff/`·`/staff/categories/`·`/staff/categories/37/edit/` × 320·375·1440px 전부 `--bg` 라이트(공개 #f5f6f8, 스태프 #eef0f4), `color-scheme` light, `data-theme` null, theme 리소스 요청 0, 가로 넘침 0. 공개 헤더 높이 320·375 = 65px·1440 = 69px로 기준선과 같다. AC2 1440 탭 순서 = 건너뛰기 → takulife → 홈/이벤트/컬렉션/내 활동 → 계정 메뉴, 로고와 내비 사이 18px(gap). 320 터치 닫힘 = 건너뛰기 → 주 메뉴 → takulife → 계정 메뉴, 열림 = 내비가 둘째 줄 288×44px·aria-expanded true·넘침 0, 계정 패널 128~304px, 콘솔 오류·경고 0. 뒤로가기 뒤 `data-theme` null·라이트(DevTools 자동화에서는 bfcache가 붙지 않아 navigation type = navigate, bfcache 복원 자체는 미관측). AC8 편집 화면 1280·1440에서 미리보기 290px 폭을 카드 290×48px 하나가 채움(soft 배경 + ink 글자 "팝업스토어"), 목록 견본 쌍 7개 모두 견본 1개·다크 견본 0. 375에서는 기존 "데스크톱에서 열어주세요" 게이트로 레일이 0×0(이 트랙과 무관). AC9 ko·en·ja·zh-hans 헤더 렌더 200, 내비 번역 정상, 테마 버튼 0, 높이 69px, 넘침 0. 500 페이지(템플릿 오프라인 렌더 + 로컬 정적 파일) 320px 라이트·`data-theme` null·버튼 0·넘침 0·헤더 54px(기준선 없음 — 옛 버튼은 이 폭에서 32px로 로고 33px보다 낮았다 `[코드 옛 site-chrome.css]`).
- WED 사후 판정(2026-11-15): **Conforms** — 헤더·스태프 견본·문서 줄별 처리 전부 사전 명세와 일치, D7 정정(카테고리 이름을 ink 색으로)과 ⑩(a) "14조합" 유지는 목적에 맞는 수정으로 수용. 대비 수치 재계산은 도구가 없어 Unverified(오케스트레이터 python 재계산으로 보완 `[계산 2026-11-15]`).
- BIR 사후 판정(2026-11-15): **Conforms**, Low 결함 2건 — ① 편집 화면 팔레트 미리보기가 `aria-hidden` 없이 카테고리 이름을 다시 읽힘(목록 견본은 숨김), ② 지운 테마 스크립트를 순서 근거로 드는 주석(`base.html:5`, `base_staff.html:6`, `docs/BE/error-groups.md:152`). 함께 지적한 기존 부정확(`error-groups.md` "error_report.js가 defer 목록 첫 번째", 옛 줄 번호)도 같은 문단이라 고쳤다. 커밋 `2eab597d`, 수정 뒤 4483 passed·e2e 10 passed `[실측]`. Unverified(저위험): 500 페이지 헤더 높이 전후 비교(기준선 없음), 실제 bfcache 복원(테마 복원 경로 자체가 삭제됨 `[코드]`).
- QVL 완료 판정(2026-11-15): 코드·문서 재확인 결함 0(AC3·AC4·AC7·AC8 직접 재현, 슬롯 24값 1:1 대조), 자기 기록 이탈 2건(T1·T2 묶음 Red→Green, palette 커밋이 i18n 뒤)은 완료를 막지 않음, 완료 조건 = 오케스트레이터의 HEAD 기준 신선 재실행. 충족 `[실측 2026-11-15, HEAD 2eab597d]`: `uv run pytest -q -n auto` 4483 passed / 53.97초, e2e 10 passed / 11.23초, ruff check·format(465 files) 통과, `manage.py check` 0 issues, makemigrations 변경 없음, compilemessages 성공·언어당 django 642. → **완료**. 잔여 저위험 Unverified: 500 페이지 헤더 높이 전후 비교, 실제 bfcache 복원.

## TDD 체크포인트 (백엔드, 코치 사전 출력으로 확정)

- T1 `test_tokens_css의_팔레트_슬롯_hex_값은_PALETTE와_전부_일치한다`(이름 유지, contract): 판정을 `len(values)==2 and set==={light,dark}` → `len(values)==1 and values[0]==light`로 바꾸고 독스트링 숫자 고침 → Red 이유는 "슬롯 속성이 2번 정의됨"이어야 한다(ImportError·다른 계약 테스트 동반 실패면 설정 오류) → `tokens.css` 다크 블록 삭제 → Green. 뮤테이션: Green 뒤 `--cat-slot-0-soft`를 한 번 더 정의하면 Red, 되돌리면 Green `[문서 TDD 코치 사전 출력]`.
- T2 `test_배정된_슬롯이_있는_카테고리는_컨텍스트에_hex_2개가_내려온다`(개명, web): 키 집합을 light 두 키로 → Red 이유는 "실제 dict에 dark_soft/dark_ink가 남아 있음" → PALETTE·UNASSIGNED_PALETTE 다크 키 삭제 → Green. 템플릿이 없는 키를 찍어도 Django는 빈 문자열로 조용히 넘어가 테스트가 못 잡으므로(`style="background:;…"`) 스태프 견본 템플릿·CSS 삭제를 같은 커밋에 묶는다 `[문서 TDD 코치 사전 출력]`.
- T3 `test_ui_korean_literal_guard`: `theme.js` 삭제와 같은 커밋에서 목록·개수를 고친다. 행동 Red는 없다 — 파일만 먼저 지우면 FileNotFoundError가 나는데 이는 정당한 Red가 아니다.
- 새 백엔드 테스트는 만들지 않는다. 헤더 버튼·견본 삭제는 Frontend Work Policy의 마크업 재배치라 자동 테스트 금지이고, "다크 키가 없다"는 규칙은 T1·T2가 두 경계에서 이미 증명한다 `[문서 AGENTS.md:976-977, TDD 코치 사전 출력]`.

## Domain Boundary / Coupling / Pythonic

`core/categories.py`는 공유 커널이고 소비처는 `staff/views/categories.py`(`palette_hex_for`)와 `tokens.css`(계약 테스트)다 `[코드 rg palette_hex]`. 키를 줄이는 것뿐이라 새 결합이 없다. 파이썬 구조 변화 없음.

## 커밋 순서 (브랜치 `refactor/remove-dark-mode`, PR 1개)

1. T1 Red → Green(공개 `tokens.css` 다크 블록).
2. T2 Red → Green(PALETTE + 스태프 카테고리 견본·CSS).
3. 공개 셸: `theme.js` 삭제 + `base.html`·`_site_header.html`·`500.html` + `site-chrome.css` 토글 절 + T3.
4. 스태프 셸: `base_staff.html` + 스태프 `tokens.css`·`base.css`.
5. 컴포넌트 다크 규칙과 다크 전제 주석: `base.css`·`cards.css` + 범위 3의 주석 목록 + `core/categories.py` 주석(:158-159).
6. 번역 `.po` 3개 `[코드 범위 6]`.
7. 문서: design-principles.md·home-event-calendar.md·i18n.md:24·backlog.md.

중간 커밋(1~4)에서는 다크 토큰이 먼저 사라지고 토글·컴포넌트 다크 규칙이 잠시 남아 화면이 어긋날 수 있다. 커밋마다 pytest는 통과하고, 배포는 PR 전체 머지로만 일어나므로 받아들인다.

## 검증

착수 전: BIR 기준 (8) 헤더 높이 기준선 측정. 착수 뒤: AC3 rg 세 패턴 → T1·T2 Red/Green 출력과 T1 뮤테이션 → `uv run pytest -q -n auto` → ruff 두 검사·check·makemigrations → e2e → `compilemessages --ignore .venv`·`msgfmt --statistics` → 브라우저 AC1·AC2·AC8·AC9·BIR (1)~(10) → WED·BIR 사후 판정 → QVL.

## 이연

없음. 같은 유형 잔여(다크를 전제로 한 주석·문서 문장)는 발견 즉시 이 트랙에서 고친다.
