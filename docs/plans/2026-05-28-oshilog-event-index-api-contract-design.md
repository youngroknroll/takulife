# OshiLog Event Index Backend API Contract Design

Date: 2026-05-28
Project root: `/Users/yeongroksong/Desktop/study/project/taku`

## Source Documents

Priority order:

1. `AGENTS.md`
2. `docs/plans/2026-05-28-oshilog-event-index-design.md`
3. `docs/project-status.md`
4. `docs/refactoring/2026-05-27-backend-api-progress-log.md`
5. `docs/plans/2026-05-28-oshilog-event-index-implementation-plan.md`

The 2026-05-28 event index direction supersedes the broader 2026-05-20 MVP
direction for the next backend API slice.

## Subagent Analysis Used

- PO / General Manager: `gpt-5.5`
- Tech Lead / Architect: `gpt-5.4`
- TDD Expert: `gpt-5.4-mini`
- Security / Reliability: `gpt-5.3-codex`
- QA: `gpt-5.3-codex`

Infra / DevOps was not run as a parallel subagent because the active subagent
limit was reached. Its concerns are covered in this document as migration and
verification requirements.

## Current State

Already implemented:

- `GET /api/auth/me/`
- `GET /api/events/`
- `GET/POST /api/admin/event-drafts/`
- `PUT /api/me/event-statuses/<event_id>/`
- `POST /api/me/visit-records/`
- Visit record photo create/delete APIs.

Current product direction excludes the member-facing APIs from the next delivery
target. They may remain in code, but this API contract does not extend them.

## Approved Design Scope

This design covers the Event Index backend API contract only:

- Public published event list and detail.
- Public keyword search.
- Public region and category filters.
- Operator/admin draft create, list, detail, update, approve, and reject.
- Draft visibility rules.
- Duplicate URL rejection.
- Approval and rejection side effects.
- TDD and verification requirements for the next implementation plan.

Out of scope:

- User event status expansion.
- Visit records and photo upload.
- Personal archive APIs.
- Google login.
- User-submitted event URLs.
- AI extraction.
- Custom admin UI.
- Deployment hardening.
- Full URL fetch/extraction and SSRF hardening.

## API Naming Decisions

- Public API uses `category` as the query parameter and response field because
  the latest product design calls this an event category.
- Implementation may keep an internal model field named `event_type` only if the
  serializer maps it to `category`. The public contract must not expose both
  names.
- Public APIs must not expose `publish_status`; every public event response is
  already implicitly published.
- Admin draft APIs may expose `review_status`.

## Domain Boundary And Dependency Direction

Domain ownership:

- `events` owns published `Event` invariants, public event reads, event list
  filtering, event detail serialization, and the function that creates a
  published event from reviewed data.
- `drafts` owns `EventDraft` invariants, draft input validation, review status
  transitions, and operator workflow orchestration.
- `accounts` owns identity and staff/admin status. It is used only through
  authentication/permission checks in this slice.
- `core` remains limited to shared API root and health behavior.

Allowed dependency direction:

- `events` must not depend on `drafts`.
- `drafts.views` must not import or create `Event` directly.
- `drafts.views` may call `drafts.services`.
- `drafts.services` may call an explicit `events` service boundary to publish
  reviewed event data.
- `events` public read APIs must remain independent from draft serializers,
  draft querysets, and member-facing `/api/me/` behavior.

Business logic placement:

- Draft status transitions belong in `EventDraft` model methods or
  `drafts.services`, not in HTTP views.
- Published event creation belongs behind an `events` application boundary, not
  inline in `drafts.views`.
- HTTP views should coordinate authentication, serializer invocation, service
  calls, and response mapping only.
- Serializers should validate request shape and field-level input, but should
  not own cross-domain publication rules.

Dependencies that must be avoided or inverted:

- Avoid `drafts.views -> events.models.Event`.
- Avoid `events -> drafts`.
- Avoid adding member archive behavior to public event-index views.
- If publication needs to mutate both draft and event data, perform that
  orchestration in a clearly named application service with a transaction.

## Coupling And Cohesion Review

The design lowers coupling only if draft publication crosses into `events`
through an explicit service boundary. Direct model construction from the draft
view would increase coupling and is not acceptable for implementation under the
current guide.

Cohesion targets:

- `events`: cohesive around published event data and public reads.
- `drafts`: cohesive around operator draft review workflow.
- `accounts`: cohesive around user identity and staff/admin permission.
- `core`: cohesive around shared infrastructure only.

Remaining coupling to document as deferred work:

- Existing member-facing models and views still live in the `events` app.
- Existing `/api/me/` behavior is not part of this slice and should not be
  expanded while completing event-index APIs.

