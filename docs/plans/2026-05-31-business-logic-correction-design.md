# OshiLog Business Logic Correction Design

Date: 2026-05-31
Project root: `/Users/yeongroksong/Desktop/study/project/taku`

## Purpose

Correct the current backend business logic so the implementation matches the
OshiLog MVP boundary before adding more product behavior.

The current code already has a useful event-index foundation, but review found
four logic areas that should be corrected together:

- Published events can still be created without an official URL.
- Some draft state rules remain in HTTP views instead of the draft service
  boundary.
- Deferred member/archive APIs are currently exposed even though the event
  index MVP does not include them.
- Admin draft creation stores only the submitted URL and does not yet perform
  the planned safe fetch and rule-based extraction workflow.

This document is a design only. It does not authorize production code changes
without a follow-up implementation plan.

## Source Documents

Priority order:

1. `AGENTS.md`
2. `docs/plans/2026-05-20-oshilog-mvp-planning.md`
3. `docs/plans/2026-05-28-oshilog-event-index-implementation-plan.md`
4. `docs/plans/2026-05-29-url-fetch-extraction-design.md`
5. `docs/refactoring/2026-05-29-event-index-boundary-correction-work-log.md`
6. `docs/project-status.md`

## Approved Scope

This design covers:

- Enforcing that published events must have an official URL.
- Keeping draft review and draft update state rules inside the `drafts`
  domain/service layer.
- Bringing deferred member/archive endpoints back in line with the MVP scope.
- Implementing the first synchronous URL fetch and rule-based extraction
  pipeline for admin draft creation.
- Adding behavior tests and architecture boundary tests for the changes above.

This design does not cover:

- AI extraction.
- User-submitted URLs.
- Background workers, queues, or retry dashboards.
- A custom admin portal.
- Visit record photo processing beyond disabling or quarantining the deferred
  endpoint.
- Production-grade DNS rebinding defense.
- Full browser rendering or JavaScript execution for event pages.

## Recommended Approach

Use a conservative two-layer correction:

1. Tighten invariants and boundaries before adding fetch/extraction.
2. Add the synchronous fetch/extraction pipeline behind `drafts.services`.

This order avoids building URL fetching on top of weak publication rules. It
also keeps the MVP small: the admin still submits one URL and receives one
pending `EventDraft`; the difference is that the draft now contains fetched and
extracted candidate fields.

## Alternatives Considered

### Patch Only The Official URL Rule

This would fix the clearest violation quickly, but it leaves draft rules split
between views and services and leaves deferred member endpoints exposed. It is
too narrow for the requested scope.

### Full Refactor Into Separate Domains

Move member archive models and views out of `events`, introduce richer domain
packages, and redesign service boundaries broadly.

This is cleaner long-term, but it is too large for the MVP correction. The
current task should not normalize all future archive behavior before the event
publishing workflow is stable.

### Recommended: MVP Boundary Correction Plus URL Pipeline

Keep the Django app structure, add small named services/helpers, unexpose or
quarantine deferred member APIs, and implement the URL pipeline synchronously.

This matches the existing codebase and the current planning documents while
avoiding a broad architectural rewrite.

## Domain Boundary And Dependency Direction

Domain ownership:

- `events` owns published event invariants, public event read queries, and
  published event creation.
- `drafts` owns draft creation, URL safety, fetching, extraction, draft update
  state rules, approval, rejection, and draft-domain exceptions.
- `accounts` owns identity and staff/admin status. It is consumed through DRF
  permission classes only.
- `core` owns generic response helpers and must not import domain modules.

Allowed dependencies:

- `drafts.views -> drafts.serializers`
- `drafts.views -> drafts.services`
- `drafts.views -> core.errors`
- `drafts.services -> drafts.models`
- `drafts.services -> drafts.url_safety`
- `drafts.services -> drafts.fetching`
- `drafts.services -> drafts.extraction`
- `drafts.services -> events.services`
- `events.services -> events.models`
- `events.views -> events.serializers`
- `events.views -> events.models`

