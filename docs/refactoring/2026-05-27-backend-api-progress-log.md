# Backend API Progress Log

Date: 2026-05-27

## Scope

This work implemented the first backend API slice beyond bootstrap.

Included:

- Custom user model with `AUTH_USER_MODEL = "accounts.User"`.
- Current-user endpoint: `GET /api/auth/me/`.
- Public published-event list endpoint: `GET /api/events/`.
- Admin event draft create/list endpoint: `GET/POST /api/admin/event-drafts/`.
- User event status upsert endpoint: `PUT /api/me/event-statuses/<event_id>/`.
- Visit record create endpoint: `POST /api/me/visit-records/`.
- Visit record photo create/delete endpoints.
- Regression tests for auth, events, drafts, event status, and visit record flows.
- Project status update for the current API slice.

Not included:

- Admin draft approve/reject endpoints.
- Google login implementation.
- URL fetch and extraction pipeline.
- Duplicate draft/event checks beyond unique `source_url`.
- PostgreSQL deployment settings or production hardening.

## Files Changed

- `accounts/__init__.py`
- `accounts/apps.py`
- `accounts/models.py`
- `config/settings.py`
- `config/urls.py`
- `core/auth_views.py`
- `core/urls.py`
- `docs/project-status.md`
- `drafts/__init__.py`
- `drafts/apps.py`
- `drafts/models.py`
- `drafts/serializers.py`
- `drafts/urls.py`
- `drafts/views.py`
- `events/__init__.py`
- `events/apps.py`
- `events/models.py`
- `events/serializers.py`
- `events/status_urls.py`
- `events/urls.py`
- `events/views.py`
- `tests/test_auth_bootstrap.py`
- `tests/test_drafts_api.py`
- `tests/test_events_api.py`
- `tests/test_user_event_status_api.py`
- `tests/test_visit_records_api.py`

## Verification

Fresh verification for this work:

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

## Risks And Notes

- The event and draft models are intentionally minimal and do not yet cover the full ERD.
- `GET /api/auth/me/` now depends only on `request.user`, which improves boundary separation from the persistence layer.
- Public and user-owned APIs are separated at the URL layer: `/api/events/`, `/api/admin/`, and `/api/me/`.
- Visit record photo endpoints were verified by tests after the initial implementation already existed, so that part of the batch did not follow strict red-green order.

## Deferred Refactoring Note

- Topic: Introduce serializers or service-layer validation for visit record photo workflows and richer draft review transitions.
- Why it is not part of the current scope: The approved scope only required the first usable API surface with minimal implementation.
- Why it may be needed later: More complex validation, moderation state changes, and file handling rules will make inline view logic harder to maintain safely.
- Trigger condition: When draft approval rules or visit photo constraints expand beyond the current simple owner-only flow.
- Expected change location: `drafts/views.py`, `events/views.py`, and related serializers.
- Related tests: `uv run pytest -q`, targeted API tests for drafts, statuses, and visit records.
