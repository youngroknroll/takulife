# OshiLog Project Status

Last updated: 2026-06-01

## 2026-06-01 Event List `closing_soon` Status API

Completed:

- Extended public event list API `GET /api/events/` with a new status filter:
  - `status=closing_soon`
- Added behavior rule:
  - ongoing events only (`start_date <= today <= end_date`)
  - and ending within 5 days including today (`end_date <= today + 4 days`)
- Preserved existing status behaviors:
  - `upcoming`, `ongoing`, `ended`
  - unknown status values are still ignored.

Verification evidence:

```bash
uv run pytest -q tests/test_events_api.py
```

Result:

```text
16 passed in 0.20s
```

```bash
uv run pytest -q
```

Result:

```text
62 passed in 6.41s
```

```bash
uv run python manage.py check
```

Result:

```text
System check identified no issues (0 silenced).
```

```bash
uv run python manage.py makemigrations --check --dry-run
```

Result:

```text
No changes detected
```

Active documents added:

- `docs/plans/2026-06-01-event-list-closing-soon-status-design.md`
- `docs/plans/2026-06-01-event-list-closing-soon-status-implementation-plan.md`
- `docs/refactoring/2026-06-01-event-list-closing-soon-status-work-log.md`

## 2026-05-31 Takulife Event Detail Static UI

Completed:

- Added design and implementation plan documents for static event-detail page.
- Added new public web route `/events/<int:event_id>/` with `core.views.event_detail`.
- Added `templates/core/event_detail.html` static UI:
  - two-column detail layout (desktop) and stacked mobile layout
  - 행사 기본 정보, 설명, 지도 영역, 유의사항
  - 우측 요약 패널(상태/액션 링크/주최·문의/비슷한 행사)
- Kept backend/domain/API behavior unchanged.

Verification evidence:

```bash
uv run python manage.py check
```

Result:

```text
System check identified no issues (0 silenced).
```

```bash
uv run python manage.py shell -c "from django.test import Client; c=Client(); r=c.get('/events/1/', HTTP_HOST='localhost'); s=r.content.decode(); print(r.status_code); print('행사 상세' in s); print('지도' in s); print('비슷한 행사' in s)"
```

Result:

```text
200
True
True
True
```

Not run:

- Frontend test code addition/execution (user-approved exception).
- Full regression suite (`uv run pytest -q`) for this task.

Active documents added:

- `docs/plans/2026-05-31-takulife-event-detail-static-ui-design.md`
- `docs/plans/2026-05-31-takulife-event-detail-static-ui-implementation-plan.md`
- `docs/refactoring/2026-05-31-takulife-event-detail-static-ui-work-log.md`

## 2026-05-31 Event List Query Alias/Ordering API

Completed:

- Extended public event list API `GET /api/events/` query compatibility:
  - `event_type` alias (maps to `category`)
  - `work_title` filter
  - `starts_after` alias (maps to `start_date_from`)
  - `starts_before` alias (maps to `start_date_to`)
- Added default list ordering policy:
  1. ongoing first (ending sooner first)
  2. upcoming next (starting sooner first)
  3. ended last (recently ended first)
- Preserved existing path/permission boundaries and existing filters.

Verification evidence:

```bash
uv run pytest -q tests/test_events_api.py
```

Result:

```text
15 passed in 0.17s
```

```bash
uv run pytest -q
```

Result:

```text
61 passed in 6.39s
```

```bash
uv run python manage.py check
```

Result:

```text
System check identified no issues (0 silenced).
```

```bash
uv run python manage.py makemigrations --check --dry-run
```

Result:

```text
No changes detected
```

Active documents added:

- `docs/plans/2026-05-31-event-list-query-alias-ordering-design.md`
- `docs/plans/2026-05-31-event-list-query-alias-ordering-implementation-plan.md`
- `docs/refactoring/2026-05-31-event-list-query-alias-ordering-work-log.md`

## 2026-05-31 Takulife Event List Static UI

Completed:

- Added design and implementation plan documents for static event-list page.
- Added new public web route `/events/` with `core.views.event_list`.
- Added `templates/core/event_list.html` static UI:
  - top search/action row
  - quick filter chips
  - left filter panel (region/period/category)
  - right list cards with D-day, location, period, and status actions
