# URL Fetch Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a synchronous, SSRF-aware URL fetch and rule-based extraction pipeline to admin event draft creation.

**Architecture:** Keep fetch, URL safety, extraction, and draft creation orchestration inside the `drafts` app. `drafts.services` owns the workflow, `events.services` remains used only for publication, and HTTP views only map domain results or exceptions to responses. External network access must be mocked in tests.

**Tech Stack:** Python 3.13, Django, Django REST Framework, pytest, pytest-django, httpx, BeautifulSoup.

---

## Approved Scope

Implement the approved design in
`docs/plans/2026-05-29-url-fetch-extraction-design.md`.

Included:

- URL safety validation before fetch.
- Bounded synchronous HTML fetch for admin draft creation.
- Rule-based extraction into existing `EventDraft` fields.
- Controlled API errors for unsafe URL, timeout, fetch failure, unsupported
  content type, oversized response, and empty extraction.
- Architecture boundary tests.
- Final refactoring log and `docs/project-status.md` update.

Excluded:

- Background workers.
- AI extraction.
- Storing remote images.
- User-submitted URLs.
- Full DNS rebinding defense.

## Acceptance Criteria

- Admin draft creation from a safe mocked HTML URL returns `201` and stores
  extracted title/text/summary/date/location/category candidates.
- Unsafe URLs are rejected before any outbound request and create no draft.
- Redirects to unsafe URLs are rejected and create no draft.
- Timeout and network failures return controlled JSON errors and create no
  draft.
- Unsupported content type and oversized responses return controlled JSON
  errors and create no draft.
- Empty extraction returns a controlled JSON error and creates no draft.
- Non-admin users cannot trigger fetch/extraction.
- Existing approve/reject behavior remains unchanged.
- Domain boundaries remain explicit:
  - `drafts.views` does not import `events`.
  - `events` does not import `drafts`.
  - `drafts.fetching` and `drafts.extraction` do not import `events`.
- `uv run pytest -q`, `uv run python manage.py check`, and
  `uv run python manage.py makemigrations --check --dry-run` pass.

## Task 1: Add URL Safety Validator

**Files:**
- Create: `drafts/url_safety.py`
- Test: `tests/test_draft_url_safety.py`

**Step 1: Write the failing tests**

Create tests for safe URLs and blocked destinations:

```python
import pytest

from drafts.url_safety import UnsafeUrlError, validate_fetch_url


def test_validate_fetch_url_accepts_public_http_url(monkeypatch):
    monkeypatch.setattr("drafts.url_safety.socket.getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 443))])

    assert validate_fetch_url("https://example.com/event") == "https://example.com/event"


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/event",
        "file:///etc/passwd",
        "https://localhost/event",
        "https://127.0.0.1/event",
        "https://[::1]/event",
    ],
)
def test_validate_fetch_url_rejects_unsafe_url_without_dns(url):
    with pytest.raises(UnsafeUrlError):
        validate_fetch_url(url)


def test_validate_fetch_url_rejects_private_dns_result(monkeypatch):
    monkeypatch.setattr("drafts.url_safety.socket.getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("10.0.0.1", 443))])

    with pytest.raises(UnsafeUrlError):
        validate_fetch_url("https://example.com/event")
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest -q tests/test_draft_url_safety.py
```

Expected: FAIL because `drafts.url_safety` does not exist.

**Step 3: Write minimal implementation**

Implement:

- `UnsafeUrlError`.
- `validate_fetch_url(url: str) -> str`.
- scheme check for `http` and `https`.
- hostname presence check.
- direct IP and DNS result checks using `ipaddress`.
- blocked checks for private, loopback, link-local, multicast, unspecified,
  and reserved addresses.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest -q tests/test_draft_url_safety.py
```

Expected: PASS.

## Task 2: Add Bounded HTML Fetcher

**Files:**
- Create: `drafts/fetching.py`
- Modify: `drafts/url_safety.py`
- Test: `tests/test_draft_fetching.py`

**Step 1: Write the failing tests**

Use fake `httpx.Client` behavior or monkeypatch a small internal request
function. Cover:

```python
from types import SimpleNamespace

import httpx
import pytest

