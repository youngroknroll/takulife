# 비밀번호 해시(트랙 61) 가드레일

## (a) 현재 사실

운영 `PASSWORD_HASHERS`는 3개다 `[코드 config/settings.py PASSWORD_HASHERS]`.

- 첫 항목 `accounts.hashers.CalibratedArgon2PasswordHasher`: 새 비밀번호와
  바뀐 비밀번호를 저장한다.
- `PBKDF2PasswordHasher`, `PBKDF2SHA1PasswordHasher`: 기존 해시를 확인하는
  데만 쓴다.

`CalibratedArgon2PasswordHasher`는 Argon2id다 `[코드 accounts/hashers.py]`.

- `memory_cost` 19,456 KiB, `time_cost` 24, `parallelism` 1.
- `algorithm`은 Django 기본 `"argon2"`를 그대로 상속한다.

의존성은 `argon2-cffi` 25.1.0과 `argon2-cffi-bindings` 26.2.0이다
`[코드 uv.lock]`.

기존 PBKDF2-SHA256 해시(반복 1,000,000회
`[코드 django/contrib/auth/hashers.py:321]`)는 그 사용자가 로그인에
성공할 때 Argon2id로 바뀐다. Django 기본 동작이다
`[코드 hashers.py:58-59, base_user.py:106-110]`.

테스트 설정은 MD5 하나뿐이다 `[코드 config/settings_test.py:22]`. 그래서
테스트에서 운영 해셔를 쓰려면 `tests/auth/conftest.py`의
`production_password_hashers`와 `override_settings`를 쓴다.

`ACCOUNT_PREVENT_ENUMERATION = True`를 명시했다 `[코드 config/settings.py]`.

## (b) 결정 (2026-11-20 사용자 승인)

매개변수: 메모리는 OWASP 최소치(19 MiB)를 유지하고 `time_cost`만 올려,
해시 1회 시간을 기존 PBKDF2와 비슷하게 맞췄다.

이유: 운영 워커가 1개다(`WEB_CONCURRENCY=1`
`[문서 docs/deploy-runbook.md §1 WEB_CONCURRENCY 행]`). 메모리가 넘쳐
워커가 죽으면 서비스 전체가 멈춘다. 운영 인스턴스 메모리 한도는 어디에도
기록돼 있지 않다.

비교한 안을 표로 남긴다.

| 안 | 해시 1회 | 최대 메모리 증가 | 메모리×반복 | 실패 로그인(해시 2회) |
|---|---|---|---|---|
| 이전 PBKDF2 1,000,000회 | 0.209 s | 0.1 MiB | — | 0.418 s |
| Django 기본(m=102,400 KiB, t=2, p=8) | 0.034 s | 100.3 MiB | 200.0 MiB·회 | 0.068 s |
| OWASP 최소(m=19,456 KiB, t=2, p=1) | 0.017 s | 19.1 MiB | 38.0 MiB·회 | 0.034 s |
| 채택(m=19,456 KiB, t=24, p=1) | 0.197 s | 19.7 MiB | 456.0 MiB·회 | 0.394 s |

해시 1회·최대 메모리 증가는 로컬 Apple M1에서 해셔 하나만 돌린
프로세스의 5회 중앙값과 최대 RSS 증가다 `[실측 로컬 2026-11-20]`.
채택 행은 구현한 `CalibratedArgon2PasswordHasher`를 같은 방법으로 2회
재 첫 회 값을 적었다(1회 0.197 s·0.227 s, 메모리는 두 번 모두 19.7 MiB)
`[실측 로컬 2026-11-20]`. 메모리×반복과 실패 로그인은
`[계산 m×t, 1회 시간×2]`이다. 실패 로그인의 실제 종단 시간은 (d)에
있다.

t=24 결정 근거: PBKDF2 1,000,000회와 Argon2id를 번갈아 15쌍 잰 쌍별
시간 비율의 중앙값 `[실측 로컬, 아래 Evidence 스크립트, 2026-11-20]`.

- t=22: 0.91배
- t=24: 1.03배(최소 0.72~최대 1.25)
- t=26: 1.10배
- t=28: 1.13배

기존 해시 전환: 로그인할 때 하나씩 바꾼다. 데이터 마이그레이션으로
감싸는 방식은 쓰지 않았다. 배포 순간 모든 세션이 끊기고, 아래 (d)
타이밍 차이도 줄이지 못하기 때문이다.

