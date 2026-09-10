# 회원 닉네임(트랙 29) 가드레일

이메일이 사실상 표시 이름을 대체하던 문제를 고친 트랙이 지키는 경계와 왜
그렇게 정했는지를 남긴다. 작업 일지가 아니라 이후 이 코드를 건드릴 때
깨뜨리기 쉬운 계약만 적는다.

## (a) 닉네임=공개 예정 식별자, 이메일=비공개 경계 — 스태프 화면은 이메일 유지

`accounts/models.py:14` `User.nickname`(`CharField(max_length=20)`)이
게시글·헤더 등 공개 표시용 식별자다. 이메일은 여전히 로그인 식별자이자
비공개 경계이며(`USERNAME_FIELD = "email"`), `docs/BE/staff-account-operations.md`
(e)의 운영 식별자 결정을 이 트랙이 바꾸지 않는다 — 스태프 화면은 계속
이메일로 대상을 표시한다.

## (b) 검증 파이프라인 순서 — 폼·매니저 두 경로가 `accounts/validators.py` 하나를 공유

`validate_nickname`(`accounts/validators.py:42-54`)은 항상 이 순서로
거부한다: ① 길이(`MIN_LENGTH=2`·`MAX_LENGTH=20` [코드], `code="min_length"`/
`"max_length"`) → ② `NICKNAME_PATTERN`(`^[0-9A-Za-z_가-힣]{2,20}$`)
`fullmatch` 실패(`code="invalid"`, 자모·전각·제로폭·공백 전부 거부, silent-strip
없음) → ③ 예약어(`RESERVED_NICKNAMES`, 영문 11·한글 8 [코드] `lower()`
완전일치) 또는 예약 패턴(`RESERVED_NICKNAME_PATTERN = r"^회원\d+$"`,
`code="reserved"`). `normalize_nickname`(NFKC+strip)은 별도 함수라 호출자가
먼저 불러야 한다 — `validate_nickname` 자체는 정규화하지 않는다.

대소문자 무시 중복은 두 겹이다: 폼(`accounts/forms.py`의
`TermsAgreementFormMixin.clean_nickname`·`NicknameChangeForm.clean_nickname`)의
`filter(nickname__iexact=value)` 사전 검사 + DB
`UniqueConstraint(Lower("nickname"), name="accounts_user_nickname_ci_unique")`
(`accounts/models.py:40-44`) 최종 방어. 매니저(`accounts/managers.py`
`_create_user`)도 같은 `normalize_nickname`→`validate_nickname`을 거치므로
`create_user(nickname="admin")` 직접 호출도 거부된다(폼을 우회하는 경로 대비).

## (c) 저장 순서 제약 — allauth의 INSERT-후-custom_signup 순서 때문에 어댑터가 필요하다

allauth `save_user`가 INSERT를 커밋한 뒤에야 `custom_signup`을 부른다 —
`custom_signup`에서 nickname을 실으면 이미 NOT NULL 제약이 있는 컬럼에 빈
INSERT가 먼저 나가 실패한다. `accounts/adapters.py`의
`AccountAdapter.save_user`가 `super()` 호출 **전에**
`user.nickname = form.cleaned_data["nickname"]`을 설정해 첫 INSERT에 함께
싣는다. `settings.ACCOUNT_ADAPTER = "accounts.adapters.AccountAdapter"`로
등록돼 있고, 소셜 가입도 같은 account adapter를 거치므로
`SOCIALACCOUNT_ADAPTER`는 별도로 두지 않았다.

## (d) 백필 `회원<pk>`와 예약 패턴의 관계 — RunPython reverse는 noop, 역적용 금지

`accounts/migrations/0006_user_nickname.py`는 한 파일에 4단계를 묶는다:
`AddField(null=True)` → `RunPython(backfill_nickname, RunPython.noop)`
(NULL/빈 문자열 행만 `회원{pk}`로 채움) → `AlterField(null=False)` →
`AddConstraint`. `RESERVED_NICKNAME_PATTERN`이 `^회원\d+$`를 예약하는 이유가
바로 이 백필 값이다 — 백필 값과 사용자가 이후 고른 값이 영원히 겹치지
않게 막는다.

reverse는 `RunPython.noop`이다(백필 전 값과 이후 실사용자가 고른 값을
구분할 표식이 없어 되돌릴 수 없다). **`manage.py migrate accounts 0005`로
이 마이그레이션을 역적용하지 않는다** — `AlterField(null=False)`와
`AddConstraint`가 역방향으로도 실행되면서 백필된 `nickname` 값 자체가
소실된다(컬럼은 남아도 값이 사라진다). 배포 실패 시 대응은
`docs/deploy-runbook.md` §5 참고(코드 되돌림 + 재배포만 안전).

