# Takulife Archive Static UI Design

Date: 2026-06-01
Project: `takulife`
Scope owner: Senior Dev / Codex

## Approved Scope

- Create a new public web page for personal archive preview at `/archive/`.
- Implement static UI only (no user account binding, no backend data binding).
- Keep existing API routes, domain logic, and admin workflow unchanged.
- Preserve the practical visual tone already used by home/list/detail pages.
- Do not add frontend test code for this task (user-approved exception).

## Acceptance Criteria

- `GET /archive/` returns HTTP 200.
- Page visibly includes archive-specific blocks:
  - 기록 요약 카드(누적 방문/이번 달/예정)
  - 월별 타임라인 그룹
  - 기록 카드(행사명/방문일/한줄메모/상태)
  - 기록 작성 유도 CTA 영역
- Desktop uses two-column shell; mobile stacks naturally.
- Existing `/`, `/events/`, `/events/<id>/`, `/api/*` behavior stays unchanged.

## Design Direction

- Keep archive page informative and compact, not decorative.
- Separate "탐색 화면 리듬" from "기록 화면 리듬":
  timeline-first layout with concise memory notes.
- Keep status visibility explicit:
  방문 완료, 방문 예정, 놓침 tags remain scannable.
- Use static placeholder thumbnails only, without upload features.

## Domain Boundary and Dependency Direction

- `config.urls` owns route mapping for `/archive/`.
- `core.views.archive` owns static template rendering entry.
- `templates/core/archive.html` owns presentation only.
- Dependency direction:
  - `config -> core`
  - `core -> template`
- Avoided dependencies:
  - No import/use of `events`/`drafts` models/services.
  - No authentication or user-profile coupling for this static scope.

## Coupling and Cohesion Review

- Coupling does not increase because this task adds a presentation route only.
- Cohesion improves by isolating archive-specific information architecture in one
  template.
- Shared nav/layout extraction remains deferred to avoid out-of-scope refactor.

## Pythonic Code Design

- Keep backend explicit with a small function view returning one template.
- Keep all business rules out of view/template for static UI scope.
- Use framework-native render path without hidden side effects.

## Deferred Refactoring Note

Deferred Refactoring Note

- Topic: Unify repeated public-page shell into shared base template.
- Why it is not part of the current scope: current task is one additional static page.
- Why it may be needed later: home/list/detail/archive now share top shell and design tokens.
- Trigger condition: next public page requires same header/filter shell again.
- Expected change location: `templates/base.html`, `templates/core/*.html`, `static/css/`.
- Related tests: future render smoke checks and responsive accessibility checks.
