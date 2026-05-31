# Business Logic Correction Work Log

Date: 2026-05-31
Plan source: `docs/plans/2026-05-31-business-logic-correction-implementation-plan.md`

## Scope

Implemented the approved business logic correction scope:

- Enforced official URL requirement for published events.
- Moved draft update state rule into `drafts.services`.
- Removed deferred member/archive routes from active URL config.
- Added synchronous URL fetch + extraction pipeline for admin draft creation.

## Changes

- Added `MissingOfficialUrlError` and blank/whitespace URL guard in
  `events.services.create_published_event()`.
- Added draft creation pipeline modules:
  - `drafts/url_safety.py`
  - `drafts/fetching.py`
  - `drafts/extraction.py`
- Added `drafts.services.create_draft_from_url()` orchestration and draft
  creation exceptions.
- Added `drafts.services.update_draft()` so pending-state update rules live in
  the service layer.
- Updated `drafts.views`:
  - list/create view now routes create behavior through draft service pipeline
  - draft update now uses `update_draft()` service
  - approve view now maps missing-official-url failure to a field-level `400`
- Removed `path("api/me/", include("events.status_urls"))` from root URL
  routing.

## Verification

```bash
uv run pytest -q tests/test_events_services.py tests/test_drafts_services.py tests/test_drafts_api.py tests/test_user_event_status_api.py tests/test_visit_records_api.py tests/test_architecture_boundaries.py
```

Result:

```text
40 passed in 6.37s
```

```bash
uv run pytest -q
```

Result:

```text
55 passed in 6.47s
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

## Remaining Risks

- URL safety currently blocks localhost and unsafe literal IP ranges; full
  DNS-resolution safety and rebinding hardening remain deferred.
- Deferred member/archive endpoint code still exists in app modules, even
  though routes are unmounted from root URL config.

## Deferred Refactoring Note

- Topic: DNS-resolution-based URL safety hardening.
- Why it is not part of the current scope: synchronous MVP correction focused
  on safe minimum behavior and deterministic tests.
- Why it may be needed later: production URL fetching can be exposed to private
  destination resolution via DNS answers.
- Trigger condition: expanding URL ingestion beyond trusted admin usage or
  moving to higher-volume production traffic.
- Expected change location: `drafts/url_safety.py`, `drafts/fetching.py`, and
  related security tests.
- Related tests: URL safety and redirect safety test suites.
