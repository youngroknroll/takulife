# OshiLog Business Logic Correction Implementation Plan

Date: 2026-05-31
Design source: `docs/plans/2026-05-31-business-logic-correction-design.md`

## Approved Scope

- Enforce official URL requirement for published events.
- Move draft update state rule into `drafts.services`.
- Remove deferred member/archive endpoints from active URL routing.
- Implement admin draft URL fetch and extraction pipeline with safe URL checks.
- Add focused tests for all behavior above.

Out of scope:

- AI extraction.
- Background workers and retry queues.
- Re-enabling deferred member/archive endpoints.
- Broad model split between event index and archive domains.

## Acceptance Criteria

- Published event creation rejects missing or blank `official_url`.
- Draft approval with invalid official URL returns a controlled field error and
  keeps the draft pending.
- Draft PATCH state rule is enforced by `drafts.services` and API behavior is
  unchanged (`400` for non-pending drafts).
- `/api/me/` member/archive routes are not exposed in `config.urls`.
- `POST /api/admin/event-drafts/` performs safe fetch+extract and stores
  candidate fields into pending draft records.
- Draft creation returns controlled `400` or `503` responses for invalid URL,
  unsafe URL, unsupported content, oversized response, timeout/network failure,
  and empty extraction.
- Existing public event read and admin draft review behavior remains intact.

## Domain Boundary And Dependency Direction

Owners:

- `events`: published event invariants and creation.
- `drafts`: draft creation/review/update workflow and URL ingestion pipeline.
- `core`: generic HTTP error response helpers.

Allowed dependencies:

- `drafts.views -> drafts.services`
- `drafts.services -> drafts.models`
- `drafts.services -> drafts.url_safety`
- `drafts.services -> drafts.fetching`
- `drafts.services -> drafts.extraction`
- `drafts.services -> events.services`
- `events.services -> events.models`

Disallowed dependencies:

- `drafts.views -> events.models`
- `events -> drafts`

## Coupling And Cohesion Review

- Coupling is reduced by keeping cross-domain publication only through
  `drafts.services -> events.services`.
- Cohesion is improved by centralizing draft mutability and creation workflow
  inside `drafts.services`.
- Deferred member/archive behavior remains in code but is removed from active
  routing to preserve MVP boundary.

## Pythonic Code Design

- Use small explicit service/helper functions.
- Use domain exceptions and explicit HTTP mapping.
- Keep views thin; do not embed business transitions in view methods.
- Keep tests behavior-focused and mock external network calls.

## TDD Checkpoints

1. Add failing tests for published-event official URL invariant.
2. Add failing tests for draft update service state rule.
3. Add failing tests for deferred `/api/me/` route behavior.
4. Add failing tests for URL fetch/extraction draft creation behavior and error
   mapping.
5. Implement minimum code per checkpoint until green.

## Planned File Changes

- Modify: `events/services.py`
- Modify: `drafts/services.py`
- Modify: `drafts/views.py`
- Modify: `config/urls.py`
- Add: `drafts/url_safety.py`
- Add: `drafts/fetching.py`
- Add: `drafts/extraction.py`
- Modify/Add tests:
  - `tests/test_drafts_api.py`
  - `tests/test_drafts_services.py`
  - `tests/test_user_event_status_api.py`
  - `tests/test_visit_records_api.py`
  - `tests/test_architecture_boundaries.py`
  - `tests/test_events_services.py` (new)

## Verification Commands

```bash
uv run pytest -q tests/test_events_services.py tests/test_drafts_services.py tests/test_drafts_api.py tests/test_user_event_status_api.py tests/test_visit_records_api.py tests/test_architecture_boundaries.py
uv run pytest -q
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

## Deferred Work

Deferred Refactoring Note

- Topic: Background URL fetch worker and retry state.
- Why it is not part of the current scope: current scope is synchronous MVP.
- Why it may be needed later: latency/retry throughput at scale.
- Trigger condition: admin fetch latency or reliability becomes unacceptable.
- Expected change location: `drafts.services` and worker modules.
- Related tests: fetch retry and async state transition tests.
