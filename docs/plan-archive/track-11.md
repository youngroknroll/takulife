# 트랙 11: 소셜 가입 약관 동의(B2) + 헤더 인증 버튼 폰트 정렬 (2026-08-26)

> 배경: 첫 배포 완료 후 사용자가 Google 로그인 활성화를 요청. 백로그 B2
> [실측]이 차단 사유 — 소셜 가입 경로에 약관 동의 필드가 없어
> (`SOCIALACCOUNT_FORMS` 미설정, `rg` 0건) OAuth를 켜는 순간 동의 없는
> 가입 경로가 열린다. 추가 실측: `SOCIALACCOUNT_AUTO_SIGNUP` 기본값
> `true`(allauth 65.18.0 `adapter.py:172`)라 폼에 필드를 추가해도 신규
> 소셜 유저는 가입 폼 자체를 건너뛴다 — 폼 강제(`False`)가 같은 트랙의
> 필수 구성 요소다. 부수 요청: 헤더 로그인/회원가입 버튼 폰트를 같은 줄
> 주 메뉴 폰트와 동일하게.

## 승인 범위

**A. 소셜 가입 약관 동의 (백엔드, B2 해소)**

1. `accounts/forms.py`: `SocialSignupForm` 신설 —
   `allauth.socialaccount.forms.SignupForm` 상속, 기존 `SignupForm`과 동일한
   `terms_agreed` 필수 필드 + `custom_signup`에서 `terms_agreed_at` 기록.
   두 폼의 동의 규칙이 서로 어긋나면 법적 증적이 갈라지므로 공용 믹스인
   (`TermsAgreementFormMixin`)으로 한 곳에 둔다(소셜 `SignupForm`에도 동일
   `custom_signup` 훅이 있음을 소스로 확인 — `socialaccount/forms.py:32`).
2. `config/settings.py`: `SOCIALACCOUNT_FORMS = {"signup":
   "accounts.forms.SocialSignupForm"}` + `SOCIALACCOUNT_AUTO_SIGNUP = False`
   (신규 소셜 유저가 반드시 동의 폼을 거치게 하는 안전장치).
3. `templates/socialaccount/signup.html`: `{{ form.as_p }}`가 새 체크박스를
   포함해 렌더되는지 확인하고, 일반 가입 화면(`account/signup.html`)의 동의
   체크박스 마크업 규약과 어긋나면 그 규약으로 정렬(프론트 구현 역할 담당).

**B. 헤더 인증 버튼 폰트 정렬 (프론트)**

4. `static/css/components/modal.css` `.topbar-link`: `font-size: 0.615rem`
   → `0.92rem`(주 메뉴 `.site-nav a`와 동일 — site-chrome.css:64 [코드]).
   위쪽 "3/4 축소" 주석은 코드와 어긋나게 되므로 함께 갱신. 패딩·min-height
   등 다른 속성은 리뷰어 사양이 요구할 때만 조정.

## 배제 (범위 밖)

- Google Cloud Console OAuth 클라이언트 생성, Render env 등록(사용자 액션).
- 기존 가입자 약관 재동의, 약관 문서 내용 변경, 다른 소셜 제공자.
- `SOCIALACCOUNT_EMAIL_AUTHENTICATION`(기존 계정 자동 연결) 정책 변경 —
  기존 계정은 최초 가입 시 이미 동의했으므로 이번 범위가 아니다.

## 수용 기준

- 신규 소셜 로그인 시도는 자동 가입되지 않고 가입 폼을 거친다(설정 계약).
- 소셜 가입 폼은 `terms_agreed` 미체크 제출을 거부하고 한국어 오류를 낸다.
- 동의 제출 시 `terms_agreed_at`이 기록된다(일반 가입과 동일 증적).
- 일반 가입 폼의 기존 동작은 회귀 없음(기존 테스트 초록 유지).
- 헤더 로그인/회원가입 버튼 폰트 크기가 주 메뉴와 같은 0.92rem으로 실측
  확인되고, 헤더가 1줄로 유지된다(데스크톱·모바일 뷰포트 스크린샷).

## Test List (백엔드)

| ID | 행위 | 경계 | 근거 |
|---|---|---|---|
| T11-1 | 소셜 가입 폼은 약관 미동의 제출을 거부하고 지정 오류 메시지를 낸다 | domain | 폼 검증 규칙 자체가 계약 |
| T11-2 | 소셜 가입 폼이 동의와 함께 저장되면 terms_agreed_at이 기록된다 | domain | 증적 기록이 관찰 가능한 결과 |
| T11-3 | 소셜 가입 설정 계약: SOCIALACCOUNT_FORMS가 SocialSignupForm을 가리키고 AUTO_SIGNUP이 False다 | contract | 이 두 값 중 하나만 풀려도 동의 우회가 다시 열린다 — 설정이 곧 보안 계약 |
| T11-4 | 소셜 가입 제출 엔드포인트에 일반 가입과 같은 레이트리밋이 걸려 있다 | slow | 보안 검토 F1: allauth 소셜 SignupView는 로컬과 달리 rate_limit 데코레이터가 없다([코드] allauth account/views.py:144 유·socialaccount/views.py:31-50 무). 코치 계약에서 slow(behavior, 429 실관찰) 경계로 확정 — GET은 allauth가 카운트 제외([실측] core/internal/ratelimit.py:186)라 POST로 검증. 트랙 중 발견 동일 유형 결함 — 같은 트랙에서 수정(2026-08-25 표준 결정) |