- Kept backend/domain/API behavior unchanged.

Verification evidence:

```bash
uv run python manage.py check
```

Result:

```text
System check identified no issues (0 silenced).
```

```bash
uv run python manage.py shell -c "from django.test import Client; c=Client(); r=c.get('/events/', HTTP_HOST='localhost'); s=r.content.decode(); print(r.status_code); print('행사 목록' in s); print('검색 결과 42개' in s); print('필터 적용' in s)"
```

Result:

```text
200
True
True
True
```

Not run:

- Frontend test code addition/execution (user-approved exception).
- Full regression suite (`uv run pytest -q`) for this task.

Active documents added:

- `docs/plans/2026-05-31-takulife-event-list-static-ui-design.md`
- `docs/plans/2026-05-31-takulife-event-list-static-ui-implementation-plan.md`
- `docs/refactoring/2026-05-31-takulife-event-list-static-ui-work-log.md`

## 2026-05-31 Event List Date/Status Filter API

Completed:

- Extended public event list API `GET /api/events/` with date filters:
  - `start_date_from`
  - `start_date_to`
- Added public status filter for event progress:
  - `status=upcoming`
  - `status=ongoing`
  - `status=ended`
- Kept existing `q`, `region`, and `category` filters unchanged.
- Added regression tests for date filters, status filters, and unknown status
  behavior.

Verification evidence:

```bash
uv run pytest -q tests/test_events_api.py
```

Result:

```text
13 passed in 0.16s
```

```bash
uv run pytest -q
```

Result:

```text
59 passed in 6.16s
```

```bash
uv run python manage.py check
```

Result:

```text
System check identified no issues (0 silenced).
```

```bash
uv run python manage.py makemigrations --check --dry-run
```

Result:

```text
No changes detected
```

Active documents added:

- `docs/plans/2026-05-31-event-list-date-status-filter-implementation-plan.md`
- `docs/refactoring/2026-05-31-event-list-date-status-filter-work-log.md`

## 2026-05-31 Takulife Mainpage Reference Alignment

Completed:

- Added reference-alignment design and implementation plan documents for the
  homepage rework.
- Reworked `templates/core/home.html` to align with approved design references
  while preserving the existing scope boundary.
- Updated homepage information architecture to discovery-first layout:
  - top search/action row
  - quick filter chips
  - sectioned event blocks: 이번 주 갈 만한 행사 / 곧 종료돼요 / 새로 등록
  - operations principle block for admin draft review publication flow
- Kept existing backend/API behavior unchanged.

Verification evidence:

```bash
uv run python manage.py check
```

Result:

```text
System check identified no issues (0 silenced).
```

```bash
uv run python manage.py shell -c "from django.test import Client; c=Client(); r=c.get('/', HTTP_HOST='localhost'); s=r.content.decode(); print(r.status_code); print('takulife' in s); print('이번 주 갈 만한 행사' in s); print('곧 종료돼요' in s); print('새로 등록' in s)"
```

Result:

```text
200
True
True
True
True
```

Not run:

- Frontend test code addition/execution (user-approved exception).
- Full regression suite (`uv run pytest -q`) for this task.

Active documents added:

- `docs/plans/2026-05-31-takulife-mainpage-reference-alignment-design.md`
- `docs/plans/2026-05-31-takulife-mainpage-reference-alignment-implementation-plan.md`
- `docs/refactoring/2026-05-31-takulife-mainpage-reference-alignment-work-log.md`

## 2026-05-31 Business Logic Correction

Completed:

- Added business-logic correction design and implementation plan documents.
- Enforced official URL requirement in published-event creation logic.
- Added draft URL ingestion pipeline for admin draft creation:
  - URL safety validation
  - bounded HTML fetching
  - rule-based field extraction
- Moved draft update pending-state rule into `drafts.services`.
- Added controlled API error mapping for unsafe URL, fetch failure, oversized
  response, unsupported content, and empty extraction.
- Unmounted deferred member/archive routes from root URL config by removing
  `api/me/` inclusion.
