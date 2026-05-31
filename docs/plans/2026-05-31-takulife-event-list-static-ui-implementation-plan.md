# Takulife Event List Static UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a static event-list page UI at `/events/` that matches the approved discovery-first design direction.

**Architecture:** Keep backend behavior minimal by adding a simple `core` function view and URL route, then render static event list markup in a dedicated template. Do not connect this page to `events` APIs yet.

**Tech Stack:** Django function view, Django URL routing, inline CSS template.

---

## Approved Scope

- Add `core.views.event_list`.
- Add root route `/events/` in `config.urls`.
- Create `templates/core/event_list.html` with static event-list UI.
- Update project documents for plan/work-log/status.
- Do not add frontend tests for this task (user-approved exception).

## Acceptance Criteria

- `GET /events/` returns HTTP 200.
- Event list page includes:
  - search row and quick chips
  - left filter panel (region/period/category controls)
  - right card list emphasizing category, D-day, location, period
  - status action buttons on cards
- Existing homepage `/` and API routes remain unchanged.

## Domain Boundary and Dependency Direction

- `config.urls` maps URL -> view.
- `core.views` renders the static template.
- `templates/core/event_list.html` contains presentation only.
- Dependency direction unchanged:
  - `config -> core`
  - `core -> templates`
- Forbidden expansion:
  - no new dependency from `core` UI layer into `events`/`drafts` business modules.

## Coupling and Cohesion Review

- Coupling remains stable because no backend domain orchestration is introduced.
- Cohesion improves by isolating event-list UI concerns into one template.
- Any shared component extraction remains deferred.

## Pythonic Code Design

- Explicit, small function view for rendering static HTML.
- No hidden mutation, no abstraction layer, no mixed business logic.
- Framework-native route and render pattern only.

## Implementation Steps

1. Add `event_list()` function view in `core/views.py`.
2. Add `/events/` route in `config/urls.py`.
3. Create `templates/core/event_list.html`:
   - top bar + quick chips
   - filter sidebar
   - event card list and static pagination
   - mobile-safe responsive layout
4. Run verification commands.
5. Record completion in refactoring log and project status.

## Verification Commands

- `uv run python manage.py check`
- `uv run python manage.py shell -c "from django.test import Client; c=Client(); r=c.get('/events/', HTTP_HOST='localhost'); s=r.content.decode(); print(r.status_code); print('행사 목록' in s); print('검색 결과 42개' in s); print('필터 적용' in s)"`

## Test Policy Exception

- User-approved exception: no frontend test code addition/execution for this task.

## Deferred Work

Deferred Refactoring Note

- Topic: Migrate inline CSS and duplicate header patterns into shared template/static assets.
- Why it is not part of the current scope: this task targets one new static page.
- Why it may be needed later: upcoming detail/archive pages will repeat layout styles.
- Trigger condition: second and third public pages share the same shell.
- Expected change location: `templates/base.html`, `templates/core/*.html`, `static/css/`.
- Related tests: future template smoke checks and accessibility checks.
