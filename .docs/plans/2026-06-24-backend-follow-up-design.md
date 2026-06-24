# Backend Follow-up Design

Date: 2026-06-24
Project root: `/Users/yeongroksong/Desktop/study/project/taku`

## Purpose

Document the follow-up backend changes recommended by the June 24 senior review.
This design records what should be changed, what should stay stable, where the
business rules should live, and which items remain deferred.

This document authorizes a follow-up implementation plan, not production code by
itself.

## Approved Scope

In scope:

- Preserve the current public API and database behavior unless this document
  explicitly calls out a controlled compatibility-preserving refinement.
- Keep `events` as the owner of the published public event catalog.
- Keep `drafts` as the owner of URL intake, extraction, review state, and event
  publication orchestration.
- Keep `archive` as the only active owner of user-owned archive status flows.
- Record and implement safe follow-up changes for the review findings:
  - clarify active versus legacy archive ownership;
  - harden the draft fetch pipeline against redirect, DNS, content-type, and
    response-size issues;
  - make draft service rules more self-defensive instead of relying only on DRF
    serializers;
  - remove serializer-object coupling from archive application services;
  - consolidate published-event query intent usage behind the `events` domain;
  - add characterization tests for implicit current query policies;
  - expand boundary and service regression tests.
- Keep all currently inactive legacy `/api/me/*` archive routes inactive.
- Produce a detailed implementation plan for a later code change session.

Out of scope:

- New public endpoints, filters, payload fields, or frontend behavior.
- Search infrastructure, queues, workers, or AI extraction.
- PostgreSQL-specific tuning, live query-plan optimization, or search indexes.
- A broad global exception framework.
- Production-grade media storage, signed URLs, virus scanning, or image
  re-encoding.
- Full removal of the legacy inactive archive models and views from `events`
  without a dedicated migration and data-history review.
- Any change that widens the approved domain dependencies.

## Current State

### Events

The active public event catalog is in good shape structurally:

- `PublicEventListView` validates request input and delegates query behavior to
  `EventQuerySet`.
- `EventQuerySet` owns published visibility, public filters, public temporal
  status filters, and default ordering.
- `create_published_event()` acts as the current publication boundary used by
  the drafts domain.

The main structural weakness is that legacy inactive archive code still lives in
the `events` app:

- `events.models.UserEventStatus`
- `events.models.VisitRecord`
- `events.models.VisitRecordPhoto`
- `events.views.UserEventStatusUpsertView`
- `events.views.VisitRecord*`
- `events.status_urls`

These routes are intentionally unmounted, but the duplicated concepts make the
domain boundary harder to read.

### Drafts

The drafts domain already expresses its workflow clearly:

- URL input validation happens before fetch.
- External fetch and extraction happen outside transactions.
- `update_draft()`, `approve_draft()`, and `reject_draft()` lock rows and keep
  state transitions inside transactions.
- The API preserves stable, controlled error responses for admin workflows.

The weak points are at the external I/O edge and at service self-defense:

- `fetch_html()` validates content type and size after downloading the full
  response.
- current URL validation does not re-check redirect targets or DNS-resolved IP
  addresses during fetch.
- duplicate draft creation is guarded mainly by serializer-level uniqueness, not
  by a stable service-level race mapping.
- `update_draft()` trusts the caller's field list more than the domain should.

### Archive

The active archive flow is intentionally small:

- `archive.serializers.UserEventStatusSerializer` validates published events.
- `archive.services.create_user_event_status()` maps duplicates under
  `transaction.atomic()`.
- `archive.views` scopes data to the current user and maps HTTP responses.

The main maintainability issue is not complexity inside the flow itself. The
issues are:

- the active archive service accepts a DRF serializer object instead of explicit
  domain inputs;
- the active owner is `archive`, while legacy inactive archive concepts still
  exist in `events`;
- published-event selection is not consistently routed through
  `Event.objects.published()`.

### Tests

The current suite protects the active contracts reasonably well:

- public event list/detail behavior;
- draft create/review/approve/reject behavior;
- active archive status API behavior;
- import and route boundary checks.

The weakest test coverage is around:

- external fetch edge cases;
- duplicate-create race handling in drafts;
- service-level misuse that serializers currently happen to prevent;
- implicit public event query policies that exist in code but are not fully
  described by tests.

## Recommended Delivery Approach

Use a contract-preserving hardening slice first, then keep riskier structural
cleanup deferred unless separately approved.

### Slice 1: Safe follow-up hardening

Implement only changes that:

- preserve current endpoint and payload contracts;
- preserve current schema and migration state;
- improve domain clarity, safety, and test protection;
- do not require deleting legacy archive models from `events`.

