# OshiLog REST API Design Plan

Date: 2026-05-26
Sources:
- `docs/plans/2026-05-20-oshilog-mvp-planning.md`
- `docs/erd/2026-05-26-oshilog-screen-design-erd.html`
- `docs/plans/2026-05-26-oshilog-auth-design-plan.md`
- `docs/proposal/가제oshilog_integrated_planning_document_v2.html`

Project root: `/Users/yeongroksong/Desktop/study/project/taku`

## 1. Goal

Define the first REST API surface for OshiLog so the backend can support:

- public event discovery,
- event draft review and approval,
- user event status management,
- visit record creation,
- photo attachment for visit records,
- and later user-submitted event URLs.

This document is a design plan, not an implementation plan. It is meant to sit on top of the existing API bootstrap plan and fill in the domain resource map that the ERD requires.

## 2. Scope

### Included

- `Event` public API.
- `EventDraft` admin API.
- `UserEventStatus` user API.
- `VisitRecord` user API.
- `VisitRecordPhoto` user API.
- Deferred `EventSubmission` API shape.
- Filtering, pagination, and core validation rules.
- Permission boundaries for public, authenticated, and admin-only actions.

### Excluded

- Frontend implementation.
- Database migrations.
- Admin UI customization details.
- Queue workers, search indexing, and AI extraction.
- Full production settings split.

## 3. Resource Map

### Core public resources

- `Event`: published event data visible on list and detail pages.
- `EventDraft`: unreviewed event candidate created from official URLs.

### Screen-driven extension resources

- `UserEventStatus`: one user-specific status per event.
- `VisitRecord`: one or more personal visit notes per user/event pair.
- `VisitRecordPhoto`: photo attachments for a visit record.

### Deferred resource

- `EventSubmission`: user-submitted URL that can later become an `EventDraft`.

## 4. Authentication Model

- Django auth is the base authentication system.
- The project should introduce a custom `accounts.User` model that extends `AbstractUser`.
- Google login is the primary member login path.
- Local password signup is not required for the first MVP.
- Admin operators still use Django admin and staff permissions.

Recommended auth-related endpoints:

| Method | Path | Purpose | Auth |
| --- | --- | --- | --- |
| GET | `/api/auth/me/` | current logged-in user | required |
| POST | `/api/auth/google/` | Google login or account creation | public |
| POST | `/api/auth/logout/` | end current session | required |

## 5. API Surface

### Public

| Method | Path | Purpose | Auth |
| --- | --- | --- | --- |
| GET | `/api/` | API root | none |
| GET | `/api/health/` | health check | none |
| GET | `/api/events/` | published event list | optional |
| GET | `/api/events/{id}/` | published event detail | optional |

### User-owned resources

| Method | Path | Purpose | Auth |
| --- | --- | --- | --- |
| GET | `/api/me/event-statuses/` | list current user statuses | required |
| PUT | `/api/me/event-statuses/{event_id}/` | upsert one status for an event | required |
| DELETE | `/api/me/event-statuses/{event_id}/` | clear one status | required |
| GET | `/api/me/visit-records/` | list current user visit records | required |
| POST | `/api/me/visit-records/` | create a visit record | required |
| GET | `/api/me/visit-records/{id}/` | retrieve one record | required |
| PATCH | `/api/me/visit-records/{id}/` | edit one record | required |
| DELETE | `/api/me/visit-records/{id}/` | delete one record | required |
| POST | `/api/me/visit-records/{id}/photos/` | upload a photo to a record | required |
| DELETE | `/api/me/visit-records/{id}/photos/{photo_id}/` | remove one photo | required |

### Admin-only resources

| Method | Path | Purpose | Auth |
| --- | --- | --- | --- |
| GET | `/api/admin/event-drafts/` | list drafts | admin |
| POST | `/api/admin/event-drafts/` | create draft from official URL | admin |
| GET | `/api/admin/event-drafts/{id}/` | inspect a draft | admin |
| PATCH | `/api/admin/event-drafts/{id}/` | edit draft candidates | admin |
| POST | `/api/admin/event-drafts/{id}/approve/` | approve draft into event | admin |
| POST | `/api/admin/event-drafts/{id}/reject/` | reject draft | admin |

### Deferred

| Method | Path | Purpose | Auth |
| --- | --- | --- | --- |
| POST | `/api/event-submissions/` | submit a user URL | authenticated or public, decision later |
| GET | `/api/admin/event-submissions/` | review user submissions | admin |

## 6. Data Rules

### Event

- Only published events are returned by public endpoints.
- `official_url` must be unique.
- D-Day and progress state are derived, not stored.
- `publish_status` should support at least `draft`, `published`, and `archived`.

### EventDraft

- `source_url` must be unique.
- Drafts are never exposed on public event endpoints.
- Draft fields store extracted candidates, not final truth.
- Approval creates or updates a published `Event` only after duplicate URL validation passes.

### UserEventStatus

- One user can have only one status per event.
- Allowed values should match the screen design: `interested`, `planned`, `visited`, `missed`.
- The event detail response can include the current user's status as a convenience field.

### VisitRecord

- Visit records belong to one user and one event.
- Multiple visit records per user/event pair are allowed unless product rules later say otherwise.
- `visited_on` is the primary timeline field.
- `rating`, `wait_time_minutes`, and `memo` are optional.

### VisitRecordPhoto

- Only user-uploaded photos are allowed.
- Official images, social images, and poster images are not stored.
- Photos are ordered per record.

## 7. Endpoint Behavior

### Event list and detail

- Support filtering by `region`, `event_type`, `work_title`, `q`, `starts_after`, `starts_before`, and `status` where relevant.
- Default list ordering should surface upcoming and soon-ending events first.
- Public responses should be stable and compact, suitable for list cards.

### Draft creation and review

- Draft creation takes a single official URL.
- The service fetches and extracts candidates before saving `EventDraft`.
- Admins can edit extracted fields before approving.
- Rejection should preserve the draft record and rejection metadata.

### Status and record actions

- Status updates should be idempotent.
- Record creation should be tied to a published event only.
- Photo upload should only accept direct user files tied to a `VisitRecord`.

## 8. Security And Reliability

- Draft creation, review, approval, and rejection are admin-only.
- User status and visit record routes require authentication.
- CSRF must be enforced for session-based write requests.
- Draft URL fetching must block unsupported schemes, localhost, private IP ranges, and timeouts.
- Duplicate `official_url` and `source_url` values must be rejected clearly.
- API responses for validation errors should be explicit enough for admin tooling.

## 9. Implementation Order

1. Keep the current API bootstrap plan as the foundation.
2. Add `events` app and public list/detail endpoints.
3. Add `drafts` app and admin review workflow.
4. Add `UserEventStatus`.
5. Add `VisitRecord` and `VisitRecordPhoto`.
6. Add `EventSubmission` only when the product starts accepting user URLs.

## 10. Deferred Refactoring Note

Deferred Refactoring Note

- Topic: Normalize work, venue, and source into separate tables.
- Why it is not part of the current scope: The screen-driven MVP can operate on denormalized strings for speed and clarity.
- Why it may be needed later: Search, analytics, venue reuse, and source lineage will get harder as the dataset grows.
- Trigger condition: When duplicate venue handling or cross-event work analytics becomes a product requirement.
- Expected change location: `events` and `drafts` domain models.
- Related tests: event filtering, draft approval, and record display tests.
