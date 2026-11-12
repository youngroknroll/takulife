# 트랙 45: 문서 전수검사(2026-10-27) 코드·운영 잔여 정리 [v1 — 사용자 지시 2026-10-27 "모든 백로그 수정, 트랙 44 머리말 갱신, 어댑터 진행 파일 규약 삭제" [문서 사용자 지시]. 정본 목록은 `docs/backlog.md` L절]

> **기준선**: main `37e4a9d1`(문서 전수검사 커밋 5개 [실측 git log]), 전체 회귀 4284 passed / 10 deselected / 152.46초 [실측 2026-10-27 main e38a0db9]. main 직접 커밋(머지 후 후속 수정 규약, PR 없음).
> **Activated Roles**: WED·BIR(FE 이중 리뷰, 깊이 Light 제안), Frontend Implementation Engineer, Backend & Integration Engineer, QVL 역할은 오케스트레이터가 대행(회귀·증거 대조). **Not Activated**: PSO(제품 결정 없음), DAR(패키지 내부 이동뿐), SRR(보안 경계 변경 없음), DOR(배포 변경 없음), AAA, TDD 코치(동작 변경 없음 — 테스트 위생·Tidy).

## 1. 범위
- FE [실측 2026-10-27 전수검사]: ① 활동 달력 `.date-detail-section`에 `scroll-margin-top` 추가(홈·행사 달력과 동일) ② `static/css/staff/base.css` 중복 블록(`.page`·`[hidden]`) 두 번째 복사본 삭제 ③ `_home_event_calendar.html` 8행 주석 정정 ④ `auth.css` `.auth-panel-form form p` 폴백 블록 삭제(소비처 0건 [실측 awk]).
- BE [실측 2026-10-27 전수검사]: ⑤ `core/client_error_views.py` 주석 정정 ⑥ 시각 의존 테스트 2곳 — `tests/drafts/test_discovery_runs.py` 파라미터의 `timezone.now()`를 실행 시점 계산으로, `tests/drafts/test_agent_drafts.py` 모듈 상수 `_TODAY`를 호출 시점 계산으로 ⑦ `staff/views/events.py` 809줄 [실측 wc -l] → `StaffEventBulkUnpublishView`·`MAX_BULK_EVENT_IDS`를 `staff/views/events_actions.py`로 이동(동작 불변, `staff/views/__init__.py` 재수출 유지).
- 측정·운영 [문서 docs/backlog.md L절]: ⑧ 폰트 preload 교집합 재측정(공개 3페이지 × ko/en/ja/zh-hans, Chrome DevTools) → 필요 시 `FONT_PRELOAD_CHUNKS` 갱신 ⑨ `EmailAddress` 중복 감사 2건 — 운영 DB는 사용자 실행, 절차를 런북에 적고 로컬 DB로 명령만 검증.
- 문서 [문서 사용자 지시]: ⑩ 이 파일 §트랙 44 머리말 갱신 ⑪ 어댑터 2개(`backend-integration-engineer`·`frontend-implementation-engineer`)의 `/tmp/claude-progress` 진행 파일 규약 삭제(소비자 없음) ⑫ backlog L절·관련 기술기록 갱신.
- 제외: IP 보조 스로틀 착수(별도 사용자 결정), 번역 품질 검수.

## 2. 수용 기준·검증
- AC1 활동 달력 날짜 선택 후 `#selected-date`의 `getBoundingClientRect().top`이 헤더 높이 이상 [브라우저 실측 예정].
- AC2 `staff/views/events.py` 800줄 미만 [실측 wc -l 예정], `tests/staff` 전부 통과, 경계 가드 통과.
- AC3 시각 의존 테스트: 수집 후 121초 대기 플러그인(`scratchpad/redplugin`)으로 현재 코드 Red 관측 → 수정 후 같은 플러그인으로 Green [실측 예정].
- AC4 전체 회귀 `uv run pytest -q` 통과, e2e 10건 [실측 예정].
- AC5 WED·BIR 사후 verdict 둘 다 Conforms(또는 사용자 수용).

## 3. 이연
- IP 보조 스로틀(`core/client_error_views.py`): 트리거(`TRUSTED_PROXY_COUNT` 존재)는 충족이나 착수는 사용자 결정 [문서 docs/BE/error-groups.md].
- `EmailAddress` 중복 감사의 운영 DB 실행: 절차는 `docs/operations-runbook.md` §10, 로컬 DB 12행·중복 0건 [실측 2026-10-27], 운영 실행은 사용자 몫.

## 4. Evidence (2026-10-27)
- AC1 활동 달력: 날짜 칸 클릭 → `#selected-date` top 85px / `.site-header` 하단 65px / `document.activeElement` 일치 true / `scrollMarginTop` 85px; 키보드(링크 focus 후 Enter, 빈 상태 날짜)도 top 85px·포커스 true; 콘솔 메시지 0건 [실측 Chrome DevTools MCP, 뷰포트 500×800, 로그인 테스트 사용자(측정 후 삭제)]. 부수 측정: `/accounts/signup/` 닉네임 힌트 margin-top 삭제 전 4px → 삭제 후 4px, `auth.css` cssRules 58개 중 `form p` 선택자 0건 [실측 캐시 무시 재로드]; `/staff/dashboard/` `.page` padding 14px, `[hidden]` 17개 전부 display none [실측].
- AC2 `staff/views/events.py` 731줄, `events_actions.py` 185줄 [실측 wc -l]; `tests/staff tests/drafts tests/core/test_architecture_boundaries.py` 1219 passed [실측].
- AC3 시각 의존 테스트: 수집 후 121초 대기 플러그인(`scratchpad/redplugin/sleep_after_collect.py`)으로 수정 전 2 failed / 1 passed(123.57초) → 수정 후 3 passed(123.29초) [실측]. `_TODAY` 자정 경계는 재현 수단 없이 구조 수정만(호출 시점 계산).
- AC4 전체 회귀 4284 passed / 10 deselected / 145.07초, e2e 10 passed / 10.37초, `manage.py check` 0건, `makemigrations --check --dry-run` 변경 없음 [실측 2026-10-27].
- AC5 WED 사후 verdict Conforms(4건 전부, 아젠다 상한 주석 3건 정정 포함); BIR 사후 verdict Conforms(4건 전부, 결함 0건) — 단 스태프 패널 실제 열기/닫기 상호작용·다크모드·데스크톱 1280px 달력은 미측정이라 Unverified 잔여 위험(사용자 수용 필요) [문서 WED·BIR 사후 보고 2026-10-27].
- 폰트 preload 재측정: 3페이지 × ko/en/ja/zh-hans 12조합 전부 preload 13개 사용·"preloaded but not used" 경고 0건; ja 10개·zh-hans 11개 청크를 CSS 경로로 추가 로드 → `FONT_PRELOAD_CHUNKS` 유지 [실측 Chrome DevTools MCP 2026-10-27, 상세 docs/FE/font-delivery.md F5].

---

