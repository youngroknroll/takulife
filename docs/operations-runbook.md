# Operations Runbook

takulife 운영자를 위한 실전 대응 가이드. 코드 변경 없음 — `config/settings.py`에 실제로 설정된 값만 인용한다.

## 1. Brute-force Lockout & Recovery (django-axes)

### 실제 설정값 (`config/settings.py`)

```python
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hours
AXES_LOCKOUT_PARAMETERS = ["ip_address"]
AXES_RESET_ON_SUCCESS = True
AXES_HTTP_RESPONSE_CODE = 429
AXES_LOCKOUT_TEMPLATE = "account/lockout.html"
AXES_USERNAME_FORM_FIELD = "login"
```

- **5회 실패**하면 잠금(`AXES_FAILURE_LIMIT`).
- 잠금은 **1시간(`AXES_COOLOFF_TIME`) 후 자동 해제**(no-action recovery).
- 로그인 성공 시 해당 계정의 실패 카운트 리셋(`AXES_RESET_ON_SUCCESS`).
- 잠금 응답 코드는 `429`, 템플릿은 `templates/account/lockout.html`.
- `AXES_USERNAME_FORM_FIELD = "login"` — allauth 로그인 폼이 식별자를 `login` 필드로 전송하므로, axes도 동일 필드를 읽어 시도를 기록한다.

### CRITICAL — 잠금은 IP 기준이다

`AXES_LOCKOUT_PARAMETERS = ["ip_address"]` 이므로 **잠금은 IP 단위로 걸린다.** 사용자명(계정) 단위가 아니다.

이 사실이 복구 명령 선택에 직접 영향을 준다:

| 상황 | 올바른 명령 | 틀린 명령(효과 없음) |
|---|---|---|
| 특정 IP가 잠긴 경우 | `uv run python manage.py axes_reset_ip <ip>` | `uv run python manage.py axes_reset_username <email>` |
| 전체 초기화(비상시) | `uv run python manage.py axes_reset` | - |

**주의:** `axes_reset_username <email>`은 해당 사용자명으로 기록된 시도 카운트만 지운다. 잠금 자체는 IP 파라미터에 걸려 있으므로, 이 명령을 실행해도 **IP 기반 잠금은 풀리지 않는다.** 사용자가 "로그인이 안 된다"고 문의하면, 운영자는 반드시 실제로 잠긴 대상이 IP라는 것을 인지하고 `axes_reset_ip`를 사용해야 한다.

### 확인된 axes 관리 명령 (`uv run python manage.py help` 실측)

```
[axes]
    axes_list_attempts
    axes_reset
    axes_reset_failure_logs
    axes_reset_ip
    axes_reset_ip_username
    axes_reset_logs
    axes_reset_username
```

자주 쓰는 명령:

```bash
# 특정 IP 잠금 해제 (1차 대응 — 가장 일반적인 케이스)
uv run python manage.py axes_reset_ip 203.0.113.10

# 전체 잠금/시도 기록 초기화 (비상시)
uv run python manage.py axes_reset

# 현재 잠긴/기록된 시도 목록 확인
uv run python manage.py axes_list_attempts
```

### 시도 기록 확인 위치

Django admin에서 `AccessAttempt`, `AccessLog` 모델로 실패/성공 시도 이력을 조회할 수 있다 (django-axes가 자동 등록).

### 무대응 복구

아무 조치도 하지 않으면 `AXES_COOLOFF_TIME = 1`(시간) 경과 후 자동으로 잠금이 풀린다. 급하지 않은 문의는 이 사실을 안내하는 것으로 충분하다.

## 2. allauth Rate Limits

### 실제 설정값

```python
ACCOUNT_RATE_LIMITS = {
    "signup": "5/m/ip,30/h/ip",
    "login_failed": "10/m/ip,5/300s/key",
    "reset_password": "20/m/ip,5/m/key",
}
```

- `signup`: IP당 분당 5회 + 시간당 30회.
- `login_failed`: IP당 분당 10회, **그리고 계정(key)당 5분에 5회**.
- `reset_password`: IP당 분당 20회, 계정(key)당 분당 5회.

### 동작 차이 — 429 vs 폼 거부

- 위 한도를 초과하면 allauth가 `templates/429.html`을 렌더링(HTTP 429)한다.
- 단, `login_failed`의 **계정(key) 단위 윈도우**가 소진되면 — 이는 axes의 IP 잠금과 별개로 — **올바른 비밀번호를 입력해도 로그인 폼이 인증을 거부**한다. 이것은 429 응답이 아니라 로그인 폼의 일반적인 실패 처리로 나타나므로, 사용자에게는 "비밀번호가 틀렸다"는 것과 구분이 잘 안 될 수 있다. 운영자가 문의를 받으면 axes의 `axes_list_attempts`와 함께 이 계정 단위 윈도우도 염두에 두어야 한다(단, 이 윈도우에는 별도의 리셋 관리 명령이 없고, 5분 경과 시 자동으로 풀린다).

