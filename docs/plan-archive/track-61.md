# 트랙 61: 비밀번호 해시를 Argon2id로 전환 (2026-11-20) [v5 — 사용자 승인 2026-11-20: D1=C(t=24), D2=A, 범위 추가 2건 승인. v5: 사용자 요청 "오류가 있는지 검토" 뒤 독립 검토 발견 반영]

> 사용자 지시: "Argon2부터 계획 작성" (2026-11-20). 그 전 대화: "argon2를 이용해서 암호화를 강력하게 하고" (2026-11-19).
> 계획서 위치: `prompt_plan.md`는 사용자가 비우기 전이라(688줄 [실측 wc]) 트랙 60처럼 이 파일에 둔다. 비워지면 Edit로 옮긴다.

## 1. 목표

새로 저장하는 비밀번호 해시를 Django 기본 PBKDF2-SHA256에서 Argon2id로 바꾼다. 기존 사용자 해시는 로그인에 성공할 때 Argon2id로 바뀐다. 로그인·가입·재설정·비밀번호 변경 동작과 기존 보호 장치(axes 잠금, allauth 속도 제한, 이메일 인증 필수)는 그대로 둔다.

## 2. 현재 사실

| 항목 | 값 | 출처 |
|---|---|---|
| 운영 해셔 | `PASSWORD_HASHERS` 미설정 → Django 기본 목록 5개(PBKDF2, PBKDF2SHA1, Argon2, BCryptSHA256, Scrypt 순), 첫 항목 PBKDF2-SHA256 | `[실측 rg PASSWORD_HASHERS config/]` `[코드 django/conf/global_settings.py:544-550]` |
| 해셔 적재 시점 | `get_hashers()`가 처음 불릴 때 `import_string` — `manage.py check`·Docker 헬스 체크는 해셔를 적재하지 않는다 | `[코드 hashers.py:116-127]` |
| 해셔 캐시와 테스트 | `override_settings(PASSWORD_HASHERS=…)` 진입·종료 때 `setting_changed` → 캐시 비움 | `[코드 hashers.py:134-139]` |
| `hasher=` 인자 사용 | 0건 — 가입·변경·재설정·`createsuperuser`는 모두 기본(첫) 해셔를 쓴다 | `[실측 rg -n "hasher=" --type py -g '!.venv/**' . → 0]` |
| 세션 해시 갱신 호출 | 저장소 코드 0건(allauth 비밀번호 변경 흐름 안에만 있다) | `[실측 rg update_session_auth_hash -g '!.venv/**' → 0]` |
| PBKDF2 반복 횟수 | 1,000,000회 | `[코드 .venv/.../django/contrib/auth/hashers.py:321]` |
| Django 버전 | 5.2.17 | `[실측 uv run python -c "import django"]` |
| argon2 패키지 | 미설치(`uv.lock`에 argon2 0건) | `[실측 rg -c argon2 uv.lock]` |
| 해셔 계약 테스트 | 운영 설정 첫 해셔 == PBKDF2를 고정 | `[코드 tests/core/test_test_settings_boundary.py:55-62]` |
| 테스트 해셔 | MD5 하나만(테스트 설정) — 테스트에서는 해시 전환이 절대 일어나지 않는다 | `[코드 config/settings_test.py:20]` |
| 운영 워커 | 코드 기본값은 3개 `[코드 docker/entrypoint.sh:19]`, Render가 `WEB_CONCURRENCY=1`을 넣어 운영은 1개 `[문서 docs/deploy-runbook.md:70]`. `--threads` 미설정(sync 워커) `[코드 docker/entrypoint.sh:17-22]` → 지금 운영에서 동시에 도는 해시는 1개. 이 env가 바뀌면 R5 가정도 바뀐다 | 위 |
| 실패 로그인 1회의 해시 횟수 | 2회 — ModelBackend 1회 + allauth 백엔드 1회(없는 이메일이면 두 백엔드가 각각 기본 해셔로 더미 해시). axes 백엔드는 해시하지 않는다 | `[코드 config/settings.py:463-469,478]` `[코드 allauth/account/auth_backends.py:86-101]` `[코드 django/contrib/auth/backends.py:66-69]` (SRR 추적, 오케스트레이터 재확인) |
| 로그인 실패 제한 | axes IP당 5회/1시간 `[코드 config/settings.py:560-561]`, allauth `login_failed` "10/m/ip,5/300s/key" `[코드 config/settings.py:549]` | 위 |
| 다른 계정 열거 경로 | allauth `PREVENT_ENUMERATION` 기본 True `[코드 allauth/account/app_settings.py:44-45]`, 저장소에서 재정의 없음 `[실측 rg ACCOUNT_PREVENT_ENUMERATION config/ → 0]` — 기본값에 기대고 있을 뿐 명시되지 않았다 | 위 |
| bcrypt 패키지 | 미설치 `[실측 rg -c '^name = "bcrypt"' uv.lock → 0]`. 그런데 지금 Django 기본 목록에 `BCryptSHA256PasswordHasher`가 들어 있어, 그 형식 해시를 만나면 `_load_library`가 ValueError를 낸다 `[코드 hashers.py:227]` | 위 |
| 운영 인스턴스 메모리 한도 | 기록 없음 | `[실측 rg -i "512 ?MB\|인스턴스\|starter" docs/ 메모리]` |
| 세션 무효화 기준 | 세션 해시 = 비밀번호 필드의 HMAC → 해시가 바뀌면 그 사용자의 기존 세션이 끊긴다 | `[코드 django/contrib/auth/base_user.py:135-137]` |
| 해시 전환 시점 | `check_password` 성공 + 선호 해셔와 다르면 `set_password` 후 `save(update_fields=["password"])` | `[코드 base_user.py:106-110]` `[코드 hashers.py:58-59]` |
| 알고리즘 변경 시 타이밍 보호 | Django는 알고리즘이 바뀌면 타이밍 열거를 막지 않는다고 명시 | `[코드 hashers.py:62-65 주석]` |
| 존재하지 않는 계정 | 기본(첫) 해셔로 한 번 해시해 시간을 맞춘다 | `[코드 django/contrib/auth/backends.py:66-69]` `[코드 allauth/account/auth_backends.py:100]` |
| 로그인 중 비밀번호 재입력 경로 | 계정 삭제 `web/views/account.py:195`(직후 logout `:212`), 이메일 변경 `accounts/forms.py:104`, allauth 비밀번호 변경(변경 뒤 `update_session_auth_hash` `allauth/account/internal/flows/password_change.py:51`) | `[코드]` |
| `password_changed_at` | allauth 신호 3종(changed/set/reset)에서만 기록 — 해시 전환은 신호를 내지 않는다(추정, T61-5로 확인) | `[코드 accounts/models.py:25-32]` |
| allauth 재인증·MFA | `allauth.mfa` 미등록, `ACCOUNT_REAUTHENTICATION_REQUIRED` 미설정(기본 False) | `[실측 rg config/settings.py]` |