## Pythonic Code Design

Implementation should be explicit, boring, and framework-native:

- Use DRF generic views or small `APIView` classes only as HTTP adapters.
- Use separate serializers when create/detail/update contracts differ enough to
  avoid silent data mutation.
- Use model methods or service functions for draft status transitions.
- Use an `events` service function for published event creation from reviewed
  data.
- Use `transaction.atomic()` in the service that changes draft status and
  creates a published event.
- Use database constraints and explicit validation together for duplicate URL
  behavior.
- Use small named helper functions if mapping draft fields into event fields
  becomes non-trivial.

Avoid:

- large procedural view methods that mix validation, transition, persistence,
  and response construction
- silent dropping of writable fields in serializers
- cross-domain imports from HTTP views
- generalized service frameworks or base classes that are not needed for this
  slice

## Public Event APIs

### `GET /api/events/`

Access:

- Public.
- No authentication required.

Query parameters:

- `q`: optional keyword search.
- `region`: optional exact region filter.
- `category`: optional exact event category filter.
- `page`: optional pagination parameter from DRF page pagination.

Behavior:

- Return only events with `publish_status=published`.
- Apply `q`, `region`, and `category` together with AND semantics.
- Return an empty result set when no event matches.
- Keep DRF pagination shape: `count`, `next`, `previous`, `results`.

Response event fields:

- `id`
- `title`
- `category`
- `work_title`
- `location_name`
- `region`
- `start_date`
- `end_date`
- `official_url`
- `source_name`
- `summary`

### `GET /api/events/{id}/`

Access:

- Public.
- No authentication required.

Behavior:

- Return `200` for a published event.
- Return `404` for unpublished, draft, rejected, or missing records.
- Do not reveal whether an unpublished record exists.

Response fields:

- Same event fields as the public list item.

## Admin Draft APIs

All admin draft endpoints require admin/operator permission. In the current
Django project, this means `IsAdminUser` / `is_staff` unless a later approved
auth policy defines a separate operator role.

### `POST /api/admin/event-drafts/`

Request fields:

- `source_url`: required, HTTP or HTTPS URL.

Behavior:

- Create a pending draft.
- Reject duplicate `source_url`.
- Reject non-HTTP(S) URL schemes.
- Do not fetch or extract remote content in this slice.

Success:

- `201 Created`
- Response includes draft fields.

Failure:

- `400 Bad Request` with DRF field errors for invalid URL, unsupported scheme,
  or duplicate `source_url`.

### `GET /api/admin/event-drafts/`

Behavior:

- Return all drafts visible to admin users.
- Default ordering may remain newest first.
- Public users and non-admin users are denied.

### `GET /api/admin/event-drafts/{id}/`

Behavior:

- Return one draft for admin users.
- Return `404` when the draft does not exist.

### `PATCH /api/admin/event-drafts/{id}/`

Allowed fields:

- `extracted_title`
- `extracted_category`
- `extracted_work_title`
- `extracted_location_name`
- `extracted_region`
- `extracted_start_date`
- `extracted_end_date`
- `extracted_summary`
- `source_name`

Behavior:

- Only pending drafts may be updated.
- `review_status` must not be patchable.
- Approved and rejected drafts are read-only until a separate reopen workflow is
  explicitly approved.

Failure:

- `400 Bad Request` with `detail` for invalid state transition or read-only
  draft updates.

### `POST /api/admin/event-drafts/{id}/approve/`

Behavior:

- Only pending drafts may be approved.
- Approval creates one published `Event`.
- Approval marks the draft as approved.
- Event creation and draft state update must be atomic.
- Approval must be implemented through a draft workflow service that delegates
  published event creation to an `events` service boundary.
- Duplicate `official_url` must be rejected before creating another `Event`.
- Repeated approve or approve-after-reject must fail.

Success:

- `200 OK`
- Response includes the approved draft and the created event id, or the created
  event representation.

Failure:

- `400 Bad Request` for duplicate `official_url` or invalid state transition.
- No partial write is allowed on failure.

### `POST /api/admin/event-drafts/{id}/reject/`

Behavior:

- Only pending drafts may be rejected.
- Rejection marks the draft as rejected.
- Rejection does not create an `Event`.
- Repeated reject or reject-after-approve must fail.

Success:

- `200 OK`
- Response includes the rejected draft.

Failure:

- `400 Bad Request` for invalid state transition.

## Draft Fields

Minimum draft fields for this slice:

- `id`
- `source_url`
- `source_name`
- `raw_title`
- `raw_text`
- `extracted_title`
- `extracted_category`
- `extracted_work_title`
- `extracted_location_name`
- `extracted_region`
- `extracted_start_date`
- `extracted_end_date`
- `extracted_summary`
- `review_status`
- `created_at`
- `updated_at`

## Permission Contract

- Anonymous users may access only public event list/detail.
- Authenticated non-admin users may access only public event list/detail for this
  slice.
- Admin users may access public event APIs and all admin draft APIs.
- Public endpoints must not use admin serializers or draft querysets.

## Error Contract

Use DRF's default response style instead of introducing a new global error
shape in this slice.

Expected mappings:

- Validation errors: `400`
- Duplicate URL errors: `400`
- Invalid draft state transition: `400`
- Permission denied: `403`
- Missing or unpublished public event detail: `404`

## TDD Plan For Implementation

Add one failing behavior test at a time.

Recommended order:

1. `test_public_event_detail_returns_published_event`
2. `test_public_event_detail_hides_unpublished_event`
3. `test_public_event_list_filters_by_q`
4. `test_public_event_list_filters_by_region`
5. `test_public_event_list_filters_by_category`
6. `test_admin_can_retrieve_event_draft`
7. `test_admin_can_patch_pending_event_draft`
8. `test_admin_cannot_patch_approved_event_draft`
9. `test_admin_can_approve_event_draft`
10. `test_admin_can_reject_event_draft`
11. `test_non_admin_cannot_access_event_drafts`
12. `test_duplicate_source_url_is_rejected_on_create`
13. `test_approve_rejects_duplicate_official_url`
14. `test_approve_is_atomic_when_event_creation_fails`

Test placement:

- Public event behavior: `tests/test_events_api.py`
- Draft workflow behavior: `tests/test_drafts_api.py`

Assertions should verify behavior only:

- HTTP status.
- Response body fields.
- Result counts.
- Draft status changes.
- Event creation or non-creation.

Do not assert private serializer internals or query construction.

## Implementation Boundary

Expected files for the next implementation plan:

- `events/models.py`
- `events/serializers.py`
- `events/services.py`
- `events/views.py`
- `events/urls.py`
- `drafts/models.py`
- `drafts/serializers.py`
- `drafts/services.py`
- `drafts/views.py`
- `drafts/urls.py`
- `tests/test_events_api.py`
- `tests/test_drafts_api.py`
- Django migration files for changed models.
- `docs/project-status.md`
- A work log under `docs/refactoring/`.

Do not modify in the next slice unless a failing test proves it is required:

- `accounts/*`
- `core/*`
- Existing `/api/me/` member endpoints.
- Visit record/photo behavior.

## Migration And Operational Notes

- Adding event and draft fields requires migrations.
- Published event `official_url` should be unique at the database level.
- Existing SQLite tests are acceptable for the current project state, but the
  implementation should avoid relying on SQLite-only behavior.
- Approval must use a transaction so draft state and event creation cannot
  diverge.
- URL fetch/extraction must remain deferred; accepting a URL is not the same as
  safely fetching that URL.

## Verification Commands

Targeted during TDD:

```bash
uv run pytest -q tests/test_events_api.py
uv run pytest -q tests/test_drafts_api.py
```

Final verification:

```bash
uv run python manage.py check
uv run pytest -q
```

## Deferred Refactoring Notes

Deferred Refactoring Note

- Topic: URL fetch SSRF hardening and network egress safety.
- Why it is not part of the current scope: This slice defines URL input and
  duplicate behavior only; real remote fetching remains out of scope.
- Why it may be needed later: Fetch/extraction will introduce SSRF, redirect,
  DNS, timeout, and private-network risks.
- Trigger condition: When `source_url` based HTTP fetch/extraction is added.
- Expected change location: `drafts` URL validation/fetch boundary and runtime
  network configuration.
- Related tests: scheme allowlist, private/loopback IP blocking, redirect
  limits, timeout handling, DNS rebinding defenses.

Deferred Refactoring Note

- Topic: Separate member-facing event APIs from public event index code.
- Why it is not part of the current scope: The approved scope is public event
  read APIs and operator draft workflow, not internal module cleanup.
- Why it may be needed later: Member archive features and public event index
  features currently coexist inside `events`, increasing coupling risk.
- Trigger condition: When `/api/me/` member features resume active development
  or public event APIs grow beyond list/detail/search/filter.
- Expected change location: `events/views.py`, `events/status_urls.py`, and
  possibly a future member-focused module.
- Related tests: `tests/test_events_api.py`,
  `tests/test_user_event_status_api.py`, `tests/test_visit_records_api.py`.
