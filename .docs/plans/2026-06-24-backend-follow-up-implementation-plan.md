# Backend Follow-up Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Apply the safe, contract-preserving backend follow-up changes identified by the June 24 review while keeping schema churn and speculative refactors out of scope.

**Architecture:** Keep published catalog rules in `events`, fetch and review workflow rules in `drafts`, and active user-owned status rules in `archive`. Improve safety and maintainability by tightening service boundaries, making draft fetches validate the full request path, and characterizing current public query behavior instead of redesigning it.

**Tech Stack:** Django, Django REST Framework, httpx, pytest, SQLite-backed local tests

---

## Scope

In scope:

- Preserve all active endpoint URLs, payload fields, and status codes.
- Preserve the current schema and migration state.
- Characterize and protect current public event query behavior.
- Route published-only query intent through `Event.objects.published()` where
  active code still repeats the filter directly.
- Refactor `archive.services.create_user_event_status()` to accept explicit
  domain inputs instead of a serializer object.
- Harden draft fetch safety for redirect targets, resolved IPs, and oversized
  bodies.
- Map duplicate draft creation races into the existing controlled error
  contract.
- Add service-level draft field allowlist enforcement.
- Expand focused tests and architecture boundary tests.
- Update `.docs/project-status.md` and write a refactoring work log after the
  implementation slice is complete.

Out of scope:

- Removing legacy archive models/views from `events`.
- New endpoints or query parameters.
- Search/index tuning.
- Global error-framework refactors.
- Queue-based or asynchronous fetch processing.

## Acceptance Criteria

- `GET /api/events/` and `GET /api/events/{id}/` keep current behavior and add
  explicit tests for the currently implicit policies.
- Active archive status endpoints keep current status codes and response bodies.
- `create_user_event_status()` no longer depends on a DRF serializer object.
- Any active code that needs published-only events uses
  `Event.objects.published()` unless a documented exception remains.
- Draft create requests reject unsafe redirect targets and unsafe resolved
  addresses with the existing unsafe-URL contract.
- Draft create requests stop reading bodies past `MAX_RESPONSE_BYTES`.
- Concurrent duplicate draft creates are mapped into the same controlled
  duplicate field error contract as ordinary duplicates.
- `update_draft()` rejects immutable-field updates even when called directly.
- No migrations are generated.
- Focused tests, full pytest, Django check, and migration drift check pass.

## Domain Boundary And Dependency Direction

Events:

- Owns published event visibility, public filters, public ordering, and
  publication of approved drafts.
- Must not import `archive`.

Drafts:

- Owns fetch safety, extraction, draft state transitions, and publication
  orchestration.
- May depend on `events.services`.
- Must not import `archive`.

Archive:

- Owns active user status writes and owner scoping.
- May depend on `events.models.Event` for published-event validation.
- Must not import `drafts`.

Core:

- Owns only domain-agnostic response helpers.

Business logic placement:

- `events.querysets`: published/public query intent.
- `drafts.url_safety` and `drafts.fetching`: request-path fetch validation.
- `drafts.services`: draft state rules and exception mapping.
- `archive.services`: duplicate mapping and archive transaction boundaries.
- `tests/*`: behavior and boundary characterization only, not implementation
  detail assertions.

## Coupling And Cohesion Review

This plan reduces coupling by:

- removing serializer-object dependence from archive services;
- reusing the event domain's published query intent instead of repeating
  `publish_status` filters;
- keeping draft fetch safety inside the drafts domain rather than scattering it
  across views and serializers.

This plan improves cohesion by:

- making drafts own more of their state and fetch invariants directly;
- keeping active archive writes small and explicit;
- preserving `events` as the single owner of public catalog query behavior.

Deferred remaining coupling:

- legacy inactive archive code remains in `events` until a separate migration
  slice is approved.

## Pythonic Code Design

- Prefer explicit kwargs to serializer-object service contracts.
- Prefer small named helper functions over frameworks or hook-heavy indirection.
- Use Django `QuerySet` methods for reusable query intent.
- Keep DRF serializers responsible for request parsing and field validation.
- Keep service functions responsible for transaction boundaries and domain error
  mapping.
- Use characterization tests when preserving a contract is the primary goal.

## Verification Commands

Run these during the plan:

```bash
uv run pytest -q tests/test_events_api.py
uv run pytest -q tests/test_events_services.py
uv run pytest -q tests/test_drafts_api.py
uv run pytest -q tests/test_drafts_services.py
uv run pytest -q tests/test_user_event_status_api.py
uv run pytest -q tests/test_architecture_boundaries.py
uv run pytest -q
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

## Task 1: Establish The Green Baseline

**Files:**

- Read: `AGENTS.md`
- Read: `.docs/plans/2026-06-24-backend-follow-up-design.md`
- Read: `.docs/project-status.md`
- Test: `tests/test_events_api.py`
- Test: `tests/test_events_services.py`
- Test: `tests/test_drafts_api.py`
- Test: `tests/test_drafts_services.py`
- Test: `tests/test_user_event_status_api.py`
- Test: `tests/test_architecture_boundaries.py`

**Step 1: Confirm worktree scope**

Run:

```bash
git status --short --branch
```

Expected: only the approved documentation changes are present before production
edits begin.

**Step 2: Run focused regression suite**

Run:

```bash
uv run pytest -q tests/test_events_api.py tests/test_events_services.py tests/test_drafts_api.py tests/test_drafts_services.py tests/test_user_event_status_api.py tests/test_architecture_boundaries.py
```

Expected: pass.

**Step 3: Run full baseline suite**

Run:

```bash
uv run pytest -q
```

Expected: all tests pass. Record the exact count.

**Step 4: Commit nothing yet**

Do not change production code until the focused and full baselines are green.

## Task 2: Characterize Current Public Event Query Policies

**Files:**

- Modify: `tests/test_events_api.py`
- Modify: `events/views.py` only if a small compatibility-preserving cleanup is
  required by the tests

**Step 1: Write a failing reversed-range characterization test**

Add:

```python
@pytest.mark.django_db
def test_public_event_list_reversed_start_date_range_returns_empty_results(client):
    Event.objects.create(
        title="June event",
        start_date="2026-06-10",
        publish_status=Event.PublishStatus.PUBLISHED,
    )

    response = client.get(
        "/api/events/",
        {"start_date_from": "2026-06-30", "start_date_to": "2026-06-01"},
    )

    assert response.status_code == 200
    assert response.json()["results"] == []