## (c) 가드레일

1. 목록 규칙. 이 규칙은 `tests/core/test_test_settings_boundary.py`의
   계약 테스트가 고정한다.
   - Argon2 해셔가 첫 항목이고, PBKDF2 두 항목은 유지한다.
   - `argon2` 알고리즘 항목은 하나만 둔다. 알고리즘별 사전에서는 마지막
     항목이 이긴다 `[코드 hashers.py:131-132]`.
   - 설치되지 않은 패키지가 필요한 해셔(BCryptSHA256 등)는 넣지 않는다.
2. 매개변수를 바꿀 때
   - `algorithm`은 그대로 둔다. 그러면 Django `must_update`가 다음
     로그인 때 다시 해시한다 `[코드 hashers.py:452-460]`.
   - Argon2는 `harden_runtime`이 아무것도 하지 않는다
     `[코드 hashers.py:462-465]`. 그래서 옛 매개변수 해시와 새 매개변수
     해시 사이의 응답 시간 차이가 전환 기간 동안 남는다.
   - 바꾸기 전에 Evidence 스크립트로 다시 잰다.
3. 롤백 규칙 (런북 §5와 같은 문안)
   - argon2-cffi 추가 이전 이미지로 되돌리지 않는다.
   - Argon2 해셔를 목록에 둔 채 PBKDF2를 첫 항목으로 올리는 설정 변경만
     배포한다. 코드와 의존성은 그대로 둔다.
   - Argon2 해셔가 목록에서 사라지면 이미 전환된 사용자는 로그인할 수
     없고, 복구 방법은 그 사용자의 비밀번호 재설정뿐이다
     `[코드 hashers.py:44-56 — 알 수 없는 해시는 가짜 실행 뒤 False]`.
   - 이 롤백은 env 토글이 아니다. `config/settings.py` 코드 커밋 →
     main PR → deploy PR 머지(`docs/deploy-runbook.md` §7)를 거친다.
4. 로그인한 사용자에게 비밀번호를 다시 확인할 때
   - setter가 없는 모듈 함수
     `django.contrib.auth.hashers.check_password(raw, user.password)`를
     쓴다.
   - 모델 메서드 `user.check_password`는 해시를 바꾼다. 해시가 바뀌면
     세션 해시가 달라져 다음 요청에서 로그아웃된다
     `[코드 django/contrib/auth/__init__.py:312-334]`.
   - 현재 적용 위치는 두 곳이다.
     - `accounts/forms.py` `EmailChangeForm.clean_current_password`.
     - `accounts/forms.py` `PasswordChangeForm.clean_oldpassword`.
       allauth `ChangePasswordForm`을 `ACCOUNT_FORMS["change_password"]`로
       교체한 것이다 `[코드 config/settings.py ACCOUNT_FORMS]`. 교체한
       이유: 원본은 새 비밀번호를 검증하기 전에 해시를 바꾼다. 그래서
       새 비밀번호가 거부되면 폼은 실패하는데 해시는 이미 바뀌어 다음
       요청에서 로그아웃됐다
       `[코드 allauth/account/forms.py:48-55,595-599]`.
   - 계정 삭제(`web/views/account.py`)는 확인 직후 로그아웃하므로
     해당하지 않는다.
   - 비밀번호를 다시 확인하는 화면을 새로 만들 때도 같은 규칙을 따른다.
   - 라이브러리 코드도 대상이다. allauth 안에서 모델 `check_password`를
     부르는 곳은 셋이다
     `[실측 rg --no-ignore -n '\.check_password\(' .venv/lib/python3.13/site-packages/allauth, 테스트 제외]`.
     - 로그인 백엔드 `allauth/account/auth_backends.py:108`: 해시가
       바뀐 뒤에 같은 사용자 객체로 세션을 만들어 안전하다.
     - 비밀번호 변경 폼 `allauth/account/forms.py:597`: 위에서
       교체했다.
     - headless 비밀번호 변경 입력
       `allauth/headless/account/inputs.py:183`: 지금은
       `INSTALLED_APPS`에 headless가 없어 닿지 않는다. headless를
       켜면 같은 규칙을 적용해야 한다.
   - 재인증 `allauth/account/adapter.py:827-843`(`reauthenticate`)도
     `authenticate`를 거쳐 해시를 바꾼다. 다만
     `ACCOUNT_REAUTHENTICATION_REQUIRED` 기본값이 False이고
     `[코드 allauth/account/app_settings.py:549-550]` 저장소에 설정이
     없어 지금은 닿지 않는다. 켜면 같은 확인이 필요하다.
   - allauth를 올리거나 새 allauth 화면을 켤 때는 위 rg를 다시 돌린다.
