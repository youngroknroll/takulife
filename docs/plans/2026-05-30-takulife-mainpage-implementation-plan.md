# Takulife Main Page Implementation Plan

Date: 2026-05-30
Project: `takulife`
Scope owner: Senior Dev / Codex

## Approved Scope

- Add a public web main page at `/`.
- Render a Django template that reflects the MVP direction from
  `docs/plans/2026-05-20-oshilog-mvp-planning.md`.
- Use the product name `takulife` on the page.
- Do not add frontend test code for this task (user-approved exception).

## Acceptance Criteria

- `GET /` returns HTTP 200.
- Main page clearly shows the name `takulife`.
- Main page content communicates MVP purpose: official offline event discovery
  and admin-curated event publication workflow.
- Existing API routes remain unchanged.

## Domain Boundary and Dependency Direction

- `config.urls` owns top-level route wiring.
- `core` owns lightweight web home view composition for shared/root behavior.
- Template layer owns presentation only.
- Dependency direction:
  - `config -> core`
  - `core view -> template`
- Avoided dependencies:
  - No direct dependency from this page on `events` or `drafts` domain logic.

Business logic placement:

- No new business logic is introduced.
- The view only delegates presentation rendering.

## Coupling and Cohesion Review

- Coupling is not increased across event/draft domains because the page does
  not import or orchestrate those modules.
- Cohesion in `core` improves by keeping root-level web entry behavior in a
  single domain-aligned location.
- Remaining coupling is unchanged from current project structure.

## Pythonic Code Design

- Use a small, explicit Django function view with `render`.
- Keep data flow obvious with a minimal context dictionary.
- Use framework-native template rendering; avoid custom abstraction layers.
- Reject non-pythonic shortcuts such as inline HTML string responses or hidden
  side effects in URL config.

## Implementation Steps

1. Add a `core` web home view for `/`.
2. Register root URL in `config.urls`.
3. Add a Django template for the main page.
4. Run focused verification commands.
5. Record work log and project status updates.

## Verification Commands

- `uv run python manage.py check`
- `uv run python manage.py test` (regression safety for existing backend tests)

## Deferred Work

Deferred Refactoring Note

- Topic: Dedicated web app/module for full frontend information architecture.
- Why it is not part of the current scope: Current task is a single main page.
- Why it may be needed later: As public web flows grow, home/list/detail UI may
  need separate ownership from shared API-root concerns.
- Trigger condition: Multiple public web pages with shared navigation/layout and
  UI state requirements are introduced.
- Expected change location: New web-focused app and template/static structure.
- Related tests: Future page-level integration and accessibility checks.