### Slice 2: Deferred structural retirement

Handle removal of legacy inactive archive models/views from `events` only in a
separate migration-reviewed task after the active archive implementation is
fully settled and covered.

## Domain Boundary And Dependency Direction

### Events

Ownership:

- published event catalog;
- public event list/detail reads;
- reusable published-event query intent;
- publication of reviewed drafts into published events.

Allowed dependencies:

- `events.views -> events.serializers`
- `events.views -> events.models`
- `events.views -> events.querysets` through `Event.objects`
- `events.services -> events.models`
- `events.models -> events.querysets`

Disallowed dependencies:

- `events -> archive`
- `events -> drafts`

Business rules owned here:

- what counts as a published event;
- public event filtering and ordering intent;
- creation of published events from approved review data.

### Drafts

Ownership:

- source URL intake;
- fetch safety checks for external event sources;
- extraction of review candidates;
- draft review state transitions;
- orchestration into event publication.

Allowed dependencies:

- `drafts.views -> drafts.serializers`
- `drafts.views -> drafts.services`
- `drafts.services -> drafts.models`
- `drafts.services -> drafts.fetching`
- `drafts.services -> drafts.extraction`
- `drafts.services -> drafts.url_safety`
- `drafts.services -> events.services`

Disallowed dependencies:

- `drafts -> archive`

Business rules owned here:

- what makes a fetch target valid or unsafe for this application;
- how draft states transition;
- which fields are mutable during admin review;
- how publication failures are mapped into draft-domain errors.

### Archive

Ownership:

- active user event status records and future archive-owned user resources;
- owner scoping;
- duplicate mapping for archive-owned writes;
- archive-facing validation of published event references.

Allowed dependencies:

- `archive.views -> archive.serializers`
- `archive.views -> archive.services`
- `archive.services -> archive.models`
- `archive.serializers -> events.models`
- `archive.models -> events.models`

Disallowed dependencies:

- `archive -> drafts`
- `events -> archive`

Business rules owned here:

- who may see or mutate archive-owned records;
- duplicate archive write handling;
- archive input validation after serializer parsing.

### Core

Ownership:

- small cross-domain HTTP response helpers only where the response contract is
  truly shared.

Allowed dependencies:

- `core.errors` must stay domain-agnostic.

Disallowed dependencies:

- `core -> events`
- `core -> drafts`
- `core -> archive`

## Detailed Code Design

### 1. Events Follow-up Design

#### 1.1 Preserve `Event.objects.published()` as the active public visibility boundary

The events domain already has the right reusable query intent:

- [events/querysets.py](/Users/yeongroksong/Desktop/study/project/taku/events/querysets.py:7)

Follow-up work should make that intent the preferred access path anywhere code
needs "published events only".

Recommended change:

- replace direct `filter(publish_status=Event.PublishStatus.PUBLISHED)` usages in
  active archive serializers and any still-referenced legacy archive views with
  `Event.objects.published()`.

Reasoning:

- the published predicate is a domain rule, not a repeated caller decision;
- this lowers drift risk if the published rule changes later;
- this is a cohesion improvement without adding abstraction.

#### 1.2 Preserve current public query behavior, but make it explicit

The current public list flow should stay behavior-compatible. The design intent
for the follow-up slice is to characterize and document the existing policies,
not to invent a new public query contract.

The current policy that should be preserved and tested explicitly is:

- unknown query parameters are ignored;
- blank documented string filters are ignored;
- `status` continues to reject invalid values with `400`;
- invalid dates continue to reject with `400`;
- `start_date_from > start_date_to` should remain a normal empty result unless a
  later product decision explicitly changes that contract;
- records with missing dates continue to sort after ranked dated events through
  the `_state_rank=3` path.

Recommended change:

- add characterization tests that describe these rules as current contract;
- do not convert them into a new stricter API unless explicitly approved later.

Reasoning:

- the review found ambiguity, not a proven bug;
- preserving the current contract avoids accidental compatibility changes while
  still documenting the behavior.

#### 1.3 Do not tune public event query performance before measurement

The query design is readable but potentially expensive as data grows:

- `icontains` filters for `q` and `work_title`;
- `Case`-based ordering for public ranking;
- only limited indexing currently exists on the model.

Recommended decision:

- record this as deferred performance work;
- do not add indexes or alternate search logic in this slice without measured
  evidence from actual query plans or production-like data.

Reasoning:

- current project policy rejects speculative optimization;
- the present issue is foreseeable cost, not yet a verified bottleneck.

#### 1.4 Treat legacy archive code in `events` as retired-but-not-removed

The legacy inactive archive classes in `events` are a real readability problem,
but removing them now risks schema and migration churn.