## 3. SessionAuthentication Pin (DRF)

```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    ...
}
```

- DRF 기본값(`BasicAuthentication` 포함)을 그대로 두지 않고 `SessionAuthentication`만 남겼다.
- Basic 인증은 CSRF 검사를 우회하므로, 이를 허용하면 스태프 자격증명으로 위조된 크로스사이트 요청이 상태를 변경(mutate)할 수 있는 구멍이 생긴다. `SessionAuthentication`은 세션 인증에 CSRF를 강제한다.
- 결과: 이 앱은 **브라우저/세션 기반 전용**이다. API 엔드포인트에 Basic Auth로 접근하는 클라이언트(예: curl -u)는 지원되지 않는다. 서버 간 통합이 필요하면 별도의 인증 스킴을 새로 설계해야 한다(현재는 미지원).

## 4. Deployment WARNING — Reverse Proxy IP 해석 (가장 중요)

(2026-07-14 PR-0d로 해결: `TRUSTED_PROXY_COUNT` env + `core/ip.py` +
`AXES_CLIENT_IP_CALLABLE`. 아래는 배포 시 실제로 설정해야 하는 값이다.)

- axes의 잠금은 `ip_address` 기준이다. 리버스 프록시(nginx, 로드밸런서 등) 뒤에 배포하면, django-axes가 프록시 IP를 "클라이언트 IP"로 오인할 수 있다.
- 이 상태에서는:
  - 모든 요청이 동일한(프록시) IP에서 온 것으로 보여 **공격자 한 명이 5회 실패시키면 전체 사용자가 잠긴다.**
  - 반대로 실제 공격자별 IP가 분리되지 않아 **잠금 자체가 무의미해질 수도 있다**(공격자가 IP를 회전하지 않아도 프록시 IP 뒤에서 실사용자와 섞임).
- **프로덕션 배포 전 반드시** `TRUSTED_PROXY_COUNT` env를 실제 프록시 홉 수(보통 1)로 설정해야 한다. 이 값이 설정되면 `config/settings.py`가
  `AXES_CLIENT_IP_CALLABLE = "core.ip.get_client_ip"`로 배선하고, `core/ip.py`가
  `X-Forwarded-For`의 **오른쪽에서 n번째** 홉을 신뢰(왼쪽은 공격자가 위조 가능)하여
  `StaffActionLog.ip_address`와 axes 잠금 모두 동일한 파싱을 사용한다.
  미설정 시(로컬 dev 기본값)에는 `X-Forwarded-For`를 아예 읽지 않고 `REMOTE_ADDR`만
  사용한다 — 스푸핑 방어 기본값.
  이 프로젝트는 `django-ipware`를 설치하지 않으므로 axes 자체의
  `AXES_IPWARE_*` 설정은 죽은 설정이며 사용하지 않는다.

### `TRUSTED_PROXY_COUNT`의 전제 조건 — 프록시가 append/overwrite 해야 한다

`TRUSTED_PROXY_COUNT`는 각 신뢰 프록시 홉이 `X-Forwarded-For`에 실제
클라이언트 IP를 **덧붙이거나(append) 자신이 받은 값을 검증 후
재작성(overwrite)** 한다는 전제로만 안전하다. 프록시가 클라이언트가 보낸
헤더를 그대로 통과(passthrough)시키면, 그 프록시는 신뢰 홉으로 세지만
실제로는 아무 값도 검증하지 않으므로 클라이언트가 임의의
`X-Forwarded-For`를 주입해 오른쪽에서 n번째 자리를 직접 조작할 수 있다
— **passthrough 프록시는 신뢰 홉으로 세면 안 된다.**

복붙 가능한 설정 예시(nginx, append 방식):

```nginx
location / {
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_pass http://app_upstream;
}
```

`$proxy_add_x_forwarded_for`는 nginx가 수신한 `X-Forwarded-For`(있다면)
뒤에 실제 커넥션의 클라이언트 IP를 **덧붙인다** — passthrough가 아니다.
PaaS(managed load balancer 등)를 쓰는 경우 이 설정은 보통 플랫폼이 대신
관리하므로, T1/T2 확정 후 실제 사용할 PaaS의 공식 문서에서
"X-Forwarded-For 처리 방식"과 "신뢰 프록시 홉 수"를 반드시 확인한다.

### 비대칭 위험 — `TRUSTED_PROXY_COUNT`는 과대설정보다 과소설정이 안전하다

