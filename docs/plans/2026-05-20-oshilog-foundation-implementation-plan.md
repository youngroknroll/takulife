# OshiLog Foundation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create the initial Django project foundation for OshiLog and verify that the root page boots successfully.

**Architecture:** Start with a small Django monolith. The first structure creates `config` for project settings, a `core` app for the root page and shared utilities, and test configuration for behavior-first development. Event and draft domain apps are deferred to the next plan task after the foundation is verified.

**Tech Stack:** Python, uv, Django, pytest, pytest-django, SQLite for local bootstrap, future PostgreSQL support.

---

## Approved Scope

This plan covers only the basic project foundation:

- Python dependency files.
- Django project scaffold.
- `core` app with root page.
- Test tooling.
- One behavior test proving the root URL returns HTTP 200 and includes the OshiLog name.
- Basic project documentation updates.

This plan does not implement:

- `Event` model.
- `EventDraft` model.
- URL fetching or extraction.
- Admin approval workflow.
- Public event list/detail.
- User status, visit records, image upload, or archive pages.

## Acceptance Criteria

- `python manage.py check` exits successfully.
- `python -m pytest -q` exits successfully.
- Root URL `/` returns HTTP 200.
- Root response contains `OshiLog`.
- Project structure matches the first MVP direction in `docs/plans/2026-05-20-oshilog-mvp-planning.md`.

## Task 1: Dependency And Test Configuration

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`

**Step 1: Create dependency file**

Add minimal dependencies:

```text
Django>=5.2,<6.0
pytest>=8.0,<9.0
pytest-django>=4.8,<5.0
beautifulsoup4>=4.12,<5.0
httpx>=0.27,<1.0
```

**Step 2: Create pytest configuration**

```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = tests.py test_*.py *_tests.py
```

**Step 3: Verify dependency install**

Run:

```bash
python -m pip install -r requirements.txt
```

Expected:

- Dependencies install without errors.

## Task 2: Django Project Scaffold

**Files:**
- Create: `manage.py`
- Create: `config/__init__.py`
- Create: `config/settings.py`
- Create: `config/urls.py`
- Create: `config/asgi.py`
- Create: `config/wsgi.py`

**Step 1: Generate or create Django project files**

Use Django defaults where practical, with the project package named `config`.

**Step 2: Configure minimal settings**

Minimum settings:

- `INSTALLED_APPS` includes Django defaults and `core`.
- `ROOT_URLCONF = "config.urls"`.
- SQLite local database at `BASE_DIR / "db.sqlite3"`.
- Template discovery enabled with `templates/`.
- Static URL configured.

**Step 3: Run system check**

Run:

```bash
python manage.py check
```

Expected:

- Django system check reports no issues.

## Task 3: Core App Root Page With TDD

**Files:**
- Create: `core/__init__.py`
- Create: `core/apps.py`
- Create: `core/views.py`
- Create: `core/urls.py`
- Create: `templates/core/home.html`
- Create: `tests/test_bootstrap.py`
- Modify: `config/urls.py`

**Step 1: Write the failing test**

Create `tests/test_bootstrap.py`:

```python
import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_root_page_loads_with_product_name(client):
    response = client.get(reverse("core:home"))

    assert response.status_code == 200
    assert b"OshiLog" in response.content
```

**Step 2: Run test to verify RED**

Run:

```bash
python -m pytest -q tests/test_bootstrap.py
```

Expected:

- FAIL because `core:home` route or app does not exist yet.

**Step 3: Write minimal implementation**

Create a `core` app with:

- `CoreConfig`.
- `home` view rendering `templates/core/home.html`.
- `core.urls` exposing `name="home"`.
- `config.urls` including `core.urls` at root.
- Template containing `OshiLog`.

**Step 4: Run test to verify GREEN**

Run:

```bash
python -m pytest -q tests/test_bootstrap.py
```

Expected:

- PASS.

**Step 5: Run broader verification**

Run:

```bash
python manage.py check
python -m pytest -q
```

Expected:

- Both commands pass.

## Task 4: Status Documentation

**Files:**
- Create: `docs/project-status.md`

**Step 1: Document current status**

Include:

- Current task: foundation scaffold.
- Approved scope.
- Verification commands and results.
- Deferred work: events, drafts, admin approval workflow.
- Links to planning documents.

**Step 2: Verify docs are present**

Run:

```bash
find docs -maxdepth 3 -type f | sort
```

Expected:

- Planning document, implementation plan, and project status document are listed.

## Verification Commands

Run before reporting completion:

```bash
python manage.py check
python -m pytest -q
find docs -maxdepth 3 -type f | sort
```

## Deferred Work

Deferred Refactoring Note

- Topic: Split settings into local/production modules.
- Why it is not part of the current scope: The first foundation task only needs a working local scaffold.
- Why it may be needed later: Deployment to Render and PostgreSQL configuration will require environment-specific settings.
- Trigger condition: Before adding deployment configuration or production database settings.
- Expected change location: `config/settings/` or `config/settings.py`.
- Related tests: `python manage.py check`, deployment configuration tests if added.
