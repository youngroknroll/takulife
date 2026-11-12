# 트랙 29: 회원 닉네임 도입 — 가입 필수 입력·헤더/마이페이지 표시·기존 회원 백필·변경 화면 (2026-09-10) [v2 — PSO·DAR·TDD 코치·WED·BIR·SRR·QVL·DOR 8역할 검토 반영, **사용자 승인 대기**]

> **검토 반영 요약(v1 → v2)** [8역할 병렬 산출 2026-09-10, 인용 file:line·건수는 오케스트레이터가 rg/sed로 재확인]
> - PSO: "게시글에 닉네임" 요청은 **지금 작성자 라벨을 그리는 화면이 없으므로**(`templates/core` rg `owner|author|created_by|user\.email` → 본인
>   표시 6곳뿐 [실측]) "향후 공개 표시가 읽을 단일 식별자 소스를 지금 만드는 트랙"으로 범위 문장 확정. 이메일 로컬파트 백필 **기각 권고**(★1).
> - DAR: 새 `User.nickname`(기존 미사용 `username` 재활용 기각) / 유일성은 **DB `UniqueConstraint(Lower("nickname"))` + 폼 iexact 사전 검사 둘 다** /
>   저장은 `accounts/adapters.py` 신설 `save_user` 오버라이드(allauth 65.18.0 `account/forms.py:440` save_user 커밋 → `:441` custom_signup 순서 [실측]) /
>   검증 규칙은 `accounts/validators.py` 순수 함수로 폼 2개+매니저+마이그레이션이 공유 [코드] / **변경 뷰는 `accounts/views.py`**(web/views 아님 —
>   `accounts/views.py:21` `account_settings`가 archive 무의존 계정 화면의 선례) / `display_name` 간접층 과잉 기각.
> - TDD 코치: Test List 18건 [계산] + 정정 2건 — 가입 POST 지점은 17건이 아니라 **`"password1"` 제출 13곳/5파일** [실측 rg -c 합산 4+2+4+1+2],
>   RunPython 테스트 선례는 **있다**(`tests/archive/test_collection_item_goods_migration.py` CP10 방식: 모듈 import 후 `django.apps.apps`로 직접 호출).
>   `make_user`/`make_verified_user` 호출 **754건/94파일** [실측] → conftest 기본값 필수. "M0" 용어는 AGENTS.md에 없음 → 사용 안 함.
> - WED: 깊이 Standard 제안(BIR High와 합집합 → **High 확정**). 필드 위치 이메일 뒤·비밀번호 앞, 힌트 한 줄은 `email_change.html:35` `.account-settings-email-hint`
>   패턴(rule-list 아님), 오류 문안 5종 [계산] 확정, 예약어 문안은 단어 비노출. **마이페이지에 "이름 줄"은 없다**(`mypage.html:14` h1은 정적 "마이페이지") →
>   `.mypage-nickname` p 신설, h1 유지. 계정 섹션 "닉네임" 행 맨 위, 액션 "변경". 설정 탭 순서 로그인 정보/닉네임/이메일/비밀번호/탈퇴. 백필 유도 배너 기각.
> - BIR: **High**. 결함 3건 [계산] → 계획 반영: (a) 모바일(45rem 이하)에서 `.topbar-username`은 `display:none`(`site-chrome.css:126` [코드])이라 **헤더 어디에도
>   닉네임이 안 보임** → 계정 메뉴 패널에 닉네임 줄 신설(★5), (b) `.topbar-username` `title`도 닉네임으로(표시 텍스트=title 관행), (c) 변경 폼 유일성 검사에
>   **자기 자신 제외** 필수(NICK-18). 기존 결함 1건: `base.html:102` `.site-messages`에 `role="status"` 없음(★6) [코드]. `autocomplete="nickname"`은 폼 위젯 attrs로 명시.
> - SRR: F1 이메일 로컬파트 백필은 **배포 블로커**(충돌·문자 위반 시 `set -e` entrypoint가 기동 중단) → `회원<pk>` 채택 시 소멸. F2 변경 엔드포인트
>   **사용자당 빈도 제한** 필요(`ACCOUNT_RATE_LIMITS`는 allauth 뷰 4키만 [실측 `config/settings.py:485-490`]). F3 **NFKC 정규화 → 정규식 fullmatch(거부, silent-strip
>   아님) → 정규화+소문자 예약어 완전일치**, 정규식 `^[0-9A-Za-z_가-힣]{2,20}$`. F8 `create_user(nickname="admin")` 직접 호출도 거부(매니저 경로가 폼을 우회).
>   XSS는 plain `{{ }}` 유지로 방어. 재확인 불필요, 이력은 이연.
> - QVL: 초안 수치 불일치 0건 [실측]. **누락 3건** [계산] 반영: `tests/e2e/conftest.py:63-71` `verified_user`는 별도 픽스처(e2e 8파일 [실측] 연쇄 파손 후보) / 팩토리
>   미경유 직접 호출 3곳 [실측](`test_auth_backend.py:285`, `test_draft_source_admin.py:11`, `test_social_signup_terms_agreement.py:32`) / 백필 규칙에 NFC·절단·유예 계정
>   명시. 회귀 기준선 2547 passed / 10 deselected / 80.22초 [문서 pr-log #356] — 착수 시 재측정.
> - DOR: 초안 3단계 단일 파일은 `archive/migrations/0003` 선례와 달리 **마지막 단계가 실제 DDL(NOT NULL+UNIQUE)** [코드] → 선례 오인. 블로커 2건 [계산]: 배포 스왑
>   창(구 코드 INSERT가 NOT NULL 위반)과 `accounts_user` 행 수 미실측. RunPython **reverse는 noop**(선례 `archive/0003:12`·`0016`·`0018` 전부 noop [코드]). 결정 ★2.

> 배경: 사용자 원문(2026-09-10) "회원가입 시 닉네임을 만들어야 하는데 빼먹었다. 현재는 이메일이 닉네임 자리를 대체한다. 앱에서 출력되는 게시글에는
> 해당 id의 닉네임이 떠야 한다. 헤더에 id 대신 닉네임으로 대체되듯이."
> 현황 [실측 2026-09-10]: 리포 전체 `nickname|닉네임|display_name` 관련 0건 / `accounts/models.py:8` `username`은 AbstractUser 잔재(nullable·non-unique,
> `ACCOUNT_USER_MODEL_USERNAME_FIELD=None` `config/settings.py:426`) / 이메일이 이름 자리인 회원 화면: `_topbar.html:16`(`.topbar-username`)·`:21`(`.account-mark`
> 이니셜)·`:24`(메뉴 이메일), `mypage.html:12`(아바타)·`:15`(`.mypage-email`)·`:51`(계정 섹션 이메일 행), `_account_settings_index.html:37`, `email_change.html:19` /
> 스태프 화면 7곳 [실측 rg]은 이메일=운영 식별자(docs/BE/staff-account-operations.md (e)) / `SOCIALACCOUNT_AUTO_SIGNUP=False`(`:469`)라 소셜 신규도 폼 경유 /
> `ACCOUNT_ADAPTER` 미설정·`accounts/adapters.py` 없음 / 최신 마이그레이션 `accounts/migrations/0005` / 운영 DB 회원 행 수 **미실측**(사용자 액션 U1).

## 승인 범위 (★ = 사용자 결정 필요, 권고안 병기)

**A. 스키마** (`accounts/models.py`, `accounts/migrations/0006_*.py`) [DAR 채택]
- `nickname = CharField(max_length=20)` 신설. `Meta.constraints`에 `UniqueConstraint(Lower("nickname"), name="accounts_user_nickname_ci_unique")`
  (필드 `unique=True`는 쓰지 않음 — 인덱스 중복 방지). `REQUIRED_FIELDS = ["nickname"]`(createsuperuser가 묻게, 현행 `[]` [코드]). 기존 `username` 컬럼 무변경.
- 마이그레이션 0006 한 파일·atomic: AddField(null=True) → RunPython 백필(★1, reverse=`RunPython.noop`) → AlterField(null=False) → AddConstraint.
  **★2 — 배포 구조**: (권고) 단일 배포. 잔여 위험 = Render 스왑 창(신규 컨테이너 헬스체크 통과 후 구 컨테이너 종료 사이, 초 단위 [추정])에 **구 코드**로 들어온 가입
  POST 한 건이 NOT NULL 위반 오류 — 재시도하면 신 코드로 성공. 대안 = expand-contract 두 차례 배포(0006은 null 허용+백필+제약, 0007이 NOT NULL) — 배포 PR이
  #334·#336처럼 장기간 열려 있는 현재 배포 주기에서는 contract 단계가 기약 없이 미뤄지므로 권고하지 않음. 어느 쪽이든 AddField~커밋까지 `accounts_user`
  ACCESS EXCLUSIVE 락이 걸리므로 **U1(행 수 실측)이 배포 전 선행**.
- **★1 백필 값**: (권고) `회원<pk>` — 결정적·멱등·충돌 불가·이메일 무상관(PSO·SRR 권고 일치). 대안 `user_<hex>`(추측 불가, 단 재실행 시 비결정적).
  `^회원\d+$`는 **예약 패턴**으로 가입/변경 폼에서 거부해(NICK-03) 백필 값과 사용자 선택 값이 영원히 겹치지 않게 한다. 유예 탈퇴 계정도 백필 대상(제외 근거 없음, QVL).

**B. 검증 규칙** (`accounts/validators.py` 신설) [DAR·SRR 채택]
- `normalize_nickname(raw) -> str`: `unicodedata.normalize("NFKC", raw).strip()`. `validate_nickname(value)`: 정규식 `^[0-9A-Za-z_가-힣]{2,20}$` fullmatch 실패 →
  ValidationError(자모 낱자·전각·제로폭·RTL·결합문자·공백 전부 거부, 조용한 제거 없음) / 예약어 완전일치(정규화+`lower()`) → ValidationError / 예약 패턴 `^회원\d+$` → ValidationError.
- **★4 예약어 범위**: (권고) 브랜드·운영진·시스템 완전일치만 — 영문 `admin, administrator, root, system, staff, moderator, mod, support, official, superuser, takulife`,
  한글 `관리자, 운영자, 스태프, 시스템, 공식, 고객센터, 운영팀, 타쿠라이프`. 욕설·부분 문자열·편집거리 탐지는 이연.
- 모델 필드 `validators=[validate_nickname]`로 `full_clean()` 경로에도 걸고, `UserManager._create_user`가 `nickname`을 정규화+검증한 뒤 저장(NICK-08b: `create_user(nickname="admin")` 거부).
- 오류 문안 [WED 확정]: 필수 "닉네임을 입력해 주세요." / 길이 "닉네임은 2자 이상 20자 이하로 입력해 주세요." / 문자 "닉네임은 한글, 영문, 숫자, _(밑줄)만 사용할 수 있습니다." /
  중복 "이미 사용 중인 닉네임입니다." / 예약어·예약 패턴 "이 닉네임은 사용할 수 없습니다."(단어 비노출, auth-editorial A6 톤). 글자 수 상한 표기(2·20)는 §B 정규식 [코드]과 같은 값.

**C. 가입 저장** (`accounts/forms.py`, `accounts/adapters.py` 신설, `config/settings.py`) [DAR 채택]
- `TermsAgreementFormMixin`에 `nickname = CharField(min_length=2, max_length=20, widget=TextInput(attrs={"autocomplete": "nickname", "placeholder": "닉네임"}))` +
  `clean_nickname`(정규화 → validate → `User.objects.filter(nickname__iexact=...)` 사전 중복 검사). `ACCOUNT_SIGNUP_FIELDS`는 allauth 내장 필드 전용이라 무변경. 길이 값은 §B와 동일 [코드].
- `AccountAdapter(DefaultAccountAdapter).save_user`: `super()` 호출 **전에** `user.nickname = form.cleaned_data["nickname"]`. `ACCOUNT_ADAPTER = "accounts.adapters.AccountAdapter"`.
  소셜은 `socialaccount/adapter.py:119`가 같은 account adapter를 타므로 별도 어댑터 불필요. 경쟁 창의 `IntegrityError`는 어댑터가 잡아 폼 오류(중복 문안)로 번역.
- 소셜 구글 `name`을 initial로 제안하는 기능은 **이연**(PSO).

**D. 닉네임 변경 화면** (`accounts/views.py`, `accounts/forms.py` `NicknameChangeForm`, `config/urls.py`, `templates/account/nickname_change.html` 신설,
`_account_settings_index.html`) [DAR 위치 정정·SRR F2]
- URL `accounts/settings/nickname/` name `account-nickname-page`, `@login_required`, GET 현재 값 채운 폼 / POST 정규화·검증·**자기 자신 제외** iexact 중복 검사 → 저장 →
  `messages.success("닉네임이 변경되었습니다.")` → 같은 URL로 PRG. 같은 값 재제출은 오류 없이 302(NICK-18).
- **★3 재확인·빈도 제한**: (권고) 비밀번호 재확인 없음(닉네임은 자격 증명이 아님, SRR 동의) + **사용자당 시간당 다섯 회**(이 계획서 권고값, 단위 회/시간) 캐시 카운터
  (`accounts/services.py`에 `is_nickname_change_throttled(user)`/`register_nickname_change(user)` — 기존 `delete_attempts` 카운터와 같은 캐시 패턴 [코드], 한도 초과는
  DB write 없이 폼 오류 "닉네임 변경이 너무 잦습니다. 잠시 후 다시 시도해 주세요.").
- 템플릿은 `password_change.html` 구조(`_account_settings_panel_head.html` kicker "계정 설정"/title "닉네임 변경", `_account_settings_field.html` label "새 닉네임",
  힌트 한 줄 `.account-settings-nickname-hint` "2~20자, 한글·영문·숫자·_ 사용 가능"(§B 값 [코드]), 제출 "닉네임 변경", `data-submit-guard`(버튼에 `name` 금지 —
  account-settings-editorial G1), `account-settings-back`). 탭 순서: 로그인 정보 / 닉네임 변경 / 이메일 변경 / 비밀번호 변경 / 회원 탈퇴(`is-danger`는 탈퇴만). `settings.html` 개요 dl에 닉네임 행 추가.

**E. 표시 교체(회원 화면만)** [WED·BIR 확정]
- `_topbar.html:16` `.topbar-username` 텍스트·`title` 모두 `request.user.nickname` / `:21` `.account-mark` `{{ request.user.nickname|first|upper }}` / `:24` 메뉴 이메일 줄 유지 +
  **★5 (권고) 그 위에 `<p class="account-menu-nickname">{{ request.user.nickname }}</p>` 신설**(모바일 헤더 공백 해소, BIR High). `aria-label="계정 메뉴"` 유지.
- `mypage.html:12` 아바타 이니셜 → 닉네임 첫 글자 / `:14` h1 "마이페이지" **유지** / `:13`에 `<p class="mypage-nickname">` 신설, `:15` 이메일 줄 유지 / 계정 섹션 맨 위에
  "닉네임" 행(값 + 액션 "변경" → `account-nickname-page`).
- `_account_settings_index.html:37`, `email_change.html:19`, 스태프 화면 전부(현황 절 [실측] 참조): **무변경**(이메일=정보 표기·운영 식별자).
- CSS: `.account-menu-nickname`, `.mypage-nickname`, `.account-settings-nickname-hint` 규칙 신설(rem, OOCSS). `.topbar-username` max-width 15rem·ellipsis(`modal.css:9-23` [코드])와
  모바일 `display:none`(`site-chrome.css:126` [코드]) 기존 규칙 그대로. `dist/shell.css`는 빌드 산출물 — 직접 편집 금지.
- **★6 (권고) 같은 트랙 즉시 수정**: `templates/base.html:102` `<ul class="site-messages">`에 `role="status"` 한 줄 추가(PRG 성공 메시지가 스크린리더에 무음 — 기존 결함, 단일 파일,
  "같은 트랙에서 소규모 결함 즉시 수정" 2026-08-25 규약).

**F. 테스트 팩토리·기존 테스트 정합** [QVL·코치, 건수 전부 실측 2026-09-10]
- `tests/conftest.py:63-73` `make_user`·`:165-171` `make_verified_user`, **`tests/e2e/conftest.py:63-71` `verified_user`** 세 픽스처에 `kwargs.setdefault("nickname", f"user_{secrets.token_hex(4)}")`.
  프로덕션 매니저에는 기본값 로직을 두지 않는다(DAR).
- 팩토리 미경유 직접 호출 3곳 [실측](`tests/auth/test_auth_backend.py:285`, `tests/drafts/test_draft_source_admin.py:11`, `tests/auth/test_social_signup_terms_agreement.py:32`)에 `nickname=` 인자 추가.
- `"password1"` 가입 제출 13곳/5파일 [실측](`test_auth_backend.py` 4, `test_auth_field_errors.py` 2, `test_auth_rate_limit.py` 4, `test_signup_flow.py` 1, `test_signup_terms_agreement.py` 2)에
  `"nickname": "..."` 추가 — NICK-05 Green 커밋에 포함, 별도 커밋·백로그 이연 금지.

**G. 문서**
- `docs/BE/account-identity.md` 신설(계정 도메인 정본 없음 — `staff-account-operations.md`는 스태프 운영 전용): 닉네임=공개 예정 식별자·이메일=비공개 경계, 검증 파이프라인 순서,
  백필 규칙과 예약 패턴 근거, 역적용 금지(`accounts 0005`로 되돌리지 않는다 — 코드만 되돌리는 것은 안전), 변경 빈도 제한.
- `docs/deploy-runbook.md` 배포 후 확인 절에 항목 두 줄(`curl -s https://takulife.kr/accounts/signup/ | grep -c 'name="nickname"'` → 기대 1 [계산] / `psql "$DATABASE_URL" -c "SELECT count(*) FROM accounts_user WHERE nickname IS NULL;"` → 기대 0 [계산]),
  롤백 절 인접에 마이그레이션 실패 시 동작(`set -e`로 기동 중단 = 구 컨테이너 계속 서비스) 문장. `docs/operations-runbook.md` createsuperuser 절에 닉네임 프롬프트 추가 언급.
- `.docs/FE/2026-09-10-nickname.md` FE 기록, `docs/backlog.md` 갱신, 머지 시 `docs/pr-log.md` 롤링.

## 명시적 제외 / 이연
- 제외: 게시글·공개 콘텐츠 작성자 표시 신설(현재 화면 없음·교환 게이트 전), 닉네임 검색·멘션·공개 프로필, 프로필 사진·자기소개, 스태프 콘솔 표시 변경, `username` 컬럼 정리.
- 이연(백로그 신설): 소셜 `name` initial 제안 / 닉네임 변경 이력·과거 닉네임 조회(신고·차단 게이트와 함께) / `/staff/accounts/`(superuser 전용) 닉네임 열·검색 /
  욕설·부분 문자열·유사 사칭 탐지 / 실시간 사용 가능 여부 AJAX(추가 시 별도 빈도 제한 필수) / `statement_timeout`·`lock_timeout` DB 옵션 / 마이그레이션 소요시간 알림.

## 수용 기준 (증거 매핑)
1. 이메일 가입에서 닉네임 미입력·중복(대소문자 무시)·형식 위반·예약어·예약 패턴 제출은 200+폼 오류, 유저 미생성 — NICK-05·07·02·03 (web/unit).
2. 유효 닉네임 가입(이메일·소셜)은 INSERT 시점에 값이 실려 저장된다 — NICK-06·09 (web).
3. 폼을 우회한 ORM 직접 저장도 대소문자 무시 유일성·형식·예약어를 DB/매니저가 강제 — NICK-08·08b (domain/contract).
4. 마이그레이션 후 기존 회원 전원이 `회원<pk>` 닉네임을 가진다(NULL·중복 0건), 빈 DB에서도 통과, reverse는 noop — NICK-11~14 (contract, CP10 방식).
5. 로그인 회원의 헤더(데스크톱 텍스트·모바일 메뉴 패널)·마이페이지에 닉네임이 뜨고 이메일은 정보 줄에 남는다 — HTTP 렌더 확인 + 브라우저 증거(자동 테스트 아님, Frontend Work Policy).
6. 닉네임 변경 GET/POST/중복/자기 값 재제출/빈도 초과가 각각 200·302·오류·302·오류(DB write 없음)로 동작 — NICK-15~19 (web).
7. `createsuperuser`가 닉네임을 요구한다 — NICK-10 (contract) + 수동 확인.
8. 스태프 화면·설정 인덱스·이메일 변경 화면 렌더는 무변경 — 기존 테스트 Green + QVL rg.
9. 신규 nickname 출력에 `|safe`/`mark_safe`/인라인 script 0건 [실측 예정] — rg.

## Activated Roles / Not Activated
- Activated: Product Scope Owner, Domain Architecture Reviewer, Backend TDD Coach, Backend & Integration Engineer, Quality Verification Lead, Web Experience Designer,
  Browser Interaction Reviewer, Frontend Implementation Engineer, Security & Resilience Reviewer, Deployment & Operations Reviewer.
- Not Activated: AI Automation Architect(LLM 범위 없음).

## 파일 목록 (신규 ✚ / 수정 ✎)
- ✚ `accounts/validators.py`, ✚ `accounts/adapters.py`, ✚ `accounts/migrations/0006_user_nickname.py`, ✎ `accounts/models.py`, ✎ `accounts/managers.py`, ✎ `accounts/forms.py`,
  ✎ `accounts/services.py`(빈도 제한 함수), ✎ `accounts/views.py`(변경 뷰), ✎ `config/settings.py`(`ACCOUNT_ADAPTER`), ✎ `config/urls.py`
- ✚ `templates/account/nickname_change.html`, ✎ `templates/account/signup.html`, ✎ `templates/socialaccount/signup.html`, ✎ `templates/account/settings.html`,
  ✎ `templates/core/partials/_account_settings_index.html`, ✎ `templates/core/partials/_topbar.html`, ✎ `templates/core/mypage.html`, ✎ `templates/base.html`(★6),
  ✎ `static/css/components/site-chrome.css`(`.account-menu-nickname`), ✎ `static/css/pages/mypage.css`, ✎ `static/css/pages/account_settings.css`
- ✚ `tests/auth/test_nickname_validators.py`, ✚ `tests/auth/test_nickname_signup.py`, ✚ `tests/auth/test_nickname_model_contracts.py`, ✚ `tests/auth/test_nickname_backfill_migration.py`,
  ✚ `tests/auth/test_account_nickname_change.py`(코치 제안 `tests/accounts/`는 기존 디렉터리 관례 `tests/auth/`로 통일), ✎ `tests/conftest.py`, ✎ `tests/e2e/conftest.py`, ✎ §F가 나열한 기존 테스트 파일들
- ✚ `docs/BE/account-identity.md`, ✎ `docs/deploy-runbook.md`, ✎ `docs/operations-runbook.md`, ✎ `docs/backlog.md`, ✚ `.docs/FE/2026-09-10-nickname.md`

## 구현 단계 (커밋 단위)
1. §B 검증 함수 (NICK-01~04) → 2. §A 모델·마이그레이션·매니저 (NICK-08·08b·10·11~14) + §F 픽스처 세 곳 → 3. §C 폼·어댑터·settings (NICK-05·06·07·09) + §F의 가입 제출 지점·직접 호출 지점 →
4. §D 변경 뷰·폼·URL·빈도 제한 (NICK-15~19) → 5. FE: 가입 템플릿 둘·헤더·마이페이지·설정 탭·변경 템플릿·CSS·★6 (WED/BIR 사전 산출 있음 → FIE 편집 가능) → 6. 브라우저 증거·
사후 리뷰 → 7. 문서 → 8. 검증·PR. PR은 트랙 하나 = 한 개(pr-granularity).

## Domain Boundary / Coupling / Pythonic [DAR]
- accounts 내부 완결. 허용 의존: `accounts/adapters.py`→allauth, `accounts/views.py`→accounts.forms/services. 금지: accounts→archive/drafts/events/staff/web
  (`tests/core/test_architecture_boundaries.py:313-326` 가드 유지). 신규 서비스·시그널·미들웨어 없음. 트랜잭션 경계=어댑터 내부 단일 `user.save()`, 경쟁 창은 IntegrityError 번역.
- 결합도 증가 없음, 응집도 상승(규칙·저장·변경이 accounts에 모임). 표시는 템플릿 직접 참조.

## §T Test List (코치 산출 + 오케스트레이터 반영분, 총 20건 [계산], 전부 `tests/auth/`, 한국어 행위 명명)
| ID | 행위 | 마커 | 첫 Red 사유 |
|---|---|---|---|
| NICK-01 | 길이가_2자_미만인_닉네임은_검증에서_거부된다 | unit | `accounts.validators` ImportError |
| NICK-02 | 허용되지_않는_문자가_포함된_닉네임은_검증에서_거부된다(공백·자모·전각·제로폭 파라미터) | unit | 동일 |
| NICK-03 | 예약어_및_회원숫자_패턴_닉네임은_검증에서_거부된다(전각 `ａｄｍｉｎ`·제로폭 `ad​min` 포함) | unit | 동일 |
| NICK-04 | 정규화는_NFKC_변환과_앞뒤_공백_제거를_적용한다 | unit | 동일 |
| NICK-05 | 닉네임_없이_가입하면_가입이_거부되고_사용자가_생성되지_않는다 | web | 폼에 필드 없어 302 가입 성공 |
| NICK-06 | 유효한_닉네임으로_가입하면_사용자_닉네임에_반영된다 | web | 컬럼 없음 |
| NICK-07 | 대소문자만_다른_기존_닉네임으로_가입하면_거부된다 | web | 중복 검사 없어 두 계정 생성 |
| NICK-08 | 대소문자만_다른_닉네임은_DB_제약으로도_저장할_수_없다(ORM 직접) | domain | 제약 없음 |
| NICK-08b | 매니저로_예약어_닉네임을_만들면_거부된다 | domain | 매니저 검증 없음 |
| NICK-09 | 소셜_가입시_유효한_닉네임을_제출하면_사용자_닉네임에_반영된다 | web | 소셜 폼에 필드 없음 |
| NICK-10 | REQUIRED_FIELDS는_닉네임을_포함한다 | contract | `[]` |
| NICK-11 | 백필_실행시_모든_기존_회원에_회원pk_닉네임이_채워진다 | contract | 마이그레이션 모듈 없음 |
| NICK-12 | 백필은_이미_닉네임이_있는_행을_덮어쓰지_않는다(멱등) | contract | 동일 |
| NICK-13 | 빈_DB에서_백필은_예외_없이_통과한다 | contract | 동일 |
| NICK-14 | 유예_탈퇴_중_계정도_백필_대상이다 | contract | 동일 |
| NICK-15 | 로그인_사용자가_닉네임_변경_페이지에_접근하면_현재_닉네임이_채워진_폼이_렌더링된다 | web | 404 |
| NICK-16 | 유효한_새_닉네임을_제출하면_닉네임이_갱신되고_같은_페이지로_리다이렉트된다 | web | 404 |
| NICK-17 | 타인이_사용중인_닉네임으로_변경을_시도하면_거부되고_기존_닉네임이_유지된다 | web | 404 |
| NICK-18 | 자신의_현재_닉네임을_그대로_재제출하면_오류_없이_저장된다 — **뮤테이션 증거 필수**(exclude 제거 시 Red) | web | 404 |
| NICK-19 | 한_시간_한도를_넘는_닉네임_변경은_DB_변경_없이_거부된다 | web | 제한 없음 |
- 테스트하지 않는 것: topbar·mypage 템플릿 치환(순수 표시), allauth 내부 호출 순서, `ACCOUNT_SIGNUP_FIELDS` 값, 예약어 목록 완전성. "필드 렌더" 테스트는 이미-Green 위험으로 배제.
- 첫 계약: NICK-01, Green 경계 = `validate_nickname`이 두 글자 미만만 거부. 사이클마다 `uv run pytest -q <표적>` 후 `tests/auth/` 슬라이스.

## Frontend Review Evidence
- 깊이 **High**(BIR: 전 페이지 공유 헤더 + 설정 IA 탭 추가 + 신규 PRG 화면; WED Standard와 합집합).
- WED 사전 사양: §B 문안·§D 템플릿 구조·§E 표시 결정(위 반영). BIR 사전 기준: `autocomplete="nickname"` 명시, `minlength/maxlength`는 CharField가 자동 부여(렌더 HTML로 재확인),
  `title`=닉네임, 메뉴 패널 닉네임 줄, 자기 자신 제외, `data-submit-guard`+`pageshow`는 기존 `api.js` 공용 핸들러 재사용, 필드 오류는 `aria-describedby` 자동 연결.
- 계획 브라우저 증거(뷰포트 320·768·1280px, Chrome DevTools MCP): 가입 input 속성·오류 재채움 / 헤더 텍스트·title·접근성 트리(모바일 패널 닉네임 포함) / 설정 탭(신설 포함 다섯 개)
  `scrollWidth` vs `clientWidth`·탭 높이 / 변경 성공 `role="status"` 존재 / 같은 값 재제출 / 뒤로가기 버튼 복구 / 가로 스크롤 0px [실측 예정]. 캡처는 검증 후 삭제.
- 사후 판정: WED·BIR 각 `Conforms/Deviates/Unverified` + QVL 완료 판정 — 구현 후 기입.
- **Evidence(2026-09-10 실측, 브랜치 feat/user-nickname)**: 커밋 d2074c5·3a2f2ef·30af246·db3c14c·731a9d0·3916ede·c07db63·2d66228·751db15·c5ee681 [코드 git log].
  회귀 `uv run pytest -q` 2582 passed / 10 deselected / 80.01초 [실측](기준선 main 2547 passed / 83.33초 [실측 착수 시 재측정] → 신규 35건 [계산]). e2e 10 passed [실측].
  check 0 issues·`makemigrations --check` No changes·`sqlmigrate accounts 0006` = ADD COLUMN NULL → RunPython → SET NOT NULL → CREATE UNIQUE INDEX (LOWER) [실측].
  뮤테이션 증거 5건 [실측]: NICK-04 strip 제거 / NICK-07 iexact→exact(DB UniqueViolation이 최후 방어) / NICK-12 백필 필터 제거 / NICK-18 exclude 제거→200 / NICK-20 refresh 제거→헤더 오표시.
  브라우저(Chrome DevTools MCP, 320·768·1280px) [실측]: 페이지 가로 스크롤 0px, 헤더 69px 한 줄, 데스크톱 `.topbar-username` 텍스트=title=닉네임, 모바일 메뉴 패널 닉네임 줄, 설정 탭 5개(트랙 내부 스크롤 506px > 288px), 가입 input
  `autocomplete/maxlength/minlength/required`, 힌트 간격 4px, 중복 오류 aria-describedby/aria-invalid 연결, 성공 PRG `role="status"` 메시지, 콘솔 오류 0건. 캡처는 검증 후 삭제.
  사후 리뷰: **WED Conforms**(c07db63) / **BIR 1차 Deviates**(경쟁 창 IntegrityError 미번역, 계획 §C) → 751db15 수정(선등록 `SignupView`+`NicknameConflictFormMixin`, NICK-20·21) → **BIR 재판정 Conforms**.
  BIR 정보 1건: 가입 뷰 atomic 범위가 인증 메일 발송까지 포함(SMTP 실패 시 가입 롤백) — docs/BE/account-identity.md (g) 기록.
  계획 대비 편차 [실측 근거]: 백필 테스트는 CP10 대신 MigrationExecutor 0005→0006 실이주(NOT NULL 컬럼엔 NULL 행을 만들 수 없음) / 테스트는 `tests/auth/`에 배치 / pytest-django `admin_user` 픽스처 덮어쓰기(닉네임 없는 create_superuser로 31건 ERROR [실측]) /
  약관 라벨 `format_lazy`(모듈 수준 폼 임포트가 URLconf 순환 임포트 유발) / 가입 힌트는 `_auth_field.html` `hint` 인자(형제 배치 시 플렉스 gap으로 20px 이격 [실측]) / 경쟁 창 번역은 어댑터가 아니라 뷰 선등록(어댑터에서는 폼으로 되돌아갈 수 없음).
  QVL: 1차 보류(판정문 원본 미첨부 — 오케스트레이터 증거 파일 갱신 누락, 정정 기록) → 원본 첨부 후 재판정 결과는 채팅 보고에 기입.

## 검증 명령·기대 증거
- 표적: `uv run pytest -q tests/auth/test_nickname_*.py tests/auth/test_account_nickname_change.py` / `uv run python manage.py check` / `uv run python manage.py makemigrations --check --dry-run`
  / `uv run python manage.py sqlmigrate accounts 0006`(락 유발 문장 확인) / 로컬 왕복 `migrate accounts 0005` → `migrate accounts`(로컬·CI 전용, **운영 금지**)
- 경계 가드: `uv run pytest -q tests/core/test_architecture_boundaries.py tests/core/test_comment_language_guard.py tests/core/test_secret_literal_guard.py`
- 회귀: `uv run pytest -q` — 기준선 2547 passed [문서] 재측정 후 신규 20건 [계산] 이상 증가·실패 0 / e2e: `uv run pytest -q -m e2e tests/e2e` 10 passed [문서] 유지(`verified_user` 수정 필수)
- rg: 신규 nickname 출력 `|safe|mark_safe` 0건 [실측 예정].

## 사용자 결정 (★) — 권고안에 "승인"이면 그대로 진행
- ★1 백필 값: `회원<pk>`(권고) / `user_<hex>`
- ★2 — 배포 구조: **단일 배포로 확정**(U1 해소 — 실질 회원 0이라 교체 창·락 위험 없음, 사용자 진술 2026-09-10). expand-contract 대안 폐기.
- ★3 변경 화면: 비밀번호 재확인 없음 + 시간당 다섯 회 제한(권고)
- ★4 예약어: 브랜드·운영진·시스템 완전일치만(권고), 욕설 필터 이연
- ★5 계정 메뉴 패널에 닉네임 줄 신설(권고)
- ★6 `base.html:102` `role="status"` 한 줄 같은 트랙 수정(권고)
- U1 **해소(2026-09-10 사용자 진술: "지금 실질 회원은 없다")** — 운영 `accounts_user`는 슈퍼유저·시험 계정 수준 [사용자 진술, 미실측]. 따라서 ★2의 락 시간·
  교체 창 위험은 실질 0이며 **단일 배포로 확정**. 백필 RunPython은 남아 있는 소수 행(슈퍼유저 등)을 `회원<pk>`로 채우는 용도로 유지(NICK-11~14는 그대로 —
  빈 DB·소수 행 모두 통과해야 한다). 배포 후 확인 절의 `count(*) WHERE nickname IS NULL` → 0 항목은 유지.

## Deferred / 문서 대상 / 핸드오프
- 이연 목록은 위 "명시적 제외 / 이연". 문서 대상 §G. 핸드오프 핵심: 백필 값·예약 패턴 관계, 역적용 금지, 어댑터 저장 순서, 픽스처 세 곳 기본값.

---