- **과대설정**(실제 프록시 홉 수보다 큰 값, 또는 passthrough 프록시를
  신뢰 홉으로 오산정): `X-Forwarded-For`의 왼쪽(공격자 제어 가능 영역)까지
  신뢰 구간으로 끌어들여 **스푸핑 우회로 이어진다** — 치명적. axes
  잠금과 `StaffActionLog.ip_address` 모두 위조된 IP를 실제 클라이언트로
  기록한다.
- **과소설정**(실제보다 작은 값, 또는 아예 미설정): `core.ip.get_client_ip`가
  `REMOTE_ADDR`(프록시 IP)로 폴백할 뿐이다 — 이전(PR-0d 이전) 동작과
  동일한 수준으로 **안전이 저하될 뿐, 새로운 스푸핑 경로는 열리지
  않는다.**
- 따라서 **실제 프록시 홉 수가 불확실하면 낮게 잡고(0 또는 미설정)
  스테이징에서 검증한 뒤에만 올린다.** 확신 없이 추측값을 프로덕션에
  바로 배포하지 않는다.

- 별개로, `SECURE_COOKIES` 환경변수가 설정되면(`os.environ.get("SECURE_COOKIES", "").lower() in ("1", "true", "yes")`) `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE`가 켜져 HTTPS에서만 쿠키가 전송된다. HTTPS 배포 시 이 환경변수를 반드시 설정한다.

### 배포 체크리스트 — 위조 X-Forwarded-For 스테이징 검증

- **스테이징에서 위조 `X-Forwarded-For`를 전송해, 앱이 기록하는 IP가
  영향받지 않는지 확인한다** (예: `curl -H "X-Forwarded-For: 1.2.3.4"
  https://staging.example/staff/home-categories/` 후
  `StaffActionLog.ip_address`가 실제 요청 발신 IP인지 위조 값
  `1.2.3.4`인지 확인). `TRUSTED_PROXY_COUNT`를 프로덕션 값으로 올리기
  **전** 반드시 이 검증을 거친다.
- axes 잠금과 프록시 IP 연동 자체는
  `tests/auth/test_auth_lockout.py::test_신뢰된_프록시_뒤에서는_공유_프록시_주소가_아닌_전달된_클라이언트_IP_기준으로_잠긴다`로
  자동화 검증돼 있다(같은 `REMOTE_ADDR`·다른 `X-Forwarded-For`의 실패
  로그인이 서로 다른 잠금 버킷으로 분리됨을 확인, 5회 연속 실행으로
  결정성 확인됨). 다만 이 테스트는 Django 테스트 클라이언트가 직접
  `X-Forwarded-For` 헤더를 주입하는 방식이라, **실제 프록시가 헤더를
  append/overwrite하는지는 검증하지 않는다** — 위 스테이징 curl 검증이
  그 갭을 메운다.

## 5. Staff Console Access (`/staff/`)

- `staff/permissions.py`의 `staff_console_required` 데코레이터가 모든 `/staff/` 뷰를 게이트한다.
- **익명 사용자** → `settings.LOGIN_URL`(`/accounts/login/`)로 리다이렉트(`next` 파라미터 보존).
- **로그인했지만 스태프가 아닌 사용자** → `403 PermissionDenied`(로그인 페이지로 되돌리지 않는다 — 이미 로그인된 상태에서 LOGIN_URL로 보내면 allauth의 인증됨 리다이렉트와 충돌해 무한 루프가 될 수 있기 때문).
- Django 기본 관리자 페이지(`/admin/`)는 슈퍼유저용 백업 경로로 계속 유지된다 — Staff Console 접근에 문제가 생기면 슈퍼유저는 `/admin/`으로 계정/권한을 직접 조작할 수 있다.

## 6. Migration Rollback — `archive` 0022 (`ActivityLogEntry`) 역적용 금지

- **`archive` 0022(`activitylogentry`) 마이그레이션을 명시적으로 역적용(`uv run python manage.py migrate archive <0022 이전 번호>`)하지 않는다.** 0022의 reverse 연산은 `DropModel`이라, 그때까지 쌓인 사용자 활동 이력(찜·상태 변경·방문 기록·굿즈 등록/정리)이 **전량 소실**된다.
- **코드만 롤백하는 경우는 안전하다** — 이전 이미지를 재배포해도 배포 entrypoint의 `migrate`는 코드에 없는(더 앞선) 마이그레이션을 자동으로 역적용하지 않는다. 즉 "코드는 이전 버전, 스키마는 0022 유지" 상태로 안전하게 되돌아간다.
- 위험한 것은 오직 **운영자가 직접 `migrate archive <0022 이전>`을 실행하는 경우**뿐이다.
- 스키마(테이블) 자체를 제거해야 하는 경우는 별도 승인과 보존 정책이 먼저 필요하다(`.docs/plans/2026-07-19-dual-calendar-service-design.md` §14).
