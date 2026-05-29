# OshiLog Event Index Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the first OshiLog release as a searchable event information index with draft-based operator publishing.

**Architecture:** Keep the backend as a Django + Django REST Framework monolith. Limit this phase to `Event` public read APIs and `EventDraft` operator workflow APIs. Defer member-facing APIs even if some related code already exists.

**Contract source:** Implement against `docs/plans/2026-05-28-oshilog-event-index-api-contract-design.md`.

**Tech Stack:** Python, uv, Django, Django REST Framework, pytest, pytest-django.

---

## Approved Scope

This plan covers only:

- Published event list API.
- Published event detail API.
- Keyword search.
- Region and category filtering.
- Draft creation from official URL.
- Draft list/detail/update APIs.
- Draft approve/reject APIs.
- Duplicate URL rejection.

This plan does not implement:

- User event status.
- Visit records.
- Photo upload.
- Google login flow.
- User-submitted event URLs.

## Acceptance Criteria

- Public users can read published event list and detail.
- Public users can search by keyword.
- Public users can filter by region and category.
- Operators can create drafts from official URLs.
- Operators can list, edit, approve, and reject drafts.
- Approval creates a published event.
- Duplicate official URLs are blocked.
- Public API uses `category`; do not expose both `category` and `event_type`.
- Member-facing `/api/me/` APIs remain unchanged.
- Domain boundaries and dependency direction from the contract design are
  preserved.
- Business logic does not live in HTTP views when it belongs in domain methods
  or application services.
- The implementation remains idiomatic Python/Django/DRF: explicit, readable,
  framework-native, and free of silent data mutation.
- `python manage.py check` exits successfully.
- `python -m pytest -q` exits successfully.

## Domain Boundary And Dependency Direction

The implementation boundary is:

- `events` owns published event fields, public read query behavior, and the
  service that creates a published event from reviewed draft data.
- `drafts` owns draft fields, draft status transitions, draft validation, and
  the operator review workflow.
- `accounts` is used only for admin/staff identity through DRF permissions.
- `core` is not part of this implementation slice.

Allowed dependencies:

- `drafts.views -> drafts.serializers`
- `drafts.views -> drafts.services`
- `drafts.services -> drafts.models`
- `drafts.services -> events.services`
- `events.services -> events.models`
- `events.views -> events.serializers`
- `events.views -> events.models`

Disallowed dependencies:

- `events -> drafts`
- `drafts.views -> events.models`
- public event views using draft serializers or draft querysets
- member-facing `/api/me/` code changes for this slice

Cross-domain publication must be orchestrated in `drafts.services`, and
published event creation must be delegated to `events.services`.

## Coupling And Cohesion Review

This plan lowers coupling by preventing draft HTTP views from creating `Event`
records directly. The draft workflow can publish an event only through a named
service boundary.

This plan increases cohesion by keeping:

- public event reads and event creation invariants in `events`
- draft validation and state transitions in `drafts`
- authentication/identity behavior outside the event-index workflow

Remaining coupling:

- Existing member-facing models and views still live in `events`. This is
  deferred because the current scope is public event/admin draft completion, not
  member archive cleanup.

## Pythonic Code Design

Use explicit Django/DRF structures:

- Keep views small and focused on HTTP concerns.
- Put draft approve/reject business rules in `drafts.services` or model methods.
- Put published `Event` construction in `events.services`.
- Use serializers for input/output boundaries, not cross-domain state
  transitions.
- Use `transaction.atomic()` around draft status changes and event publication.
- Reject invalid or immutable input explicitly instead of silently dropping it.
- Prefer small named functions over clever abstractions or broad base classes.

Non-pythonic shortcuts rejected for this plan:

- Large procedural approve/reject methods in `drafts.views`.
- Direct `Event.objects.create()` calls from `drafts.views`.
- Serializer `update()` methods that silently discard mutable input.
- New generic service framework abstractions.

## Task 1: Align Domain Models To Event Index Scope

**Files:**
- Modify: `events/models.py`
- Add: `events/services.py`
- Modify: `drafts/models.py`
- Add: `drafts/services.py`
- Test: `tests/test_events_api.py`
- Test: `tests/test_drafts_api.py`

