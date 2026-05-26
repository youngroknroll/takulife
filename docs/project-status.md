# OshiLog Project Status

Last updated: 2026-05-26

## End-Of-Day Summary

Today's work established the OshiLog project as a uv-managed Django REST Framework backend.

Completed today:

- Created project operating guide: `AGENTS.md`.
- Installed and verified LazyWeb MCP for future UX/UI reference work.
- Created OshiLog MVP planning document.
- Switched implementation direction to RESTful API backend first.
- Created API backend implementation plan.
- Added screen-driven DB ERD document.
- Added REST API design plan based on the ERD.
- Added authentication design plan for Google login and custom User.
- Created uv project configuration and lockfile.
- Scaffolded Django project package: `config`.
- Scaffolded DRF core app: `core`.
- Added API root endpoint: `GET /api/`.
- Added health endpoint: `GET /api/health/`.
- Added TDD bootstrap tests.
- Moved `SECRET_KEY` loading to environment or ignored `.env`.
- Added committed `.env.example` template.
- Added `.gitignore` for `.env`, `.venv`, cache files, bytecode, and local SQLite DB.

## Current Status

RESTful API backend foundation is scaffolded.

Completed scope:

- uv-based Python project configuration.
- Django project package: `config`.
- Django REST Framework installed and configured.
- Core app package: `core`.
- API root endpoint: `GET /api/`.
- Health endpoint: `GET /api/health/`.
- Bootstrap API tests.
- `.env`-based `SECRET_KEY` loading with ignored local secret files.

## Verification Evidence

Fresh verification run on 2026-05-20:

```bash
uv run pytest -q tests/test_api_bootstrap.py
```

Result:

```text
2 passed in 0.20s
```

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
3 passed in 0.03s
```

Additional verification after `.env` secret loading:

```bash
uv run pytest -q tests/test_settings_env.py
```

Result:

```text
1 passed in 0.01s
```

## Active Documents

- `AGENTS.md`
- `docs/plans/2026-05-20-oshilog-mvp-planning.md`
- `docs/plans/2026-05-20-oshilog-api-backend-implementation-plan.md`
- `docs/plans/2026-05-26-oshilog-rest-api-design-plan.md`
- `docs/plans/2026-05-26-oshilog-auth-design-plan.md`
- `docs/erd/2026-05-26-oshilog-screen-design-erd.html`
- `.lazyweb/design-research/oshilog-screen-design-2026-05-26/report.html`
- `docs/refactoring/2026-05-20-api-foundation-work-log.md`

## Deferred Work

- Event model and public event API.
- EventDraft model and draft API.
- User status, visit record, and photo upload APIs.
- Custom User model and Google login flow.
- Admin approval workflow.
- URL fetch, extraction, duplicate URL checks, and SSRF protection.
- Authentication and authorization policy.
- PostgreSQL and deployment settings.
- Git repository initialization and first commit.

## Notes

- Package management is uv-only for this project.
- Secret values must live in `.env`, which is ignored by git. Use `.env.example` as the committed template.
- The earlier `docs/plans/2026-05-20-oshilog-foundation-implementation-plan.md` is superseded by the API backend implementation plan for code work.
