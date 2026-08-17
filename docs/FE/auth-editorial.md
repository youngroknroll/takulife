# 인증 화면 12개 (에디토리얼) — 기술 기록

기준일: 2026-07-31 · 브랜치 `design/auth-editorial`
대상: `templates/account/{login,signup,password_reset,password_reset_done,
password_reset_from_key,password_reset_from_key_done,verification_sent,lockout,
password_set}.html`, `templates/socialaccount/{login,signup,authentication_error}.html`,
`templates/core/partials/{_auth_field,_auth_form_errors}.html`,
`static/css/pages/auth.css`

이 문서는 **가드레일만** 담는다. 계획서는 `.docs/FE/auth-editorial.md`에 있고
git-ignored라 소실된다. 여기 적힌 것은 다음 작업자가 모르면 같은 실수를 반복할 것들이다.

## A1 ⚠️ 한국어 제목은 `word-break: keep-all` 없이는 조사가 고아가 된다

**현상**: 768px에서 좌패널 h2가 「덕질 라이프 / 를」로 끊겨 조사 "를"이 홀로 떨어졌다.
`[실측]` 브라우저 스크린샷으로만 드러났고, 마크업을 아무리 읽어도 보이지 않는다.

**원인 두 겹**:
1. `word-break: keep-all`이 `.auth-panel-domains li`에만 있고 h2에 없었다. CSS 기본
   `word-break: normal`은 한국어를 **글자 단위**로 끊는다.
2. 폼 패널이 `468px` 고정이라 화면이 좁아질 때 줄어드는 쪽은 **선언 패널**이다.
   태블릿 구간 글자 크기 조정이 없어 40px 글자가 285px 패널에 들어가지 못했다.

**가드레일**: 이 저장소의 한국어 제목·문장 블록에는 `word-break: keep-all`을 건다.
그리고 **고정폭 열이 있는 그리드에서는 유동 열이 얼마나 좁아지는지 실측**하라 —
`grid-template-columns: 1fr 468px`은 좁은 화면에서 1fr 쪽을 무자비하게 압축한다.

`[실측]` 수정 후 Range API로 시각적 줄을 측정: 753px/28px과 1025px/40px 양쪽 모두
`["그대들의", "덕질 라이프를", "위하여"]`. 브레이크포인트는 `--page-pad-x`가 이미 쓰는
`64rem`을 재사용했고 새 브레이크포인트를 만들지 않았다.

## A2 ⚠️ aria 속성은 누락된 적이 없다 — **참조가 끊겨 있었다**

`[실측 2026-07-31, Django 5.2.14]` 착수 시점의 진단이 틀렸다. 계획서·검토자 산출물·
직전 트랙 기록이 모두 「`_auth_field.html`에 `aria-describedby`/`aria-invalid`가
없다」고 적었으나, **Django 5.2의 `BoundField`가 이미 자동으로 붙이고 있었다.**

변경 전 `{{ field }}`가 실제로 낸 것(오류 상태):

```html
<input ... required aria-invalid="true" aria-describedby="id_password2_error" id="id_password2">
<ul class="field-error" id="id_password2-error">...</ul>
```

`aria-describedby`는 `id_password2_error`(밑줄)를 가리키는데 템플릿이 만든 것은
`id_password2-error`(하이픈)다. **참조 대상이 문서에 존재하지 않았다.**
누락보다 나쁘다 — 마크업은 올바르게 보이는데 스크린리더가 따라가면 아무것도 없다.

같은 문제가 **정상 상태에도** 있었다. `password1`에는 help_text(비밀번호 규칙 4줄)가
있어 `{{ field }}`가 `aria-describedby="id_password1_helptext"`를 냈는데, 파셜은
help_text 행을 렌더하지 않는다 → 또 하나의 끊긴 참조.

**그래서 수동 렌더가 옳다.** Django가 못 해서가 아니라, 우리가 **Django와 다른 id로
자체 오류 요소를 렌더하기 때문**이다. `[실측]` 수정 후: 정상 필드는 참조 자체가 없고
오류 필드의 참조는 유효하다(dangling 0건).

