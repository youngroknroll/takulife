# Core Error Response Helpers Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a small shared `core.errors` helper module for HTTP error response formatting while keeping domain exceptions inside their owning apps.

**Architecture:** `core.errors` will expose generic response helpers only. `drafts.services` keeps draft-domain exceptions, and `events.services` keeps event-domain exceptions. `drafts.views` may import `core.errors` for response formatting and `drafts.services` for workflow exceptions, but it must not import `events` modules.

**Tech Stack:** Python, Django REST Framework, pytest.

---

## Approved Scope

- Add shared error response helper functions under `core/errors.py`.
- Use the helpers in draft approve/reject/update error responses.
- Preserve existing response payloads and status codes.
- Preserve domain boundaries:
  - domain exceptions remain in `drafts.services` and `events.services`
  - `drafts.views` must not import `events` modules
  - `core.errors` must not import `drafts` or `events`

## Acceptance Criteria

- Existing draft API error responses remain unchanged.
- `core.errors.error_response()` returns `{"detail": message}`.
- `core.errors.field_error_response()` returns `{field: [message]}`.
- `drafts.views` uses `core.errors` helpers for repeated error response shapes.
- Architecture tests prevent `core.errors` from importing domain modules.
- `uv run pytest -q` passes.
- `uv run python manage.py check` passes.

## Domain Boundary And Dependency Direction

Allowed dependencies:

- `drafts.views -> core.errors`
- `drafts.views -> drafts.services`
- `drafts.views -> drafts.serializers`
- `drafts.services -> events.services`

Disallowed dependencies:

- `core.errors -> drafts`
- `core.errors -> events`
- `drafts.views -> events`

## Coupling And Cohesion Review

This keeps HTTP response formatting cohesive in `core.errors` without moving
business meaning into `core`. Domain-specific exception names stay in their
owning domains, so `core` does not become a business-logic registry.

## Pythonic Code Design

Use two small explicit helper functions instead of a generic error framework.
Keep the helpers boring and DRF-native by returning `rest_framework.response.Response`.

## Task 1: Add Core Error Response Helpers

**Files:**
- Create: `core/errors.py`
- Modify: `tests/test_architecture_boundaries.py`

**Step 1: Write the failing tests**

Add tests that:

- `error_response("Not found.", 404)` returns status `404` and `{"detail": "Not found."}`
- `field_error_response("official_url", "Duplicate")` returns status `400` and `{"official_url": ["Duplicate"]}`
- `core.errors` does not import `drafts` or `events`

**Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_architecture_boundaries.py`

Expected: FAIL because `core.errors` does not exist.

**Step 3: Write minimal implementation**

Create `core/errors.py` with:

- `error_response(detail, status_code)`
- `field_error_response(field, message, status_code=400)`

**Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/test_architecture_boundaries.py`

Expected: PASS.

## Task 2: Use Helpers In Draft Views

**Files:**
- Modify: `drafts/views.py`
- Test: `tests/test_drafts_api.py`
- Test: `tests/test_architecture_boundaries.py`

**Step 1: Write or confirm behavior tests**

The existing draft API tests already cover:

- missing draft approve/reject returns 404 detail response
- invalid state returns 400 detail response
- duplicate official URL returns 400 field response
- publish failure returns 503 detail response

**Step 2: Run tests before implementation**

Run: `uv run pytest -q tests/test_drafts_api.py tests/test_architecture_boundaries.py`

Expected: PASS before refactor.

**Step 3: Refactor minimally**

Import `error_response` and `field_error_response` from `core.errors`.
Replace repeated `Response(...)` calls in `drafts.views` where the shape matches
the helpers.

**Step 4: Run tests after refactor**

Run: `uv run pytest -q tests/test_drafts_api.py tests/test_architecture_boundaries.py`

Expected: PASS.

## Task 3: Verification And Documentation

**Files:**
- Modify: `docs/project-status.md`
- Modify: `docs/refactoring/2026-05-29-event-index-boundary-correction-work-log.md`

**Step 1: Run verification**

Run:

```bash
uv run pytest -q
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

Expected: all pass, and no migrations are generated.

**Step 2: Update docs**

Record the new helper module, boundary decision, and verification evidence.
