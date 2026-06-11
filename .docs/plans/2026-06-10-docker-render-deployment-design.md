# Docker Render Deployment Design

## Goal

Prepare OshiLog for a low-cost always-on deployment using a Dockerized Django
runtime on Render, GitHub Actions CI/CD, GitHub Container Registry, and Render
managed PostgreSQL.

## Approved Direction

- Runtime host: Render Docker Web Service.
- Database: Render managed PostgreSQL.
- Image registry: GitHub Container Registry.
- CI/CD runner: GitHub Actions.
- Application server: Gunicorn serving `config.wsgi:application`.
- Static files: WhiteNoise-backed Django static file serving.
- Local development database: SQLite fallback unless `DATABASE_URL` is set.

## Alternatives Reviewed

### Render Native Python Runtime

This is the simplest Render path, but it does not match the desired CI/CD
workflow. It also leaves less value in building and verifying the runtime image
in GitHub Actions.

### Docker On EC2

This gives full control, but it adds server patching, firewall, process
supervision, TLS, Docker host maintenance, and database networking work. It is
too much operational surface for the current MVP.

### Docker On Render

This keeps the runtime image reproducible while letting Render handle the host
and managed PostgreSQL. It fits the current desire for GitHub Actions-driven
image builds without taking on EC2 operations.

## Scope

In scope:

- Add a production Docker runtime for the Django app.
- Add production-safe environment parsing in Django settings.
- Add PostgreSQL support through `DATABASE_URL`.
- Add WhiteNoise static file support.
- Add Gunicorn runtime support.
- Add GitHub Actions workflows for tests, Docker build, image push, and Render
  deployment trigger.
- Add Render deployment configuration or documented Render service settings.
- Add verification commands for local, container, and CI-style checks.

Out of scope:

- Running PostgreSQL inside the production container.
- EC2 deployment.
- Kubernetes, Docker Swarm, or blue-green deployment.
- Celery, background workers, schedulers, or async job runners.
- S3, R2, or Supabase Storage integration for uploaded media.
- Production observability beyond basic deployment checks.
- Changing product API behavior.

## Domain Boundary And Dependency Direction

Deployment belongs to the project infrastructure boundary. It must not change
business ownership in the Django apps.

- `config` owns environment-specific Django configuration.
- GitHub Actions owns CI/CD orchestration.
- Render owns runtime hosting and managed PostgreSQL.
- `accounts`, `events`, `drafts`, `archive`, and `core` must not depend on
  deployment-specific modules.
- Application code must read deployment concerns only through Django settings.

Avoided dependencies:

- Domain apps must not import CI, Docker, Render, or environment parsing helper
  modules directly.
- Runtime start commands must not embed business behavior.
- Database migration execution must remain an operational step, not application
  startup business logic.

Business logic placement:

- No product business rules are introduced by this deployment build.
- Settings helpers may parse environment values, but they must stay small,
  explicit, and side-effect free except for reading environment variables.

## Coupling And Cohesion Review

This design avoids increasing domain coupling by keeping deployment code at the
project edge: `Dockerfile`, `.github/workflows/`, `render.yaml`, and
`config/settings.py`.

It improves infrastructure cohesion by placing runtime configuration in one
deployment slice instead of scattering host-specific assumptions through app
modules.

Remaining coupling:

- `config/settings.py` will know about `DATABASE_URL`, static file storage, and
  security env vars. This is acceptable for the current single-settings-module
  project.
- A future split into `config/settings/base.py`, `local.py`, and
  `production.py` is deferred until settings complexity grows.

Deferred Refactoring Note

- Topic: Split Django settings into environment-specific modules.
- Why it is not part of the current scope: The current project uses one small
  `config/settings.py`, and a split would add structure before the settings are
  complex enough to need it.
- Why it may be needed later: More deployment targets, storage backends,
  observability, or test-specific settings may make one settings file harder to
  reason about.
- Trigger condition: A second production-like environment is added, or settings
  conditionals become difficult to review.
- Expected change location: `config/settings/`.
- Related tests: `uv run python manage.py check`, production settings tests,
  and CI workflow verification.

## Pythonic Code Design

- Use small parsing helpers in `config/settings.py` for booleans and comma-list
  values instead of clever global configuration frameworks.
- Use `dj-database-url` for `DATABASE_URL` parsing rather than custom URL
  parsing.
