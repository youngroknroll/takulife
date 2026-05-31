# OshiLog Event List Query Alias/Ordering Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend public event list API query compatibility and default ordering
without changing endpoint boundaries.

**Architecture:** Keep all list-query business rules inside
`PublicEventListView.get_queryset` in the `events` domain. Reuse existing
`category` and date-filter semantics through aliases to avoid schema changes.
Use ORM annotations for explicit ordering by event progress stage.

**Tech Stack:** Python, Django, Django REST Framework, pytest, pytest-django

---

## Approved Scope

- Extend `GET /api/events/` query support:
  - `event_type` alias for `category`
  - `work_title` filter
  - `starts_after` alias for `start_date_from`
  - `starts_before` alias for `start_date_to`
- Add default ordering policy for unfiltered public list:
  1. ongoing first (`end_date` ascending)
  2. upcoming next (`start_date` ascending)
  3. ended last (`end_date` descending)
- Preserve all existing API paths and permission boundaries.

Out of scope:

- Event model/schema changes
- New endpoint creation
- Re-enabling deferred `/api/me/*` routes
- Admin draft workflow changes

## Acceptance Criteria

- `event_type` and `category` provide compatible filtering behavior.
- `work_title` query narrows published events by work title text match.
- `starts_after`/`starts_before` apply start-date bounds.
- Existing `start_date_from`/`start_date_to` continue to work.
- Default list ordering reflects ongoing/upcoming/ended priority.
- Existing behavior tests remain green.

## Domain Boundary And Dependency Direction

- Owner: `events` domain
- Rule ownership:
  - Query interpretation and list ordering in `events.views`
  - Persistence and fields in `events.models`
- Allowed dependencies:
  - `events.views -> events.models`
  - `events.views -> events.serializers`
- Forbidden dependencies:
  - `events.views` depending on `drafts` internals
  - Moving query business rules to tests or URL config

## Coupling And Cohesion Review

- Coupling: no new app-to-app dependencies introduced.
- Cohesion: event discovery query policy stays cohesive in one list-view unit.
- Deferred coupling cleanup:

Deferred Refactoring Note

- Topic: Dedicated query object/service for complex public event search policy.
- Why it is not part of the current scope: Current scope is small and can stay
  explicit in one view without new abstraction.
- Why it may be needed later: Additional filters/sorting combinations may make
  `get_queryset` harder to maintain.
- Trigger condition: Three or more additional filter families or repeated query
  logic across multiple endpoints.
- Expected change location: `events/views.py`, potentially new `events/query.py`.
- Related tests: `tests/test_events_api.py`.

## Pythonic Code Design

- Keep explicit param parsing with small helper methods where needed.
- Use `date.fromisoformat` and ignore invalid date formats for compatibility.
- Use ORM-native `Case/When` annotations for readable ordering semantics.
- Avoid generic filter framework introduction (YAGNI).

## TDD Checkpoints

1. Add one failing behavior test for query aliases
   (`event_type`, `starts_after`, `starts_before`).
2. Run target test and verify RED for expected missing behavior.
3. Add minimal view logic for aliases.
4. Run target test and verify GREEN.
5. Add one failing behavior test for default ordering priority.
6. Run target test and verify RED.
7. Add minimal ordering annotation logic.
8. Run target tests and verify GREEN.
9. Run regression checks and document evidence.

## Planned File Changes

- Modify: `tests/test_events_api.py`
- Modify: `events/views.py`
- Add: `docs/refactoring/2026-05-31-event-list-query-alias-ordering-work-log.md`
- Modify: `docs/project-status.md`

## Verification Commands

```bash
uv run pytest -q tests/test_events_api.py
uv run pytest -q
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```
