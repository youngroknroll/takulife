# OshiLog MVP Planning

Date: 2026-05-20
Source: `/Users/yeongroksong/Downloads/oshilog_integrated_planning_document_v2.html`
Project root: `/Users/yeongroksong/Desktop/study/project/taku`

## 1. Product Summary

OshiLog is a web service for anime, game, and subculture fans who want to discover official offline events and keep a personal archive of their activity.

The full product vision connects three needs:

- Find official pop-up stores, collaboration cafes, theater bonuses, and goods reservation events.
- Save event interest or visit status.
- Record visited events with personal notes and photos.

The first implementation will intentionally focus on the operational data foundation: creating, reviewing, and publishing official event information.

## 2. First MVP Scope

The first MVP scope is:

- Published event list.
- Published event detail page.
- Event filtering by region, date, category, and keyword.
- Admin URL-based event draft creation.
- Rule-based extraction of title, source text, date candidates, and location candidates.
- Admin review, edit, approve, or reject workflow.
- Approved `EventDraft` becomes a published `Event`.

The first MVP success criterion is:

> An admin can create an event draft from an official URL, review it, publish it, and a user can view the published event in the public list and detail page.

## 3. Deferred Scope

The following features remain part of the broader OshiLog product, but are deferred from the first MVP:

- User event status: interested, planning to visit, visited, missed.
- Visit records.
- User photo upload.
- Personal archive page.
- User-submitted event URLs.
- AI-based JSON extraction.
- Comments, direct messages, follows, community feed.
- Payments, trade, complex recommendation, app push.

## 4. Target Users

Initial users are Seoul and 수도권 subculture fans who often attend offline events.

Primary personas:

- Event explorer: wants to find events happening this week.
- Schedule keeper: wants to avoid missing events related to favorite works.
- Archive-oriented fan: eventually wants to keep personal visit history.

The first MVP primarily serves the event explorer and establishes the admin workflow needed to keep event data fresh.

## 5. Event Categories

Included categories:

- Pop-up store.
- Collaboration cafe.
- Theater bonus.
- Goods reservation.

Deferred categories:

- Birthday cafe.
- Doujin or only events.
- Fan-hosted events.
- General exhibitions without strong subculture relevance.

## 6. Product Rules

Core rules for the first MVP:

- Events without an official URL cannot be published.
- `EventDraft` records are never shown on public pages before approval.
- The same official URL cannot create duplicate published events.
- Extracted date and location values are candidates, not final truth.
- Admin review is required before publishing.
- Official images, social media images, and poster images are not stored.
- Public event cards use category-based default thumbnails.

## 7. Recommended Technical Direction

Use a small Django REST API backend first:

- Backend: Django.
- API: Django REST Framework.
- Database: PostgreSQL.
- Frontend: deferred until the API foundation is stable.
- Styling: deferred.
- Parser: `httpx` or `requests` plus BeautifulSoup.
- Date extraction: rule-based regular expressions.
- Admin: Django Admin customization first, not a custom back office.
- Deployment target: Render.

Recommended app boundaries:

- `config`: settings and root URL configuration.
- `core`: shared utilities, health check, API root.
- `events`: published event model, public list, detail, filtering.
- `drafts`: URL fetch, extraction, draft review, approval, rejection.

Avoid early over-engineering:

- Do not introduce a separate frontend yet.
- Do not build a custom admin portal yet.
- Do not add AI extraction in the first MVP.
- Do not normalize works, characters, venues, or sources too early.
- Do not add queues or search engines until current requirements force them.

## 8. Core Data Models

### Event

Represents reviewed and publishable event data.

Expected fields:

- `title`
- `event_type`
- `work_title`
- `location_name`
- `region`
- `start_date`
- `end_date`
- `official_url`
- `source_name`
- `summary`
- `publish_status`
- `created_at`
- `updated_at`

Derived values such as "upcoming", "ongoing", "ended", and D-Day are calculated from dates and not stored as fixed database fields.

### EventDraft

Represents unreviewed data generated from an official URL.

Expected fields:

- `source_url`
- `source_name`
- `raw_title`
- `raw_text`
- `extracted_title`
- `extracted_event_type`
- `extracted_work_title`
- `extracted_location_name`
- `extracted_region`
- `extracted_start_date`
- `extracted_end_date`
- `extracted_summary`
- `confidence_score`
- `status`: pending, approved, rejected.
- `created_at`
- `reviewed_at`

## 9. Service Boundaries

Keep external I/O and workflow logic outside model methods where practical.

Recommended services:

- `DraftFetchService`: fetch URL with timeout, user agent, redirect limits, and failure handling.
- `DraftExtractService`: extract title, meta description, body snippet, dates, and location candidates.
- `DraftReviewService`: approve or reject drafts and enforce review rules.
- `EventPublishService`: convert approved draft data into a published event.

## 10. Security And Reliability Requirements

First MVP must account for:

- Admin-only access for draft creation, review, approval, and rejection.
- CSRF protection on all write actions.
- Safe template escaping for all extracted and admin-edited text.
- SSRF protection for URL fetching.
- Only `http` and `https` URLs allowed for external fetches.
- Timeout on URL fetches.
- No fetching of localhost, private IP ranges, or unsupported schemes.
- Duplicate URL detection.
- Failure messages for fetch timeout, invalid URL, parsing failure, and duplicate URL.

Deferred hardening:

- DNS rebinding defense.
- Virus scanning and image re-encoding.
- Signed media URLs.
- Advanced rate limiting.
- Structured security audit logs.
- Admin MFA.

## 11. TDD Milestones

Implementation should follow small behavior tests.

1. Bootstrap
   - Test: root URL resolves and returns HTTP 200.
   - Minimum green: Django project boots with a basic home page.

2. Published events
   - Test: public list shows only published events.
   - Test: public detail renders a published event.
   - Minimum green: one published event appears; unpublished data does not.

3. Filters
   - Test: event list filters by region.
   - Add date, category, and keyword filters one behavior at a time.

4. Draft creation
   - Test: admin can create a pending draft from an official URL.
   - Minimum green: source URL, raw title, raw text, and candidate fields are stored.

5. Approval workflow
   - Test: approving a draft creates a published event.
   - Test: rejected draft does not create a public event.
   - Minimum green: draft status changes and event publication is controlled.

6. Safety checks
   - Test: duplicate source URL is rejected.
   - Test: invalid or unsafe URL is rejected.
   - Test: non-admin cannot access draft actions.

## 12. Acceptance Criteria

The first MVP is acceptable when:

- A published event can be created from an approved draft.
- Pending and rejected drafts are not visible on public event pages.
- Public users can view event list and detail pages.
- Public users can filter events by at least region, with date/category/keyword added incrementally.
- Admin can create, review, approve, and reject drafts.
- Duplicate official URLs are blocked.
- Official images are not stored.
- URL fetch failures are handled without crashing the app.
- Security basics for admin-only actions, CSRF, escaping, and unsafe URL rejection are tested or manually verified.

## 13. Verification Commands

Expected commands after implementation begins:

```bash
python manage.py check
python -m pytest -q
python manage.py makemigrations --check --dry-run
```

Additional checks may be added once the project scaffold and tooling are selected.

## 14. Open Decisions

- Tailwind CSS vs Bootstrap 5.
- Local development database: PostgreSQL from the start vs SQLite for initial bootstrap.
- Whether the first admin workflow lives entirely inside Django Admin or includes a minimal custom admin view.
- Initial seed data format and source list.
- Exact URL safety implementation depth for the first local MVP.
