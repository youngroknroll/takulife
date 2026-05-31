# Takulife Archive Static UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a static archive page UI at `/archive/` for monthly visit history preview.

**Architecture:** Add a small `core` function view and root URL route for `/archive/`, then render a dedicated static archive template using existing Takulife visual language and responsive layout behavior.

**Tech Stack:** Django function view, Django URL routing, inline CSS template.

---

## Approved Scope

- Add `core.views.archive`.
- Add root route `/archive/` in `config.urls`.
- Create `templates/core/archive.html` with static archive UI.
- Update project documents for plan/work-log/status.
- Do not add frontend tests for this task (user-approved exception).

## Acceptance Criteria

- `GET /archive/` returns HTTP 200.
- Archive page includes:
  - 기록 요약 카드
  - 월별 타임라인 섹션
  - 기록 카드(행사명/방문일/메모/상태)
  - 기록 작성 유도 CTA
- Desktop: two-column shell.
- Mobile: single-column stacked layout with readable spacing.

## Domain Boundary and Dependency Direction

- `config.urls` maps URL -> view.
- `core.views` renders static template.
- `templates/core/archive.html` owns presentation only.
- Dependency direction unchanged:
  - `config -> core`
  - `core -> templates`
- Forbidden expansion:
  - no dependency from this page to `events`/`drafts` business logic.

## Coupling and Cohesion Review

- Coupling remains stable because no cross-domain orchestration is introduced.
- Cohesion improves by grouping archive presentation in one template.
- Shared layout extraction remains deferred.

## Pythonic Code Design

- Explicit function view with small context payload.
- No abstraction layers for hypothetical reuse.
- No hidden state mutation or side effects.

## Implementation Steps

1. Add `archive()` function view in `core/views.py`.
2. Add `/archive/` route in `config/urls.py`.
3. Create `templates/core/archive.html`:
   - top shell and navigation link set
   - archive summary cards
   - month timeline sections with visit cards
   - right panel for quick actions and 기록 작성 CTA
   - responsive behavior desktop -> mobile
4. Run verification commands.
5. Record completion in work log and project status.

## Verification Commands

- `uv run python manage.py check`
- `uv run python manage.py shell -c "from django.test import Client; c=Client(); r=c.get('/archive/', HTTP_HOST='localhost'); s=r.content.decode(); print(r.status_code); print('내 기록장' in s); print('월별 타임라인' in s); print('기록 추가' in s)"`

## Test Policy Exception

- User-approved exception: no frontend test code addition/execution for this task.

## Deferred Work

Deferred Refactoring Note

- Topic: Shared layout componentization for public templates.
- Why it is not part of the current scope: this task adds one static page only.
- Why it may be needed later: repeated shell sections across four public pages.
- Trigger condition: fifth public page introduces duplicate layout updates.
- Expected change location: `templates/base.html`, `templates/core/*.html`, `static/css/`.
- Related tests: future template smoke checks and accessibility checks.
