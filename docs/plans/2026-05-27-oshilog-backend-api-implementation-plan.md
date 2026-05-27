# OshiLog Backend API Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the first OshiLog REST API surface for authentication, public events, draft review, user status, and visit records.

**Architecture:** Keep Django + Django REST Framework as the backend core. Introduce a custom `accounts.User` model from the start, then add small domain apps for `events` and `drafts`, followed by user-owned record APIs. Public read APIs stay separate from admin-only review APIs, and screen-driven extension models are added only where the ERD and product screens require them.

**Tech Stack:** Python, uv, Django, Django REST Framework, pytest, pytest-django, PostgreSQL-ready schema design, session auth for Django admin and API, Google login integration planned behind a dedicated auth boundary.

---

## Approved Scope

This plan covers the first API implementation slice beyond bootstrap:

- Custom user model and auth boundary.
- Public event read APIs.
- Admin draft creation/review APIs.
- User event status APIs.
- Visit record APIs.
- Visit record photo APIs.
- API documentation and status updates.

This plan does not implement:

- Full frontend UI.
- Queue workers, search indexing, or AI extraction.
- Social login provider expansion beyond the first Google login path.
- Complex recommendation or community features.
- Production deployment hardening.

## Acceptance Criteria

- Authenticated users can be represented by a custom `accounts.User` model.
- Public users can read published events only.
- Admins can create, review, approve, and reject drafts.
- Logged-in users can store one status per event.
- Logged-in users can create visit records for published events.
- Logged-in users can attach and remove photos from visit records.
- `python manage.py check` exits successfully.
- `python -m pytest -q` exits successfully.

## Task 1: Add Auth And Account Boundary

**Files:**
- Create: `accounts/__init__.py`
- Create: `accounts/apps.py`
- Create: `accounts/models.py`
- Modify: `config/settings.py`
- Modify: `config/urls.py`
- Modify: `core/views.py` or create `core/auth_views.py`
- Test: `tests/test_auth_bootstrap.py`

**Step 1: Write the failing test**

Add a test that confirms the app exposes a current-user endpoint and uses the custom user model setting:

```python
def test_auth_me_requires_login(client):
    response = client.get("/api/auth/me/")

    assert response.status_code in (401, 403)


def test_auth_model_setting_is_custom_user(settings):
    assert settings.AUTH_USER_MODEL == "accounts.User"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_auth_bootstrap.py`

Expected: FAIL because the `accounts` app and auth endpoint are not wired yet.

**Step 3: Write minimal implementation**

- Introduce `accounts.User` extending `AbstractUser`.
- Point `AUTH_USER_MODEL` at `accounts.User`.
- Add a minimal `/api/auth/me/` endpoint returning the current user identity when authenticated.
- Keep unauthenticated access denied.

**Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/test_auth_bootstrap.py`

Expected: PASS.

## Task 2: Add Public Event Read API

**Files:**
- Create: `events/__init__.py`
- Create: `events/apps.py`
- Create: `events/models.py`
- Create: `events/serializers.py`
- Create: `events/views.py`
- Create: `events/urls.py`
- Modify: `config/settings.py`
- Modify: `config/urls.py`
- Test: `tests/test_events_api.py`

**Step 1: Write the failing test**

Add one behavior test for the list endpoint:

```python
def test_public_event_list_returns_only_published_events(client, event_factory):
    published = event_factory(publish_status="published")
    event_factory(publish_status="draft")

    response = client.get("/api/events/")

    assert response.status_code == 200
    assert len(response.json()["results"]) == 1
    assert response.json()["results"][0]["id"] == published.id
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_events_api.py`

Expected: FAIL because the `events` app and endpoint are not implemented yet.

**Step 3: Write minimal implementation**

- Add `Event` model fields from the ERD.
- Expose a paginated public list endpoint.
- Filter by `publish_status="published"`.

**Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/test_events_api.py`

Expected: PASS.

## Task 3: Add Draft Review API

