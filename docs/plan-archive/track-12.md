# 트랙 12: 비밀번호 생성 경로 보안 강화 (2026-08-26) · **상태(2026-11-12)**: 계획만 승인, 구현 미착수(사용자 지시 "계획 문서까지만", 2026-08-26 `[문서 메모리]`). · **폐기(2026-11-18)**: 미착수인 채로 폐기한다 `[문서 사용자 지시 2026-11-18 "열린 트랙 폐기. 작업 혼동 가능성."]`. 이 절은 실행 계획이 아니라 기록이다.

> 배경: 사용자 문제 제기 — "비밀번호 변경에 이메일 코드가 필요하지 않나 +
> 구글 가입 유저는 비밀번호 변경 불가여야 하지 않나". 실측: 일반 변경은
> 이미 `oldpassword` 확인이 있으나, **소셜 전용(unusable password) 유저는
> allauth가 변경 화면에서 설정(set) 화면으로 보내 현재 비밀번호 확인 없이
> 비밀번호를 만들 수 있다**([코드] allauth account/views.py:477·523). 변경·
> 설정 시 알림 메일도 꺼져 있다(`ACCOUNT_EMAIL_NOTIFICATIONS` 기본 False).
> 사용자 승인 범위(권장안): 이메일 OTP는 도입하지 않는다 — 세션만으로
> 비밀번호를 만들 수 없게 set 경로를 차단하고(이메일 증명이 있는 리셋
> 경로만 허용), 변경·설정·리셋·이메일 변경 알림 메일을 켠다.

## 승인 범위

**A. 알림 메일 활성화 (백엔드)**

1. `config/settings.py`: `ACCOUNT_EMAIL_NOTIFICATIONS = True`. allauth
   adapter.send_notification_mail이 이 플래그로 게이트됨을 소스로 확인
   ([코드] adapter.py:922-924).
2. 한국어 메일 템플릿 오버라이드: `templates/account/email/`의 기존 한국어
   관례(email_confirmation, password_reset_key)를 따라
   `password_changed_message.txt`/`_subject.txt`,
   `password_set_message.txt`/`_subject.txt`,
   `email_changed_message.txt`/`_subject.txt` 신설.

**B. 소셜 전용 유저의 비밀번호 설정(set) 경로 차단 (백엔드+프론트)**

3. `accounts/views.py` + `config/urls.py`: `account_set_password` 경로를
   트랙 11의 선등록 패턴으로 오버라이드 — 접근 시 설정 허브로 리다이렉트
   + 안내 메시지. set 뷰는 unusable-password 유저만 도달 가능한 화면이므로
   (usable 유저는 allauth가 change로 되돌림) 전면 차단이 곧 소셜 전용 유저
   차단이다. url name `account_set_password` 유지(allauth 내부 reverse 참조).
   비밀번호를 원하는 소셜 유저의 유일한 경로는 이메일 리셋(소유 증명 게이트).
4. 설정 화면 분기: `user.has_usable_password`가 False면 설정 허브의
   비밀번호 행과 인덱스 탭을 안내로 대체("Google 로그인 전용 —
   비밀번호를 만들려면 비밀번호 재설정 메일 이용" 취지).

## 배제 (범위 밖)

- 이메일 OTP(변경 시 코드 확인) — 사용자 결정으로 미도입. 필요 시 별도 트랙.
- 비밀번호 리셋 플로우 변경(현행 이메일 링크 유지), 소셜 연결 해제 UX,
  2FA. 로그인 알림(unknown device) 등 추가 알림 종류.

## 수용 기준

- 소셜 전용 유저가 `account_set_password`에 GET/POST 해도 비밀번호가
  생성되지 않고 설정 허브로 안내된다.
- 일반 유저의 비밀번호 변경 플로우는 회귀 없음(기존 테스트 초록 유지).
- 비밀번호 변경 시 가입 이메일로 알림 메일이 발송된다.
- 소셜 전용 유저의 설정 화면에는 변경 링크 대신 안내가 보인다.
- 소셜 전용 유저의 이메일 리셋 경로는 계속 동작한다.

## Test List (초안 — 코치가 계약 확정)

| ID | 행위 | 경계 | 근거 |
|---|---|---|---|
| T12-1 | 알림 설정 계약: ACCOUNT_EMAIL_NOTIFICATIONS가 True다 | contract | 꺼지면 변경 알림이 조용히 사라짐 — 설정이 보안 속성 |
| T12-2 | 비밀번호 변경이 성공하면 가입 이메일로 알림 메일이 발송된다 | web | 발송은 뷰 플로우(finalize_password_change)의 관찰 결과 |
| T12-3 | 소셜 전용 유저가 비밀번호 설정 경로에 접근하면 거부되고 비밀번호가 생성되지 않는다 | web | 차단 자체가 URL 계층 계약 |
| T12-4 | 소셜 전용 유저도 이메일 리셋 경로로는 비밀번호를 만들 수 있다 | web | 차단이 복구 경로까지 막지 않음을 고정 |

## Activated Roles

- Backend TDD Coach / Backend & Integration Engineer / Quality Verification
  Lead: TDD 사이클·구현·완료 판정
- Security & Resilience Reviewer: 차단 설계의 우회 경로 검토(리셋·change
  리다이렉트·내부 reverse)
- Web Experience Designer / Browser Interaction Reviewer / Frontend
  Implementation Engineer: 설정 화면 분기(리뷰 깊이 Light~Standard)

Not Activated: Product Scope Owner(사용자가 범위 직접 결정), Domain
Architecture Reviewer(accounts 내부), Deployment & Operations
Reviewer(런타임 설정 1건은 계약 테스트로 고정, env 변화 없음 — SMTP는
배포에서 이미 설정됨), AI Automation Architect(해당 없음).

## Frontend Review Evidence

- 깊이·사전 산출물·사후 판정은 구현 전후 이 절에 기록한다.

## 검증 커맨드

- `uv run pytest -q tests/auth/` → `uv run pytest -q`
- `uv run python manage.py check`
- 브라우저: 설정 화면 분기(일반/소셜 전용) 렌더 확인 — 소셜 전용 유저는
  로컬에서 unusable password 계정으로 재현

## Deferred

- 이메일 OTP 재검토(사용자 요청 시), 로그인 이상 징후 알림, 2FA