from drafts.fetching import (
    DraftFetchContentTypeError,
    DraftFetchSizeError,
    DraftFetchTimeoutError,
    fetch_html,
)


def test_fetch_html_returns_html(monkeypatch):
    response = SimpleNamespace(
        status_code=200,
        headers={"content-type": "text/html; charset=utf-8"},
        content=b"<html><title>Popup</title></html>",
        url="https://example.com/event",
        raise_for_status=lambda: None,
    )
    monkeypatch.setattr("drafts.fetching._request_once", lambda url: response)
    monkeypatch.setattr("drafts.fetching.validate_fetch_url", lambda url: url)

    result = fetch_html("https://example.com/event")

    assert result.url == "https://example.com/event"
    assert "Popup" in result.html


def test_fetch_html_rejects_unsupported_content_type(monkeypatch):
    response = SimpleNamespace(
        status_code=200,
        headers={"content-type": "application/pdf"},
        content=b"%PDF",
        url="https://example.com/event",
        raise_for_status=lambda: None,
    )
    monkeypatch.setattr("drafts.fetching._request_once", lambda url: response)
    monkeypatch.setattr("drafts.fetching.validate_fetch_url", lambda url: url)

    with pytest.raises(DraftFetchContentTypeError):
        fetch_html("https://example.com/event")


def test_fetch_html_converts_timeout(monkeypatch):
    def timeout(url):
        raise httpx.TimeoutException("slow")

    monkeypatch.setattr("drafts.fetching._request_once", timeout)
    monkeypatch.setattr("drafts.fetching.validate_fetch_url", lambda url: url)

    with pytest.raises(DraftFetchTimeoutError):
        fetch_html("https://example.com/event")
```

Add a size-limit test after the first green pass.

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest -q tests/test_draft_fetching.py
```

Expected: FAIL because `drafts.fetching` does not exist.

**Step 3: Write minimal implementation**

Implement:

- `FetchedHtml` dataclass with `url` and `html`.
- fetch exceptions:
  - `DraftFetchError`
  - `DraftFetchTimeoutError`
  - `DraftFetchNetworkError`
  - `DraftFetchContentTypeError`
  - `DraftFetchSizeError`
- `_request_once(url)` using `httpx.Client(follow_redirects=False)`.
- manual redirect loop with a small max redirect count.
- call `validate_fetch_url` before the first request and before each redirect.
- HTML content type allowlist: `text/html`, `application/xhtml+xml`, and empty
  content type only when the body looks like HTML.
- max body size constant.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest -q tests/test_draft_fetching.py
```

Expected: PASS.

## Task 3: Add Rule-Based Extractor

**Files:**
- Create: `drafts/extraction.py`
- Test: `tests/test_draft_extraction.py`

**Step 1: Write the failing tests**

Cover title, summary, date, region, and empty extraction:

```python
import pytest

from drafts.extraction import DraftExtractionError, extract_event_candidates


def test_extract_event_candidates_reads_title_summary_and_date():
    html = """
    <html>
      <head>
        <meta property="og:title" content="Oshi Popup Store">
        <meta name="description" content="Seoul popup from 2026-06-01 to 2026-06-10">
      </head>
      <body><h1>Oshi Popup Store</h1><p>서울 홍대에서 열리는 팝업스토어입니다.</p></body>
    </html>
    """

    result = extract_event_candidates(html, source_url="https://example.com/event")

    assert result.raw_title == "Oshi Popup Store"
    assert "Seoul popup" in result.raw_text
    assert result.extracted_title == "Oshi Popup Store"
    assert result.extracted_category == "popup_store"
    assert result.extracted_region == "seoul"
    assert str(result.extracted_start_date) == "2026-06-01"
    assert str(result.extracted_end_date) == "2026-06-10"


def test_extract_event_candidates_rejects_empty_html():
    with pytest.raises(DraftExtractionError):
        extract_event_candidates("<html></html>", source_url="https://example.com/event")
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest -q tests/test_draft_extraction.py
```

Expected: FAIL because `drafts.extraction` does not exist.

**Step 3: Write minimal implementation**

Implement:

- `DraftCandidateData` dataclass.
- `DraftExtractionError`.
- BeautifulSoup parsing.
- extraction helpers for title, meta description, visible text, category,
  region, and simple dates.
- conservative fallback behavior:
  - title from Open Graph title, `<title>`, or `h1`.
  - summary from meta description or first useful text snippet.
  - raw text normalized and bounded.
  - dates from ISO-like `YYYY-MM-DD` and Korean `YYYY년 M월 D일` patterns.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest -q tests/test_draft_extraction.py
```

