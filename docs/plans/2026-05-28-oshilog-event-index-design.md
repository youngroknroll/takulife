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
3. System fetches and extracts candidate information into `EventDraft`.
4. Operator corrects only what is needed.
5. Operator approves or rejects the draft.
6. Approved drafts become public `Event` records.

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

## 8. Deferred Work

Deferred Refactoring Note

- Topic: Re-enable member features such as status tracking and visit records.
- Why it is not part of the current scope: The delivery goal is a one-day event information site, and operator workflow is the immediate bottleneck.
- Why it may be needed later: Personal archive features can improve retention after event data flow is stable.
- Trigger condition: After the event index flow is working and events can be published consistently.
- Expected change location: `events`, `accounts`, and future member-facing API endpoints.
- Related tests: event status, visit record, and photo upload tests.