Recommended decision for this slice:

- keep them unmounted;
- strengthen tests that prevent accidental activation or new coupling;
- document them as retired candidates owned by a later dedicated cleanup task;
- do not remove models from `events.models` in the safe hardening slice.

Reasoning:

- the current highest risk is accidental confusion, not live incorrect behavior;
- schema-affecting deletion needs a separate migration plan.

### 2. Drafts Follow-up Design

#### 2.1 Fetch safety should move from single-shot validation to request-path validation

The current flow validates only the original input URL before calling
`httpx.Client(..., follow_redirects=True)`. That is not enough for the intended
SSRF baseline.

Recommended request-path design:

1. Parse and validate the initial URL scheme and hostname.
2. Resolve the hostname to all returned IPs and reject the target if any
   resolved address is unsafe for this application.
3. Perform fetches with `follow_redirects=False`.
4. When a redirect response is received:
   - build the absolute redirect target;
   - re-run the same scheme, hostname, and resolved-IP validation against that
     target;
   - reject the redirect chain if the target becomes unsafe;
   - stop after `MAX_REDIRECTS`.
5. Only accept a final non-redirect HTML/XHTML response.

Recommended helper structure:

- `validate_fetch_url(url)` remains the public validation entry point.
- add a lower-level helper that validates resolved addresses for a target host.
- keep `fetch_html()` responsible for executing the redirect loop and applying
  validation at every hop.

Reasoning:

- this keeps the safety rule in the drafts domain where it belongs;
- manual redirect handling is explicit and easier to reason about than hidden
  redirect following.

#### 2.2 Enforce response-size limits before reading the whole body

The current implementation reads the full body and then checks length.

Recommended change:

- use streaming reads for the final response body;
- accumulate bytes until `MAX_RESPONSE_BYTES`;
- abort immediately once the limit is exceeded;
- only decode to text after the body stays under the limit.

Recommended behavior:

- oversized responses continue to map to the existing controlled error path;
- supported content types remain `text/html` and `application/xhtml+xml`.

Reasoning:

- this addresses both efficiency and reliability;
- it avoids paying memory and parse cost for responses already known to be too
  large for the product.

#### 2.3 Preserve current create-draft API contract while adding race-safe duplicate mapping

The current duplicate source URL case is usually caught by serializer
uniqueness. That is insufficient for concurrent requests.

Recommended change:

- wrap `EventDraft.objects.create(...)` in a `try/except IntegrityError`;
- map the database race into a drafts-domain duplicate creation exception;
- have the view translate that exception into the same field-keyed `400`
  response shape already used for ordinary duplicate source URLs.

Reasoning:

- this preserves public behavior while removing a likely 500 race path;
- the service layer, not the serializer alone, should own persistence races.

#### 2.4 Make `update_draft()` self-defensive

`update_draft()` currently applies any provided field names after the caller has
already validated them. That makes the service too trusting.

Recommended change:

- define one explicit mutable-field allowlist in the drafts service;
- reject updates that try to change fields outside that allowlist;
- keep the existing serializer guard in place so API callers still receive the
  current field-keyed validation errors;
- add service-level tests for direct misuse.

Recommended business rule:

- immutable fields remain `source_url`, `raw_title`, `raw_text`, and
  `review_status`;
- mutable fields remain the `extracted_*` review fields and `source_name` only
  if that is intentionally approved by the implementation review.

Reasoning:

- domain invariants should not disappear when a service is called from another
  internal path later;
- this is a maintainability hardening change, not a new external feature.

#### 2.5 Keep extraction intentionally simple

The review found weak heuristics in extraction, but that is aligned with the
current product choice: rough automatic draft, then admin review.

Recommended decision:

- do not expand extraction sophistication in this slice;
- strengthen safety and correctness around fetch, state transitions, and error
  contracts instead.

Reasoning:

- improving extraction quality is a larger product slice;
- it should not be mixed into operational safety hardening.

### 3. Archive And Core Follow-up Design

#### 3.1 Archive services should accept explicit domain inputs, not DRF serializer objects

Current archive create service:

- [archive/services.py](/Users/yeongroksong/Desktop/study/project/taku/archive/services.py:10)

Recommended change:

- change `create_user_event_status()` to accept explicit arguments such as
  `user`, `event`, and `status`;
- keep serializer parsing in the view layer;
- let the service own duplicate checking and transaction boundaries only.

Reasoning:

- a service boundary that accepts explicit values is easier to test, reuse, and
  understand;
- it avoids leaking presentation-layer objects into the application layer.

#### 3.2 Preserve current archive duplicate response contract

The current archive duplicate response is intentionally bespoke:

- HTTP `409`
- JSON body with `code` and `detail`