⚠️ `{{ field }}`로 되돌리려면 **Django의 id 형식(`id_x_error`)을 맞추고 help_text도
렌더**해야 한다. 하나만 하면 끊긴 참조가 되살아난다.

### 그때 `widget.attrs`가 조용히 사라진다

수동 렌더로 바꾸면 **allauth가 이미 넣어둔 속성을 verbatim echo하지 않는 한 전부
날아간다.**

`[실측]` allauth가 5개 폼 10개 필드에 넣어둔 것:

| 필드 | placeholder | autocomplete | maxlength |
|---|---|---|---|
| login / email | 이메일 주소 | email | 320 |
| password | 비밀번호 | current-password | — |
| password1 | 비밀번호 / 새 비밀번호 | new-password | — |
| password2 | 비밀번호 (확인) / 새 비밀번호 (확인) | new-password | — |

`_account_settings_field.html:25`의 attrs 루프를 그대로 쓴다. 비밀번호 필드는
`value`를 되돌려 쓰지 않는다(Django `PasswordInput`의 `render_value=False`와 같은 이유).

⚠️ 착수 전 조사가 "플레이스홀더가 존재하지 않는다"고 잘못 판단했다. **위젯을 실제로
덤프해서 확인하라** — allauth 폼 소스를 읽는 것만으로는 틀린다.

### 수동 렌더가 재현하지 못하는 것: `disabled`

`[실측]` `disabled=True` 필드를 두 방식으로 렌더한 결과 — `{{ field }}`는
`disabled`를 내보내고 **수동 렌더는 빠뜨린다**. `widget.attrs` 루프에 없기 때문이다.

현재 인증 폼에 `disabled` 필드는 없어 발현되지 않는다. 하지만 생기면 **입력은
편집 가능한데 Django는 제출값을 무시하고 `initial`을 쓰는** 조용한 불일치가 된다.
그런 필드를 추가하려면 파셜에 `{% if field.field.disabled %}disabled{% endif %}`를
먼저 넣어라.

### 남은 갭: 비밀번호 규칙이 사용자에게 보이지 않는다 (3화면)

`[실측]` help_text를 **바운드 인스턴스에서** 재면 4개 폼에 있다. 그중 실제 비밀번호
규칙(「최소 8자 이상」 등 4줄)은 **signup · password_reset_from_key · password_set
3화면**이다. `login`의 것은 「비밀번호를 잊으셨나요?」 링크라 우리가 이미 별도 링크
행으로 제공하므로 렌더하지 않는 것이 맞다.

어느 화면도 규칙을 렌더하지 않는다. 변경 전에는 끊긴 `aria-describedby`로 남아
있었고 지금은 그냥 없다 — 회귀는 아니지만 **사용자가 제출 전에 비밀번호 요건을 알 수
없다.** 별도 트랙에서 다룰 것.

⚠️ **`base_fields`로 세지 마라.** 클래스 레벨은 2건만 보이고 allauth가 인스턴스
생성 시점에 붙이는 2건을 놓친다. 이 문서도 처음에 그렇게 틀렸다.

## A3 `--accent`는 이 저장소에 없다 (시안이 쓴 세 번째 없는 토큰)

`[실측]` `rg "var\(--accent" static/ templates/` → **0건**. 시안은 보드 안에서 자체
정의했을 뿐이다. 직전 트랙 기록(`account-settings-editorial.md` G4)은 `--border-strong`과
bare `--mint` 2종만 잡아뒀다.

이 저장소의 3색 팔레트는 **brand / rose / mint**뿐이다. 시안의 `--accent`(「내 활동」
tick)는 `--mint-ink`로 간다.

## A4 G1(제출 가드가 버튼 `name`을 먹는 결함)은 이 12화면에서 성립하지 않는다

직전 트랙에서 이메일 폼 3개를 조용히 죽인 사슬이다. **성립 조건이 두 개**인데
여기서는 둘 다 없다:

1. `[코드]` allauth `LoginView.form_valid`/`SignupView`/`PasswordResetView`/
   `PasswordResetFromKeyView`는 전부 `form.is_valid()`로만 분기한다. 버튼 `name`으로
   분기하는 것은 `EmailView`(범위 밖) 하나뿐이다.
