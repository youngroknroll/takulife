# Event Index Boundary Correction Work Log

Date: 2026-05-29

## Scope

Reviewed and corrected the Event Index backend implementation against the
revised domain-boundary, coupling/cohesion, and Pythonic code design
requirements.

## Agent Review Inputs

- Tech Lead / Architect reviewed domain boundaries, dependency direction,
  coupling/cohesion, and Pythonic Django/DRF design.
- TDD Expert identified the smallest behavior tests for immutable draft fields
  and draft workflow service boundaries.
- Security / Reliability reviewed duplicate publication, state transitions,
  admin-only access, URL validation, data exposure, and failure semantics.

## Changes

- Added `events.services.create_published_event()` as the published event
  creation boundary.
- Added `drafts.services.approve_draft()` and `drafts.services.reject_draft()`
  as the draft workflow boundary.
- Removed direct published `Event` creation from `drafts.views`.
- Removed `events` module imports from `drafts.views`; event publication
  failures are mapped to draft-domain exceptions in `drafts.services`.
- Kept draft approve/reject HTTP views focused on permissions, object lookup,
  service calls, and response mapping.
- Added `core.errors` for generic HTTP error response helpers while keeping
  domain exceptions in `drafts.services` and `events.services`.
- Removed the approve/reject pre-lookup from `drafts.views`; missing draft
  behavior is now handled through the draft service boundary.
- Added explicit immutable-field PATCH rejection for `source_url`, `raw_title`,
  and `raw_text`.
- Added an architecture boundary test that prevents `drafts.views` from
  importing `events` modules.
- Added service-level tests for draft approval and rejection.
- Changed publish failure behavior from an uncaught server exception to a
  controlled `503` JSON response without changing draft status.
- Clarified the design document: this slice creates URL-only drafts and does
  not fetch or extract remote content.
- Replaced a model-shape-first TDD step in the implementation plan with a
  public API behavior test requirement.

## Verification

```bash
uv run pytest -q tests/test_architecture_boundaries.py tests/test_drafts_api.py
```

Result:

```text
23 passed in 4.29s
```

```bash
uv run pytest -q tests/test_architecture_boundaries.py tests/test_drafts_api.py tests/test_drafts_services.py
```

Result:

```text
22 passed in 4.91s
```

```bash
uv run pytest -q tests/test_drafts_api.py tests/test_drafts_services.py
```

Result:

```text
19 passed in 4.45s
```

```bash
uv run pytest -q
```

Result:

```text
44 passed in 5.16s
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

## Remaining Risks And Deferred Work

Deferred Refactoring Note

- Topic: Normalize `source_url` before uniqueness checks.
- Why it is not part of the current scope: The current correction focused on
  documented service boundaries and explicit update errors.
- Why it may be needed later: Equivalent URLs with casing, default ports, or
  trailing slash differences may bypass operator intent.
- Trigger condition: Before adding remote fetching/extraction or importing
  event URLs from external feeds.
- Expected change location: `drafts.serializers` or a draft URL normalization
  helper.
- Related tests: draft creation duplicate URL behavior.

Deferred Refactoring Note

- Topic: Split public event-index code from deferred member archive code.
- Why it is not part of the current scope: The revised plan explicitly keeps
  member-facing APIs unchanged.
- Why it may be needed later: Public event APIs and `/api/me/` archive APIs
  still share `events.views` and `events.serializers`.
- Trigger condition: Before expanding either public discovery behavior or
  member archive behavior.
- Expected change location: `events.views`, `events.serializers`, and URL
  modules.
- Related tests: public event API tests and member `/api/me/` API tests.
