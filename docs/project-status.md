# OshiLog Project Status

Last updated: 2026-05-29

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
