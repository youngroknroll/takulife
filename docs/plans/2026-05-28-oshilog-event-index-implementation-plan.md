# OshiLog Event Index Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the first OshiLog release as a searchable event information index with draft-based operator publishing.

**Architecture:** Keep the backend as a Django + Django REST Framework monolith. Limit this phase to `Event` public read APIs and `EventDraft` operator workflow APIs. Defer member-facing APIs even if some related code already exists.

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
- `python manage.py check` exits successfully.
- `python -m pytest -q` exits successfully.

## Task 1: Align Domain Models To Event Index Scope

**Files:**
- Modify: `events/models.py`
- Modify: `drafts/models.py`
- Test: `tests/test_events_api.py`
- Test: `tests/test_drafts_api.py`

**Step 1: Write the failing test**

Add a test that the public event model exposes category and region filtering fields.

**Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_events_api.py`

Expected: FAIL because current `Event` model is too narrow.

**Step 3: Write minimal implementation**

- Extend `Event` with fields needed for public list/detail:
  - `event_type`
  - `work_title`
  - `location_name`
  - `region`
  - `official_url`
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
- filtering by `event_type`
- keyword search

**Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_events_api.py`

Expected: FAIL because detail and filters are incomplete.

**Step 3: Write minimal implementation**

- Add public detail endpoint.
- Add list filtering for:
  - `q`
  - `region`
  - `event_type`
- Keep only `published` events visible.

**Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/test_events_api.py`

Expected: PASS.

## Task 3: Expand Draft Review Workflow

**Files:**
- Modify: `drafts/serializers.py`
- Modify: `drafts/views.py`
- Modify: `drafts/urls.py`
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

**Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/test_drafts_api.py`

Expected: PASS.

## Task 4: Approve Draft Into Published Event

**Files:**
- Modify: `drafts/views.py`
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
  - create `Event`
  - mark draft approved
- On reject:
  - mark draft rejected
  - do not create `Event`

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