2. 이 12화면의 제출 버튼에는 `name` 속성이 없다.

**가드레일**: 이 폼들의 제출 버튼에 **`name`을 붙이지 마라.** 두 개의 제출 동작을
구분해야 하면 `<input type="hidden">`으로 보낸다(`email_change.html` 선례).

`[실측]` 실제 브라우저에서 로그인·회원가입 폼을 버튼 클릭으로 제출해 서버 오류가
렌더되는 것을 확인했다. 조용한 302 무동작 없음.

## A5 `_auth_field.html` 사용처는 5개 템플릿 / 10개 include 사이트

```
rg -n '\{%\s*include\s*"core/partials/_auth_field\.html"' templates/
```

`[실측]` login 2 · signup 3 · password_reset 1 · password_reset_from_key 2 ·
password_set 2 = **10 사이트 / 5 템플릿**.

⚠️ 직전 트랙 문서 2곳이 **「12개」**라고 적었다. 12는 `auth.css`를 로드하는 템플릿
수이며 **단위가 뒤바뀐 것**이다. 이번 트랙에서 두 곳을 정정했다
(`docs/FE/account-settings-editorial.md`, `_account_settings_field.html` 주석).

## A6 오류는 rose, 정체성은 brand — 시안의 blanket 브랜드-레드를 쓰지 않는다

