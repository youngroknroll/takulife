# OshiLog Event List `closing_soon` Status Filter Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 공개 이벤트 목록 API에 `status=closing_soon` 필터를 추가한다.

**Architecture:** 기존 `events.views.PublicEventListView`의 status 필터 분기만
확장한다. 비즈니스 규칙은 `_filter_by_status`에 유지하고, TDD로 테스트
추가→RED 확인→최소 구현→GREEN 순서를 따른다.

**Tech Stack:** Python, Django, Django REST Framework, pytest, pytest-django

---

## Approved Scope

- `GET /api/events/`에 `status=closing_soon` 필터 추가
- 기준:
  - `start_date <= today <= end_date`
  - `end_date <= today + 4일` (오늘 포함 종료일까지 5일)
- 기존 status 필터 동작 유지
- 테스트/문서 업데이트

Out of scope:

- 모델/스키마 변경
- 신규 API 경로 추가
- 기본 정렬 정책 변경

## Acceptance Criteria

- `status=closing_soon`에서 조건 충족 이벤트만 반환
- 진행중이지만 종료 6일 이상 남은 이벤트 제외
- ended/upcoming 이벤트 제외
- 기존 테스트 회귀 없음

## Domain Boundary And Dependency Direction

- 규칙 소유: `events` 도메인
- 구현 위치: `events.views.PublicEventListView._filter_by_status`
- 허용 의존:
  - `events.views -> events.models`
  - `events.views -> events.serializers`
- 금지 의존:
  - `events -> drafts`
  - status 규칙을 테스트/URL 계층으로 이동

## Coupling And Cohesion Review

- status 해석 규칙을 기존 함수에 통합해 응집도 유지
- 앱 간 신규 의존성 추가 없음

## Pythonic Code Design

- `date.today()` 기반 계산을 명시적으로 구현
- 최소 분기 추가만 수행
- ORM-native queryset filtering 유지

## TDD Checkpoints

1. `tests/test_events_api.py`에 `status=closing_soon` 실패 테스트 추가
2. `uv run pytest -q tests/test_events_api.py -k closing_soon`으로 RED 확인
3. `events/views.py`에 최소 로직 추가
4. 동일 테스트 GREEN 확인
5. `tests/test_events_api.py` 전체 GREEN 확인
6. 전체 회귀/체크/마이그레이션 검증 실행

## Planned File Changes

- Modify: `tests/test_events_api.py`
- Modify: `events/views.py`
- Add: `docs/refactoring/2026-06-01-event-list-closing-soon-status-work-log.md`
- Modify: `docs/project-status.md`

## Verification Commands

```bash
uv run pytest -q tests/test_events_api.py -k closing_soon
uv run pytest -q tests/test_events_api.py
uv run pytest -q
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

## Deferred Work

Deferred Refactoring Note

- Topic: 공통 status 판별 로직을 QuerySet/서비스로 분리
- Why it is not part of the current scope: 현재는 상태 종류가 적고 뷰 내부가
  가장 단순/명시적이다.
- Why it may be needed later: status 종류가 늘어나면 분기 복잡도가 증가한다.
- Trigger condition: status 변형이 3개 이상 추가되거나, 동일 규칙을 다른
  엔드포인트에서도 재사용해야 할 때.
- Expected change location: `events/views.py`, (필요 시) `events/query.py`.
- Related tests: `tests/test_events_api.py`.