- Expanded tests for events service invariants, draft services, draft API
  creation behavior, deferred route behavior, and architecture boundaries.

Verification evidence:

```bash
uv run pytest -q tests/test_events_services.py tests/test_drafts_services.py tests/test_drafts_api.py tests/test_user_event_status_api.py tests/test_visit_records_api.py tests/test_architecture_boundaries.py
```

Result:

```text
40 passed in 6.37s
```

```bash
uv run pytest -q
```

Result:

```text
55 passed in 6.47s
```

```bash
uv run python manage.py check
```

Result:

```text
System check identified no issues (0 silenced).
```

```bash
uv run python manage.py makemigrations --check --dry-run
```

Result:

```text
No changes detected
```

Active documents added:

- `docs/plans/2026-05-31-business-logic-correction-design.md`
- `docs/plans/2026-05-31-business-logic-correction-implementation-plan.md`
- `docs/refactoring/2026-05-31-business-logic-correction-work-log.md`

## 2026-05-30 Takulife Main Page Creation

Completed:

- Added root web route `/` for a public main page.
- Added `core.views.home` and connected it from `config.urls`.
- Added `templates/core/home.html` with project name `takulife`.
- Reworked the main page UI using existing design references:
  - home/list-oriented layout
  - filter controls for keyword/region/category/period
  - event card-style listing preview
  - admin review workflow summary
- Reflected MVP purpose and admin-curated publication principles on the page.
- Kept existing API routes and backend behavior unchanged.

Verification evidence:

```bash
uv run python manage.py check
```

Result:

```text
System check identified no issues (0 silenced).
```

```bash
uv run pytest -q
```

Result:

```text
44 passed in 5.44s
```

```bash
uv run python manage.py shell -c "from django.test import Client; r=Client().get('/', HTTP_HOST='localhost'); print(r.status_code); print('takulife' in r.content.decode())"
```

Result:

```text
200
True
```

Not run:

- Frontend 신규 테스트 코드는 사용자 요청에 따라 작성하지 않음.

Active documents added:

- `docs/plans/2026-05-30-takulife-mainpage-implementation-plan.md`
- `docs/refactoring/2026-05-30-takulife-mainpage-work-log.md`

## 2026-05-28 Agent Definition Update

Completed:

- Added Claude-style project agent definitions under `.claude/agents/`.
- Created role definitions for all default roles listed in `AGENTS.md`.
- Added role-specific model frontmatter matching `AGENTS.md`.
- Added an implementation boundary plan for agent definition work.
- Added an agent definition work log.

Verification evidence:

```bash
find .claude/agents -maxdepth 1 -type f -name '*.md' | sort
```

Result:

```text
.claude/agents/infra-devops.md
.claude/agents/po-general-manager.md
.claude/agents/qa.md
.claude/agents/security-reliability.md
.claude/agents/senior-dev-codex.md
.claude/agents/tdd-expert.md
.claude/agents/tech-lead-architect.md
.claude/agents/web-frontend-developer.md
.claude/agents/web-ux-ui-designer.md
```

```bash
rg '^name:|^description:' .claude/agents docs/plans/2026-05-28-oshilog-agent-definition-plan.md docs/refactoring/2026-05-28-agent-definition-work-log.md docs/project-status.md
```

Result:

```text
All 9 agent files expose name and description frontmatter.
```

```bash
rg '^model:' .claude/agents
```

Result:

```text
All 9 agent files expose role-specific model frontmatter matching AGENTS.md.
```

Not run:

- Application tests, because this task changed only agent configuration and
  documentation.

Active documents added:

- `docs/plans/2026-05-28-oshilog-agent-definition-plan.md`
- `docs/refactoring/2026-05-28-agent-definition-work-log.md`

## 2026-05-28 Event Index API Contract Design

Completed:

- Re-ran PO analysis with the `AGENTS.md` model mapping: `gpt-5.5`.
- Ran follow-up analysis with role-specific models:
  - Tech Lead / Architect: `gpt-5.4`
  - TDD Expert: `gpt-5.4-mini`
  - Security / Reliability: `gpt-5.3-codex`
  - QA: `gpt-5.3-codex`
