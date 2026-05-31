# Takulife Event List Static UI Design

Date: 2026-05-31
Project: `takulife`
Scope owner: Senior Dev / Codex

## Approved Scope

- Create a new public web page for event browsing at `/events/`.
- Implement static UI only (no API binding, no backend filtering behavior).
- Keep existing API routes and domain logic unchanged.
- Follow local reference guidance in:
  - `.lazyweb/design-research/oshilog-screen-design-2026-05-26/report.html`
- Do not add frontend test code for this task (user-approved exception).

## Acceptance Criteria

- `GET /events/` returns HTTP 200.
- Page visibly includes event-list interaction blocks:
  - top search bar
  - quick filter chips
  - left filter panel
  - right event card list with D-day and status actions
- The page keeps an operations-first discovery tone (not marketing layout).
- Existing `/` homepage and `/api/*` behavior stays unchanged.

## Design Direction

- Preserve the current Takulife visual language used in `home.html`:
  soft neutral background, thin borders, blue accent, dense information cards.
- Prioritize scan speed:
  category, D-day, location, and period are shown before long descriptions.
- Keep mobile behavior simple:
  stacked layout where the filter panel moves above the result list.

## Domain Boundary and Dependency Direction

- `config.urls` owns route mapping for `/events/`.
- `core.views.event_list` owns static template rendering entry.
- `templates/core/event_list.html` owns presentation only.
- Dependency direction:
  - `config -> core`
  - `core -> template`
- Avoided dependencies:
  - No import/use of `events` or `drafts` domain modules for this page.

## Coupling and Cohesion Review

- Coupling does not increase because no cross-domain integration is introduced.
- Cohesion improves in web presentation because event-list-specific layout lives
  in a dedicated template.
- Shared layout extraction is deferred to avoid out-of-scope refactor.

## Pythonic Code Design

- Keep backend code explicit with a small function view that renders one template.
- Keep business logic out of views/templates since this is static UI scope.
- Avoid hidden side effects and avoid introducing generic abstractions.

## Deferred Refactoring Note

Deferred Refactoring Note

- Topic: Introduce shared base template and split CSS into static assets.
- Why it is not part of the current scope: current change is one additional
  static page.
- Why it may be needed later: multi-page public UI will duplicate top bar,
  spacing, and color tokens.
- Trigger condition: event detail and archive pages are added.
- Expected change location: `templates/base.html`, `static/css/`.
- Related tests: future template render smoke checks and a11y review.
