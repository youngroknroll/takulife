# Operations Runbook

oshilife 운영자를 위한 실전 대응 가이드. 코드 변경 없음 — `config/settings.py`에 실제로 설정된 값만 인용한다.

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
| 특정 IP가 잠긴 경우 | `python manage.py axes_reset_ip <ip>` | `python manage.py axes_reset_username <email>` |
| 전체 초기화(비상시) | `python manage.py axes_reset` | - |

**주의:** `axes_reset_username <email>`은 해당 사용자명으로 기록된 시도 카운트만 지운다. 잠금 자체는 IP 파라미터에 걸려 있으므로, 이 명령을 실행해도 **IP 기반 잠금은 풀리지 않는다.** 사용자가 "로그인이 안 된다"고 문의하면, 운영자는 반드시 실제로 잠긴 대상이 IP라는 것을 인지하고 `axes_reset_ip`를 사용해야 한다.

### 확인된 axes 관리 명령 (`python manage.py help` 실측)

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
python manage.py axes_reset_ip 203.0.113.10

# 전체 잠금/시도 기록 초기화 (비상시)
python manage.py axes_reset

# 현재 잠긴/기록된 시도 목록 확인
python manage.py axes_list_attempts
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

`config/settings.py`의 인라인 주석이 명시하는 그대로:

> NOTE (deployment): behind a reverse proxy, configure AXES_IPWARE_* so the real client IP is used — otherwise every request looks like the proxy IP and one attacker can lock out everyone. Do not enable in prod until the proxy is set.

- axes의 잠금은 `ip_address` 기준이다. 리버스 프록시(nginx, 로드밸런서 등) 뒤에 배포하면, django-axes가 프록시 IP를 "클라이언트 IP"로 오인할 수 있다.
- 이 상태에서는:
  - 모든 요청이 동일한(프록시) IP에서 온 것으로 보여 **공격자 한 명이 5회 실패시키면 전체 사용자가 잠긴다.**
  - 반대로 실제 공격자별 IP가 분리되지 않아 **잠금 자체가 무의미해질 수도 있다**(공격자가 IP를 회전하지 않아도 프록시 IP 뒤에서 실사용자와 섞임).
- **프로덕션 배포 전 반드시** `AXES_IPWARE_*` 계열 설정(또는 동등한 신뢰 프록시 IP 해석 설정, 예: `django-ipware` 연동)을 구성해 실제 클라이언트 IP가 사용되도록 해야 한다. 이 설정이 끝나기 전에는 axes를 프로덕션에서 활성화하지 않는다.
- 별개로, `SECURE_COOKIES` 환경변수가 설정되면(`os.environ.get("SECURE_COOKIES", "").lower() in ("1", "true", "yes")`) `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE`가 켜져 HTTPS에서만 쿠키가 전송된다. HTTPS 배포 시 이 환경변수를 반드시 설정한다.

## 5. Staff Console Access (`/staff/`)

- `staff/permissions.py`의 `staff_console_required` 데코레이터가 모든 `/staff/` 뷰를 게이트한다.
- **익명 사용자** → `settings.LOGIN_URL`(`/accounts/login/`)로 리다이렉트(`next` 파라미터 보존).
- **로그인했지만 스태프가 아닌 사용자** → `403 PermissionDenied`(로그인 페이지로 되돌리지 않는다 — 이미 로그인된 상태에서 LOGIN_URL로 보내면 allauth의 인증됨 리다이렉트와 충돌해 무한 루프가 될 수 있기 때문).
- Django 기본 관리자 페이지(`/admin/`)는 슈퍼유저용 백업 경로로 계속 유지된다 — Staff Console 접근에 문제가 생기면 슈퍼유저는 `/admin/`으로 계정/권한을 직접 조작할 수 있다.
