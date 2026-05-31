# Takulife Event Detail Static UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a static event-detail page UI at `/events/1/` with extended information sections.

**Architecture:** Add a small `core` function view and dynamic URL route for `/events/<id>/`, then render a dedicated static detail template using existing Takulife visual language. Do not connect to backend event APIs yet.

**Tech Stack:** Django function view, Django URL routing, inline CSS template.

---

## Approved Scope

- Add `core.views.event_detail`.
- Add root route `/events/<int:event_id>/` in `config.urls`.
- Create `templates/core/event_detail.html` with static extended detail UI.
- Update project documents for plan/work-log/status.
- Do not add frontend tests for this task (user-approved exception).

## Acceptance Criteria

- `GET /events/1/` returns HTTP 200.
- Detail page includes:
  - 행사명/카테고리/기간/장소/상태
  - 설명 본문
  - 예매/공식 링크
  - 지도 영역
  - 주최/문의
  - 유의사항
  - 비슷한 행사 카드
- Desktop: two-column information layout.
- Mobile: stacked layout preserving readability.

## Domain Boundary and Dependency Direction

- `config.urls` maps URL -> view.
- `core.views` renders static template with route param.
- `templates/core/event_detail.html` owns presentation only.
- Dependency direction unchanged:
  - `config -> core`
  - `core -> templates`
- Forbidden expansion:
  - no new dependency from presentation layer into `events`/`drafts` domain logic.

## Coupling and Cohesion Review

- Coupling remains stable because no cross-domain orchestration is introduced.
- Cohesion improves by keeping all event-detail presentation concerns together.
- Shared layout extraction remains deferred to avoid scope expansion.

## Pythonic Code Design

- Explicit function view with `render()` and small context.
- No hidden mutation and no abstraction layer.
- Framework-native URL parameter usage only.

## Implementation Steps

1. Add `event_detail()` function view in `core/views.py`.
2. Add `/events/<int:event_id>/` route in `config/urls.py`.
3. Create `templates/core/event_detail.html`:
   - top navigation/action row
   - left main content: title/meta/description/map/notices
   - right summary panel: status/actions/host/contact/similar events
   - responsive two-column -> single-column behavior
4. Run verification commands.
5. Record completion in work log and project status.

## Verification Commands

- `uv run python manage.py check`
- `uv run python manage.py shell -c "from django.test import Client; c=Client(); r=c.get('/events/1/', HTTP_HOST='localhost'); s=r.content.decode(); print(r.status_code); print('행사 상세' in s); print('지도' in s); print('비슷한 행사' in s)"`

## Test Policy Exception

- User-approved exception: no frontend test code addition/execution for this task.

## Deferred Work

Deferred Refactoring Note

- Topic: Move repeated UI shell and color tokens to base template/static CSS.
- Why it is not part of the current scope: this task adds one static detail page.
- Why it may be needed later: more public pages will increase template duplication.
- Trigger condition: archive/member/public search pages adopt same shell.
- Expected change location: `templates/base.html`, `templates/core/*.html`, `static/css/`.
- Related tests: future template smoke checks and accessibility checks.