Expected: PASS.

## Task 4: Add Draft Creation Service

**Files:**
- Modify: `drafts/services.py`
- Test: `tests/test_drafts_services.py`

**Step 1: Write the failing tests**

Add service behavior tests before changing production code:

```python
import pytest

from drafts.models import EventDraft
from drafts.services import DraftCreationError, create_draft_from_url


@pytest.mark.django_db
def test_create_draft_from_url_fetches_extracts_and_creates_pending_draft(monkeypatch):
    monkeypatch.setattr(
        "drafts.services.fetch_html",
        lambda url: type("Fetched", (), {"url": url, "html": "<html><title>Popup</title><body>서울 팝업스토어 2026-06-01</body></html>"})(),
    )

    draft = create_draft_from_url("https://example.com/event")

    assert draft.source_url == "https://example.com/event"
    assert draft.review_status == EventDraft.ReviewStatus.PENDING
    assert draft.raw_title
    assert draft.raw_text


@pytest.mark.django_db
def test_create_draft_from_url_maps_fetch_failure_to_domain_error(monkeypatch):
    def fail(url):
        raise RuntimeError("network")

    monkeypatch.setattr("drafts.services.fetch_html", fail)

    with pytest.raises(DraftCreationError):
        create_draft_from_url("https://example.com/event")

    assert not EventDraft.objects.exists()
```

Prefer concrete fetch/extraction exceptions when implementation names exist.

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest -q tests/test_drafts_services.py
```

Expected: FAIL because `create_draft_from_url` does not exist.

**Step 3: Write minimal implementation**

In `drafts.services`:

- Add `DraftCreationError` base exception.
- Add specific draft creation exceptions as needed:
  - `DraftCreationUnsafeUrlError`
  - `DraftCreationFetchError`
  - `DraftCreationExtractionError`
- Add `create_draft_from_url(source_url)`.
- Call `fetch_html`, then `extract_event_candidates`.
- Create `EventDraft` with existing fields.
- Keep approval/rejection behavior unchanged.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest -q tests/test_drafts_services.py
```

Expected: PASS.

## Task 5: Wire Admin Draft Create API To The Service

**Files:**
- Modify: `drafts/serializers.py`
- Modify: `drafts/views.py`
- Test: `tests/test_drafts_api.py`

**Step 1: Write the failing API tests**

Add behavior tests:

```python
import pytest

from drafts.models import EventDraft


@pytest.mark.django_db
def test_admin_create_event_draft_fetches_and_extracts(admin_client, monkeypatch):
    def create(source_url):
        return EventDraft.objects.create(
            source_url=source_url,
            raw_title="Oshi Popup Store",
            raw_text="서울 팝업스토어 2026-06-01",
            extracted_title="Oshi Popup Store",
            extracted_category="popup_store",
            extracted_region="seoul",
        )

    monkeypatch.setattr("drafts.views.create_draft_from_url", create)

    response = admin_client.post("/api/admin/event-drafts/", {"source_url": "https://example.com/event"})

    assert response.status_code == 201
    assert response.json()["raw_title"] == "Oshi Popup Store"
    assert response.json()["extracted_region"] == "seoul"


@pytest.mark.django_db
def test_admin_create_event_draft_returns_controlled_error(admin_client, monkeypatch):
    from drafts.services import DraftCreationUnsafeUrlError

    def fail(source_url):
        raise DraftCreationUnsafeUrlError

    monkeypatch.setattr("drafts.views.create_draft_from_url", fail)

    response = admin_client.post("/api/admin/event-drafts/", {"source_url": "https://localhost/event"})

    assert response.status_code == 400
    assert response.json() == {"detail": "Unsafe URL."}
```

