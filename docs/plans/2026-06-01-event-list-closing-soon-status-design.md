# OshiLog Event List `closing_soon` Status Filter Design

Date: 2026-06-01

## Goal

공개 이벤트 목록 API `GET /api/events/`에 `status=closing_soon` 필터를
추가해, 사용자/운영자가 "곧 종료" 이벤트를 빠르게 조회할 수 있도록 한다.

## Approved Scope

- `GET /api/events/`에서 `status=closing_soon` 지원 추가
- `closing_soon` 정의:
  - 진행중 이벤트(`start_date <= today <= end_date`) 중
  - 종료일까지 5일 이내(`end_date <= today + 4일`)
- 기존 `status=upcoming|ongoing|ended` 및
  알 수 없는 status 무시 동작 유지
- 기존 엔드포인트/권한/모델 스키마 변경 없음

Out of scope:

- 신규 엔드포인트 추가
- 이벤트 모델 필드/마이그레이션 변경
- 기본 정렬 정책 변경
- `/api/me/*` 경로 재활성화

## Acceptance Criteria

- `status=closing_soon` 요청 시 조건에 맞는 진행중 이벤트만 반환된다.
- 종료가 6일 이상 남은 진행중 이벤트는 제외된다.
- 이미 종료되었거나 아직 시작 전 이벤트는 제외된다.
- 기존 `status` 값 동작은 회귀 없이 유지된다.

## Domain Boundary And Dependency Direction

- 소유 도메인: `events`
- 규칙 위치: `events.views.PublicEventListView._filter_by_status`
- 허용 의존:
  - `events.views -> events.models`
  - `events.views -> events.serializers`
- 금지 의존:
  - `events -> drafts`
  - 상태 규칙을 URL 설정/테스트 코드로 이전

## Coupling And Cohesion Review

- 도메인 간 신규 결합도 증가 없음.
- status 필터 규칙을 기존 `_filter_by_status`에 응집시켜 cohesion 유지.
- 남는 결합 이슈 없음(현재 범위 기준).

## Pythonic Code Design

- `datetime.date.today()` 기반 명시적 날짜 계산 유지.
- 상태별 조건 분기를 작은 if 블록으로 유지하여 가독성 확보.
- ORM 필터 체이닝으로 조건을 직접 표현하고 숨은 변환 로직 도입 금지.
- 범위 외 일반화(전략 객체/플러그인형 필터 시스템) 도입 금지.

## Risks

- "5일 이내"의 포함 기준(오늘 포함)을 문서/테스트로 명확히 고정하지 않으면
  향후 해석 차이가 생길 수 있다.
- 서버 기준 날짜가 바뀌는 자정 경계에서 결과가 달라질 수 있으므로
  테스트 데이터는 상대 날짜(`today ± n`)로 작성한다.
