# Backend Follow-up Work Log

Date: 2026-06-24

## Scope Completed

- Characterized reversed event date ranges and null-date ordering without
  changing the public response contract.
- Reused `Event.objects.published()` in active archive validation and inactive
  legacy event views where direct publication filters remained.
- Changed archive status creation to explicit `user`, `event`, and `status`
  service inputs instead of passing a DRF serializer into the service layer.
- Added per-hop redirect validation, hostname resolution checks, and streaming
  byte limits to draft URL fetching.
- Mapped draft creation unique races into the existing field-keyed HTTP error
  shape.
- Added a service-level mutable-field allowlist for pending draft updates.
- Expanded event service contract and cross-domain import boundary tests.

## Design Review

Events remains the owner of published catalog query intent. Drafts owns URL
fetch safety, extraction input handling, draft state rules, and publication
orchestration. Archive owns user status persistence and duplicate handling. No
new dependency on `archive` was introduced from `events` or `drafts`.

The archive service no longer depends on an HTTP/DRF object. Draft fetch rules
are cohesive in `drafts.url_safety` and `drafts.fetching`, while HTTP response
mapping remains in `drafts.views`. The implementation uses small functions,
Django querysets, explicit domain exceptions, and transaction boundaries rather
than adding a generalized framework.

## TDD And Review Evidence

Targeted tests were observed failing before implementation for:

- explicit archive service inputs;
- unsafe redirect mapping and redirect-hop validation;
- resolved loopback addresses;
- streaming response size enforcement;
- duplicate draft creation races;
- direct immutable draft field updates.

Characterization tests for existing event ordering, reversed ranges, published
archive input, and event service mappings passed against existing behavior and
did not justify behavior changes.

Task reviews confirmed that endpoint routes, payload fields, status codes,
database models, and migration state remained in scope and unchanged.

## Final Verification

- `uv run pytest -q tests/test_events_api.py tests/test_events_services.py tests/test_drafts_api.py tests/test_drafts_services.py tests/test_user_event_status_api.py tests/test_architecture_boundaries.py`
  - `106 passed in 10.44s`
- `uv run pytest -q`
  - `118 passed in 11.93s`
- `uv run python manage.py check`
  - `System check identified no issues (0 silenced).`
- `.venv/bin/python manage.py makemigrations --check --dry-run`
  - `No changes detected`
- `git diff --check`
  - clean before final documentation

## Remaining Risks And Deferred Refactoring

Deferred Refactoring Note

- Topic: Remove inactive archive code from `events`.
- Why it is not part of the current scope: Removal requires migration and route
  history review beyond this contract-preserving hardening slice.
- Why it may be needed later: Duplicate concepts obscure ownership and increase
  maintenance cost.
- Trigger condition: Remaining visit-record and photo APIs are activated and
  their data migration path is approved.
- Expected change location: `events.models`, legacy event archive views,
  serializers, URL modules, and migrations.
- Related tests: archive API and architecture boundary suites.

Deferred Refactoring Note

- Topic: Pin validated DNS results to outbound connections.
- Why it is not part of the current scope: It requires transport-level behavior
  and deployment network decisions beyond the approved small fetch hardening.
- Why it may be needed later: Resolving before a connection leaves a DNS
  rebinding time-of-check/time-of-use window.
- Trigger condition: Production URL fetching is enabled without an outbound
  proxy or network-level private-address deny policy.
- Expected change location: `drafts.fetching` and deployment networking.
- Related tests: draft URL safety and integration tests with a controlled DNS
  resolver.

Deferred Refactoring Note

- Topic: Public event query performance and broader error abstractions.
- Why it is not part of the current scope: No measured performance problem or
  repeated error contract currently justifies additional abstraction.
- Why it may be needed later: Larger datasets or repeated workflows may expose
  a concrete need.
- Trigger condition: Query measurements regress or the same exception mapping
  appears in at least three active workflows.
- Expected change location: event querysets, indexes, or `core.errors`.
- Related tests: event API ordering/filter tests and domain service tests.

The inactive legacy archive code in `events` was intentionally left in place.