- Use Django's standard `STATIC_ROOT`, `STATIC_URL`, and storage settings.
- Use WhiteNoise through Django middleware, keeping static behavior inside the
  framework-supported path.
- Keep local behavior explicit: SQLite remains the fallback when
  `DATABASE_URL` is absent.
- Avoid hidden mutation during imports beyond normal Django settings evaluation.

## Runtime Architecture

```text
Developer push
  -> GitHub Actions test workflow
  -> Docker build workflow
  -> GHCR image push
  -> Render deploy trigger
  -> Render pulls image
  -> Render pre-deploy migration
  -> Gunicorn serves Django
  -> Django connects to Render PostgreSQL by DATABASE_URL
```

## Required Environment Variables

- `SECRET_KEY`: required outside local development.
- `DEBUG`: defaults to false in deployment.
- `ALLOWED_HOSTS`: comma-separated host list.
- `CSRF_TRUSTED_ORIGINS`: comma-separated trusted origins.
- `DATABASE_URL`: Render PostgreSQL connection URL.
- `DJANGO_SETTINGS_MODULE`: `config.settings`.
- `PORT`: provided by Render.

Optional environment variables:

- `SECURE_SSL_REDIRECT`: enable after Render proxy behavior is verified.
- `SESSION_COOKIE_SECURE`: enable for HTTPS deployment.
- `CSRF_COOKIE_SECURE`: enable for HTTPS deployment.

## Database Plan

- Production uses Render managed PostgreSQL.
- The app container does not run PostgreSQL.
- Local development keeps SQLite fallback.
- CI may use SQLite for fast tests unless a PostgreSQL-specific behavior is
  added later.
- Migration execution belongs to Render pre-deploy or a CI deploy step, not the
  Gunicorn start command.

## Media Plan

The current archive API can upload visit record photos, but production media
storage is not part of this deployment build.

For the first deployment, choose one of these before exposing photo upload to
real users:

- Keep photo upload hidden from public usage and document media storage as
  deferred.
- Add Render persistent disk in a separate, approved deployment-media plan.
- Add S3, Cloudflare R2, or another object storage in a separate plan.

## CI/CD Plan

Pull request workflow:

- Install dependencies with `uv`.
- Run focused Django checks and tests.
- Verify migrations are committed.
- Build the Docker image without pushing it.

Main branch workflow:

- Run the same verification.
- Build Docker image.
- Push image to GHCR with immutable commit tag and `latest`.
- Trigger Render deploy.

## Acceptance Criteria

- Local tests still pass.
- `manage.py check` passes with local settings.
- Migration dry-run reports no missing migrations.
- Docker image builds successfully.
- The Docker container can run Django checks.
- CI workflow runs tests before image push.
- Main-branch deploy workflow pushes a GHCR image and triggers Render.
- Render runtime uses `DATABASE_URL` for PostgreSQL.
- Product API behavior is unchanged.
- Deployment risks and deferred media work are documented.

## Verification Commands

Before implementation completion:

```bash
uv run pytest -q
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py check --deploy
docker build -t oshilog:local .
docker run --rm --env-file .env.example oshilog:local uv run python manage.py check
git diff --check
git status --short
```

`check --deploy` may require deployment-style environment variables. If a local
environment cannot safely provide them, record the exact skipped condition.

## Deferred Work

Deferred Refactoring Note

- Topic: Production media storage.
- Why it is not part of the current scope: The deployment build focuses on the
  app runtime, CI/CD, and PostgreSQL. Media storage has separate persistence,
  backup, URL, and access-control decisions.
- Why it may be needed later: Visit record photo uploads need durable storage
  before public usage.
- Trigger condition: Photo upload is enabled for real users outside local
  testing.
- Expected change location: `config/settings.py`, storage backend dependency,
  archive photo upload tests, deployment env docs.
- Related tests: archive photo API tests and a deployment storage smoke check.

Deferred Refactoring Note

- Topic: PostgreSQL-backed CI test job.
- Why it is not part of the current scope: Current behavior tests are database
  portable and SQLite is fast for the initial CI loop.
- Why it may be needed later: PostgreSQL-specific constraints, indexes, or SQL
  behavior may need CI coverage.
- Trigger condition: A bug or feature depends on PostgreSQL-specific behavior.
- Expected change location: `.github/workflows/`.
- Related tests: full Django test suite under a PostgreSQL service container.
