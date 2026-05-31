# Event List `closing_soon` Status Work Log

Date: 2026-06-01
Plan source: `docs/plans/2026-06-01-event-list-closing-soon-status-implementation-plan.md`

## Scope

`GET /api/events/`에 `status=closing_soon` 필터를 추가했다.

## Changes

- 신규 status 필터 추가:
  - `status=closing_soon`
  - 조건:
    - `start_date <= today <= end_date`
    - `end_date <= today + 4일` (오늘 포함 종료일까지 5일)
- 기존 `status=upcoming|ongoing|ended` 동작 유지
- 알 수 없는 status 무시 동작 유지

Implementation files:

- `tests/test_events_api.py`
- `events/views.py`

## TDD Evidence

RED:

```bash
uv run pytest -q tests/test_events_api.py
```

Result:

```text
1 failed, 15 passed
```

GREEN:

```bash
uv run pytest -q tests/test_events_api.py
```

Result:

```text
16 passed in 0.20s
```

## Verification

```bash
uv run pytest -q
```

Result:

```text
62 passed in 6.41s
```

```bash
uv run python manage.py check
```

Result:

```text
System check identified no issues (0 silenced).
```

```bash
uv run python manage.py makemigrations --check --dry-run
```

Result:

```text
No changes detected
```

## Risks / Notes

- `closing_soon`의 5일 기준은 "오늘 포함"으로 고정했다.
- 날짜 경계(자정)에서는 서버 기준 날짜에 따라 결과가 달라질 수 있다.