Update the existing `test_admin_can_create_event_draft_from_url` so it does not
perform a real network call. It should monkeypatch service creation or fetcher
behavior.

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest -q tests/test_drafts_api.py
```

Expected: FAIL because create view still uses default serializer creation.

**Step 3: Write minimal implementation**

In `AdminEventDraftListCreateView`:

- Override `create`.
- Validate input with serializer or a small create serializer.
- Call `create_draft_from_url(source_url)`.
- Serialize the returned draft.
- Map domain exceptions:
  - unsafe URL: `400 {"detail": "Unsafe URL."}`
  - fetch content type/size/extraction: `400`
  - timeout/network/unexpected: `503`
  - duplicate source URL: keep field-level `400`.

Keep `EventDraftUpdateSerializer` behavior unchanged.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest -q tests/test_drafts_api.py
```

Expected: PASS.

## Task 6: Add Redirect And Boundary Regression Tests

**Files:**
- Modify: `tests/test_draft_fetching.py`
- Modify: `tests/test_architecture_boundaries.py`

**Step 1: Write failing tests**

Add redirect safety coverage:

```python
def test_fetch_html_validates_redirect_target(monkeypatch):
    calls = []

    def validate(url):
        calls.append(url)
        if url == "http://127.0.0.1/admin":
            from drafts.url_safety import UnsafeUrlError

            raise UnsafeUrlError
        return url

    first = type("Response", (), {
        "status_code": 302,
        "headers": {"location": "http://127.0.0.1/admin"},
        "content": b"",
        "url": "https://example.com/event",
        "raise_for_status": lambda self: None,
    })()
    monkeypatch.setattr("drafts.fetching._request_once", lambda url: first)
    monkeypatch.setattr("drafts.fetching.validate_fetch_url", validate)

    from drafts.fetching import DraftFetchUnsafeUrlError, fetch_html

    with pytest.raises(DraftFetchUnsafeUrlError):
        fetch_html("https://example.com/event")

    assert calls == ["https://example.com/event", "http://127.0.0.1/admin"]
```

Add architecture tests:

```python
@pytest.mark.parametrize("module_path", ["events/services.py", "events/views.py", "events/serializers.py"])
def test_events_modules_do_not_import_drafts(module_path):
    ...


@pytest.mark.parametrize("module_path", ["drafts/fetching.py", "drafts/extraction.py"])
def test_draft_fetch_and_extraction_do_not_import_events(module_path):
    ...
```

Use the existing AST style in `tests/test_architecture_boundaries.py`.

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest -q tests/test_draft_fetching.py tests/test_architecture_boundaries.py
```

Expected: FAIL until redirect exception mapping and boundary files are correct.

**Step 3: Write minimal implementation**

- Add `DraftFetchUnsafeUrlError` mapping in `drafts.fetching`.
- Ensure redirect target validation happens before redirect request.
- Keep imports one-way and local to domain boundaries.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest -q tests/test_draft_fetching.py tests/test_architecture_boundaries.py
```

Expected: PASS.

## Task 7: Final Review, Documentation, And Verification

**Files:**
- Create: `docs/refactoring/2026-05-29-url-fetch-extraction-work-log.md`
- Modify: `docs/project-status.md`

**Step 1: Run focused tests**

Run:

```bash
uv run pytest -q tests/test_draft_url_safety.py tests/test_draft_fetching.py tests/test_draft_extraction.py tests/test_drafts_services.py tests/test_drafts_api.py tests/test_architecture_boundaries.py
```

Expected: PASS.

**Step 2: Run full verification**

Run:

```bash
uv run pytest -q
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
git diff --check
```

Expected: all pass and no migrations are generated unless a model field change
is explicitly introduced and justified.

**Step 3: Write final work log**

Record:

- What changed.
- What was verified.
- Remaining risks.
- Deferred refactoring notes for background workers and DNS rebinding.
- Any TDD deviations, if they happened.

**Step 4: Update project status**

Add a new 2026-05-29 section with:

- Completed scope.
- Verification commands and results.
- Active documents.
- Deferred work.

**Step 5: Commit**

Use the project convention:

```bash
git add drafts tests docs
git commit -m "feat(drafts): Add URL fetch extraction pipeline"
```

Expected: commit succeeds with only approved-scope files.