Disallowed dependencies:

- `events -> drafts`
- `drafts.views -> events.models`
- `drafts.fetching -> events`
- `drafts.extraction -> events`
- public event views using draft querysets or serializers
- member/archive routes expanding during this correction

Business logic placement:

- Published-event URL requirements belong in `events.services` and, where
  practical, model validation or database constraints.
- Draft state transitions and draft mutability rules belong in
  `drafts.services`.
- URL safety, HTTP fetching, and extraction belong in dedicated `drafts`
  helpers called by `drafts.services`.
- HTTP views should remain adapters for permissions, serializers, service
  calls, and response mapping.

## Coupling And Cohesion Review

This design lowers coupling by keeping cross-domain publication as
`drafts.services -> events.services`. Draft HTTP views never create `Event`
records directly.

It improves cohesion by keeping:

- event publication invariants in `events`
- draft lifecycle and URL ingestion behavior in `drafts`
- member/archive behavior outside the active MVP route surface

Remaining coupling:

- Member/archive models still live in `events.models`. This remains acceptable
  only if the endpoints are not expanded in this correction.
- `drafts.services` depends on `events.services` for publication. This is an
  intentional application-service dependency for the approval workflow.

Deferred trigger:

- If member/archive features return to active scope, split their views,
  serializers, services, URLs, and tests away from public event-index code.

## Pythonic Code Design

Use explicit Django and DRF structures:

- Small service functions for business actions.
- Dataclasses for simple service result objects when useful.
- Domain-specific exception classes mapped to HTTP responses in views.
- DRF serializers for request shape, response shape, and field validation.
- `transaction.atomic()` for approval and any multi-write workflow.
- Small pure helper functions for URL safety and extraction parsing.

Avoid:

- broad base service classes
- hidden serializer side effects that create or publish events
- large view methods mixing validation, persistence, state transition, and
  response construction
- silent input mutation or ignored fields
- real network calls in tests

## Design Area 1: Published Events Require Official URL

Rule:

- No `Event` with `publish_status=published` may be created without a non-empty
  official URL.

Design:

- `events.services.create_published_event()` validates `official_url` before
  duplicate checks or database writes.
- Blank strings, whitespace-only strings, and `None` raise a domain exception.
- Duplicate URL behavior remains a separate domain exception.
- Direct model creation in tests may still create draft/unpublished events
  without URLs, but published events should be protected either by model
  validation, a conditional database constraint, or a documented service-only
  rule.

Recommended implementation detail:

- Add `MissingOfficialUrlError` in `events.services`.
- Add a conditional database constraint only if it can be represented clearly
  for the selected database. If cross-database support is uncertain, start with
  service validation plus behavior tests and document the database constraint as
  deferred hardening.

Required tests:

- `create_published_event()` rejects `None`.
- `create_published_event()` rejects `""` and whitespace.
- Draft approval preserves the draft as pending when publication fails because
  the URL is missing.
- Public APIs still hide unpublished events.

## Design Area 2: Draft State Rules Move To Service Layer

Rule:

- Only pending drafts can be updated, approved, or rejected.

Design:

- Introduce a draft update service, for example `update_draft(draft_id, data)`.
- The service owns the pending-state check and raises `DraftStateError` for
  approved or rejected drafts.
- The serializer still owns field-level validation and immutable field errors.
- `AdminEventDraftDetailView.update()` becomes a thin adapter:
  validate request data, call the service, serialize the returned draft, map
  domain exceptions to HTTP responses.

Required tests:

- Pending draft update succeeds.
- Approved draft update returns controlled `400`.
- Rejected draft update returns controlled `400`.
- Immutable fields still return field-level `400`.
- Architecture tests confirm `drafts.views` does not import `events`.