### 로컬 측정 (Apple M1 8코어, argon2-cffi 25.1.0, 5회 중앙값) `[실측 scratchpad/t61/measure_hash.py, tune_t.py, 2026-11-20]`

| 해셔 | 1회 시간 | 최대 RSS 증가 | 저장 접두 |
|---|---|---|---|
| PBKDF2-SHA256 1,000,000회(현재) | 0.209 s | 0.1 MiB | `pbkdf2_sha256$1000000$` |
| Argon2id Django 기본(m=102,400 KiB, t=2, p=8) | 0.034 s | 100.3 MiB | `argon2$argon2id$v=19$m=102400,t=2,p=8$` |
| Argon2id OWASP 최소(m=19,456 KiB, t=2, p=1) | 0.017 s | 19.1 MiB | `argon2$argon2id$v=19$m=19456,t=2,p=1$` |
| Argon2id RFC 9106 둘째 권장(m=65,536 KiB, t=3, p=4) | 0.031 s | 64.2 MiB | `m=65536,t=3,p=4` |
| Argon2id m=19,456 KiB, p=1, t=24 | 0.194 s(PBKDF2 대비 0.93배) | 측정 안 함(m이 같아 19 MiB대 예상) | — |

운영 CPU에서의 시간과 PBKDF2 대비 비율은 미측정이다.

재현 명령(저장소 루트에서): `uv run --with argon2-cffi python -I <scratchpad>/t61/measure_hash.py <pbkdf2|argon2_default|argon2_owasp_min|argon2_rfc9106_2nd>`, `uv run --with argon2-cffi python -I <scratchpad>/t61/tune_t.py`. 스크립트는 세션 scratchpad에 있으므로, 구현 단계 0에서 다시 재고 그 결과를 `docs/BE/password-hashing.md` Evidence에 명령과 함께 남긴다.

## 3. 사용자 결정 사항

> **결정(2026-11-20 사용자 답 "1. C 2. ok 3. ok")**: D1=C, D2=A, §4 범위 추가(`ACCOUNT_PREVENT_ENUMERATION` 명시·해셔 목록 정리) 승인.
> 단계 0 재측정으로 t=24 고정 — PBKDF2 1,000,000회와 Argon2id(m=19,456 KiB, p=1)를 번갈아 15쌍 잰 쌍별 비율 중앙값: t=22 0.91배, **t=24 1.03배**(최소 0.72~최대 1.25), t=26 1.10배, t=28 1.13배 `[실측 로컬 Apple M1, uv run --with argon2-cffi python -I <scratchpad>/t61/tune_t_paired.py, 2026-11-20]`. 같은 날 PBKDF2 1회 중앙값은 0.223~0.247 s로 §2 표(0.209 s)보다 높게 나왔다(측정 잡음) `[실측 같은 명령·tune_t_fine.py]`.

### D1. Argon2 매개변수
- **A. Django 기본값** — 코드 추가 없음. Django가 기본값을 올리면 다음 로그인 때 자동으로 다시 해시한다. 로그인 한 번에 메모리 +100 MiB `[실측 로컬]`. 고르기 전에 사용자가 Render 대시보드에서 ① Settings → Instance Type의 메모리 한도, ② Metrics 탭의 평소 메모리 사용량을 읽어야 한다(DOR). 워커가 1개라 메모리 초과로 워커가 죽으면 재시작까지 서비스 전체가 멈춘다.
- **B. OWASP 최소(m=19 MiB, t=2, p=1)** — `accounts/hashers.py`에 하위 클래스 1개(속성 3개). 메모리 +19 MiB. 1회 0.017 s `[실측 로컬]`.
- **C. (권장) m=19 MiB, p=1, t를 지금 PBKDF2 1회 시간에 맞춤(로컬 t≈24~26)** — B와 같은 하위 클래스, 값만 다르다. 메모리 +19 MiB, 로그인 시간은 지금과 비슷하다. 전환 기간에 "기존 PBKDF2 사용자에게 틀린 비밀번호" 시간과 "없는 이메일" 시간 차이가 좁아진다(R1). 운영 CPU에서도 비율이 비슷한지는 미확인이다(§10 운영 재측정).

