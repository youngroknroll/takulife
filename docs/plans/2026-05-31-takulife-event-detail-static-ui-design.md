# Takulife Event Detail Static UI Design

Date: 2026-05-31
Project: `takulife`
Scope owner: Senior Dev / Codex

## Approved Scope

- Create a new public web page for event detail at `/events/<id>/`.
- Implement static UI only (no API binding, no backend detail lookup).
- Keep existing API routes and domain logic unchanged.
- Reflect approved extended information structure:
  - 기본 정보 + 설명
  - 지도 영역
  - 주최/문의
  - 유의사항
  - 비슷한 행사 카드

## Acceptance Criteria

- `GET /events/1/` returns HTTP 200.
- Page visibly includes:
  - 행사명, 카테고리, 기간, 장소, 상태
  - 본문 설명
  - 지도 플레이스홀더
  - 주최/문의 정보
  - 유의사항 목록
  - 비슷한 행사 카드 목록
- Layout follows two-column information pattern on desktop and stacks on mobile.
- Existing `/`, `/events/`, and `/api/*` behavior stays unchanged.

## Design Direction

- Preserve Takulife discovery-first tone from existing pages.
- Keep dense but scannable card UI with explicit labels.
- Use static action links for 예매/공식 링크/목록 복귀.
- Prioritize readability on mobile by stacking right summary panel under main content.

## Domain Boundary and Dependency Direction

- `config.urls` owns route mapping for `/events/<id>/`.
- `core.views.event_detail` owns static template rendering entry.
- `templates/core/event_detail.html` owns presentation only.
- Dependency direction:
  - `config -> core`
  - `core -> template`
- Avoided dependencies:
  - No import/use of `events`/`drafts` domain services or models.

## Coupling and Cohesion Review

- Coupling does not increase because this task adds only presentation route/view.
- Cohesion improves by isolating event-detail-specific sections in one template.
- Shared layout and CSS extraction is intentionally deferred.

## Pythonic Code Design

- Keep backend code explicit with a small function view rendering one template.
- Keep business logic out of views/templates for static scope.
- Use framework-native URL parameter passing without hidden side effects.

## Deferred Refactoring Note

Deferred Refactoring Note

- Topic: Introduce shared base template/components for list/detail shell.
- Why it is not part of the current scope: current task is one additional static page.
- Why it may be needed later: list/detail/home already repeat top navigation and tokens.
- Trigger condition: event archive or member pages adopt same shell.
- Expected change location: `templates/base.html`, `templates/core/*.html`, `static/css/`.
- Related tests: future template smoke checks and responsive accessibility checks.
