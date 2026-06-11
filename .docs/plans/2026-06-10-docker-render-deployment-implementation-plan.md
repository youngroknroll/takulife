# Docker Render Deployment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Dockerized Render deployment path with GitHub Actions CI/CD,
GHCR image publishing, and Render PostgreSQL configuration.

**Architecture:** Keep product code unchanged and place deployment behavior at
the project edge. `config/settings.py` reads environment variables for
production settings, Docker packages the Django app, GitHub Actions verifies and
publishes the image, and Render hosts the container with managed PostgreSQL.

**Tech Stack:** Django, Django REST Framework, uv, Gunicorn, WhiteNoise,
dj-database-url, psycopg, Docker, GitHub Actions, GHCR, Render PostgreSQL

---

## Required Reading

Read these files before editing:

- `AGENTS.md`
- `.docs/plans/2026-06-10-docker-render-deployment-design.md`
- `.docs/plans/2026-05-20-oshilog-mvp-planning.md`
- `.docs/plans/2026-06-09-personal-archive-remaining-api-design.md`
- `config/settings.py`
- `pyproject.toml`

## Approved Scope

In scope:

- Add deployment dependencies.
- Add production-safe settings env parsing.
- Add Docker runtime files.
- Add GitHub Actions CI and Docker publish workflows.
- Add Render deployment configuration or documentation.
- Add focused tests for settings behavior where practical.
- Add deployment work log and update `.docs/project-status.md`.

Out of scope:

- Changing application API behavior.
- Changing frontend templates or mock pages.
- Running PostgreSQL inside Docker for production.
- EC2 deployment.
- Object storage or persistent media storage integration.
- Celery, workers, schedulers, blue-green deployment, or Kubernetes.

## Acceptance Criteria

- `uv run pytest -q` passes.
- `uv run python manage.py check` passes.
- `uv run python manage.py makemigrations --check --dry-run` passes.
- Docker image builds locally.
- A containerized Django check can run with deployment-like environment values.
- CI workflow runs tests and migration checks.
- Docker workflow builds on PR without pushing.
- Main branch workflow can push to GHCR and trigger Render.
- Product domain apps do not import deployment modules.
- `.docs/project-status.md` and a refactoring work log record verified,
  unverified, and deferred items.

## Domain Boundary And Dependency Direction

Deployment boundary:

- `Dockerfile`, `.dockerignore`, `.github/workflows/`, and Render config own
  runtime and CI/CD behavior.
- `config/settings.py` owns environment parsing and Django deployment settings.

Product boundaries:

- `accounts`, `events`, `drafts`, `archive`, and `core` must not import Docker,
  Render, GitHub Actions, or deployment helper code.
- Product serializers, services, views, models, and templates must not change
  unless a failing test proves a deployment-related bug inside the approved
  scope.

Allowed dependencies:

- `config/settings.py` may depend on `os`, `pathlib`, `dj_database_url`, and
  Django setting names.
- Docker and GitHub Actions may call Django management commands.

Avoided dependencies:

- No domain app imports from deployment files.
- No migration execution inside `config.wsgi`.
- No database or network calls at settings import time beyond parsing env vars.

Business logic placement:

- No product business logic is introduced.
- Settings parsing helpers stay in `config/settings.py` unless they become
  large enough to justify a separate tested module.

## Coupling And Cohesion Review

This plan keeps deployment concerns cohesive by grouping runtime packaging,
CI/CD, and Render configuration in deployment files. It avoids coupling domain
apps to infrastructure by using Django settings as the only runtime interface.

Remaining coupling:

- `config/settings.py` will support both local and production behavior. This is
  accepted for the first deployment build and documented as deferred if it
  becomes hard to review.

## Pythonic Code Design

- Add small explicit helpers such as `env_bool(name, default=False)` and
  `env_list(name, default=None)`.
- Use `dj_database_url.config(default=...)` instead of hand-parsing
  PostgreSQL URLs.
- Use Django's standard `STATIC_ROOT`, `MEDIA_ROOT`, and security settings.
- Keep default local behavior readable and unsurprising.
- Avoid broad settings frameworks or hidden side effects.

## TDD Strategy

Deployment code has fewer pure behavior seams than API code, but settings
behavior can still be covered before production changes.

Required TDD order:

1. Add the smallest failing settings test for an environment parsing behavior.
2. Verify it fails for the expected reason.
3. Implement the minimal settings helper or setting change.
4. Verify the test passes.
5. Add the next behavior test only after green.
6. Add Docker and workflow files after settings behavior is covered.

## Task 1: Settings Env Parsing

**Files:**

- Modify: `config/settings.py`
- Create or modify: `tests/test_deployment_settings.py`

**Step 1: Write failing test for boolean parsing**

