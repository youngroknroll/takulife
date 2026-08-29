# 트랙 6 프론트 잔여 정리 스윕 — 기술 기록 (2026-08-24)

## 범위와 결정

- **500 페이지**: Django 표준 `server_error()`가 request 없이 렌더해 `_topbar.html`의 인증 분기가 항상 비로그인으로 떨어지는 착시 → `templates/500.html`이 `{% block site_header %}`를 오버라이드해 **인증 영역 없는 중립 헤더**를 직접 렌더(후보 ② 채택 — 커스텀 handler500은 오류 상황에서 미들웨어 정상 동작을 전제해 기각). `_site_header.html`·`_topbar.html`·`base.html` 무수정.
- **필수(＊) 통일**: `_auth_field.html`·`_account_settings_field.html`·`delete_account.html` 라벨에 sr-only "(필수)" + 8개 템플릿에 범례 1회씩. **저장소에 전역 `.sr-only`가 없어** `auth.css`·`account_settings.css`에 페이지 스코프 clip 규칙을 함께 신설(누락 시 텍스트 노출 회귀 — BIR 사전 기준이 예고).
- **visit.js**: 죽은 캐러셀 핸들러(함수+호출부 2곳 동시) 제거. 호출부만 남기면 `bindRecordDeletes` 미도달로 삭제 버튼 전면 마비였다.

## 가드레일 (나중 작업자용)

- 500.html의 헤더 복제는 의도된 중복이다 — `_site_header.html`을 수정하면 500.html 사본도 함께 검토할 것. 인증 영역(`topbar-auth`·`[data-account-menu]`)을 500에 되살리면 착시가 재발한다.
- `[data-account-menu]` wrapper는 toggle·panel과 전부-또는-전무로만 렌더할 것 — wrapper만 있으면 account_menu.js가 로드 시점 TypeError.
- auth/account_settings의 `.sr-only`는 페이지 스코프(`.auth-page`/`.account-settings-page`) — 새 화면이 이 파셜을 쓰면 그 페이지 루트 클래스가 두 스코프 중 하나여야 비가시가 유지된다.

## 검증 증거 [실측 2026-08-24]

- FE 이중 게이트: **WED Conforms / BIR Conforms** (사전 명세·기준 → 구현 → 사후 판정, Standard).
- 브라우저(DEBUG=false+collectstatic 서버, 임시 /__boom__/ 경로로 실 500 유발 후 원복): 로그인 상태 500 헤더에 인증 링크·메뉴 전무, 랜드마크 4종, 회복 링크 자연 포커스, 다크모드 토큰 전환, 콘솔 JS 오류 0 / 404는 로그인 반영 유지 / sr-only 전 지점 1×1px·describedby 끊김 0·320px 무오버플로 / 삭제 흐름 DELETE 204·검색 교체 후 재바인딩 정상.
- 전체 회귀 `uv run pytest -q` → 2282 passed(프론트 전용 변경, 건수 불변).
- 잔여 Unverified(명세 이탈 아님): 실기기 스크린리더 낭독, email_change 인증 대기 3폼 상태의 시각 확인.

## 이연

- `visit_edit.html` 범례 누락(archive 기존 불일치) — 범위 밖, 다음 archive 정리 시 후보.
