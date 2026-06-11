# OshiLog Project Status

## Current Focus

Dockerized Render deployment planning.

The approved deployment direction is:

- Render Docker Web Service for the Django runtime.
- Render managed PostgreSQL for production data.
- GitHub Container Registry for Docker images.
- GitHub Actions for CI/CD.

## Required Reading For Next Deployment Work

Read in this order:

1. `AGENTS.md`
2. `.docs/plans/2026-06-10-docker-render-deployment-design.md`
3. `.docs/plans/2026-06-10-docker-render-deployment-implementation-plan.md`
4. `config/settings.py`
5. `pyproject.toml`

For archive API context, also read:

1. `.docs/plans/2026-06-09-personal-archive-remaining-api-design.md`
2. `.docs/plans/2026-06-09-personal-archive-remaining-api-implementation-plan.md`

## Verified

- Deployment design direction reviewed and documented.
- Implementation boundary documented before production code changes.
- No production code changed by the deployment planning update.

## Not Verified

- Docker image build.
- GitHub Actions workflow execution.
- Render deployment.
- Render PostgreSQL connection.
- Production `manage.py check --deploy`.

These are not verified because this update is planning-only.

## Deferred Work

- Production media storage for visit record photos.
- PostgreSQL-backed CI test job.
- Environment-specific Django settings module split.
- Runtime observability and alerting.
- Blue-green or canary deployment.

## Latest Planning Documents

- `.docs/plans/2026-06-10-docker-render-deployment-design.md`
- `.docs/plans/2026-06-10-docker-render-deployment-implementation-plan.md`
