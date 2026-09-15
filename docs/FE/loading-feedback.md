# 요청 중 피드백 (클릭 방지 + 스피너)

서버 요청을 일으키는 컨트롤은 **누른 즉시 비활성화되고 스피너를 보여야
한다.** 사이트 전역 계약이며, 소비자와 스태프 콘솔 양쪽에 같은 방식으로
적용된다.

## 두 갈래 경로

| 경로 | 거는 주체 | 대상 |
|---|---|---|
| 일반 POST 폼 | `static/js/shared/submit_guard.js` | `data-submit-guard`를 단 `<form>` |
| JS 주도(fetch) | `TakuAPI.setLoading(button, true/false)` | 호출부가 넘긴 버튼 |

둘 다 결과는 같다 — 버튼에 `disabled`와 `.is-loading`이 붙는다.

⚠️ **클래스 이름은 `.is-loading`으로 고정이다.** `api.js`의 전역 `pageshow`
핸들러가 이 이름을 보고 bfcache 복원 시 버튼을 되살린다. 다른 이름을 쓰면
뒤로가기 후 버튼이 영영 비활성으로 남는다.

## 가드는 옵트인이고, 스크립트는 양쪽 셸에 있다

`submit_guard.js`는 `templates/base.html`과 `templates/staff/base_staff.html`
양쪽에서 로드된다. 폼은 `data-submit-guard` 속성으로 옵트인한다 — 전역
`form` 선택자를 쓰지 않는 이유는 새 폼이 추가될 때 조용히 가드에 걸리는 일을
막기 위해서다.

> 이력: 이 스크립트는 원래 `staff_submit_guard.js`로 스태프 셸에만 있었고,
> 소비자 쪽은 계정 화면 4곳이 페이지마다 `<script>`를 직접 붙여 쓰고 있었다.
> 그래서 회원가입·로그인·비밀번호 재설정·소셜 로그인·**로그아웃**(인증된 모든
> 페이지 헤더) 폼은 아무 보호가 없었다 `[실측 2026-09-13: POST 폼 34개 중 12개
> 무방비]`. 개명 후 양쪽 셸에 올리고 34/34로 맞췄다.

**새 POST 폼을 만들면 `data-submit-guard`를 달아라.** 안 달면 가드가 없다.

`required` 검증에 걸리면 `submit` 이벤트 자체가 발생하지 않아 버튼이 잠기지
않는다 — 가드가 막는 게 아니라 제출이 일어나지 않은 것이라 정상이다.

## 스피너는 버튼 폭을 바꾸면 안 된다

```css
button.is-loading, a.is-loading { font-size: 0; }
button.is-loading::after {
  position: absolute; top: 50%; left: 50%;
  width: 0.85rem; height: 0.85rem; margin: -0.425rem 0 0 -0.425rem;
  border: 2px solid currentColor; border-top-color: transparent;
}
```

세 가지가 모두 의도적이다.

**1. 라벨을 `font-size: 0`으로 접는다(`color: transparent`가 아니다).**
`color`를 건드리면 `currentColor`까지 투명해져 스피너가 사라진다. 그러면
버튼 계열마다 색을 따로 지정해야 하는데, 그 목록은 조합 클래스에서 곧바로
어긋난다 — `.staff-cta-accent`는 `.staff-cta`와 함께 쓰여 흰 글자 파란
버튼에 검은 스피너가 나왔다 `[실측]`. 그래서 스피너 크기는 `em`이 아니라
`rem`으로 잡는다(font-size가 0이므로).

**2. 색은 `currentColor`다.** 버튼 8계열의 배경·글자색을 재보니 **정답 색은
언제나 그 버튼의 글자색**이었다 — 파란 배경엔 흰색, 흰 배경엔 검정, 외곽선
위험 버튼엔 빨강 `[실측 2026-09-13]`. 열거하지 마라.