- Added backend API contract design for the Event Index slice.
- Decided that the public API uses `category`; implementation must not expose
  both `category` and `event_type`.
- Kept member-facing APIs out of the next delivery target.

Verification evidence:

```bash
rg '^name:|^description:|^model:' .claude/agents
```

Result:

```text
All 9 agent definitions expose name, description, and model frontmatter.
```

Not run:

- Application tests, because this update changed documentation and agent
  configuration only.

Active documents added:

- `docs/plans/2026-05-28-oshilog-event-index-api-contract-design.md`
- `docs/refactoring/2026-05-28-event-index-api-contract-design-log.md`

## 2026-05-29 Event Index API Completion

Completed:

- Added public event detail API: `GET /api/events/{id}/`.
- Added public event list filtering by `q`, `region`, and `category`.
- Updated public event responses to expose event-index fields and hide
  `publish_status`.
- Added admin draft detail/update API.
- Added admin draft approve/reject APIs.
- Approval creates a published `Event`; rejection creates no `Event`.
- Added duplicate `source_url` and duplicate `official_url` behavior coverage.
- Added HTTP/HTTPS-only source URL validation.
- Added initial migrations for `accounts`, `events`, and `drafts`.
- Addressed QA and Tech Lead review findings by expanding regression coverage,
  narrowing draft PATCH scope, blocking draft PUT, and hardening approve/reject
  state transitions.

Verification evidence:

```bash
uv run pytest -q tests/test_events_api.py
```

Result:

```text
9 passed in 0.13s
```

```bash
uv run pytest -q tests/test_drafts_api.py
```

Result:

```text
17 passed in 3.81s
```

```bash
uv run pytest -q
```

Result:

```text
36 passed in 4.81s
```

```bash
uv run python manage.py check
```

Result:

```text
System check identified no issues (0 silenced).
```

```bash
uv run python manage.py makemigrations --check --dry-run
```

Result:

```text
No changes detected
```

Active documents added:

- `docs/refactoring/2026-05-29-event-index-api-completion-work-log.md`

## 2026-05-29 Event Index Boundary Correction

Completed:

- Reviewed the implementation against the revised domain-boundary,
  coupling/cohesion, and Pythonic code design requirements.
- Used Tech Lead / Architect, TDD Expert, and Security / Reliability review
  outputs to identify required corrections.
- Added explicit service boundaries:
  - `events.services` owns published event creation.
  - `drafts.services` owns approve/reject workflow orchestration.
- Removed direct `Event` creation from draft HTTP views.
- Removed `events` module imports from draft HTTP views; publication failures
  are mapped to draft-domain exceptions in `drafts.services`.
- Removed the approve/reject view pre-lookup and kept missing draft handling
  behind the draft service boundary.
- Added `core.errors` for generic HTTP error response helpers while keeping
  domain exceptions inside their owning apps.
- Changed immutable draft field PATCH attempts from silent ignore to explicit
  `400` field errors.
- Changed unexpected publish failures from uncaught 500 exceptions to a
  controlled `503` JSON response while preserving the pending draft state.
- Clarified the design document that this slice creates URL-only drafts and
  defers remote fetching/extraction.
- Updated the implementation plan to prefer public API behavior tests over
  model-shape tests.

Verification evidence:

```bash
uv run pytest -q tests/test_architecture_boundaries.py tests/test_drafts_api.py
```

Result:

```text
23 passed in 4.29s
```

```bash
uv run pytest -q tests/test_architecture_boundaries.py tests/test_drafts_api.py tests/test_drafts_services.py
```

Result:

```text
22 passed in 4.91s
```

```bash
uv run pytest -q tests/test_drafts_api.py tests/test_drafts_services.py
```

Result:

```text
19 passed in 4.45s
```

```bash
uv run pytest -q
```

Result:

```text
44 passed in 5.16s
```

```bash
uv run python manage.py check
```

Result:

```text
System check identified no issues (0 silenced).
```

```bash
uv run python manage.py makemigrations --check --dry-run
```

Result:

```text
No changes detected
```

Active documents added:

- `docs/refactoring/2026-05-29-event-index-boundary-correction-work-log.md`