직전 트랙(PR #264)에서 사용자가 확정한 G4를 승계한다. `.auth-error-banner`는
`account_settings.css`의 `.account-settings-error-banner`와 같은 레시피
(`--rose-border` 테두리 + `--rose-soft` 배경 + `--rose-ink` 글자)다. 시안의 위아래
테두리만 있는 밴드와 `✦` 마커는 채택하지 않았다 — 계정 영역 오류 문법을 하나로 유지한다.

⚠️ **`login.html`의 고정 오류 문구를 보존하라.** allauth 원문 대신 「이메일 또는
비밀번호가 올바르지 않습니다.」를 쓰는 것은 **어느 쪽이 틀렸는지 알려주지 않기 위한
결정**이다. 디자인 작업이 뒤집을 사안이 아니다.

## A7 kicker에 URL을 넣지 않는다

시안은 `/accounts/login/` 같은 라우트를 kicker로 그렸으나 그것은 **디자인 문서용
라벨**이다. 12화면 전부 상수 `"계정"`을 쓴다. 직전 트랙 선례와 같다
(`_account_settings_panel_head.html` 6개 호출부가 전부 `kicker="계정 설정"`).

## A8 좌패널은 미인증 화면에만

인증 상태로 열리는 화면(`password_set`은 `@login_required`, `password_reset`의
`user.is_authenticated` 분기)에 「그대들의 덕질 라이프를 위하여」를 띄우는 것은 맥락
이탈이다. 그 2화면은 `.auth-shell.is-standalone`(단일 열 + 중앙 정렬)로 간다.

모바일(`≤45rem`)에서는 좌패널을 `display:none`으로 **완전 제거**한다.
⚠️ `order`/`grid-column` 재배치를 쓰지 마라 — DOM이 이미 좌→우 순서라 첫 블록을
숨기면 두 번째가 구조·시각 모두 첫 번째가 된다. 이 저장소는 모바일 `order` 역전으로
탭 순서를 깨뜨린 전례가 있다(WCAG 1.3.2).

## A9 장식 글리프는 패널의 `overflow:hidden`에 의존한다

좌패널 우하단 `✦`는 `position:absolute`에 11.875rem(190px)이라 **패널 경계를 넘는다**.
`[실측]` 753px에서 글리프 우변 302px vs 패널 우변 285px — 17px 초과.
`.auth-panel-declare { overflow: hidden }`가 잘라내므로 페이지 가로 스크롤은 0px다.

**그 `overflow:hidden`을 제거하지 마라.** 제거하면 태블릿 구간에서 가로 스크롤이 생긴다.

## A10 시안 대비 의도적 차이 (px → rem 변환의 결과)

입력 padding 14px(시안 13px) · 링크 라벨 14px(13.5px) · 힌트 12.5px(12px).
저장소 CSS 단위 규약(`rem` 기준, px는 border·shadow·radius만)이 시안의 raw px 리터럴과
정확히 일치할 수 없어서 생긴다. **결함이 아니라 규약 우선 적용이다.**

규칙선·체크박스 테두리의 `1.5px`는 **2px**로 올렸다 — 소수점 px는 계산값 단계에서
1px로 내려가 평범한 구분선과 구별되지 않는다(PR #244 실측).

## A11 검증 한계 (다음 작업자가 알아야 할 것)

`[실측 2026-07-31]` 브라우저로 확인한 것: 로그인·회원가입·재설정·재설정 발송 화면,
오류 상태 2종, 320/768/1040/1280 뷰포트, 라이트·다크.

**확인하지 못한 것**:
- `password_set`, `password_reset` 인증 분기 — standalone 카드 2화면. 브라우저 도달에
  각각 사용 불가 비밀번호 계정 / 로그인 상태가 필요하다
- `password_reset_from_key`의 비밀번호 2필드 — 서명된 재설정 키 필요
- socialaccount 3화면 — Google `client_id` 미설정으로 도달 불가. **OAuth를 켜는
  작업자는 이 3화면을 먼저 브라우저로 확인하라**

standalone 2화면과 `socialaccount/{login,authentication_error}`은 이미 실측된 공통
선택자(`.auth-panel-form`, `.auth-field input`)를 상속하고 화면 고유 규칙이
`.auth-shell.is-standalone` 하나뿐이라 위험이 낮다.

⚠️ **`socialaccount/signup.html`은 예외다 — 위 문장을 이 화면에 적용하지 마라.**
`[실측]` 이 화면만 `{{ form.as_p }}`를 쓴다(`:44`). `_auth_field.html`을 거치지 않으므로
`.auth-field input`을 **상속하지 않고**, `auth.css`의 별도 폴백 블록
(`.auth-panel-form form p`)으로 스타일된다. 그 결과 나머지 11화면과 다음이 다르다:

| | 나머지 11화면 | `socialaccount/signup.html` |
|---|---|---|
| 필드 스타일 | `.auth-field input` | `.auth-panel-form form p` 폴백 |
| 오류 마크업 | 커스텀 `.field-error` + `id_x-error` | Django 기본 `errorlist` |
| aria 연결 | 파셜이 직접 부여 | Django 자동(`id_x_error`) |
| 필수 표시 `*` | 있음 | 없음 |

필드 집합이 어댑터 설정에 달려 정적으로 알 수 없어 개별 include로 재작성하지 않았다.
**OAuth를 켤 때 이 화면은 별도로 육안 검수하라.**

## A12 잠금 화면은 **임계를 넘는 그 요청에만** 나온다

`[실측]` `AXES_FAILURE_LIMIT = 5` 기준으로 실제 5회 실패를 유발한 결과:

| 시도 | 응답 | 화면 |
|---|---|---|
| 1~4 | 200 | 로그인 (오류 배너) |
| **5** | **429** | **`로그인 일시 차단` — `lockout.html`** |
| 이후 | 200 | 로그인 (일반 오류 배너) |

즉 **재시도를 계속하면 잠금 안내가 다시 보이지 않는다.** 임계를 넘는 순간의 응답만
axes가 가로채고, 이후에는 인증 백엔드가 거부한 것을 allauth가 일반 폼 오류로 번역한다.
`AccessAttempt.failures_since_start`는 5에서 더 오르지 않는다.

이것은 **선재 동작**(axes + allauth 상호작용)이며 이번 트랙이 만든 것이 아니다.
다만 사용자가 잠금 사실을 한 번만 안내받는다는 뜻이므로, 인증 UX를 다시 볼 때
고려할 사항으로 남긴다.

`[실측]` 잠금 상태에서 회복 경로는 살아 있다 — `/accounts/password/reset/`가 200이고
제출 버튼이 존재한다. 429 응답 본문에 새 콘텐츠(h1·오류 배너·N4 안내문
「차단은 일정 시간이 지나면 자동으로 해제됩니다」·재설정 링크·좌패널)가 전부 있다.
검증 중 생긴 axes 기록은 `axes_reset`으로 정리했다.

## A13 자동 테스트는 이 변경을 거의 잡지 못한다

`[실측]` 프론트 전용이라 신규 테스트 0건, 회귀 2044 passed(착수 시점과 동일).

깨진 테스트는 단 1건이었고 **동작이 아니라 CSS 클래스명을 못 박고 있었다**
(`tests/auth/test_auth_field_errors.py`가 `<p class="auth-error">` 마크업 전체를 단언).
문구만 검사하도록 느슨하게 고치고 뮤테이션 왕복으로 실효를 확인했다.

**교훈: 테스트에 프레젠테이션 클래스명을 넣지 마라.** 리스킨 때마다 깨지면서 정작
동작 회귀는 못 잡는다. `[실측]` 전수 검색 결과 이런 고정은 저장소에 그 1건뿐이었다.

## A14 셸은 `.page` 안의 카드다 — 폭은 `.page`가, 안쪽 여백은 패널이 준다

`[실측 2026-08-17]` 원래 `.auth-shell`은 `<body>` 직속이라 헤더·푸터의 1120px 컨테이너를
벗어나 화면 끝까지 뻗었다. 1440px 기준 좌패널 h2가 x=44에서 시작해 헤더 로고(x=192)보다
116px 왼쪽이었고, 폼 우변 1440은 푸터 우변 1280보다 160px 바깥이었다.

지금은 12화면 전부 `<main class="page" id="content"><div class="auth-shell">` 구조다.

- **`id="content"`는 `<main>`에 둔다.** 안쪽 `div`로 옮기지 마라 — skip-link 대상이자
  랜드마크다.
- **`.auth-shell`에 가로 패딩을 주지 마라.** 바깥 여백은 `.page` 하나가 담당한다.
  둘 다 주면 이중 들여쓰기가 된다.
- 정렬 기준선은 컨테이너 박스(1120)가 아니라 **그 안쪽 콘텐츠 라인**이다.
  `[실측]` 1440px에서 헤더 로고 left=192, 푸터 저작권 right=1248 — 카드 경계가
  이 192/1248과 일치해야 맞춘 것이다.

### `min-height: 100vh` 계산은 되살리지 마라

원래 `min-height: calc(100vh - var(--site-header-h))`가 있었는데 베타 배너(`[실측]`
36.5px)와 푸터 `margin-top`(2.5rem)을 계산에 넣지 않아 어떤 화면에서도 스크롤이 생겼다.
**수식을 고치지 말고 삭제하는 것이 답이다** — 이 사이트의 다른 어떤 화면도 뷰포트를
채우려 하지 않고, 배너는 전 페이지에 항상 렌더되는 공유 크롬이라 페이지 CSS가
그 높이를 추적할 수 없다. `align-items: stretch`가 이미 두 패널 높이를 맞추므로
`min-height` 없이도 `[실측]` 짧은 화면 445/445, 긴 화면 699/699로 동일하다.

### 카드의 `overflow:hidden`은 모바일 폼 패딩과 한 쌍이다

둥근 모서리를 위해 `.auth-shell{overflow:hidden}`을 쓴다(패널마다 `border-radius`를
주는 대신 부모가 잘라낸다). 그래서 **모바일 `.auth-panel-form`의 가로 패딩을 0으로
만들면 안 된다** — 입력창이 카드 경계에 붙어 포커스 링이 잘린다.
`[코드]` 이 파일의 최대 링 확장은 4px(`outline 2px` + `outline-offset 2px`)이고
현재 여유는 `[실측]` 17px(패딩 1rem + 테두리 1px)이다.
`var(--page-pad-x)` 대신 리터럴 `1rem`을 쓴 것은 이 값이 바깥 여백이 아니라
**링 여유**라는 뜻을 남기기 위해서다.

### 고정폭 열은 좁은 컨테이너에서 제로섬이 된다 (A1의 재발)

`.page`가 좌우 여백을 가져가면서 카드가 좁아지자, 폼 열 `29.25rem` 고정이
줄어드는 몫을 전부 좌패널에 떠넘겼다. `[실측]` 721px에서 좌열 203px →
h2가 `그대들의 / 덕질 / 라이프를 / 위하여` 4줄로 깨지고(A1이 기록한 조사 고아의 재발)
도메인 설명은 54px 폭 4줄이 됐다.

`clamp(22rem, 50%, 29.25rem)`으로 양쪽이 함께 줄게 했다. `[실측]` 결과:
1025px 이상 468px 유지(변경 전과 동일) · 1024px 506/468 · 900px 425/425 ·
721px 319/352, h2는 전 구간 3줄.

⚠️ **폼 열을 고정값으로 되돌리지 마라.** 468px 고정은 좌패널을 깨고,
22rem 고정은 반대로 폼을 깨서 `[실측]` 1024px에서 링크 힌트가
`메일로 재설 / 정 링크 발송`으로 어절 중간에서 끊겼다.

### 721–870px는 두 열 다 만족시킬 수 없다 → 힌트를 감춘다

카드가 673px뿐인 721px에서 좌열이 읽히려면 ~320px가 필요하고, 남는 352px로는
`.auth-links-row`의 라벨+힌트+화살표가 들어가지 않는다. `[실측]` 860px에서도
힌트 둘째 줄이 11px·22px 조각이었다.

그래서 `.auth-links-hint{display:none}`의 경계를 `45rem`에서 **`56.25rem`**(900px,
이미 `event_list.css`·`archive_collection.css`가 쓰는 값)로 넓혔다. 새 경계값을
만들지 않았다. `[실측]` 901px에서 힌트가 각 1줄로 다시 나타난다.

힌트는 행 전체를 감싼 `<a>` 안의 `<span>`이라 **탭 정지 수가 변하지 않는다** — 링크
이름이 짧아질 뿐이고 라벨만으로 의미가 선다. 실제로 힌트를 렌더하는 템플릿은
`[코드]` `login.html`(2개)과 `lockout.html`(1개) 둘뿐이라 나머지 10화면에는 무동작이다.

### 상하 여백은 `.auth-page`가 대칭으로 잡는다

`[실측]` `.page`의 기본값만 쓰면 위 26px(`padding-top: 1.625rem`) / 아래 120px
(`padding-bottom: 5rem` 80 + `.site-footer{margin-top: 2.5rem}` 40)로 비대칭이라
카드가 넓은 빈 들판에 떠 있는 섬처럼 보였다(사용자 지적, 2026-08-17).

12화면은 `<main class="page auth-page" id="content">`이고 `auth.css`가 덮는다:

```css
.auth-page { padding-bottom: 1.625rem; }
.auth-page + .site-footer { margin-top: 0; }
```

⚠️ **`page` 클래스를 지우고 `auth-page`만 남기지 마라.** `page`가
`max-width: 1120px`와 가로 `--page-pad-x`를 담당한다 — 빼면 풀블리드 결함이 되살아난다.

⚠️ **`static/css/base.css`의 `.page`나 `site-chrome.css`의 `.site-footer{margin-top}`을
직접 고쳐 이 문제를 풀지 마라.** `[코드]` `.page`는 19개 템플릿(인증 12 + 스태프 3 +
드래프트 2 + 법적 2)이, `.site-footer`는 전 페이지가 공유한다.

인접 형제(`+`)가 성립하는 근거: `base.html`에서 `{% block content %}` 바로 다음이
`{% block site_footer %}`이고, `{% if messages %}`는 content **앞**에 오며,
`[코드]` 두 블록을 재정의하는 템플릿은 저장소에 없다. 이 전제가 깨지면 선택자는
**조용히 매치되지 않고** 여백이 120px로 돌아간다 — 오류도 경고도 나지 않는다.
확인법은 `.site-footer`의 computed `margin-top`이 `0px`인지 보는 것이다(전역값은 40px).

여백 측정 기준은 `.site-banner` 바깥 아래 모서리 → 카드 바깥 위 모서리, 카드 바깥 아래
모서리 → **`.site-footer` 바깥 위 모서리**다. `.site-footer-inner`로 재면 푸터 안쪽
패딩 32px이 섞여 26px이 58px로 잘못 나온다.