## (e) 닉네임 변경 빈도 제한 — allauth `ACCOUNT_RATE_LIMITS` 미적용, 직접 카운트

`/accounts/settings/nickname/`(`accounts.views.nickname_change`)은 allauth
뷰가 아니라 커스텀 뷰라 `settings.ACCOUNT_RATE_LIMITS`가 덮지 않는다.
`accounts/services.py`의 `is_nickname_change_throttled`/`register_nickname_change`가
캐시 키 `nickname-change:{pk}`로 직접 센다 —
`NICKNAME_CHANGE_LIMIT = 5`회 `[코드]` / `NICKNAME_CHANGE_WINDOW_SECONDS = 3600`초
`[코드]` 고정 창(마감 시각을 레코드에 저장, `delete_attempts`와 동일 패턴).
뷰는 폼 유효성 검사 **전에** 스로틀을 먼저 확인해 한도 초과 시 DB를 쓰지
않는다.

## (f) `format_lazy` 약관 라벨 — 모듈 수준 `.format(reverse_lazy)`는 URLconf 순환 임포트를 유발한다

`accounts/forms.py`의 `_TERMS_AGREEMENT_LABEL`은 `mark_safe(format_lazy(...))`로
쓴다. `'...'.format(terms=reverse_lazy(...))`처럼 문자열 `.format()`을 쓰면
lazy 객체가 **즉시 평가**돼, `accounts/views.py`가 모듈 수준에서
`from .forms import NicknameChangeForm`을 하는 순간 URLconf가 아직 로딩되지
않은 상태에서 `reverse_lazy`가 강제로 풀려 `config.urls has no patterns`로
죽는다. `format_lazy`는 실제 렌더 시점까지 평가를 미루므로 이 순환을
피한다 — forms.py에 새 URL 참조 라벨을 추가할 때 이 함정을 다시 만들지
않는다.

## (g) 가입 경쟁 창의 `IntegrityError`는 nickname 필드 오류로 번역된다

폼의 `iexact` 사전 중복 검사와 실제 INSERT 사이에는 창이 있다 — 두 요청이
거의 동시에 같은 닉네임으로 가입하면 사전 검사를 둘 다 통과하고 DB
`UniqueConstraint`가 최후 방어로 작동한다. `accounts/views.py`의
`NicknameConflictFormMixin.form_valid`가 allauth `form_valid`를
`transaction.atomic()`으로 감싸고, `accounts/services.py`의
`is_nickname_conflict(exc)`(`exc.__cause__.diag.constraint_name`이
`accounts_user_nickname_ci_unique`인지 판별)로 nickname 제약 위반만 골라
`form.add_error("nickname", NICKNAME_DUPLICATE_MESSAGE)`로 200 재렌더한다
— 다른 제약(이메일 등) 위반은 그대로 재전파해 500이 유지된다.

Current fact: 가입 뷰의 atomic 블록은 allauth `form_valid` 전체
(`complete_signup`의 인증 메일 발송 포함)를 감싸므로, 닉네임 충돌과 무관한
예외(예: SMTP 실패)에서도 계정 생성이 롤백된다 — 이전(`ATOMIC_REQUESTS`
미설정, 자동커밋)과 달라진 실패 의미이며 재가입 재시도로 복구된다.

가입 뷰 `accounts.views.SignupView`(`NicknameConflictFormMixin` +
allauth `SignupView`)는 `config/urls.py`에서 `include("allauth.urls")`보다
먼저 선등록한다(url name `account_signup` 유지). allauth
`SignupView.dispatch`가 이미 자체 `rate_limit`을 걸므로 이 뷰에는 별도
데코레이터를 추가하지 않는다(`SocialSignupView`는 자체 레이트리밋이 없어
계속 필요).

닉네임 변경 뷰(`accounts.views.nickname_change`)도 같은 방식으로 감싸되,
실패 시 `request.user.refresh_from_db(fields=["nickname"])`로 메모리
상의 `request.user.nickname`(실패한 저장 시도로 이미 바뀐 값)을 DB의
원래 값으로 되돌린 뒤 재렌더한다 — 그러지 않으면 헤더·메뉴 패널이 실패한
닉네임을 잠깐 보여준다.

Evidence: `tests/auth/test_nickname_signup.py`의 NICK-21, `tests/auth/test_account_nickname_change.py`의
NICK-20 — 둘 다 폼의 `clean_nickname`을 `monkeypatch`로 우회해 사전 검사를
건너뛴 경쟁 창을 재현한다.