| 안 | 메모리 | 메모리×반복(공격 비용 지표) | 실패 로그인 1회(해시 2회, 로컬) |
|---|---|---|---|
| 현재 PBKDF2 | 0.1 MiB | — | 0.418 s |
| A | +100 MiB | 200.0 MiB·회(B의 5.26배) | 0.068 s |
| B | +19 MiB | 38.0 MiB·회(1배) | 0.034 s |
| C(t=24) | +19 MiB | 456.0 MiB·회(B의 12배) | 0.388 s |

수치 출처: 메모리·1회 시간 `[실측 로컬 §2]`, 나머지 `[계산 python3, 1회 시간×2, m×t]`.

- 권장 근거: C는 메모리를 B만큼 작게 쓰면서(워커 1개라 메모리 초과는 서비스 전체 중단) 세 안 중 공격 비용이 가장 크고, 로그인 시간과 R1 타이밍 차이를 지금 수준에 가깝게 둔다. 대가는 로그인 CPU 비용을 지금처럼 유지한다는 것(A·B로 얻을 로그인 단축을 포기)이며 새 DoS 위험은 만들지 않는다(SRR). SRR 판정은 "C 또는 B가 보안상 타당".

### D2. 기존 해시 전환 방식
- **A. (권장) 로그인 성공 때 점진 전환** — Django 기본 동작, 코드 없음. 로그인하지 않는 사용자는 PBKDF2 1,000,000회로 남는다. 이 값은 OWASP 권장(PBKDF2-SHA256 600,000회)보다 높다 `[문서 OWASP Password Storage Cheat Sheet]`.
- **B. 데이터 마이그레이션으로 기존 해시를 Argon2로 감싸기** — Django 문서의 "로그인 없이 업그레이드" 방식. 감싼 해셔 클래스를 계속 유지해야 하고, 배포 때 모든 사용자 세션이 한꺼번에 끊긴다(세션 해시가 비밀번호 필드 HMAC). 감싼 해시를 검증할 때도 PBKDF2를 먼저 계산하므로 R1 타이밍 차이는 남는다.

## 4. 범위와 제외

- 범위: 의존성 `argon2-cffi` 추가, `PASSWORD_HASHERS` 설정, (D1=B/C) `accounts/hashers.py`, 테스트, 문서.
- 범위 추가(SRR 지적, 같은 인증 설정 영역의 소규모 항목): `ACCOUNT_PREVENT_ENUMERATION = True`를 운영 설정에 명시한다. 지금은 기본값에만 기대고 있어 R1을 "다른 열거 경로 없음"으로 판정한 근거가 문서화된 보장이 아니다.
- 제외: JSON 로그인 API(트랙 62로 별도), 로그인 백엔드 2개(ModelBackend·allauth)가 실패 로그인에서 각각 해시하는 기존 구조(로그인 백엔드 구성 변경이라 다른 종류의 일 — 이 트랙 전후로 실패 로그인의 해시 횟수는 바뀌지 않는다), 테스트 MD5 해셔(그대로), README 트러블슈팅 서술(과거형 사실이라 그대로).

## 5. 수용 기준

- AC1 새로 저장하는 비밀번호(가입·재설정·변경·`createsuperuser`)는 D1의 Argon2id 매개변수로 저장된다. 네 경로 모두 `hasher=` 없이 기본(첫) 해셔를 쓰므로 `[실측 rg "hasher=" → 0]` unit 시나리오 T61-2(·T61-2b)로 증명한다(경로별 HTTP 시나리오는 두지 않는다).
- AC2 기존 PBKDF2 사용자는 그대로 로그인할 수 있고, 로그인에 성공하면 해시가 Argon2id로 바뀐다.
- AC3 틀린 비밀번호는 해시를 바꾸지 않는다.
- AC4 해시 전환은 `password_changed_at`을 바꾸지 않는다.
- AC5 로그인한 사용자가 이메일 변경 화면에서 현재 비밀번호를 넣어 해시가 바뀌어도 그 세션은 끊기지 않는다(R2). (v5) 비밀번호 변경 화면에서 현재 비밀번호는 맞고 새 비밀번호가 거부될 때도 같다(T61-8).
- AC6 운영 설정 계약: `PASSWORD_HASHERS`는 Argon2(첫 항목)·`PBKDF2PasswordHasher`·`PBKDF2SHA1PasswordHasher` 셋뿐이다. MD5 계열과 설치되지 않은 패키지가 필요한 해셔(BCryptSHA256 등)는 없고, `argon2` 알고리즘 항목은 하나다(SRR).
- AC9 운영 설정은 계정 열거 방지(`ACCOUNT_PREVENT_ENUMERATION`)를 명시적으로 켠다.
- AC7 axes IP 잠금과 allauth 속도 제한 기존 테스트가 그대로 통과한다(두 파일은 테스트 MD5 해셔로 돌아 운영 해셔 변경과 무관하다 — 회귀 확인용).
- AC8 R3의 롤백 규칙이 런북 §5에 그 문안대로 들어가 있다(diff로 확인).

## 6. 위험

