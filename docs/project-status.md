# OshiLog Project Status

Last updated: 2026-05-27

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

RESTful API backend first slice is partially implemented and verified.

Completed scope:

- Custom user model: `accounts.User`.
- Auth identity endpoint: `GET /api/auth/me/`.
- Public published-event list endpoint: `GET /api/events/`.
- Admin event draft create/list endpoint: `GET/POST /api/admin/event-drafts/`.
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
- `docs/erd/2026-05-26-oshilog-screen-design-erd.html`
- `.lazyweb/design-research/oshilog-screen-design-2026-05-26/report.html`
- `docs/refactoring/2026-05-20-api-foundation-work-log.md`
- `docs/refactoring/2026-05-27-backend-api-progress-log.md`

## Deferred Work

- Admin draft review approve/reject endpoints.
- Google login flow and provider boundary implementation.
- URL fetch, extraction, duplicate URL checks, and SSRF protection.
- Stronger authentication and authorization policy details.
- PostgreSQL and deployment settings.
- Request/response documentation for each API.
- TDD cleanup for visit record photo endpoints, which currently have tests added after the initial implementation.

## Notes

- Package management is uv-only for this project.
- Secret values must live in `.env`, which is ignored by git. Use `.env.example` as the committed template.
- The earlier `docs/plans/2026-05-20-oshilog-foundation-implementation-plan.md` is superseded by the API backend implementation plan for code work.
- The 2026-05-27 implementation followed the approved plan scope, but the visit record photo tests were added after the first implementation pass and should be treated as a TDD process gap to correct in later batches.