Create `tests/test_deployment_settings.py` with a small helper import test. Use
`pytest.monkeypatch` and reload the settings module carefully.

Expected behavior:

- `DEBUG=False` env value is parsed as `False`.
- `DEBUG=True` env value is parsed as `True`.

**Step 2: Run the failing test**

Run:

```bash
uv run pytest -q tests/test_deployment_settings.py
```

Expected: fail because `DEBUG` is currently hard-coded to `True`.

**Step 3: Implement minimal boolean env helper**

In `config/settings.py`, add an explicit helper:

```python
def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
```

Set:

```python
DEBUG = env_bool("DEBUG", default=True)
```

**Step 4: Verify green**

Run:

```bash
uv run pytest -q tests/test_deployment_settings.py
```

Expected: pass.

**Step 5: Task review**

Confirm:

- No product app changed.
- Settings behavior remains local-friendly.
- Test verifies observable settings behavior, not private implementation only.

## Task 2: Hosts, CSRF, And Security Env Settings

**Files:**

- Modify: `config/settings.py`
- Modify: `tests/test_deployment_settings.py`

**Step 1: Write failing tests for comma-list parsing**

Expected behavior:

- `ALLOWED_HOSTS=example.com,.onrender.com` becomes
  `["example.com", ".onrender.com"]`.
- `CSRF_TRUSTED_ORIGINS=https://example.com` becomes
  `["https://example.com"]`.
- Empty env values are ignored.

**Step 2: Run failing test**

Run:

```bash
uv run pytest -q tests/test_deployment_settings.py
```

Expected: fail because `ALLOWED_HOSTS` is currently `[]` and no CSRF setting is
defined.

**Step 3: Implement minimal list helper and settings**

Add:

```python
def env_list(name, default=None):
    value = os.environ.get(name)
    if value is None:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]
```

Set:

```python
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", default=False)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", default=False)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", default=False)
```

**Step 4: Verify green**

Run:

```bash
uv run pytest -q tests/test_deployment_settings.py
```

Expected: pass.

## Task 3: PostgreSQL And Static Runtime Dependencies

**Files:**

- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `config/settings.py`
- Modify: `tests/test_deployment_settings.py`

**Step 1: Write failing database-url test**

Expected behavior:

- Without `DATABASE_URL`, default database remains SQLite.
- With a PostgreSQL `DATABASE_URL`, settings use the PostgreSQL engine.

**Step 2: Run failing test**

Run:

```bash
uv run pytest -q tests/test_deployment_settings.py
```

Expected: fail because `DATABASE_URL` is ignored.

**Step 3: Add dependencies**

Run:

```bash
uv add gunicorn whitenoise dj-database-url "psycopg[binary]"
```

Expected: `pyproject.toml` and `uv.lock` update.

**Step 4: Implement database and static settings**

- Import `dj_database_url`.
- Use SQLite default when `DATABASE_URL` is absent.
- Use `dj_database_url.config()` when present.
- Add WhiteNoise middleware after `SecurityMiddleware`.
- Add `STATIC_ROOT = BASE_DIR / "staticfiles"`.
- Add `MEDIA_URL = "media/"`.
- Add `MEDIA_ROOT = BASE_DIR / "media"`.

**Step 5: Verify green**

Run:

```bash
uv run pytest -q tests/test_deployment_settings.py
uv run python manage.py check
```

Expected: both pass.

## Task 4: Docker Runtime

**Files:**

- Create: `Dockerfile`
- Create: `.dockerignore`
- Modify: `.env.example`

**Step 1: Add Dockerfile**

Requirements:

- Python 3.13 base image.
- Install `uv`.
- Copy dependency metadata first.
- Run `uv sync --frozen --no-dev`.
- Copy app source.
- Run `collectstatic --noinput` only if required environment values are safe,
  or document why collection is run at deploy time instead.
- Use non-root user if feasible.
- Expose no hard-coded port assumptions beyond Render `$PORT`.
- Default command:

```bash
uv run gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000}
```

**Step 2: Add .dockerignore**

Exclude:

- `.git`
- `.venv`
- `.pytest_cache`
- `__pycache__`
- `db.sqlite3`
- `.env`
- `.env.*`
- `.worktrees`
- `.docs` unless deployment docs are intentionally copied

**Step 3: Update .env.example**

Add documented placeholders for:

- `DEBUG`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `DATABASE_URL`
- `SECURE_SSL_REDIRECT`
- `SESSION_COOKIE_SECURE`
- `CSRF_COOKIE_SECURE`

**Step 4: Build image**

Run:

```bash
docker build -t oshilog:local .
```

Expected: image builds successfully.

**Step 5: Run containerized check**

Run:

```bash
docker run --rm \
  -e SECRET_KEY=test-secret \
  -e DEBUG=False \
  -e ALLOWED_HOSTS=localhost,127.0.0.1 \
  oshilog:local \
  uv run python manage.py check
```