- R1 전환 기간 계정 존재 여부 타이밍 노출 — **SRR 판정 Low, 차단 아님, 문서화 의무.** 기존 PBKDF2 사용자에게 틀린 비밀번호를 넣으면 PBKDF2가 2회(0.418 s), 없는 이메일은 기본 해셔 더미가 2회(D1=A 0.068 s, B 0.034 s, C 0.388 s) 돈다 `[실측 로컬 1회 시간]` `[계산 ×2]`. 노출되는 것은 "가입했고 배포 뒤 아직 로그인하지 않은 계정"이라는 신호다. 다른 열거 경로는 막혀 있다(allauth `PREVENT_ENUMERATION` 기본 True — 이 트랙에서 명시, AC9). Django는 이 경우를 막지 않는다 `[코드 hashers.py:62]`. axes가 IP당 실패 5회/1시간으로 시도 수를 제한한다 `[코드 config/settings.py:560-561]`(v1의 `:562-563`은 틀린 인용, QVL 정정). D1=C가 차이를 좁히는지는 로컬 종단 측정으로 확인한다(§9 M1).
- R2 이메일 변경 화면 세션 끊김 — `EmailChangeForm.clean_current_password`의 `check_password`가 해시를 바꾸면 세션 해시가 달라져 다음 요청에서 로그아웃된다 `[코드 accounts/forms.py:104]`. 저장소에 세션 해시 갱신 호출이 0건이라 `[실측]` SRR이 소스 추적으로 실제 결함(Medium, 머지 전 수정)으로 판정했다 — T61-6 Red로 확인한다. 수정은 setter 없는 모듈 함수 비교 `django.contrib.auth.hashers.check_password(current_password, self.user.password)` 1줄(setter가 없으면 해시를 바꾸지 않는다 `[코드 hashers.py:80-82]`). 이 화면에서는 해시 전환 기회를 하나 놓치지만 AC2는 로그인 때 전환만 약속한다. 같은 유형 전수: `check_password(`·`.authenticate(` 저장소 2건뿐 `[실측 SRR rg]` **(v5 정정: 이 rg는 저장소 코드만 봤고 앱이 쓰는 라이브러리 폼을 보지 않았다. allauth `ChangePasswordForm.clean_oldpassword`도 같은 결함 — T61-8, 독립 검토 2026-11-20)** — 계정 삭제(`web/views/account.py:195`)는 같은 요청에서 바로 logout하므로 해당 없다 `[코드 :212]`.
- R3 롤백 — 전환된 사용자는 목록에 Argon2 해셔가 없으면 로그인할 수 없다(알 수 없는 해시 → 가짜 실행 후 False `[코드 hashers.py:44-56]`). 런북 §5 공통 절차 "PaaS의 이전 배포 버전으로 즉시 되돌린다" `[문서 docs/deploy-runbook.md:406-408]`를 이 트랙에 그대로 쓰면 안 된다. 런북에 넣을 규칙(DOR 문안): **argon2-cffi 추가 이전 이미지로 되돌리지 않는다. Argon2 해셔를 목록에 둔 채 PBKDF2를 첫 항목으로 올리는 설정 변경만 배포한다(코드·의존성 유지). Argon2 해셔가 목록에서 사라지면 이미 전환된 사용자는 로그인할 수 없고, 복구는 그 사용자의 비밀번호 재설정뿐이다.**
- R4 다른 기기 세션 1회 로그아웃 — 사용자가 배포 뒤 처음 로그인해 해시가 바뀌면, 같은 사용자의 다른 기기 세션이 끊긴다(세션 해시 = 비밀번호 필드 HMAC `[코드 base_user.py:135-137]`). 사용자별 1회. 막을 방법은 D2=B도 마찬가지로 없다(B는 모두 한꺼번에 끊는다). 두 기기에서 거의 동시에 로그인하면 서로의 세션을 끊을 수도 있다(SRR). 측정으로 확인해 문서에 적는다(§9 M2).
- R5 운영 메모리 — D1=A는 로그인 한 번에 +100 MiB `[실측 로컬]`. 운영 인스턴스 메모리 한도는 미확인. sync 워커 1개라 동시 해시는 최대 1개 `[코드 docker/entrypoint.sh:17-22]` `[문서 deploy-runbook.md:70]`. 배포 직후 Render 로그에서 OOM·워커 재시작을 관찰한다.
- R6 Docker 설치·실행 — 두 단계 모두 `python:3.13-slim`, 빌더가 추가로 설치하는 패키지는 `gettext`뿐(컴파일러 없음) `[코드 Dockerfile:6,14-15,37]`. CI `docker` 잡은 이미지 빌드와 `/api/health/` 기동만 보며, 해셔는 지연 적재라 해시 연산은 증명하지 못한다 `[코드 hashers.py:116-127]`. `audit` 잡은 `uv export`만 해서 설치 가능성과 무관하다 `[코드 .github/workflows/ci.yml:218-219]`. 그래서 ① CI `docker` 잡 로그에서 `argon2-cffi-bindings`가 휠 다운로드로 설치됐는지(소스 빌드가 아닌지) 읽고, ② 로컬에서 같은 이미지로 Argon2 해시 1회를 실행해 확인한다(§10). 소스 빌드가 보이면 그때 빌더에 컴파일러를 추가한다(선제 추가 안 함).

## 7. 역할

- Activated Roles
  - Security & Resilience Reviewer — 인증 저장 방식과 타이밍 열거(R1), 세션(R2·R4).
  - Deployment & Operations Reviewer — 의존성, 운영 메모리(R5), 롤백(R3), Docker(R6).
  - Backend TDD Coach — 설정 계약과 해시 전환 동작의 Test List·Red/Green 판정.
  - Backend & Integration Engineer — 편집 담당.
  - Quality Verification Lead — 수용 기준-증거 매핑, 회귀 판단.
- Not Activated
  - Product Scope Owner — 사용자가 범위를 직접 정했다(Argon2 전환).
  - Domain Architecture Reviewer — 도메인 경계·의존 방향 변화 없음. 하위 클래스는 인증을 소유한 `accounts/`에 둔다.
  - Web Experience Designer / Browser Interaction Reviewer / Frontend Implementation Engineer — 화면 변경 없음.
  - AI Automation Architect — AI 범위 없음.

## 8. 파일과 단계

