# Event List Query Alias/Ordering Work Log

Date: 2026-05-31
Plan source: `docs/plans/2026-05-31-event-list-query-alias-ordering-implementation-plan.md`

## Scope

Implemented query compatibility and default ordering enhancements for public
event list API `GET /api/events/`.

## Changes

- Added query alias/filter support:
  - `event_type` alias for `category`
  - `work_title` partial-match filter
  - `starts_after` alias for `start_date_from`
  - `starts_before` alias for `start_date_to`
- Added default ordering priority:
  1. ongoing events (earliest `end_date` first)
  2. upcoming events (earliest `start_date` first)
  3. ended events (latest `end_date` first)
- Kept existing filters and endpoint boundaries unchanged.

Implementation files:

- `events/views.py`
- `tests/test_events_api.py`

## Verification

```bash
uv run pytest -q tests/test_events_api.py
```

Result:

```text
15 passed in 0.17s
```

```bash
uv run pytest -q
```

Result:

```text
61 passed in 6.39s
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

- `event_type`는 `category`와의 호환 별칭으로 처리되며, 둘 다 전달되면
  `category`가 우선한다.
- 날짜 없는 이벤트는 기본 정렬에서 마지막 그룹으로 배치된다.