## Design Area 3: Deferred Member APIs Return To MVP Boundary

Rule:

- User status, visit records, and photo upload are deferred from the first MVP.
  They should not be expanded while correcting the event publishing workflow.

Recommended decision:

- Keep the database models for now to avoid destructive migration churn.
- Stop exposing deferred `/api/me/` member/archive endpoints from the active URL
  configuration during the MVP correction.
- Keep or move existing code behind a clearly named deferred module only if it
  reduces risk. Do not add new member behavior.

Expected API effect:

- `/api/me/event-statuses/<event_id>/`
- `/api/me/visit-records/`
- `/api/me/visit-records/<record_id>/photos/`
- `/api/me/visit-records/<record_id>/photos/<photo_id>/`

These endpoints should not be part of the verified MVP route surface after the
correction unless the user explicitly re-approves member/archive scope.

Required tests:

- Active URL configuration no longer exposes deferred member/archive routes, or
  they return a controlled disabled response if route compatibility is required.
- Existing public event and admin draft routes still work.
- No new visit record or photo upload behavior is introduced.

Deferred Refactoring Note

- Topic: Split member archive behavior from `events`.
- Why it is not part of the current scope: The correction focuses on event
  publishing and draft ingestion.
- Why it may be needed later: Statuses, visit records, and photos need their
  own validation, ownership, and security rules when reactivated.
- Trigger condition: User archive becomes approved MVP or post-MVP scope.
- Expected change location: `events.models`, `events.views`,
  `events.serializers`, `events/status_urls.py`, and new archive services.
- Related tests: member status, visit record, photo authorization, upload
  validation, and delete behavior tests.

## Design Area 4: URL Fetch And Rule-Based Extraction

Rule:

- Admin draft creation from URL should safely fetch HTML, extract candidates,
  and create a pending `EventDraft` only after controlled validation succeeds.

Architecture:

- `drafts.url_safety`: validates URL scheme, host, resolved IPs, and redirect
  targets.
- `drafts.fetching`: performs bounded HTTP GET with timeout, redirect limit,
  content-type checks, and response size limit.
- `drafts.extraction`: parses HTML and extracts candidate fields.
- `drafts.services`: orchestrates draft creation and maps helper failures to
  draft-domain exceptions.

Data flow:

1. Admin submits `source_url`.
2. Serializer validates basic URL shape and duplicate `source_url`.
3. `drafts.services.create_draft_from_url()` validates URL safety.
4. Fetcher retrieves HTML with bounded timeout and size.
5. Redirect targets are safety-checked before each redirect is followed.
6. Extractor returns candidate values.
7. Service creates a pending `EventDraft`.
8. View returns the draft payload.

URL safety requirements:

- Allow only `http` and `https`.
- Reject missing hosts.
- Reject localhost and loopback hosts.
- Reject private, link-local, multicast, unspecified, and reserved IPs.
- Reject hosts that resolve only to blocked addresses.
- Reject unsafe redirect targets.

Fetch requirements:

- Use an OshiLog-specific user agent.
- Use short connect/read timeouts.
- Follow only a small redirect count.
- Accept only HTML-like content types.
- Enforce maximum response body size.
- Never store remote images or binary assets.
- Do not leak raw network exception messages to API responses.

Extraction requirements:

- Extract `raw_title` from Open Graph title, `<title>`, or heading text.
- Extract `raw_text` from normalized visible text or meta description.
- Extract `extracted_title` from the best title candidate.
- Extract `extracted_summary` from meta description or the first useful
  snippet.
- Extract conservative date candidates from Korean and ISO-like date patterns.
- Extract conservative region and location candidates.
- Extract category only when obvious keywords match supported categories.
- Fail with a controlled error when no meaningful title or text exists.

Error handling:

- Invalid URL: `400`.
- Unsafe URL: `400`.
- Duplicate source URL: field-level `400`.
- Unsupported content type: `400`.
- Oversized response: `400`.
- Empty extraction: `400`.
- Timeout or network failure: `503`.
- Unexpected fetch/extraction failure: log internally, return `503`.

Required tests:

- Admin draft creation fetches mocked HTML and stores extracted fields.
- Non-admin users cannot trigger fetch/extraction.
- Unsafe URLs are rejected without an outbound request.
- Redirects to unsafe URLs are rejected.
- Timeout creates no draft and returns controlled `503`.
- Unsupported content type creates no draft.
- Oversized response creates no draft.
- Empty extraction creates no draft.
- Duplicate `source_url` remains rejected.
- External network is never used in tests.

## API Contract After Correction

Public event APIs:

- `GET /api/events/`
- `GET /api/events/{id}/`

Admin draft APIs:

- `GET /api/admin/event-drafts/`
- `POST /api/admin/event-drafts/`
- `GET /api/admin/event-drafts/{id}/`
- `PATCH /api/admin/event-drafts/{id}/`
- `POST /api/admin/event-drafts/{id}/approve/`
- `POST /api/admin/event-drafts/{id}/reject/`

Deferred member/archive APIs:

- Not part of the active MVP route surface unless separately re-approved.

## TDD Checkpoints

Use one behavior test at a time.

1. Published-event official URL invariant.
2. Draft update state rule through service boundary.
3. Deferred member route behavior.
4. URL safety rejects unsafe URLs before fetch.
5. Fetcher handles timeout and unsupported content.
6. Extractor returns candidate fields from simple HTML.
7. Draft creation service creates a pending draft with extracted fields.
8. Admin API maps service errors to controlled JSON responses.
9. Architecture boundary tests preserve dependency direction.

## Verification Commands

Expected final verification after implementation:

```bash
uv run pytest -q tests/test_events_api.py tests/test_drafts_api.py tests/test_drafts_services.py tests/test_architecture_boundaries.py
uv run pytest -q
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

Additional targeted tests should be added for:

- URL safety.
- Fetching.
- Extraction.
- Disabled or unmounted deferred member routes.

## Security And Reliability Notes

- SSRF defense is current scope for the first URL fetch pipeline.
- DNS rebinding defense remains deferred unless the implementation can cover it
  simply and explicitly.
- URL fetching must be admin-only.
- Remote content must be treated as untrusted text.
- Extracted/admin-edited text must rely on standard template/serializer escaping
  when rendered.
- File upload behavior should not remain exposed as part of this MVP correction.

## Deferred Refactoring Note

- Topic: Background URL fetch and extraction worker.
- Why it is not part of the current scope: The first corrected MVP can use a
  synchronous admin workflow.
- Why it may be needed later: Slow sites, retries, and higher operator volume
  may make synchronous requests fragile.
- Trigger condition: Fetch latency exceeds acceptable admin request time or
  retry/status tracking becomes necessary.
- Expected change location: `drafts.services`, worker module, deployment
  configuration, and draft status fields.
- Related tests: draft creation, fetch retry, fetch status, and admin review
  tests.

## Deferred Refactoring Note

- Topic: Database-level published URL invariant.
- Why it is not part of the current scope: Service-level validation may be the
  smallest safe correction if conditional constraints complicate the migration.
- Why it may be needed later: Direct ORM writes, admin imports, or future
  management commands could bypass the service.
- Trigger condition: Any non-service code path creates or updates published
  events.
- Expected change location: `events.models` constraints and migrations.
- Related tests: model constraint tests and migration checks.

## Open Decisions Before Implementation Plan

- Should deferred member routes return `404` by being unmounted, or a controlled
  disabled response such as `410` or `403`?
- Should the official URL invariant be enforced only in `events.services`, or
  also as a model/database constraint in the same implementation slice?
- Which HTTP client should the fetcher use: `httpx` or `requests`?
- What maximum response size and timeout values should be used for the first
  MVP implementation?