| 파일 | 변경 | 조건 |
|---|---|---|
| `pyproject.toml`, `uv.lock` | `uv add "argon2-cffi>=25.1,<26"` | 항상 |
| `config/settings.py` | `PASSWORD_HASHERS = [Argon2(D1), PBKDF2PasswordHasher, PBKDF2SHA1PasswordHasher]`(AC6), `ACCOUNT_PREVENT_ENUMERATION = True`(AC9), 한국어 주석 1~2줄씩 | 항상 |
| `accounts/hashers.py` (신규) | `Argon2PasswordHasher` 하위 클래스, `time_cost`·`memory_cost`·`parallelism`만 | D1=B/C |
| `config/settings_test.py` | 모듈 독스트링의 "운영 비밀번호 저장 방식(기본 PBKDF2 해셔)" 현재형 사실 갱신 | 항상 |
| `tests/core/test_test_settings_boundary.py` | T61-1(기존 테스트 :55-62 기대값 변경), T61-7(신규) | 항상 |
| `tests/auth/test_password_hashing.py` (신규) | T61-2·2b (unit) | 항상 |
| `tests/auth/test_password_hash_upgrade.py` (신규, v4) | T61-3·6·4·5 (web) — 한 파일에 unit·web 마커를 섞은 예가 저장소 0건이라 분리 `[실측 grep -rl "@pytest.mark.unit" tests → web 혼용 0]` | 항상 |
| `tests/auth/conftest.py` | `production_password_hashers` 픽스처 | 항상 |
| `accounts/forms.py` | R2 수정 — `:104`를 setter 없는 `hashers.check_password(current_password, self.user.password)`로(SRR) | T61-6 Red 확인 뒤 |
| `docs/BE/password-hashing.md` (신규) | 가드레일: 해셔 목록 규칙, 롤백 규칙, 전환 효과(R1·R4) | 항상 |
| `docs/deploy-runbook.md` | §5 롤백에 R3 한 줄 + 새 문서 링크 | 항상 |

단계:
0. 구현 직전 D1=C라면 로컬에서 t를 다시 재고 고정한다(§2 측정 방법 그대로).
1. 코치가 T61-1부터 한 번에 하나씩 지정 → BIE 편집 → 오케스트레이터 Red/Green.
2. 의존성 추가는 T61-1 Green에 필요할 때 함께.
3. 문서·런북 갱신.
4. 전체 회귀·린트·체크 → 커밋 → PR.

## 9. TDD 체크포인트 (TDD 코치 확정, 2026-11-20)

ID는 v1 그대로 두고 실행 순서만 바꾼다. Red가 날 수 있는 시나리오를 먼저 소진한다.

| 순서 | ID | 경계 | AC | 테스트 이름 | 예상 Red |
|---|---|---|---|---|---|
| 1 | T61-1 | contract | AC6 | `운영_설정은_argon2를_첫_해셔로_pbkdf2는_레거시_검증용으로_남기고_md5와_argon2_중복을_배제한다` | 첫 해셔가 PBKDF2라 실패(나머지 단언 3개 — PBKDF2 포함·MD5 없음·argon2 항목 1개 — 는 Django 기본 목록에서 이미 참 `[코드 global_settings.py:544-550]`) |
| 2 | T61-2 | unit | AC1 | `운영_해셔_목록에서_새_비밀번호는_argon2id_접두로_저장된다` | (v4 정정) `ModuleNotFoundError: No module named 'accounts.hashers'` — `get_hashers()`가 목록 전 항목을 즉시 `import_string`한다 `[코드 hashers.py:116-127]` `[코드 module_loading.py:29-35]`. v3의 "`pbkdf2_sha256$` 접두라 실패"는 T61-1 Green 뒤에는 성립하지 않는다(코치 정정) |
| 2b | T61-2b (D1=B/C만) | unit | AC1 | `accounts_hashers의_argon2_해셔는_지정한_time_cost_memory_cost_parallelism으로_인코딩한다` | (v4 정정) 빈 하위 클래스가 Django 기본값으로 인코딩해 `m=102400,t=2,p=8`이라 `m=19456,t=24,p=1` 기대와 달라 실패 `[코드 hashers.py:391-393]` |
| 3 | T61-3 | web | AC2 | `기존_pbkdf2_해시_사용자가_로그인에_성공하면_해시가_argon2id로_바뀐다` | (v4 재분류) Red 불가 — 회귀 고정. T61-1·T61-2 Green으로 Django 기본 전환(`hashers.py:58`, `base_user.py:106-110`)이 이미 켜졌고 이 시나리오용 운영 코드가 없다(D2=A). 보호력 확인: override 목록을 PBKDF2 첫 순서로 잠시 바꿔 Red 1회(커밋 안 함). AC2 증거로 QVL 매핑 |
| 4 | T61-6 | web | AC5 | `이메일_변경_화면에서_현재_비밀번호를_확인해도_다음_요청까지_로그인_상태가_유지된다` | 세션이 끊겨 실패(가능성 높음, R2) |
| 5 | T61-4 | web | AC3 | `틀린_비밀번호로_로그인하면_실패하고_해시는_그대로다` | Red 불가 — 회귀 고정 |
| 6 | T61-5 | web | AC4 | `로그인_중_해시가_바뀌어도_password_changed_at은_그대로다` | Red 불가 — 회귀 고정 |
| 7 | T61-7 | contract | AC9 | `운영_설정은_계정_열거_방지를_명시적으로_켠다` | 운영 설정 모듈에 값이 없어 실패(기본값은 allauth 내부에만 있다) — 코치 확인 필요 |
| 8 (v5, 독립 검토 발견) | T61-8 | web | AC5 확장 | `비밀번호_변경_화면에서_현재_비밀번호를_확인해도_새_비밀번호가_거부되면_다음_요청까지_로그인_상태가_유지된다` | 다음 요청 `GET /accounts/settings/`가 302 — allauth `ChangePasswordForm.clean_oldpassword`가 모델 `check_password`로 해시를 바꾼 뒤 `PasswordVerificationMixin.clean()`이 새 비밀번호 불일치로 폼을 invalid로 끝낸다 `[코드 allauth/account/forms.py:48-55,595-599]` |
| 9 (v5) | T61-9 | web | AC5 확장(보안 게이트) | `비밀번호_변경에서_현재_비밀번호가_틀리면_비밀번호가_바뀌지_않는다` | Red 불가 — 회귀 고정. T61-8 재정의의 거부 분기를 지킨다. 보호력: `accounts.forms.check_password`를 항상 True로 바꾼 임시 사본에서 302 Red(필수, 보안 게이트) |