```

**Step 2: Run the single test**

Run:

```bash
uv run pytest -q tests/test_events_api.py::test_public_event_list_reversed_start_date_range_returns_empty_results
```

Expected: pass if current behavior already matches. If it fails, stop and
diagnose before changing production code.

**Step 3: Write a null-date ordering characterization test**

Add:

```python
@pytest.mark.django_db
def test_public_event_list_places_null_date_events_after_ranked_events(client):
```

Expected behavior:

- ongoing, upcoming, and ended events appear before a published event with both
  dates unset.

**Step 4: Run event API suite**

Run:

```bash
uv run pytest -q tests/test_events_api.py
```

Expected: pass.

**Step 5: Commit**

```bash
git add tests/test_events_api.py
git commit -m "test(events): Characterize public query policies"
```

## Task 3: Route Published-Only Query Intent Through The Events Domain

**Files:**

- Modify: `archive/serializers.py`
- Modify: `events/views.py`
- Modify: `tests/test_user_event_status_api.py`
- Modify: `tests/test_architecture_boundaries.py`

**Step 1: Write a narrow regression test for archive published-event validation**

Add:

```python
@pytest.mark.django_db
def test_user_event_status_create_accepts_published_event_via_events_queryset(client, django_user_model):
```

The behavior stays the same. The test exists to protect the contract while the
query path is cleaned up.

**Step 2: Run the single archive test**

Run:

```bash
uv run pytest -q tests/test_user_event_status_api.py::test_user_event_status_create_accepts_published_event_via_events_queryset
```

Expected: pass or fail only due to the new assertion setup.

**Step 3: Replace direct published filters in active code**

Implement the smallest cleanup:

- in `archive/serializers.py`, use `Event.objects.published()` for the
  `PrimaryKeyRelatedField` queryset;
- in legacy inactive `events.views`, replace direct published filters with
  `Event.objects.published()` where they still exist.

Do not change route mounting or legacy activation state.

**Step 4: Run focused suites**

Run:

```bash
uv run pytest -q tests/test_user_event_status_api.py tests/test_events_api.py tests/test_architecture_boundaries.py
```

Expected: pass.

**Step 5: Commit**

```bash
git add archive/serializers.py events/views.py tests/test_user_event_status_api.py tests/test_architecture_boundaries.py
git commit -m "refactor(events): Reuse published query intent"
```

## Task 4: Remove Serializer-Object Coupling From Archive Services

**Files:**

- Modify: `archive/services.py`
- Modify: `archive/views.py`
- Modify: `tests/test_user_event_status_api.py`

**Step 1: Write a failing service-level test for explicit inputs**

Add:

```python
@pytest.mark.django_db
def test_create_user_event_status_accepts_explicit_domain_inputs(django_user_model):
    user = django_user_model.objects.create_user(username="status-user", password="secret")
    event = Event.objects.create(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    created = create_user_event_status(user=user, event=event, status="interested")

    assert created.user_id == user.id
    assert created.event_id == event.id
    assert created.status == "interested"
```

**Step 2: Run the failing test**

Run:

```bash
uv run pytest -q tests/test_user_event_status_api.py::test_create_user_event_status_accepts_explicit_domain_inputs
```

Expected: fail because the service still expects a serializer object.

**Step 3: Implement the minimal signature change**

Change:

- `archive.services.create_user_event_status(*, user, event, status)`
- `archive.views.UserEventStatusListCreateView.create()` passes explicit
  validated values

Preserve the duplicate `409` response body unchanged.

**Step 4: Run the archive suite**

Run:

```bash
uv run pytest -q tests/test_user_event_status_api.py
```

Expected: pass.

**Step 5: Commit**

```bash
git add archive/services.py archive/views.py tests/test_user_event_status_api.py
git commit -m "refactor(archive): Use explicit service inputs"
```

## Task 5: Harden Draft Fetch Target Validation

**Files:**

- Modify: `drafts/url_safety.py`
- Modify: `drafts/fetching.py`
- Modify: `drafts/services.py`
- Modify: `tests/test_drafts_services.py`
- Modify: `tests/test_drafts_api.py`

**Step 1: Write a failing unsafe-redirect service test**

Add a focused test that simulates:

- an initial safe public URL;
- a redirect to `http://127.0.0.1/...` or `http://localhost/...`;
- expected result: the create flow raises the same unsafe-URL domain error path
  used for direct unsafe URLs.

**Step 2: Run the single failing test**

Run:

```bash
uv run pytest -q tests/test_drafts_services.py::test_create_draft_from_url_rejects_unsafe_redirect_target
```

Expected: fail because redirects are currently followed automatically.

**Step 3: Implement manual redirect handling**

Implement the smallest explicit flow:

- fetch with `follow_redirects=False`;
- inspect redirect responses manually;
- resolve relative `Location` headers into absolute URLs;
- re-run scheme, hostname, and resolved-IP validation on every hop;
- stop after `MAX_REDIRECTS`.

Keep the final public exception mapping unchanged at the API layer.

**Step 4: Add a resolved-IP validation test**

Add a unit-level test for `validate_fetch_url()` or its new helper that rejects
hostnames resolving to private or loopback IPs.

**Step 5: Run draft-focused suites**

Run:

```bash
uv run pytest -q tests/test_drafts_services.py tests/test_drafts_api.py
```

Expected: pass.

**Step 6: Commit**

```bash
git add drafts/url_safety.py drafts/fetching.py drafts/services.py tests/test_drafts_services.py tests/test_drafts_api.py
git commit -m "fix(drafts): Validate redirect fetch targets"
```

## Task 6: Enforce Draft Response Size Before Full Download

**Files:**

- Modify: `drafts/fetching.py`
- Modify: `tests/test_drafts_services.py`

**Step 1: Write a failing oversized-response test**

Add a test that simulates a response body exceeding `MAX_RESPONSE_BYTES` before
the full content is read.

Expected behavior:

- the fetch layer raises `ResponseTooLargeError`;
- the service layer maps it into the existing controlled draft create error.

**Step 2: Run the single failing test**

Run:

```bash
uv run pytest -q tests/test_drafts_services.py::test_create_draft_from_url_rejects_oversized_response_before_full_read
```

Expected: fail because the current code checks size only after full download.

**Step 3: Implement streaming size enforcement**

Use a streaming read path that:

- reads chunks;
- tracks cumulative bytes;
- aborts immediately on limit breach;
- decodes text only after size remains valid.

Do not change the configured byte limit or accepted content types.

**Step 4: Run the drafts service suite**

Run:

```bash
uv run pytest -q tests/test_drafts_services.py
```

Expected: pass.

**Step 5: Commit**

```bash
git add drafts/fetching.py tests/test_drafts_services.py
git commit -m "fix(drafts): Stream response size checks"
```

## Task 7: Add Draft Duplicate-Race Mapping

**Files:**

- Modify: `drafts/services.py`
- Modify: `drafts/views.py`
- Modify: `tests/test_drafts_services.py`
- Modify: `tests/test_drafts_api.py`

**Step 1: Write a failing service test for duplicate create race**

Add a test that simulates `EventDraft.objects.create()` raising
`IntegrityError("duplicate")`.

Expected behavior:

- the service raises a draft-domain duplicate creation exception;
- the API maps it to the same field-keyed `source_url` `400` contract used for
  ordinary duplicate input.

**Step 2: Run the single failing test**

Run:

```bash
uv run pytest -q tests/test_drafts_services.py::test_create_draft_from_url_maps_duplicate_create_race
```

Expected: fail because the current create path does not map the race.

**Step 3: Implement the minimal race mapping**

- catch `IntegrityError` around `EventDraft.objects.create(...)`;
- raise a draft-domain duplicate creation exception;
- map it in `drafts.views.AdminEventDraftListCreateView.create()` to the
  existing field-keyed duplicate response contract.

**Step 4: Run draft suites**

Run:

```bash
uv run pytest -q tests/test_drafts_services.py tests/test_drafts_api.py
```

Expected: pass.

**Step 5: Commit**

```bash
git add drafts/services.py drafts/views.py tests/test_drafts_services.py tests/test_drafts_api.py
git commit -m "fix(drafts): Map duplicate draft create races"
```

## Task 8: Make Draft Update Rules Self-Defensive

**Files:**

- Modify: `drafts/services.py`
- Modify: `tests/test_drafts_services.py`

**Step 1: Write a failing direct-service misuse test**

Add:

```python
@pytest.mark.django_db
def test_update_draft_rejects_immutable_fields_even_without_serializer():
    draft = EventDraft.objects.create(source_url="https://example.com/event")

    with pytest.raises(Exception):
        update_draft(draft.id, {"review_status": EventDraft.ReviewStatus.APPROVED})
```

Replace `Exception` with the specific new domain exception chosen for immutable
field misuse.

**Step 2: Run the failing test**

Run:

```bash
uv run pytest -q tests/test_drafts_services.py::test_update_draft_rejects_immutable_fields_even_without_serializer
```

Expected: fail because the current service accepts the field.

**Step 3: Implement a service-level mutable-field allowlist**

- define explicit allowed update fields inside `drafts.services`;
- reject any field outside the allowlist before mutation;
- preserve the existing API-level serializer validation behavior.

**Step 4: Run draft service and API suites**

Run:

```bash
uv run pytest -q tests/test_drafts_services.py tests/test_drafts_api.py
```

Expected: pass.

**Step 5: Commit**

```bash
git add drafts/services.py tests/test_drafts_services.py
git commit -m "refactor(drafts): Enforce mutable review fields"
```

## Task 9: Expand Boundary And Service Contract Tests

**Files:**

- Modify: `tests/test_architecture_boundaries.py`
- Modify: `tests/test_events_services.py`

**Step 1: Write a failing events service duplicate test**

Add:

```python
@pytest.mark.django_db
def test_create_published_event_maps_duplicate_url_to_domain_error():
```

Expected behavior:

- pre-existing event with the same `official_url`;
- service raises `DuplicateOfficialUrlError`.

**Step 2: Write a failing unexpected-error mapping test**

Add:

```python
@pytest.mark.django_db
def test_create_published_event_maps_unexpected_error_to_publish_event_error(monkeypatch):
```

Expected behavior:

- low-level create failure maps to `PublishEventError`.

**Step 3: Expand import boundary coverage**

Add AST coverage for:

- `events/querysets.py`
- `events/services.py`

Keep the same rule: active `events` and `drafts` code must not import
`archive`.

**Step 4: Run focused suites**

Run:

```bash
uv run pytest -q tests/test_events_services.py tests/test_architecture_boundaries.py
```

Expected: pass.

**Step 5: Commit**

```bash
git add tests/test_events_services.py tests/test_architecture_boundaries.py
git commit -m "test(core): Strengthen boundary and service checks"
```

## Task 10: Final Verification And Documentation

**Files:**

- Modify: `.docs/project-status.md`
- Create: `.docs/refactoring/2026-06-24-backend-follow-up-work-log.md`

**Step 1: Run focused final regression**

Run:

```bash
uv run pytest -q tests/test_events_api.py tests/test_events_services.py tests/test_drafts_api.py tests/test_drafts_services.py tests/test_user_event_status_api.py tests/test_architecture_boundaries.py
```

Expected: pass.

**Step 2: Run full verification**

Run:

```bash
uv run pytest -q
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

Expected:

- full suite passes;
- Django check passes;
- no migration drift detected.

**Step 3: Write the work log**

Record:

- what changed;
- what was verified, with exact commands and results;
- what remains deferred;
- whether the legacy inactive archive code in `events` was intentionally left in
  place.

**Step 4: Update project status**

Update:

- current focus;
- latest verified commands;
- deferred follow-up items;
- links to the design, implementation plan, and work log.

**Step 5: Commit**

```bash
git add .docs/project-status.md .docs/refactoring/2026-06-24-backend-follow-up-work-log.md
git commit -m "docs(backend): Record follow-up hardening work"
```

## Deferred Work To Preserve In The Work Log

- Removing legacy inactive archive code from `events` in a dedicated
  migration-reviewed slice.
- Public event query performance tuning after measured evidence.
- Any broader exception mapping abstraction.

Plan complete and saved to `.docs/plans/2026-06-24-backend-follow-up-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch a fresh subagent per task, review between tasks, and keep the work tightly scoped.

**2. Parallel Session (separate)** - Open a new session with `executing-plans` and run the plan task-by-task there.

Which approach?