## Activated Roles

- Backend TDD Coach: 폼 동작·설정 계약의 테스트 시퀀스 관장
- Backend & Integration Engineer: 폼·설정·테스트 구현
- Security & Resilience Reviewer: 동의 우회 경로(auto signup, 연결 로그인) 검토
- Web Experience Designer / Browser Interaction Reviewer: 소셜 가입 화면 체크박스 + 헤더 버튼 이중 리뷰(사전 사양·사후 판정)
- Frontend Implementation Engineer: 템플릿·CSS 편집
- Quality Verification Lead: 증거 매트릭스·완료 판정

Not Activated: Product Scope Owner(범위를 사용자가 직접 지정), Domain
Architecture Reviewer(accounts 내부 변경, 경계 이동 없음), Deployment &
Operations Reviewer(env 계약은 runbook에 반영 완료, 코드측 설정 2건은 계약
테스트로 고정), AI Automation Architect(해당 없음).

## Frontend Review Evidence

- 깊이: Standard(가입 폼 필드 추가 + 헤더 컴포넌트 크기 변경)

**WXD 사전 사양(요지)**: ① socialaccount/signup.html의 `{{ form.as_p }}`는
유지 불가(auth.css 456-466의 `form p input { width:100%; min-height:2.75rem }`가
체크박스를 잡아 깨짐 + terms_agreed 이중 렌더) — account/signup.html 규약대로
명시적 필드 렌더(_auth_field.html 이메일 + `.auth-consent` 블록, redirect_field는
csrf_token 직후)로 교체 ② `.topbar-link`는 `.site-nav a`의 박스 모델 복사
(font-size 0.92rem, padding 0.375rem 0.75rem, min-height 44px), 필 룩(border/
background/radius/color)은 유지, "3/4 축소·WCAG 예외" 주석은 사실과 어긋나므로
교체 ③ 확인 뷰포트 ~360-390/768/1120+.

**BIR 사전 기준(요지)**: 1.1 라벨 sibling for/id 1.2 체크박스 focus-visible
1.3 에러는 필드 인접 `#id_terms_agreed-error` 1.4 에러 시 aria-describedby/
aria-invalid(기존 account 화면의 누락 갭 — 두 화면 모두에서 트랙 내 해소 요구)
1.5 약관 링크 _blank+noopener 1.6 라벨 내 링크 클릭 시 체크박스 비토글(실클릭
필수) 1.7 터치 타깃 실측 보고 2.a 721-1024px 위험 구간 헤더 1줄+토큰 일치
2.b sticky 소비자 비겹침 2.c 햄버거 간격 2.d focus-visible 존속 2.e 44px 실측.

**구현 후 실측(오케스트레이터, Chrome DevTools MCP + render_to_string)**:
헤더 69.0px==토큰(1440/1024/900/768/721px, nav 1행, 오버플로 없음), 375px 1행
65px, 320px 2줄 깨끗한 랩(겹침 없음, 스크린샷). `.topbar-link` 실측 14.72px/
6px 12px/44px = `.site-nav a`와 동일. Tab 실키 순회로 outline solid 2px 확인.
/accounts/signup/ 미동의 제출 → is-error+에러 ul+aria 2종, 동의 후 재렌더
checked 보존. 라벨 내 "이용약관" 실클릭 → 체크박스 비토글+새 탭 열림.
socialaccount/signup.html은 OAuth 세션 없이 도달 불가 → render_to_string
13항목 ALL-PASS로 대체(실 OAuth 화면은 크리덴셜 설정 후 수동 1회).

**사후 판정**: WXD **Conforms**(두 항목 모두 — CSS 값은 소스 재독+rem 산술로
독립 교차 확인, account/signup.html도 함께 수동 마크업 전환한 것은 의도를 더
강하게 충족하는 유익한 편차로 판정). BIR **Conforms**(전 기준 pass — 1.6은
실클릭 측정, 소셜 화면은 바이트 동일 DOM이라 측정 전이 유효 판정. 잔여 비차단
2건: 체크박스 18×18px 터치 타깃은 pre-existing 미기록 항목, 320px 랩 기준선
부재 — 둘 다 제품 권고). QVL 완료 판정은 본 기록 반영 후 발급.

## 검증 커맨드

- `uv run pytest -q tests/accounts/` (타깃) → `uv run pytest -q` (회귀)
- `uv run python manage.py check`
- 브라우저: 로컬 서버에서 헤더 폰트 실측(getComputedStyle), 뷰포트 2종
  스크린샷, 소셜 가입 화면은 provider 미설정 로컬 한계로 폼 단위 검증 +
  템플릿 렌더 확인으로 대체(한계를 보고서에 명시)

## Deferred

- 기존 소셜 연결 로그인 사용자의 재동의 UX(현재 해당 사용자 0명)
- Google 외 제공자 추가 시 신뢰 정책 재검토(settings 주석 유지)

