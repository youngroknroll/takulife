# Takulife Mainpage Reference Alignment Design

Date: 2026-05-31
Project: `takulife`
Scope owner: Senior Dev / Codex

## Approved Scope

- Rework only the public main page template at `/` to align with:
  - `docs/plans/2026-05-30-takulife-mainpage-implementation-plan.md`
  - `.lazyweb/design-research/oshilog-screen-design-2026-05-26/report.html`
- Keep backend routes, domain models, and API behaviors unchanged.
- Keep product name exposure as `takulife`.
- Do not add frontend test code for this task (user-approved exception on 2026-05-31).

## Acceptance Criteria

- `GET /` returns HTTP 200.
- Main page shows `takulife`.
- Main page reflects discovery-first information hierarchy:
  - top search + quick filters
  - sections for "이번 주 갈 만한 행사", "곧 종료돼요", "새로 등록"
  - event cards emphasizing category, D-day, location, and period
- Main page preserves MVP publication principle text:
  official URL based draft creation and admin-reviewed publication.
- Existing API endpoints remain unchanged.

## Design Direction

- Keep a practical, operations-first UI tone, not a marketing hero landing.
- Prioritize scannability over decorative imagery.
- Use a soft neutral background, subtle borders, and blue-focused accents.
- Keep mobile behavior simple: stacked filters/cards and readable typography.

## Domain Boundary and Dependency Direction

- `config.urls` continues owning root route wiring.
- `core.views.home` continues owning page render entry.
- `templates/core/home.html` owns presentation only.
- Dependency direction remains unchanged:
  - `config -> core`
  - `core -> template`
- Avoided dependencies:
  - no imports from `events`/`drafts` into view/template for business logic.

## Coupling and Cohesion Review

- Cross-domain coupling is unchanged because only static presentation content changes.
- Cohesion of `core` web-entry responsibility remains intact.
- No additional orchestration logic is added.

## Pythonic Code Design

- No new backend logic introduced.
- Existing explicit function view + template rendering pattern is preserved.
- Business rules remain outside view/template layers.

## Risks and Constraints

- This task remains a static prototype page, not a bound event-list feature.
- Inline CSS remains for single-page scope; broader static asset extraction is deferred.

## Deferred Refactoring Note

Deferred Refactoring Note

- Topic: Extract shared base template and static CSS system for multi-page web UI.
- Why it is not part of the current scope: Current task is a single page redesign alignment.
- Why it may be needed later: Additional public pages will need reusable layout and style tokens.
- Trigger condition: Introduction of second and third public web pages with shared nav/layout.
- Expected change location: `templates/` base layout and `static/` stylesheet modules.
- Related tests: Future template render smoke tests and accessibility checks.