**3. `::after`를 절대 위치로 겹친다.** 텍스트 뒤에 이어붙이면 버튼이 커진다.
실측으로 컬렉션·방문·장소 저장 버튼이 제출 순간 100px → 122px로 커지며
형제를 22px 밀어냈다. 스태프 콘솔의 행 액션 버튼은 `table-layout: fixed`의
고정폭 셀 안이라 폭이 늘면 셀 경계에서 잘린다.

## ⚠️ 선택자를 `button`·`a`로 좁혀라

`.is-loading`은 버튼만이 아니라 **검색 결과 컨테이너**(`#archive-results`,
`archive_search.js`가 토글)에도 붙는다. 좁히지 않고 `font-size: 0`을 걸면
검색 결과 글자가 통째로 사라진다.

## 페이지별로 스피너를 다시 보정하지 마라

공용 규칙이 텍스트 버튼만 가정하던 시절, 아이콘 전용 버튼마다 같은 보정이
복제됐다 — `event_list.css`, `cards.css`, `archive_visit_edit.css`(2곳),
`archive_visit_detail.css`, `archive_collection_detail.css` **6곳**. `cards.css`
주석은 이것을 "이 저장소가 두 번 겪은 결함"이라고 적고 있었다.

공용 규칙이 원인을 고쳤으므로 6곳 모두 제거했다. **다시 넣지 마라.** 남겨
두면 그쪽의 `margin-left: 0`이 새 중앙 정렬을 덮어써 스피너가 가로로 반쯤
밀린다 `[실측]`.

제거 후 390px에서 아이콘 버튼 5종 전부 폭 불변·중앙 정렬·색 일치를
확인했다 `[실측 2026-09-13]`: `.event-compact-interest` 34→34,
`.visit-detail-delete-btn` 44→44, `.photo-preview-remove` 22→22,
`.visit-edit-delete-btn` 44→44, `.collection-detail-delete-btn` 44→44.

## 움직임 감소

`prefers-reduced-motion: reduce`에서 회전을 멈추고 정지된 링만 남긴다.
소비자 쪽 블록이 `hover-lift`와 `glint`만 끄고 스피너는 계속 돌게 두고
있었다 — 새로 스피너를 추가할 때 이 처리를 빠뜨리지 마라.

## 말줄임되는 셀에는 `title`을 달아라

`overflow: hidden` + `text-overflow: ellipsis`로 잘리는 값은 전체를 볼 방법이
없어진다. 관례는 `templates/staff/dashboard.html`의 `.dash-cell-target`처럼
표시 텍스트와 **같은 변수·필터**를 `title`에 그대로 쓰는 것이다.

`[실측 2026-09-13]` 소비자 20화면 × (390px, 1280px) + 스태프 10화면을
Playwright로 순회해 "ellipsis가 걸렸고 `scrollWidth > clientWidth`인데 `title`이
없는 요소"를 셌다: **84건 → 0건**. 같은 스윕에서 가로 오버플로는 전 화면·양쪽
폭에서 0건이었다.

잘리는 텍스트가 자손 링크 안에 전부 들어 있으면 그 링크에 달아도 된다 —
호버 대상이 결국 그 링크다.

**오탐 주의**: `sr-only` 라벨과 네이티브 파일 입력은 1×1px `clip`으로 숨겨져
있어 잘릴 화면 텍스트가 없다. 자동 검사가 잡더라도 결함이 아니다.

## 페이지 CSS는 자기 클래스를 스스로 정의한다

`templates/core/staff/home_categories.html`이 `events.css`에만 있는
`.events-save-cta`를 쓰고 있었는데 그 페이지는 `home_categories.css`만
로드한다. 그래서 "변경 저장" 버튼이 **브라우저 기본 회색 버튼**으로 렌더됐다
`[실측 배경 rgb(239,239,239)]`. 전 템플릿을 훑어 이런 곳이 더 있는지 확인했고
이 한 곳뿐이었다 `[실측 2026-09-13]`.