**Files:**
- Create: `drafts/__init__.py`
- Create: `drafts/apps.py`
- Create: `drafts/models.py`
- Create: `drafts/serializers.py`
- Create: `drafts/views.py`
- Create: `drafts/urls.py`
- Modify: `config/settings.py`
- Modify: `config/urls.py`
- Test: `tests/test_drafts_api.py`

**Step 1: Write the failing test**

Add one behavior test that an admin can create a draft from a URL:

```python
def test_admin_can_create_event_draft_from_url(admin_client):
    response = admin_client.post("/api/admin/event-drafts/", {"source_url": "https://example.com/event"})

    assert response.status_code == 201
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_drafts_api.py`

Expected: FAIL because draft endpoints do not exist yet.

**Step 3: Write minimal implementation**

- Add `EventDraft` model fields from the ERD.
- Add admin-only create/list/review endpoints.
- Keep `source_url` unique.
- Keep approval and rejection explicit.

**Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/test_drafts_api.py`

Expected: PASS.

## Task 4: Add User Status API

**Files:**
- Create: `events/status_serializers.py` or extend `events/serializers.py`
- Create: `events/status_views.py` or extend `events/views.py`
- Create: `events/status_urls.py` or extend `events/urls.py`
- Test: `tests/test_user_event_status_api.py`

**Step 1: Write the failing test**

Add one behavior test that a logged-in user can upsert a status:

```python
def test_logged_in_user_can_upsert_event_status(client, user, event):
    client.force_login(user)

    response = client.put(f"/api/me/event-statuses/{event.id}/", {"status": "interested"}, content_type="application/json")

    assert response.status_code in (200, 201)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_user_event_status_api.py`

Expected: FAIL because the model and route are not implemented yet.

**Step 3: Write minimal implementation**

- Add `UserEventStatus` model.
- Restrict to authenticated users.
- Make upsert idempotent.

**Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/test_user_event_status_api.py`

Expected: PASS.

## Task 5: Add Visit Record And Photo APIs

**Files:**
- Create: `events/visit_serializers.py` or extend `events/serializers.py`
- Create: `events/visit_views.py` or extend `events/views.py`
- Create: `events/visit_urls.py` or extend `events/urls.py`
- Test: `tests/test_visit_records_api.py`

**Step 1: Write the failing test**

Add one behavior test for record creation:

```python
def test_logged_in_user_can_create_visit_record(client, user, published_event):
    client.force_login(user)

    response = client.post(
        "/api/me/visit-records/",
        {"event": published_event.id, "visited_on": "2026-05-26", "short_review": "good"},
        content_type="application/json",
    )

    assert response.status_code == 201
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_visit_records_api.py`

Expected: FAIL because visit record endpoints do not exist yet.

**Step 3: Write minimal implementation**

- Add `VisitRecord` and `VisitRecordPhoto` models.
- Restrict creation and editing to the owner.
- Allow photos only through direct user upload on a visit record.

**Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/test_visit_records_api.py`

Expected: PASS.

## Task 6: Verification And Status Docs

**Files:**
- Modify: `docs/project-status.md`
- Modify: `docs/refactoring/2026-05-20-api-foundation-work-log.md` or add a new refactoring note

**Step 1: Run verification**

Run:

```bash
uv run python manage.py check
uv run pytest -q
```

Expected:

- Both commands pass.

**Step 2: Update documentation**

- Record what was implemented.
- Record what remains deferred.
- Link the new auth/API planning documents.

## Deferred Work

Deferred Refactoring Note

- Topic: Expand Google login into additional providers and optional account linking.
- Why it is not part of the current scope: Google login is enough for the first member onboarding path.
- Why it may be needed later: Some users may prefer Apple, Kakao, email-only, or linked accounts.
- Trigger condition: When member demand or regional expansion requires alternate providers.
- Expected change location: `accounts` app and auth API layer.
- Related tests: login flow, current-user endpoint, duplicate account prevention, and provider-linking tests.