Recommended decision:

- keep this contract unchanged in the follow-up slice;
- do not force it through `core.errors` because the response shape is not the
  same as draft field errors or generic detail errors.

Reasoning:

- preserving the current API contract is more important than superficial helper
  reuse;
- a shared helper should exist only if at least three active workflows truly
  share the same contract.

#### 3.3 Keep `core.errors` minimal

Recommended rule:

- `core.errors` remains a tiny helper module for shared HTTP response shapes
  only;
- do not introduce a generic domain exception registry or error framework in
  this slice.

Reasoning:

- the project explicitly avoids speculative infrastructure;
- the active error contracts still differ enough by domain.

## Coupling And Cohesion Review

This design lowers coupling in three concrete ways:

- archive application services stop depending on DRF serializer objects;
- published-event selection becomes more consistently routed through the events
  domain;
- drafts fetch safety becomes a drafts-owned rule instead of a view-only or
  serializer-only concern.

This design improves cohesion in three concrete ways:

- all published visibility intent stays with `events`;
- all draft lifecycle and fetch safety rules stay with `drafts`;
- all active user-owned archive status rules stay with `archive`.

Intentional remaining coupling:

- `drafts.services -> events.services.create_published_event`
- `archive.serializers/models -> events.models.Event`

These are allowed and should remain one-way.

## Pythonic Code Design

- prefer explicit, named helper functions over broad base classes or hidden
  hooks;
- keep reusable query intent in Django `QuerySet` methods;
- keep request validation in DRF serializers;
- keep state transitions and transaction boundaries in small service functions;
- pass explicit domain values into services instead of serializer objects;
- keep fetch safety readable with a manual redirect loop rather than clever
  event-hook indirection;
- keep exception mapping narrow and explicit;
- prefer characterization tests when preserving behavior is more important than
  redesigning it.

Rejected shortcuts:

- do not remove legacy `events` archive models in the same slice as fetch safety
  hardening;
- do not add a repository layer;
- do not add a generic service base class;
- do not change public event query behavior without product approval;
- do not optimize public catalog query plans before measuring them.

## Acceptance Criteria

The follow-up design is acceptable when a later implementation satisfies all of
these:

- public event list/detail endpoints keep the current URL, payload, and status
  contracts;
- public event query behavior for blank filters, invalid filters, unknown
  filters, reversed ranges, and null-date ordering is explicitly characterized
  by tests;
- active archive status behavior and responses remain unchanged;
- archive services no longer accept DRF serializer objects as their primary
  application-service contract;
- `Event.objects.published()` becomes the preferred source of published-only
  query intent in active code;
- draft fetches reject unsafe redirect targets and unsafe resolved addresses;
- draft fetches stop downloading bodies past the configured size limit;
- duplicate draft creation races return a controlled duplicate response instead
  of leaking a server error;
- direct service misuse of immutable draft fields is rejected;
- `events` and `drafts` do not gain dependencies on `archive`;
- full verification remains green with no migration drift.

## Deferred Refactoring Notes

Deferred Refactoring Note

- Topic: Remove legacy inactive archive code from `events`
- Why it is not part of the current scope: Model and view removal may require a
  schema and migration-history decision that exceeds the safe hardening slice.
- Why it may be needed later: Duplicate archive concepts currently obscure the
  active owner and increase maintenance confusion.
- Trigger condition: Active archive behavior is stable, fully covered, and a
  dedicated migration review is approved.
- Expected change location: `events/models.py`, `events/serializers.py`,
  `events/views.py`, `events/status_urls.py`, and migrations if approved.
- Related tests: `tests/test_architecture_boundaries.py`,
  `tests/test_user_event_status_api.py`, `tests/test_visit_records_api.py`.

Deferred Refactoring Note

- Topic: Public event query performance tuning
- Why it is not part of the current scope: The review identified potential cost,
  not a measured current bottleneck.
- Why it may be needed later: `icontains` filters and `Case` ordering may become
  expensive with real catalog growth.
- Trigger condition: Slow query evidence from production-like data or verified
  query plans.
- Expected change location: `events/models.py`, `events/querysets.py`, and
  migration files if indexes are approved.
- Related tests: `tests/test_events_api.py`, future performance benchmarks.

Deferred Refactoring Note

- Topic: Broader exception-to-response consolidation
- Why it is not part of the current scope: Current active workflows still expose
  materially different error payload shapes.
- Why it may be needed later: Repetition may become inconsistent as more active
  write workflows are added.
- Trigger condition: At least three active workflows share the same response
  contract closely enough to justify a common helper.
- Expected change location: `core/errors.py` and affected views.
- Related tests: API contract tests for each affected workflow.