5. 해셔는 처음 쓸 때 불러온다 `[코드 hashers.py:116-127]`.
   - 그래서 `manage.py check`와 Docker 헬스 체크로는 해셔 설정 오류를
     잡지 못한다.
   - 해셔나 의존성을 바꾸면 배포 이미지에서 해시를 한 번 실제로 만들어
     확인한다. 명령은 아래 Evidence에 있다.
   - CI `docker` 잡의 'Hash a password with the production hasher'
     단계가 운영 설정으로 해시 1회를 실제로 만들어 첫 해셔가
     Argon2id인지 확인한다 `[코드 .github/workflows/ci.yml]`.

## (d) 알려진 효과와 한계

계정 존재 여부의 타이밍 노출. 판정은 낮음이고 차단 사유가 아니다.

- 노출 범위: 전환 기간에 "가입했고 배포 뒤 아직 로그인하지 않은 계정"은
  틀린 비밀번호를 넣었을 때 PBKDF2로 검증된다. 그래서 없는 이메일
  (Argon2 더미)과 응답 시간이 다를 수 있다.
- Django는 알고리즘이 바뀌는 이 경우를 막지 않는다
  `[코드 hashers.py:62-65 주석]`.
- 로컬 종단 측정(테스트 클라이언트, 20회, 중앙값과 최소~최대)
  `[실측 로컬 2026-11-20]`:
  - 변경 전(PBKDF2 첫 항목):
    - 없는 이메일 0.475 s(0.452~1.088)
    - PBKDF2 사용자 틀린 비밀번호 0.468 s(0.455~0.488)
    - Argon2 사용자 틀린 비밀번호 0.452 s(0.398~0.786)
  - 변경 후(운영 목록):
    - 없는 이메일 0.471 s(0.451~0.962)
    - PBKDF2 사용자 틀린 비밀번호 0.481 s(0.465~1.111)
    - Argon2 사용자 틀린 비밀번호 0.477 s(0.414~0.995)
  - 변경 후 "PBKDF2 사용자 틀린 비밀번호"와 "없는 이메일"의 중앙값
    차이: 0.010 s `[계산]`. 두 범위는 겹친다.
- 프로세스 안에서 잰 값이라 네트워크 지연이 없다. 따라서 이 값은
  구분 가능성의 상한이다.
- 시도 횟수 제한: axes는 IP당 실패 5회에 1시간 잠근다
  `[코드 config/settings.py AXES_FAILURE_LIMIT·AXES_COOLOFF_TIME]`.
  allauth `login_failed`는 "10/m/ip,5/300s/key"다
  `[코드 config/settings.py ACCOUNT_RATE_LIMITS]`.

다른 기기 세션이 한 번 끊긴다. 사용자가 배포 뒤 처음 로그인해 해시가
바뀌면 같은 사용자의 다른 기기 세션이 끊긴다(세션 해시는 비밀번호
필드의 HMAC `[코드 base_user.py:135-137]`). 사용자당 한 번이다. 두
기기에서 거의 동시에 로그인하면 서로의 세션을 끊을 수 있다.

- 확인 절차: 클라이언트 A·B가 PBKDF2 상태로 로그인한다 → 운영 목록을
  적용한다 → A만 다시 로그인한다(저장 접두 `argon2`) → A의
  `/accounts/settings/`는 200, B는 302로
  `/accounts/login/?next=/accounts/settings/`가 된다
  `[실측 로컬 2026-11-20]`.

다시 로그인하지 않은 사용자는 PBKDF2 1,000,000회로 남는다. 이 값은
OWASP Password Storage Cheat Sheet의 PBKDF2-HMAC-SHA256 권장 600,000회보다
높다 `[문서 OWASP Password Storage Cheat Sheet]`.

운영 CPU에서의 시간 비율은 재지 않았다. 로컬 기준만 있다. Render Shell을
쓸 수 있으면 Evidence 스크립트를 한 번 돌려 확인한다.

새 네이티브 의존성의 공개 기간이 짧다.

- `argon2-cffi-bindings`는 `pyproject.toml`에 직접 버전 제약이 없는
  전이 의존성이다.