Expected: Django check passes.

## Task 5: GitHub Actions CI

**Files:**

- Create: `.github/workflows/ci.yml`

**Step 1: Add CI workflow**

Workflow behavior:

- Trigger on pull requests and pushes to `main`.
- Set up Python 3.13.
- Install `uv`.
- Run `uv sync --frozen`.
- Run:

```bash
uv run pytest -q
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

**Step 2: Validate workflow syntax locally if possible**

Run a lightweight YAML or action lint command only if tooling already exists.
Otherwise record syntax as not locally verified.

**Step 3: Run local equivalent**

Run:

```bash
uv run pytest -q
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

Expected: all pass.

## Task 6: Docker Build And Publish Workflow

**Files:**

- Create: `.github/workflows/docker.yml`

**Step 1: Add workflow**

Workflow behavior:

- On pull request: build image only.
- On push to `main`: build and push to GHCR.
- Use `docker/setup-buildx-action`.
- Use `docker/login-action` for GHCR only on push.
- Use `docker/metadata-action` for tags.
- Use `docker/build-push-action`.
- Tags include commit SHA and `latest` for main.

**Step 2: Add required permissions**

Set:

```yaml
permissions:
  contents: read
  packages: write
```

**Step 3: Verify Docker build locally**

Run:

```bash
docker build -t oshilog:local .
```

Expected: pass.

## Task 7: Render Deployment Configuration

**Files:**

- Create or modify: `render.yaml`
- Modify: `.docs/plans/2026-06-10-docker-render-deployment-design.md` if exact
  Render settings need clarification.

**Step 1: Add Render blueprint or deployment notes**

Prefer `render.yaml` when it can accurately represent:

- Docker Web Service.
- Render PostgreSQL database.
- Environment variables that are safe to define in source.
- Secret placeholders that must be configured in Render dashboard.
- Pre-deploy migration command.

If Render blueprint cannot safely represent GHCR/private image behavior, create
documented manual Render settings instead and record the reason.

**Step 2: Define migration policy**

Use Render pre-deploy command when supported:

```bash
uv run python manage.py migrate --noinput
```

Do not run migrations in the Gunicorn start command.

**Step 3: Verify local Django migration state**

Run:

```bash
uv run python manage.py makemigrations --check --dry-run
```

Expected: no changes detected.

## Task 8: Architecture Boundary Checks

**Files:**

- Modify: `tests/test_architecture_boundaries.py`

**Step 1: Add boundary test**

Add a behavior-level architecture test proving domain apps do not reference
deployment-specific terms.

Check files under:

- `accounts/`
- `events/`
- `drafts/`
- `archive/`
- `core/`

Forbidden terms:

- `render.yaml`
- `GHCR`
- `GITHUB_TOKEN`
- `DATABASE_URL`
- `gunicorn`
- `whitenoise`

Allow these terms only in `config/`, `.github/`, docs, Docker, and tests.

**Step 2: Run focused test**

Run:

```bash
uv run pytest -q tests/test_architecture_boundaries.py
```

Expected: pass.

## Task 9: Documentation And Work Log

**Files:**

- Create: `.docs/refactoring/2026-06-10-docker-render-deployment-work-log.md`
- Modify: `.docs/project-status.md`

**Step 1: Create work log**

Record:

- What changed.
- What was verified.
- What was not verified.
- Deferred work.
- Render/GHCR secrets required outside source control.

**Step 2: Update project status**

Include:

- Current deployment direction.
- Required reading for the next deployment task.
- Verification commands and latest results.
- Deferred media storage work.

## Final Verification

Run all commands before reporting completion:

```bash
uv run pytest -q
uv run pytest -q tests/test_architecture_boundaries.py
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py check --deploy
docker build -t oshilog:local .
docker run --rm \
  -e SECRET_KEY=test-secret \
  -e DEBUG=False \
  -e ALLOWED_HOSTS=localhost,127.0.0.1 \
  oshilog:local \
  uv run python manage.py check
git diff --check
git status --short
```

Record exact failures or skipped checks. Do not claim Docker, deploy, or GitHub
Actions success without fresh evidence.

## Commit Plan

Use small commits if implementing interactively:

1. `test(deployment): Add settings env tests`
2. `build(deployment): Add Docker runtime`
3. `ci(deployment): Add CI and image workflows`
4. `docs(deployment): Record Render deployment plan`

If the work stays small and all verification passes, a single commit is
acceptable:

```text
build(deployment): Add Docker Render runtime

- Dockerized Django runtime for Render deployment
- GitHub Actions CI and GHCR image publishing plan
- Render PostgreSQL environment configuration
- Deployment verification and deferred media storage notes
```
