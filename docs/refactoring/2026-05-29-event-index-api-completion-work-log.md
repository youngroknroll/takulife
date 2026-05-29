# Event Index API Completion Work Log

Date: 2026-05-29
Plan: `docs/plans/2026-05-28-oshilog-event-index-implementation-plan.md`
Contract: `docs/plans/2026-05-28-oshilog-event-index-api-contract-design.md`

## What Changed

- Added public event detail API: `GET /api/events/{id}/`.
- Kept public event list/detail limited to published events.
- Added public event list filtering:
  - `q`
  - `region`
  - `category`
- Updated the public event serializer to expose event-index fields and hide
  internal `publish_status`.
- Expanded `Event` with event-index fields:
  - `category`
  - `work_title`
  - `location_name`
  - `region`
  - `start_date`
  - `end_date`
  - `official_url`
  - `source_name`
  - `summary`
- Expanded `EventDraft` with candidate review fields and timestamps.
- Added admin draft detail/update API:
  - `GET /api/admin/event-drafts/{id}/`
  - `PATCH /api/admin/event-drafts/{id}/`
- Restricted draft updates to pending drafts.
- Added admin draft review actions:
  - `POST /api/admin/event-drafts/{id}/approve/`
  - `POST /api/admin/event-drafts/{id}/reject/`
- Approval creates a published `Event` and marks the draft approved.
- Rejection marks the draft rejected and creates no `Event`.
- Approval is wrapped in a transaction.
- Added validation for HTTP/HTTPS-only `source_url` input.
- Added initial migrations for `accounts`, `events`, and `drafts`.
- Addressed QA and Tech Lead review findings:
  - Added combined `q` + `region` + `category` filter coverage.
  - Expanded non-admin draft API access coverage.
  - Added rejected/approved state transition coverage.
  - Restricted draft PATCH to review fields.
  - Blocked `PUT /api/admin/event-drafts/{id}/`.
  - Hardened approve/reject with conditional pending-state updates.

## TDD Evidence

Targeted tests were added before implementation for the new behavior, including:

- Public event detail.
- Hidden unpublished event detail.
- `q`, `region`, and `category` filters.
- Public response `category` field and hidden `publish_status`.
- Draft detail.
- Pending draft patch.
- Approved draft patch rejection.
- Draft approve.
- Draft reject.
- Non-admin draft review access rejection.
- Duplicate `source_url` rejection.
- Non-HTTP(S) `source_url` rejection.
- Duplicate `official_url` rejection during approval.
- Approved draft cannot be rejected.
- Combined public filters.
- Rejected draft patch rejection.
- Source/raw draft field immutability on PATCH.
- Draft PUT method rejection.
- Rejected draft cannot be approved.
- Approved draft cannot be approved again.
- Approval rollback when event creation fails.

Some later tests passed immediately because earlier minimal implementation had
already introduced the required behavior. They remain as regression coverage.

## Verification

Fresh verification run:

```bash
uv run pytest -q tests/test_events_api.py
```

Result:

```text
9 passed in 0.13s
```

```bash
uv run pytest -q tests/test_drafts_api.py
```

Result:

```text
17 passed in 3.81s
```

```bash
uv run pytest -q
```

Result:

```text
36 passed in 4.81s
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

## Risks Remaining

- URL fetch/extraction is still out of scope. Accepting a URL does not mean the
  project is safe to fetch that URL yet.
- `Event.official_url` allows `NULL` so existing tests and old event creation
  paths keep working. Published events created through approval receive a real
  `official_url`.
- Initial migrations were added after models already existed in the repository.
  Existing local databases may need normal migration review or `--fake-initial`
  handling if tables were created before migrations were committed.
- Member-facing `/api/me/` endpoints still live in the `events` app and remain
  deferred from the current product direction.

## Deferred Refactoring

Deferred Refactoring Note

- Topic: URL fetch SSRF hardening and extraction pipeline.
- Why it is not part of the current scope: This slice implements the reviewed
  draft workflow and URL input boundary, not remote HTTP fetching.
- Why it may be needed later: Operator URL submission ultimately needs safe
  fetch/extraction with private-network protection, redirects, timeout, and
  retry policy.
- Trigger condition: When actual URL fetch/extraction is added.
- Expected change location: `drafts` validation/fetch code and related tests.
- Related tests: scheme allowlist, private IP blocking, redirect limits,
  timeout handling, duplicate URL behavior.

Deferred Refactoring Note

- Topic: Separate member-facing event APIs from event-index APIs.
- Why it is not part of the current scope: The approved scope keeps existing
  member APIs unchanged and completes public event/admin draft APIs.
- Why it may be needed later: Continued growth of `/api/me/` features inside
  `events` can increase coupling with public event index behavior.
- Trigger condition: When member archive features resume active development.
- Expected change location: `events/views.py`, `events/status_urls.py`, and
  future member-specific modules.
- Related tests: `tests/test_user_event_status_api.py`,
  `tests/test_visit_records_api.py`, `tests/test_events_api.py`.