- 26.2.0은 공개 7일째에 들어왔다 `[실측 uv.lock upload-time 2026-11-13]`
  `[계산]`.
- 이번 배포는 `uv sync --frozen`이 lock의 해시로 고정해 재현된다
  `[코드 Dockerfile]`.
- 다음 의존성 갱신(`uv lock --upgrade` 등)에서는 새 bindings 버전의
  공개일·변경 기록·이슈를 먼저 확인한다.
- CI `audit` 잡은 알려진 취약점만 본다
  `[코드 .github/workflows/ci.yml audit 잡]`.

## (e) 배포 뒤 확인 (운영자 몫)

- 본인이 한 번 로그인한 뒤
  `psql "$DATABASE_URL" -c "SELECT split_part(password, '\$', 1) FROM accounts_user WHERE email = '<본인 이메일>';"`를
  실행한다. 결과가 `argon2`이면 된다. 해시의 나머지 부분은 출력하지
  않는다.
- Render 로그에서 `Perhaps out of memory?`(gunicorn이 SIGKILL로 죽은
  워커에 남기는 문구 `[코드 gunicorn/arbiter.py:621-627]`)와
  `WORKER TIMEOUT (pid:`를 검색한다.
- 로그인 경로(`/accounts/login/`) 500이 없는지 본다.
- 이 확인은 런북 §3 23번과 같다.

## (f) Evidence

측정 스크립트 전문. 실행 명령은 저장소 루트에서 `uv run python -I <파일>`이다.
argon2-cffi는 이제 프로젝트 의존성이라 `--with`는 필요 없다.

```python
"""PBKDF2 1,000,000회와 Argon2id(m=19456 KiB, p=1, t)를 번갈아 15쌍 재고, 쌍별 시간 비율의 중앙값을 낸다."""
import hashlib, os, statistics, time
import argon2.low_level as ll

PW = b"correct horse battery"
salt = os.urandom(16)

def once(f):
    t = time.perf_counter(); f(); return time.perf_counter() - t

for t in (22, 24, 26, 28):
    ratios, pbs, ars = [], [], []
    for _ in range(15):
        p = once(lambda: hashlib.pbkdf2_hmac("sha256", PW, salt, 1_000_000, 32))
        a = once(lambda: ll.hash_secret_raw(PW, salt, t, 19456, 1, 32, ll.Type.ID))
        ratios.append(a / p); pbs.append(p); ars.append(a)
    print(f"t={t}\tpbkdf2 med {statistics.median(pbs):.3f}s\targon2 med {statistics.median(ars):.3f}s"
          f"\tratio med {statistics.median(ratios):.2f} (min {min(ratios):.2f}, max {max(ratios):.2f})")
```

(b) 표의 해시 1회·최대 메모리 증가 측정 방법: 한 프로세스에서
`django.conf.settings.configure()`·`django.setup()` 뒤 해셔 인스턴스로
`encode(password, salt())`를 5회 돌려 시간 중앙값을 내고, 앞뒤
`resource.getrusage(RUSAGE_SELF).ru_maxrss` 차이(macOS는 바이트 단위)를
MiB로 바꾼다. 해셔마다 프로세스를 따로 띄운다.

배포 이미지 해시 확인 명령: `docker build --platform linux/amd64 -t takulife-t61 .`
뒤
`docker run --rm --platform linux/amd64 --entrypoint python -e DJANGO_SETTINGS_MODULE=config.settings -e SECRET_KEY=<가짜 값> -e ALLOWED_HOSTS=localhost -e DEBUG=false takulife-t61 -c "import django; django.setup(); from django.contrib.auth.hashers import make_password; print(make_password('x').split('\$')[3])"`
→ `m=19456,t=24,p=1` `[실측 로컬 2026-11-20]`. 같은 내용이 CI `docker`
잡에도 있다.

관련 테스트:

- `tests/core/test_test_settings_boundary.py`: 해셔 목록 계약, 열거 방지
- `tests/auth/test_password_hashing.py`: 새 비밀번호 접두, 매개변수
- `tests/auth/test_password_hash_upgrade.py`: 로그인 전환, 이메일 변경
  세션, 틀린 비밀번호, `password_changed_at`, 비밀번호 변경 거부 뒤 세션
- `tests/auth/test_password_change.py`: 비밀번호 변경의 현재 비밀번호
  확인
