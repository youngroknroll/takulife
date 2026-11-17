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

소비자: `static/css/objects/interaction.css`(`border-right-color`는 `:37`, 스피너 블록 `:29-41`, 겹침 규칙 `:69-79`),
스태프: `static/css/staff/base.css`(약 177-196, `border-top-color`).

```css
button.is-loading, a.is-loading {
  -webkit-text-fill-color: transparent;
  text-decoration-color: transparent;
}
button.is-loading > *, a.is-loading > * { visibility: hidden; }
button.is-loading::after {
  position: absolute; top: 50%; left: 50%;
  width: 0.85rem; height: 0.85rem; box-sizing: border-box;
  margin: -0.425rem 0 0 -0.425rem;
  border: 2px solid currentColor; border-right-color: transparent;
}
```

이 조각은 요약본이다. `border`·`border-right-color`는 실제로 `.is-loading::after`(`interaction.css:29-41`)에,
나머지는 `button.is-loading::after`(`:69-79`)에 있고 조각은 둘을 합쳤다. `box-sizing: border-box`가 없으면
테두리(2px×2)가 0.85rem 바깥에 더해져 스피너 상자 중심이 버튼 중심에서 2px 오른쪽·아래로 어긋난다
(스피너 상자 17.6px → 13.6px, 버튼 중심과의 차 2px → 0px `[실측 2026-11-17 Playwright, 1280px·390px, 컬렉션 등록·방문 목록 삭제·방문 수정·개인 기록 등록의 저장·삭제 버튼]`).

스태프 쪽 규칙(`static/css/staff/base.css:175`)은 아직 `font-size: 0`으로 라벨을 접는다.
아래 설명은 소비자 쪽 규칙을 기준으로 한다.

세 가지가 모두 의도적이다.

**1. 라벨은 글자 채움색만 투명하게 한다(`color: transparent`가 아니고 `font-size: 0`도 아니다).**
`color`를 건드리면 `currentColor`까지 투명해져 스피너가 사라진다. 그러면
버튼 계열마다 색을 따로 지정해야 하는데, 그 목록은 조합 클래스에서 곧바로
어긋난다 — `.staff-cta-accent`는 `.staff-cta`와 함께 쓰여 흰 글자 파란
버튼에 검은 스피너가 나왔다 `[실측]`. `-webkit-text-fill-color`는 글자 채움만
바꾸고 `color`는 그대로 두므로 `currentColor`가 살아 있다. 자식 요소(아이콘
`span` 등)는 `visibility: hidden`으로, 링크 밑줄은 `text-decoration-color`로
숨긴다. 예전의 `font-size: 0`은 버튼 폭이 줄었고(예: 탈퇴 버튼 63.7px → 36px
`[실측 2026-11-17 Playwright]`), 쪽 CSS가 글자 크기를 다시 정하면 글자가 남았다.
스피너 크기는 `em`이 아니라 `rem`으로 둔다.

**2. 색은 `currentColor`다.** 버튼 8계열의 배경·글자색을 재보니 **정답 색은
언제나 그 버튼의 글자색**이었다 — 파란 배경엔 흰색, 흰 배경엔 검정, 외곽선
위험 버튼엔 빨강 `[실측 2026-09-13]`. 열거하지 마라.
로딩 중 버튼 색은 쪽의 비활성 규칙을 따라 계열마다 `--ink-2`·`--off`·원래 색으로 다르다(트랙 59에서 확인, 통일하지 않음).

**3. `::after`를 절대 위치로 겹친다.** 텍스트 뒤에 이어붙이면 버튼이 커진다.
실측으로 컬렉션·방문·장소 저장 버튼이 제출 순간 100px → 122px로 커지며
형제를 22px 밀어냈다. 스태프 콘솔의 행 액션 버튼은 `table-layout: fixed`의
고정폭 셀 안이라 폭이 늘면 셀 경계에서 잘린다.

2026-11-17에 로딩 클래스를 붙이고 폭·높이·글자 크기·글자 채움색·스피너 애니메이션을
재서 확인했다: 27개 주소(비로그인 3개 포함) × 폭 2개(1280px, 390px)에서
변경 전(`font-size: 0` 방식)은 버튼 368개 중 340개가 어긋났고(대부분 글자 크기 0px 판정, 탈퇴 버튼 등은 폭도 줄었다),
변경 뒤(현재 규칙)는 392개 중 0개다: 폭·높이 변화 0건, 글자 크기 변화 0건, 채움색 불투명 0건,
`btn-spin` 아닌 스피너 0건 `[실측 2026-11-17 Playwright, 로그인 24쪽 + 비로그인 3쪽 × 1280px·390px — 뒤 측정은 로컬 확인용 행사 4건이 더해져 버튼 수가 늘었다]`. 🗑 삭제 버튼 2곳, `.status-btn.active`의 `✓ `(`::before`),
`.photo-preview-remove`의 `×`, ♥ 찜 버튼은 로딩 상태 스크린샷에서 글리프가 남지
않았다 `[실측 2026-11-17 Playwright]`.