## End-Of-Day Summary

Today's work extended the backend foundation into the first usable API slice.

Completed today:

- Added custom user model boundary with `accounts.User`.
- Added current-user API: `GET /api/auth/me/`.
- Added public event list API: `GET /api/events/`.
- Added admin draft create/list API: `GET/POST /api/admin/event-drafts/`.
- Added user event status upsert API: `PUT /api/me/event-statuses/<event_id>/`.
- Added visit record create API: `POST /api/me/visit-records/`.
- Added visit record photo create/delete APIs.
- Added API regression tests for auth, events, drafts, event status, and visit records.
- Wrote backend API progress log and updated project status documentation.

## Current Status

Event Index API completion slice is implemented and verified.

Completed scope:

- Custom user model: `accounts.User`.
- Auth identity endpoint: `GET /api/auth/me/`.
- Public published-event list endpoint: `GET /api/events/`.
- Public published-event detail endpoint: `GET /api/events/{id}/`.
- Public published-event list filtering by `q`, `region`, and `category`.
- Admin event draft create/list endpoint: `GET/POST /api/admin/event-drafts/`.
- Admin event draft detail/update endpoint:
  - `GET /api/admin/event-drafts/{id}/`
  - `PATCH /api/admin/event-drafts/{id}/`
- Admin event draft review endpoints:
  - `POST /api/admin/event-drafts/{id}/approve/`
  - `POST /api/admin/event-drafts/{id}/reject/`
- User event status endpoint: `PUT /api/me/event-statuses/<event_id>/`.
- Visit record create endpoint: `POST /api/me/visit-records/`.
- Visit record photo endpoints:
  - `POST /api/me/visit-records/<record_id>/photos/`
  - `DELETE /api/me/visit-records/<record_id>/photos/<photo_id>/`
- API regression tests for the endpoints above.

## Verification Evidence

Fresh verification run on 2026-05-27:

```bash
uv run python manage.py check
```

Result:

```text
System check identified no issues (0 silenced).
```

```bash
uv run pytest -q
```

Result:

```text
13 passed in 1.20s
```

## Active Documents

- `AGENTS.md`
- `docs/plans/2026-05-20-oshilog-mvp-planning.md`
- `docs/plans/2026-05-20-oshilog-api-backend-implementation-plan.md`
- `docs/plans/2026-05-26-oshilog-rest-api-design-plan.md`
- `docs/plans/2026-05-26-oshilog-auth-design-plan.md`
- `docs/plans/2026-05-27-oshilog-backend-api-implementation-plan.md`
- `docs/plans/2026-05-28-oshilog-event-index-design.md`
- `docs/plans/2026-05-28-oshilog-event-index-implementation-plan.md`
- `docs/plans/2026-05-28-oshilog-event-index-api-contract-design.md`
- `docs/erd/2026-05-26-oshilog-screen-design-erd.html`
- `.lazyweb/design-research/oshilog-screen-design-2026-05-26/report.html`
- `docs/refactoring/2026-05-20-api-foundation-work-log.md`
- `docs/refactoring/2026-05-27-backend-api-progress-log.md`
- `docs/refactoring/2026-05-28-event-index-api-contract-design-log.md`
- `docs/refactoring/2026-05-29-event-index-api-completion-work-log.md`

## Deferred Work

- URL fetch and extraction pipeline.
- Google login flow and provider boundary implementation.
- SSRF protection for future URL fetching.
- Stronger authentication and authorization policy details.
- PostgreSQL and deployment settings.
- Review existing database migration rollout because initial migrations were
  added after app models already existed.
- Request/response documentation for each API.
- TDD cleanup for visit record photo endpoints, which currently have tests added after the initial implementation.

## Notes

- Package management is uv-only for this project.
- Secret values must live in `.env`, which is ignored by git. Use `.env.example` as the committed template.
- The earlier `docs/plans/2026-05-20-oshilog-foundation-implementation-plan.md` is superseded by the API backend implementation plan for code work.
- The 2026-05-27 implementation followed the approved plan scope, but the visit record photo tests were added after the first implementation pass and should be treated as a TDD process gap to correct in later batches.
