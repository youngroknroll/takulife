# OshiLog Event List Date/Status Filter Implementation Plan

Date: 2026-05-31

## Approved Scope

- Extend public event list API `GET /api/events/` with:
  - `start_date_from`
  - `start_date_to`
  - `status` (`upcoming`, `ongoing`, `ended`)
- Keep existing filters (`q`, `region`, `category`) behavior unchanged.
- Add focused behavior tests for new filters.

Out of scope:

- New endpoints.
- Serializer field changes.
- Admin draft workflow changes.
- Member/archive route reactivation.

## Acceptance Criteria

- `start_date_from` returns published events with `start_date >= value`.
- `start_date_to` returns published events with `start_date <= value`.
- Date range can be combined with other existing filters.
- `status=upcoming|ongoing|ended` works from `start_date`/`end_date` based on
  current date.
- Unknown status values are ignored (no extra filter), preserving stable API
  behavior.

## Domain Boundary And Dependency Direction

- `events` app owns public event filtering logic.
- Logic stays in `events.views.PublicEventListView.get_queryset`.
- No cross-app dependency changes.

Allowed:

- `events.views -> events.models`
- `events.views -> events.serializers`

Disallowed:

- `events -> drafts`
- filter logic spread into unrelated apps

## Coupling And Cohesion Review

- No new domain coupling introduced.
- Cohesion improves by keeping all public list query logic in one place.

## Pythonic Code Design

- Use explicit query-param parsing in view.
- Use `datetime.date.fromisoformat` for date parsing.
- Use `django.utils.timezone.localdate()` for status classification date.
- Keep invalid inputs non-fatal by ignoring invalid filter values.

## TDD Checkpoints

1. Add failing tests for `start_date_from`/`start_date_to`.
2. Add failing tests for `status` values.
3. Run targeted tests and confirm RED.
4. Implement minimal query logic in `events.views`.
5. Run targeted tests and confirm GREEN.
6. Run full test suite and Django checks.

## Planned File Changes

- Modify: `events/views.py`
- Modify: `tests/test_events_api.py`
- Update docs after implementation:
  - `docs/refactoring/`
  - `docs/project-status.md`

## Verification Commands

```bash
uv run pytest -q tests/test_events_api.py
uv run pytest -q
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```