## ⚠️ 선택자를 `button`·`a`로 좁혀라

`.is-loading`은 버튼만이 아니라 **검색 결과 컨테이너**(`#archive-results`,
`archive_search.js`가 토글)에도 붙는다. 좁히지 않고 글자 숨김을 걸면
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
확인했다 `[실측 2026-09-13]`(이력. 트랙 58에서 버튼 높이·누름 영역 규칙이 바뀌어 지금 폭은 다시 재지 않았다): `.event-compact-interest` 34→34,
`.visit-detail-delete-btn` 44→44, `.photo-preview-remove` 22→22,
`.visit-edit-delete-btn` 44→44, `.collection-detail-delete-btn` 44→44.

## 움직임 감소

`prefers-reduced-motion: reduce`에서 회전을 멈추고 정지된 링만 남긴다
`[코드 interaction.css:87-92]`. 이력: 예전에는 소비자 쪽 블록이 `hover-lift`와 `glint`만 끄고
스피너는 계속 돌게 두고 있었다. `hover-lift` CSS는 트랙 58에서 삭제됐고 `.glint`는
`interaction.css:17-21`에서 숨겨 둔다. 새로 스피너를 추가할 때 이 처리를 빠뜨리지 마라.

스피너는 `.is-loading::after`를 쓴다 `[코드 interaction.css:29-41]`. 그래서 작은 단추의 누름 영역을
넓히는 가상 요소는 `::before`를 쓴다 `[코드 archive_visit_edit.css:171, archive_visit_create.css:155]`.
`::after`에 누름 영역을 만들면 스피너가 덮어쓴다(트랙 58 BIR 판정).

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

## 기록 폼의 검증 실패 표시

대상은 JS로 제출하는 기록 폼이다: 컬렉션 등록·수정, 개인 기록 등록·수정, 방문 기록 등록·수정, 개인 기록의 공식 제보 폼 2곳, 그리고 컬렉션·개인 기록·방문 기록의 삭제 실패. 헬퍼는 `window.TakuFormFeedback`(`static/js/components/form_feedback.js`)이고 규칙은 다섯 가지다 `[코드 static/js/components/form_feedback.js]`.

1. 제출을 시작하면 이전 표시를 전부 해제한다(`clear`).
2. 위반 입력에는 `aria-invalid="true"`를 붙이고, 오류 상자 id를 `aria-describedby`에 추가한다(원래 있던 토큰은 보존). 위반이 여럿이면 문서 순서상 첫 입력으로 포커스를 옮긴다(`markInvalid`). 짝 컨트롤(교차 필드 오류에서 반대편 입력)을 세 번째 인자로 넘기면 그 컨트롤이 바뀔 때도 표시가 풀린다.
3. 입력의 값이 바뀌면(`input`·`change`) 그 입력의 표시만 해제한다.
4. 입력에 속하지 않는 오류(권한·서버·네트워크)와 삭제 실패는 오류 상자에 `tabindex="-1"`을 주고 포커스한다(`focusError`).
5. 서버 400 본문의 키가 입력 `name`과 같으면 그 입력을 표시한다(`showServerError`, 키 이름이 다르면 `aliases`로 잇는다).

지켜야 할 것:

- 헬퍼는 소비자 전용이다. 스태프와 공유하는 `static/js/shared/`에 두지 않는다.
- 새 폼은 페이지 JS 앞에 `form_feedback.js`를 `defer`로 로드하고, 페이지 JS는 `window.TakuFormFeedback &&`로 가드한다.
- 오류 문장 위치는 폼 아래 그대로다 `[문서 사용자 결정 2026-11-17 "지금 위치 유지"]`. 문구는 호출부의 것이고 헬퍼는 문장을 만들지 않는다.
- 부드러운 스크롤을 넣지 않는다(모션 예외 4곳 밖, `docs/FE/design-principles.md` ⑦).
- 새 JS 파일은 `tests/core/test_ui_korean_literal_guard.py`의 목록에 넣는다.

알려진 한계:

- 같은 문장을 연달아 낼 때 스크린리더가 다시 읽게 하는 보조는 없다.
- 실제 스크린리더 낭독은 확인하지 못했다.
- 모바일에서 위쪽 입력과 아래 오류 문장이 한 화면에 같이 들어오지 않을 수 있다.
