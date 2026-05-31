# Takulife Mainpage Reference Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild `/` main page presentation to match approved design references while preserving existing backend behavior.

**Architecture:** Keep route and view unchanged, update only the home template structure and styles so the page expresses discovery-first event browsing information architecture. Avoid any event/draft domain integration and keep content static demo data.

**Tech Stack:** Django template rendering, inline CSS, existing `core.views.home`.

---

## Approved Scope

- Modify `templates/core/home.html` only for page composition and styling.
- Add/update project documents for plan and completion logs.
- Do not change API behavior or add domain logic.
- Frontend test code is explicitly excluded by user request.

## Acceptance Criteria

- `GET /` returns HTTP 200.
- `takulife` string is visible on the rendered page.
- Page includes:
  - top search/action row
  - quick filter chips (region/period/category)
  - sections: 이번 주 갈 만한 행사 / 곧 종료돼요 / 새로 등록
  - operation principles block for URL-draft/admin-review publication workflow
- Existing API route behavior remains unchanged.

## Domain Boundary and Dependency Direction

- `config.urls` owns route mapping.
- `core.views.home` owns render entry.
- `templates/core/home.html` owns presentation.
- Dependency direction unchanged:
  - `config -> core`
  - `core -> template`
- Forbidden expansion:
  - No new dependency from home page presentation to `events` or `drafts` domain modules.

## Coupling and Cohesion Review

- Coupling remains stable by limiting changes to the template.
- Cohesion improves inside the page by aligning layout blocks with a single discovery-first UX narrative.
- Any shared-style extraction remains deferred.

## Pythonic Code Design

- Preserve explicit function view rendering.
- Keep business logic out of template and view.
- Use static example blocks only; no hidden state mutation.

## Implementation Steps

1. Replace home template layout with reference-aligned structure:
   - top bar with brand/search/admin link
   - quick filters chips
   - three event sections
   - operations principle section
2. Apply responsive styling tokens matching approved visual direction.
3. Run verification commands.
4. Write refactoring work log and update project status.

## Verification Commands

- `uv run python manage.py check`
- `uv run python manage.py shell -c "from django.test import Client; c=Client(); r=c.get('/', HTTP_HOST='localhost'); s=r.content.decode(); print(r.status_code); print('takulife' in s); print('이번 주 갈 만한 행사' in s); print('곧 종료돼요' in s); print('새로 등록' in s)"`

## Test Policy Exception

- User-approved exception: no frontend test code addition for this task.

## Deferred Work

Deferred Refactoring Note

- Topic: Extract page styles into shared static CSS and base layout.
- Why it is not part of the current scope: this task is a single-page template adjustment.
- Why it may be needed later: repeated style blocks will increase duplication as pages grow.
- Trigger condition: additional public pages requiring common layout/navigation.
- Expected change location: `templates/base.html`, `static/css/`.
- Related tests: future template smoke checks for shared layout.
