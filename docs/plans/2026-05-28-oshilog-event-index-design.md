# OshiLog Event Index Design

Date: 2026-05-28
Sources:
- `docs/plans/2026-05-20-oshilog-mvp-planning.md`
- `docs/plans/2026-05-26-oshilog-rest-api-design-plan.md`
- `docs/plans/2026-05-27-oshilog-backend-api-implementation-plan.md`
- `docs/erd/2026-05-26-oshilog-screen-design-erd.html`

Project root: `/Users/yeongroksong/Desktop/study/project/taku`

## 1. Product Decision

OshiLog's immediate product direction is narrowed to an event information index site that can be completed quickly.

The approved direction is:

- Public users search and browse event information only.
- Operators input official event URLs.
- The system creates `EventDraft` records from URLs.
- Operators review and publish drafts into `Event`.

This is not a personal archive MVP for now.

## 2. Site Definition

The first website is defined as:

> A subculture event information aggregation site that collects, reviews, and publishes official event information for search and browsing.

The product value is speed of event discovery, not personal account depth.

## 3. Approved Scope

### Public scope

- Event list page.
- Event detail page.
- Search by keyword.
- Minimum filters:
  - region
  - event category

### Operator scope

- URL input for draft creation.
- `EventDraft` creation.
- Draft list view.
- Draft detail and edit.
- Approve and reject actions.
- Publish approved drafts as `Event`.

## 4. Explicitly Excluded From This Phase

- User event status.
- Visit records.
- Photo upload.
- Personal archive page.
- Google login implementation.
- User-submitted event URLs.
- Social/community features.
- AI extraction.

These may remain in code or long-term plans, but they are not part of the currently approved delivery target.

## 5. Operating Model

This phase uses a semi-automatic operator workflow:

1. Operator finds an official event URL.
2. Operator submits the URL.
3. System creates a pending URL-only `EventDraft` in this implementation slice.
4. Operator fills or corrects the candidate event fields.
5. Operator approves or rejects the draft.
6. Approved drafts become public `Event` records.

Remote URL fetching and automatic extraction remain deferred. Adding that later
requires a separate approved design for SSRF protection, network egress,
redirect handling, extraction ownership, and retry/error behavior.

This avoids both extremes:

- fully manual data entry, which does not scale
- fully automatic publishing, which is too risky for incorrect event data

## 6. Acceptance Criteria

The first release is acceptable when:

1. An operator can submit an official URL and create a pending draft.
2. A draft is not shown on public event endpoints before approval.
3. An operator can edit and approve or reject the draft.
4. Approval creates a published event.
5. Public users can view published events in a list.
6. Public users can open a published event detail page.
7. Public users can search by keyword and filter by region and category.
8. Duplicate official URLs are rejected.

## 7. Architecture Direction

The backend remains a Django + Django REST Framework service.

Recommended boundaries for this phase:

- `core`: API root, health, shared utilities
- `events`: public published event model and read APIs
- `drafts`: draft creation, review, approval, rejection

The auth boundary may remain in the project, but member-facing auth is not part of this phase's product completion criteria.

### Domain Boundary And Dependency Direction

The event index design must keep domain ownership explicit:

- `events` owns published `Event` data, public event query behavior, public
  event serialization, and published-event invariants.
- `drafts` owns `EventDraft` data, draft review state transitions, draft input
  validation, and operator workflow.
- `accounts` owns identity and staff/admin status only. It must not own event or
  draft business rules.
- `core` owns shared API entry points and health utilities only. It must not
  become a business-logic dumping ground.

Allowed dependencies:

- Public event APIs may depend on `events` only.
- Draft HTTP views may depend on `drafts` serializers/services only.
- Draft workflow services may orchestrate publication through an explicit
  `events` application boundary, such as an `events` service function. They
  should not directly construct published `Event` records inside HTTP views.
- Member-facing `/api/me/` features are deferred and must not be expanded by
  this phase.

Dependencies to avoid:

- Public `events` code must not import `drafts`.
- HTTP views must not own cross-domain business orchestration.
- Serializers must not silently enforce business state transitions that belong
  to domain or service code.

### Coupling And Cohesion Review

This design should lower coupling by keeping operator draft review separate from
public event browsing. The only approved cross-domain workflow is draft approval
publishing an event, and that workflow must go through an explicit service
boundary rather than view-level model construction.

This design should increase cohesion by keeping:

- public event query/read behavior in `events`
- draft status and review behavior in `drafts`
- authentication identity behavior in `accounts`

Any remaining coupling between public event index code and member archive code
must be recorded as deferred refactoring.

### Pythonic Code Design

Implementation should use explicit, idiomatic Django/DRF structures:

- small view classes for HTTP request/response handling
- serializers for request validation and response representation
- model methods or service functions for business state transitions
- database transactions for atomic publication
- named query helpers or querysets when filtering logic grows

Avoid large procedural view methods that mix validation, state transition,
cross-domain persistence, and response construction. Avoid silent input mutation;
ignored or rejected fields must be documented and tested.

## 8. Deferred Work

Deferred Refactoring Note

- Topic: Re-enable member features such as status tracking and visit records.
- Why it is not part of the current scope: The delivery goal is a one-day event information site, and operator workflow is the immediate bottleneck.
- Why it may be needed later: Personal archive features can improve retention after event data flow is stable.
- Trigger condition: After the event index flow is working and events can be published consistently.
- Expected change location: `events`, `accounts`, and future member-facing API endpoints.
- Related tests: event status, visit record, and photo upload tests.