- T61-1은 기존 테스트 `tests/core/test_test_settings_boundary.py:55-62`를 고친다. 고치기 전 그 테스트가 지금 지키는 동작("첫 해셔 PBKDF2, MD5 없음")을 Test List에 한 줄로 남긴다(Test Authoring Policy).
- T61-4·T61-5는 Red-Green 사이클 밖이다. 틀린 비밀번호면 setter를 부르지 않고 `[코드 hashers.py:80]`, 해시 전환 setter는 allauth 신호를 보내지 않는다 `[코드 base_user.py:106-110]` `[코드 accounts/signals.py:21]`. Test List 상태는 바로 `Green`, Evidence 칸에 이 근거를 적고 QVL의 AC 증거로 분류한다. 보호력 확인으로, 각 테스트가 지키는 조건을 로컬에서 잠시 바꿔 Red를 1회 본 뒤 되돌린다(커밋 안 함, 증거로 보고).
- 운영 해셔 목록은 `tests/auth/conftest.py`의 `production_password_hashers` 픽스처가 `django.conf.Settings("config.settings").PASSWORD_HASHERS`로 돌려준다(`tests/core/test_test_settings_boundary.py:58`과 같은 방식). T61-1만 기존처럼 테스트 안에서 직접 읽는다.
- 각 web 시나리오의 Given에는 "운영 해셔 목록으로 `override_settings`한 상태에서 `make_password(password, hasher="pbkdf2_sha256")`로 만든 해시를 가진 인증된 사용자"를 본문에 드러낸다(전제를 픽스처에 숨기지 않는다).
- 참고 값: 틀린 자격 증명 로그인은 200 `[코드 tests/auth/test_auth_field_errors.py:62-79]`, 성공은 302 `[코드 tests/auth/test_login_redirect_landing.py:17-19]`, 이메일 변경 제출 URL은 `/accounts/email/` `[코드 tests/auth/test_account_email_change.py:15]`.

측정(커밋하지 않음, 증거로 보고):
- M1 실패 로그인 종단 시간 — 없는 이메일 / 기존 PBKDF2 사용자에게 틀린 비밀번호 / Argon2 사용자에게 틀린 비밀번호, 변경 전·후, 로컬 테스트 클라이언트, 각 20회. 중앙값과 최소~최대를 함께 보고하고, "axes 5회/1시간 안에서 구분 가능한가"로 해석한다. 프로세스 안 측정이라 네트워크 지연이 없으므로 이 값은 탐지 가능성의 상한이다.
- M2 다른 세션 끊김(R4) — ① 같은 사용자로 클라이언트 A·B가 PBKDF2 해시 상태에서 `/accounts/login/` POST로 로그인 ② 운영 해셔 목록 적용 ③ A만 다시 로그인(해시 전환) ④ A의 로그인 필요 페이지가 200인지 ⑤ B의 같은 페이지가 로그인 페이지로 302인지 확인.

## 10. 검증 명령

- `uv run pytest -q tests/core/test_test_settings_boundary.py tests/auth/test_password_hashing.py`
- `uv run pytest -q tests/auth/test_auth_lockout.py tests/auth/test_auth_rate_limit.py`(AC7)
- `uv run pytest -q -n auto`(전체 회귀)
- `uv run ruff check .`, `uv run ruff format --check .`
- `uv run python manage.py check`, `uv run python manage.py makemigrations --check --dry-run`(마이그레이션 없음 확인)
- CI: `ci.yml` 잡 5개 `[코드 .github/workflows/ci.yml:26,106,171,200,224]` — `test`·`lint`·`audit`·`docker`는 PR 게이트, `e2e`는 비차단 관찰(`continue-on-error: true` `[코드 :112]`)이라 통과 증거로 세지 않는다. GitHub 검사에는 GitGuardian이 1개 더 붙는다. `audit`은 새 의존성의 알려진 취약점만 보고, 설치 가능성은 증명하지 않는다.
- CI `docker` 잡 로그에서 `argon2-cffi-bindings` 설치 줄이 휠 다운로드인지 확인(R6).
- 로컬 Docker 확인(R6): `docker build -t takulife-t61 .` 뒤 `docker run --rm --entrypoint python takulife-t61 -c "from argon2 import PasswordHasher; print(PasswordHasher().hash('x')[:9])"` → `$argon2id` 출력.
- AC8: `git diff main -- docs/deploy-runbook.md`로 §5에 R3 문안이 들어갔는지 확인.
- D1=C일 때 운영 CPU 재측정(SRR 권고, 사용자 몫·선택): Render Shell을 쓸 수 있으면 §2 측정 스크립트를 1회 돌려 PBKDF2 대비 Argon2 시간 비율이 로컬(0.93배 `[실측 로컬 t=24]`)과 같은 자릿수인지 본다. 쓸 수 없으면 "운영 비율 미측정"으로 `docs/BE/password-hashing.md` Known gap에 남긴다.
- 배포 뒤(사용자 몫): 사용자 본인 로그인 1회 → `psql "$DATABASE_URL" -c "SELECT split_part(password, '\$', 1) FROM accounts_user WHERE email = '<본인 이메일>';"` → `argon2`(해시 나머지는 출력하지 않는다, DOR 제안 — 런북 §3-15·§3-16과 같은 DB 직접 조회 방식). Render 로그에서 OOM·워커 재시작과 로그인 경로 500이 없는지 관찰.

