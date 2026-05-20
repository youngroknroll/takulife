# OshiLog API Backend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create the initial RESTful API backend structure for OshiLog.

**Architecture:** Start with a Django + Django REST Framework backend. The first task creates a project scaffold, an API root endpoint, health endpoint, and test setup. Domain APIs for events and drafts come next after the backend foundation is verified.

**Tech Stack:** Python, uv, Django, Django REST Framework, pytest, pytest-django, SQLite for local bootstrap, future PostgreSQL support.

---

## Approved Scope

This plan covers only the API backend foundation:

- Python project/dependency configuration through `pyproject.toml` and uv.
- Django project scaffold.
- Django REST Framework setup.
- `core` app.
- JSON API root endpoint.
- JSON health endpoint.
- Test tooling.
- Project status documentation.

This plan does not implement:

- `Event` model.
- `EventDraft` model.
- Event list/detail endpoints.
- Draft creation endpoints.
- Admin approval workflow.
- URL fetching, SSRF protection, or extraction.
- Authentication/authorization beyond Django defaults.

## Acceptance Criteria

- `GET /api/` returns HTTP 200 JSON containing the API name.
- `GET /api/health/` returns HTTP 200 JSON with `status: ok`.
- `python manage.py check` exits successfully.
- `python -m pytest -q` exits successfully.
- The scaffold leaves clear app boundaries for future `events` and `drafts` apps.

## Task 1: Dependencies And Test Config

**Files:**
- Create or modify: `pyproject.toml`
- Create or modify: `pytest.ini`

**Step 1: Add dependencies**

```toml
[project]
dependencies = [
    "beautifulsoup4>=4.12,<5.0",
    "django>=5.2,<6.0",
    "djangorestframework>=3.15,<4.0",
    "httpx>=0.27,<1.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0,<9.0",
    "pytest-django>=4.8,<5.0",
]
```

**Step 2: Add pytest config**

```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = tests.py test_*.py *_tests.py
```

**Step 3: Install dependencies**

Run:

```bash
uv sync
```

Expected:

- Dependencies install without errors.

## Task 2: First RED Test

**Files:**
- Create: `tests/test_api_bootstrap.py`

**Step 1: Write failing API behavior tests**

```python
def test_api_root_returns_product_name(client):
    response = client.get("/api/")

    assert response.status_code == 200
    assert response.json()["name"] == "OshiLog API"


def test_health_endpoint_returns_ok(client):
    response = client.get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

**Step 2: Run tests to verify RED**

Run:

```bash
uv run pytest -q tests/test_api_bootstrap.py
```

Expected:

- FAIL because Django project settings, URL routes, or views are not implemented yet.

## Task 3: Minimal Django REST Scaffold

**Files:**
- Create: `manage.py`
- Create: `config/__init__.py`
- Create: `config/settings.py`
- Create: `config/urls.py`
- Create: `config/asgi.py`
- Create: `config/wsgi.py`
- Create: `core/__init__.py`
- Create: `core/apps.py`
- Create: `core/views.py`
- Create: `core/urls.py`

**Step 1: Create minimal Django project**

Use package name `config`.

Minimum settings:

- `INSTALLED_APPS` includes Django defaults, `rest_framework`, and `core`.
- SQLite local database.
- `ROOT_URLCONF = "config.urls"`.
- `DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"`.
- `LANGUAGE_CODE = "ko-kr"`.
- `TIME_ZONE = "Asia/Seoul"`.

**Step 2: Create DRF function views**

`core.views` should expose:

- `api_root`: returns `{"name": "OshiLog API"}`.
- `health`: returns `{"status": "ok"}`.

**Step 3: Wire URLs**

- `/api/` maps to `api_root`.
- `/api/health/` maps to `health`.
- `/admin/` maps to Django admin.

**Step 4: Run tests to verify GREEN**

Run:

```bash
uv run pytest -q tests/test_api_bootstrap.py
```

Expected:

- PASS.

## Task 4: Verification And Status Documentation

**Files:**
- Create or modify: `docs/project-status.md`

**Step 1: Run verification**

```bash
uv run python manage.py check
uv run pytest -q
```

Expected:

- Both commands pass.

**Step 2: Update project status**

Document:

- Current completed task.
- Verification commands and results.
- Deferred work: events API, drafts API, admin approval workflow, auth.
- Links to planning documents.

## Deferred Work

Deferred Refactoring Note

- Topic: Split settings for local and production.
- Why it is not part of the current scope: API bootstrap only needs local settings.
- Why it may be needed later: Render deployment, PostgreSQL, CORS, and production secrets require separate settings.
- Trigger condition: Before deployment configuration or production database integration.
- Expected change location: `config/settings.py` or `config/settings/`.
- Related tests: `python manage.py check`, API bootstrap tests.