**Step 1: Write the failing test**

Add behavior tests for the first public API behavior that needs the event-index
fields:

- published events can be listed with `category` and `region`
- unpublished events remain hidden from the public list

**Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_events_api.py`

Expected: FAIL because current public event behavior and event fields are too
narrow.

**Step 3: Write minimal implementation**

- Extend `Event` with fields needed for public list/detail:
  - `category`
  - `work_title`
  - `location_name`
  - `region`
  - `official_url`
  - `source_name`
  - `summary`
  - `start_date`
  - `end_date`
- Extend `EventDraft` with candidate fields needed for review:
  - `raw_title`
  - `raw_text`
  - extracted candidate fields
  - review status fields

**Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/test_events_api.py tests/test_drafts_api.py`

Expected: PASS.

## Task 2: Add Public Event Detail And Filters

**Files:**
- Modify: `events/serializers.py`
- Modify: `events/views.py`
- Modify: `events/urls.py`
- Test: `tests/test_events_api.py`

**Step 1: Write the failing test**

Add tests for:

- `GET /api/events/{id}/`
- filtering by `region`
- filtering by `category`
- keyword search

**Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_events_api.py`

Expected: FAIL because detail and filters are incomplete.

**Step 3: Write minimal implementation**

- Add public detail endpoint.
- Add list filtering for:
  - `q`
  - `region`
  - `category`
- Keep only `published` events visible.
- Do not expose `publish_status` in the public serializer.

**Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/test_events_api.py`

Expected: PASS.

## Task 3: Expand Draft Review Workflow

**Files:**
- Modify: `drafts/serializers.py`
- Modify: `drafts/views.py`
- Modify: `drafts/urls.py`
- Modify: `drafts/services.py`
- Test: `tests/test_drafts_api.py`

**Step 1: Write the failing test**

Add tests for:

- draft detail
- draft update
- approve action
- reject action
- duplicate source URL rejection

**Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_drafts_api.py`

Expected: FAIL because current draft API only supports list/create.

**Step 3: Write minimal implementation**

- Add detail/update endpoint.
- Add explicit approve/reject action endpoints.
- Enforce draft status transitions.
- Reject duplicate `source_url`.
- Keep HTTP views thin; delegate status transition behavior to
  `drafts.services`.
- Reject immutable update fields explicitly instead of silently ignoring them.

**Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/test_drafts_api.py`

Expected: PASS.

## Task 4: Approve Draft Into Published Event

**Files:**
- Modify: `drafts/services.py`
- Modify: `events/services.py`
- Modify: `drafts/views.py` only as an HTTP adapter if needed
- Modify: `events/models.py` if needed
- Test: `tests/test_drafts_api.py`

**Step 1: Write the failing test**

Add a test that approval creates a published `Event` and that rejected drafts do not.

**Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_drafts_api.py`

Expected: FAIL because approve/reject side effects are not implemented.

**Step 3: Write minimal implementation**

- On approve:
  - validate no duplicate `official_url`
  - call `events.services` to create `Event`
  - mark draft approved
- On reject:
  - mark draft rejected
  - do not create `Event`
- Keep `Event` construction out of `drafts.views`.
- Wrap draft status changes and event publication in one transaction.

**Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/test_drafts_api.py`

Expected: PASS.

## Task 5: Verification And Documentation

**Files:**
- Modify: `docs/project-status.md`
- Add or modify a refactoring/work log document under `docs/refactoring/`

**Step 1: Run verification**

Run:

```bash
uv run python manage.py check
uv run pytest -q
```

Expected:

- Both commands pass.

**Step 2: Update status documents**

- Record the narrowed product scope.
- Record what was implemented.
- Record remaining deferred member features.

## Deferred Work

Deferred Refactoring Note

- Topic: Restore and complete member-facing APIs after event publishing workflow is stable.
- Why it is not part of the current scope: This release is intentionally constrained to event information collection and public browsing.
- Why it may be needed later: Status tracking and visit records may improve retention after content supply is reliable.
- Trigger condition: After operators can continuously publish reviewed event data with low friction.
- Expected change location: `events`, `accounts`, and member-facing API routes.
- Related tests: status APIs, visit records, and photo upload tests.