## 11. Domain Boundary · Coupling · Pythonic

- 하위 클래스는 `accounts/`(인증 소유 앱)에 두고 `config/settings.py`가 문자열 경로로만 참조한다. 다른 앱 의존 없음.
- 하위 클래스는 Django 해셔의 매개변수 속성 3개만 덮는다. 메서드 재정의 없음. `algorithm`은 `argon2` 그대로 두어 매개변수를 바꾸면 Django `must_update`가 다음 로그인에 다시 해시한다 `[코드 hashers.py:59]`.
- `PASSWORD_HASHERS`에 `argon2` 알고리즘 항목을 둘 넣지 않는다(알고리즘별 사전은 마지막 항목이 이긴다 `[코드 hashers.py:131-132]`).

## 12. Deferred

- 없음. 검토자가 "차단 아님"으로 낸 항목도 이 트랙에서 처리한다: R2 수정, `ACCOUNT_PREVENT_ENUMERATION` 명시, 해셔 목록 정리(BCryptSHA256 제외), R4 동시 로그인 문서화. 실패 로그인 이중 해시 구조는 §4 제외(다른 종류의 일)이며 백로그 줄을 만들지 않는다.

## 13. 문서 대상과 인계 조건

- `docs/BE/password-hashing.md`(신규): Current fact, Decision(D1·D2), Guardrail(목록 규칙·롤백), Known gap(R1·R4, 미전환 사용자), Evidence.
- `docs/deploy-runbook.md` §5.
- 머지 때: `docs/pr-log.md` 롤링, `docs/backlog.md` 머지된 트랙 행, `docs/plan-archive/track-61.md`.

## Evidence

사전 검토(2026-11-20, 읽기 전용 4역할 병렬). 하위 역할의 file:line 주장은 오케스트레이터가 소스로 다시 확인한 것만 반영했다.

- SRR: D1은 C 또는 B, D2는 A. R2는 실제 결함(Medium, 머지 전 수정, setter 없는 비교 1줄). R1은 Low·차단 아님(실패 로그인 해시 2회, axes 5회/1시간/IP, allauth 5회/5분/이메일, 다른 열거 경로 없음). 해셔 목록은 Argon2·PBKDF2·PBKDF2SHA1(BCryptSHA256 제외 — bcrypt 미설치). `ACCOUNT_PREVENT_ENUMERATION` 명시 권고. 워커 수 인용 정밀도·`hashers.py:62-65` 줄 정정.
- DOR: CI는 `ci.yml` 잡 5개(v1 "6개"는 틀림), e2e는 비차단. 해셔 지연 적재로 `check`·Docker 헬스 체크가 해셔 오류를 못 잡는다. 롤백 차단 규칙 문안. 메모리는 Render Instance Type·Metrics 확인 전 A 선택 보류. 배포 뒤 `split_part` 접두 확인.
- QVL: AC1·AC5·AC8 증거 보강, M1에 최소~최대·axes 해석, M2 절차 구체화, `config/settings.py:562-563` → `:560-561` 정정, CI 잡 수 정정. 측정 스크립트 재현 명령 요구.
- TDD 코치: Test List 순서(Red 가능 시나리오 먼저), 경계 어휘 `web`, T61-2b 추가, T61-4·5는 사이클 밖 회귀 고정, `production_password_hashers` 픽스처, 기존 테스트 변경 전 보호 동작 기록.
- 오케스트레이터 정정 기록: v1과 그 전 채팅 보고에서 axes 설정을 `config/settings.py:562-563`으로 인용한 것은 틀렸다(실제 `:560-561` `[실측 sed -n 560,561p]`). v1 §10 "CI 6개 잡"도 틀렸다.

## Evidence — 구현 (2026-11-20, 브랜치 `feat/argon2-password-hashing`)

| ID | Red (오케스트레이터 실행) | Green | 커밋 |
|---|---|---|---|
| T61-1 | `AssertionError` 첫 해셔 `django.contrib.auth.hashers.PBKDF2PasswordHasher` | 14 passed | `1f6fb4f0` |
| T61-2 | `ModuleNotFoundError: No module named 'accounts.hashers'` | 15 passed (uv add argon2-cffi + 빈 하위 클래스) | `1f6fb4f0` |
| T61-2b | `assert (102400, 2, 8) == (19456, 24, 1)` | 16 passed | `77412cce` |
| T61-3 | 회귀 고정 — 보호력: PBKDF2 첫 순서 임시 사본에서 해시가 `pbkdf2_sha256$`로 남아 Red | 1 passed | `178ef4f8` |
| T61-6 | `assert 302 == 200` (`/accounts/login/?next=/accounts/settings/`) — R2 실제 결함 재현 | 6 passed (email change 4 + upgrade 2 `[실측 collect-only]`) | `d005bbcf` |
| T61-4 | 회귀 고정 — 보호력: 올바른 비밀번호 임시 사본에서 `302 == 200` Red | 4 passed | `dca374ad` |
| T61-5 | 회귀 고정 — 보호력: `password_changed.send` 임시 삽입에서 `password_changed_at` 변경 Red | 4 passed | `dca374ad` |
| T61-7 | `AttributeError: 'Settings' object has no attribute 'ACCOUNT_PREVENT_ENUMERATION'` | 15 passed | `6d08d673` |

