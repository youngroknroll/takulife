# OshiLog Event List Query Alias/Ordering Design

Date: 2026-05-31

## Goal

`GET /api/events/`에 미구현 쿼리 인터페이스(`event_type`, `work_title`,
`starts_after`, `starts_before`)와 기본 정렬 규칙을 추가해, 공개 이벤트 탐색
경험을 REST API 설계 문서와 일치시킨다.

## Approved Scope

- `GET /api/events/`에서 아래 쿼리 파라미터 지원 추가:
  - `event_type` (기존 `category`의 호환 별칭)
  - `work_title`
  - `starts_after` (기존 `start_date_from`과 동일 의미)
  - `starts_before` (기존 `start_date_to`와 동일 의미)
- 쿼리 파라미터 미지정 기본 조회 시 정렬 규칙 추가:
  - 진행중(ongoing) 먼저, 종료 임박 순
  - 다음 예정(upcoming) 다음, 시작일 빠른 순
  - 종료됨(ended) 마지막, 최근 종료 순
- 기존 필터(`q`, `region`, `category`, `start_date_from`, `start_date_to`,
  `status`) 동작 유지.

Out of scope:

- 신규 엔드포인트 추가
- 모델 필드 추가/변경
- 인증/권한 정책 변경
- `/api/me/*` 경로 재활성화

## Acceptance Criteria

- `event_type=popup_store` 요청 시 `category=popup_store`와 동일하게 필터된다.
- `work_title` 요청 시 해당 문자열 기준(부분 일치)으로 필터된다.
- `starts_after`, `starts_before`가 각각 시작일 하한/상한 필터로 동작한다.
- 기존 `start_date_from`, `start_date_to`도 계속 동작한다.
- 쿼리 미지정 기본 목록은 다음 우선순위를 따른다:
  1. 진행중 이벤트(종료 임박 순)
  2. 예정 이벤트(시작일 빠른 순)
  3. 종료 이벤트(최근 종료 순)

## Domain Boundary And Dependency Direction

- 소유 도메인: `events`
- 비즈니스 규칙 위치: `events.views.PublicEventListView.get_queryset`
- 의존 방향:
  - 허용: `events.views -> events.models`, `events.views -> events.serializers`
  - 금지: `events`가 `drafts` 또는 타 도메인 로직을 참조해 정렬/필터 판단

## Coupling And Cohesion Review

- 교차 도메인 의존성 추가 없음.
- 공개 이벤트 조회 규칙을 한 뷰 내부에 응집시켜 cohesion 유지.
- 파라미터 별칭은 기존 `category`, `start_date_*` 규칙과 호환되며 API
  소비자 결합도를 낮춘다.

## Pythonic Code Design

- 파라미터 처리:
  - 단순하고 명시적인 조건 분기 유지
  - 날짜 파싱은 `date.fromisoformat` 유지
- 정렬 처리:
  - Django ORM `Case/When` 어노테이션으로 상태 우선순위를 명시적으로 계산
  - 숨은 변환/암묵적 사이드이펙트 없이 queryset 체이닝으로 표현
- 유효하지 않은 날짜 값은 기존 정책대로 무시(비파괴 호환성 유지)

## Risks

- 기본 정렬 변경으로 클라이언트가 기존 `id` 오름차순에 암묵 의존했다면
  체감 순서가 바뀔 수 있음.
- 날짜가 비어 있는 데이터는 정렬 하위로 밀리므로, 추후 명시 정책이 필요할 수
  있음(현재 범위에서는 안정적 fallback 정렬 사용).