- 임시 사본(`tests/auth/test_t61_probe*_tmp.py`, `test_t61_measure_tmp.py`)은 실행 직후 삭제, `git status`로 확인.
- 전체 `uv run pytest -q -n auto` 6회: 1회차 3 failed/4666 passed(staff 카테고리 3건, 65.79 s, Docker 빌드 직후), 이후 5회 4669 passed `[실측]`. (PR 본문·채팅 보고의 "7회 중 6회 통과"는 셈을 잘못한 것 — 2026-11-20 재집계로 정정) 실패 2파일 직렬 3회·xdist 부분 3회 통과. 두 파일 password/hasher 참조 0건 `[실측 rg]`. 트랙 무관 판단, 사용자 보고 대상(다른 종류 — Prime Directive 2 예외 비해당, QVL).
- ruff check·format(479 files), `manage.py check` 0 issues, `makemigrations --check` No changes `[실측]`.
- M1(실패 로그인 종단, 20회 중앙값): 변경 후 없는 이메일 0.471 s / PBKDF2 틀린 비밀번호 0.481 s / Argon2 0.477 s, 범위 겹침 `[실측 로컬]`.
- M2: A 재로그인(접두 `argon2`) 뒤 A 200, B 302 `/accounts/login/?next=/accounts/settings/` `[실측 로컬]`.
- Docker linux/amd64 빌드 exit 0, uv sync에 `Building` 줄 없음(휠 설치), `DEBUG=False`·운영 설정에서 `argon2 m=19456,t=24,p=1` `[실측]`.
- 운영 해셔 재측정 1회 0.197 s·0.227 s, 최대 RSS +19.7 MiB `[실측 로컬 measure_calibrated.py]`.
- 구현 후 검토: SRR 차단 0(Low: bindings 26.2.0 공개 7일), DOR 차단 0(Medium 문서 4건 + CI 해시 단계 권고), QVL 조건부 완료(문서 표·AC8 diff·staff 플레이키 보고), 코치 리팩터링 불필요·설정 주석 개조식 지적. 전부 같은 PR에서 반영.
- v5(2026-11-20 사용자 요청 "오류가 있는지 검토. 그리고 문서 업데이트"): 내 결론을 주지 않은 독립 검토(general-purpose, 읽기 전용)가 High 1건을 찾았다 — allauth `ChangePasswordForm.clean_oldpassword`가 모델 `check_password`로 해시를 바꾼 뒤 새 비밀번호 불일치로 폼이 실패하면 다음 요청에서 로그아웃. 오케스트레이터가 소스로 재확인 `[코드 allauth/account/forms.py:48-55,595-599]`.
  - T61-8 Red: `GET /accounts/settings/` `302 == 200`(`/accounts/login/?next=/accounts/settings/`) → Green: `accounts.forms.PasswordChangeForm`(clean_oldpassword만 모듈 `check_password`) + `ACCOUNT_FORMS["change_password"]`, tests/auth 158 passed. 커밋 `48ee4c3e`(T61-4에 로그인 오류 문구 단언 추가 — 검토 L3 반영 포함).
  - T61-9(회귀 고정, 새 파일 `tests/auth/test_password_change.py`): 1 passed, 보호력 Red 302 확인. 커밋 `86b844c7`.
  - 검토 L4(T61-3에 세션 재확인 추가)는 코치가 소스로 기각: 로그인은 `_clean_with_password`에서 해시가 바뀐 같은 사용자 객체로 뒤에 `login()`을 하므로 세션 해시 불일치가 구조적으로 불가 `[코드 allauth/account/forms.py:189-203,227-238]`.
  - 검토 L5(README·test-suite-speed.md의 "PBKDF2 1회 약 0.38초")는 2026-07 당시 실측 기록이라 고치지 않는다(과거 서술, §4 제외 범위).
  - allauth 안의 모델 `check_password` 호출 전수 `[실측 rg --no-ignore, 테스트 제외]`: `account/auth_backends.py:108`(로그인, 안전), `account/forms.py:597`(교체), `headless/account/inputs.py:183`(headless 미설치 — 트랙 62에서 headless를 켜면 같은 규칙 필요). 재인증 `adapter.py:827-843`은 `ACCOUNT_REAUTHENTICATION_REQUIRED` 기본 False라 미도달.
  - 문서 오류 정정: `docs/BE/password-hashing.md` (a) `config/settings_test.py:20`→`:22`(독스트링이 2줄 늘어남), (b) 채택 행 1회 0.194 s(다른 스크립트 값)→0.197 s, 실패 로그인 0.388→0.394 s `[계산]`.
- 오케스트레이터 정정 기록(v5): ③ R2의 "같은 유형 경로 저장소 2건뿐" 판정은 저장소 코드만 rg했고 앱이 쓰는 라이브러리 폼을 보지 않아 틀렸다(T61-8). ④ PR 본문·채팅 보고의 "전체 회귀 7회 중 6회 통과"는 셈 오류 — 실제 6회 중 5회 통과.
- 오케스트레이터 정정 기록: ① 처음 로컬 Docker 확인을 `DJANGO_DEBUG` 등 틀린 env 이름으로 돌려 실제로는 `DEBUG=True` 기본값이었는데 DOR 브리프에 "DEBUG false"라고 적었다 — 올바른 env(`DEBUG=false`)로 재실행해 같은 결과 확인. ② 문서 (b) 표 채택 행 메모리를 실측 태그로 두었으나 당시 미측정 — 재측정해 19.7 MiB로 교체.
