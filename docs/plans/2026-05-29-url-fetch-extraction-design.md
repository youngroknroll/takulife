# OshiLog URL Fetch And Extraction Design

Date: 2026-05-29

## Approved Scope

Build the first URL fetch and rule-based extraction pipeline for admin event
draft creation.

This scope covers:

- Fetching an admin-submitted official URL during draft creation.
- Blocking unsafe URLs before any outbound request.
- Extracting best-effort draft candidate fields from HTML.
- Returning controlled API errors for invalid URLs, unsafe URLs, fetch
  failures, oversized responses, unsupported content, and empty extraction.
- Keeping draft workflow ownership inside the `drafts` domain.

This scope does not cover:

- Background workers or queues.
- AI extraction.
- Storing remote images or media.
- User-submitted event URLs.
- Production-grade DNS rebinding defense.
- Full browser rendering or JavaScript execution.

## Recommended Approach

Use a synchronous minimum pipeline.

When an admin posts `source_url` to `POST /api/admin/event-drafts/`, the
backend validates URL safety, fetches the HTML with a short timeout, extracts
candidate values, and creates a pending `EventDraft`.

This fits the current MVP because it keeps the workflow simple and testable.
It avoids queue infrastructure until request latency or operational load proves
that a worker is needed.

## Alternatives Considered

### Background Worker Pipeline

Create the draft first, then let a worker fetch and extract data later.

This is operationally stronger, but it requires queue configuration, worker
deployment, retry state, and a broader status model. It is deferred until the
first synchronous pipeline becomes too slow or unreliable.

### Manual HTML Paste Pipeline

Ask admins to paste source content and run extraction without network access.

This reduces SSRF risk, but it does not satisfy the intended URL-based draft
creation workflow.

## Architecture

The `drafts` app owns the fetch and extraction workflow.

Expected modules:

- `drafts.url_safety`: URL scheme, host, DNS, and redirect target safety.
- `drafts.fetching`: bounded HTTP fetch with timeout, content-type, size, and
  redirect handling.
- `drafts.extraction`: rule-based HTML-to-candidate extraction.
- `drafts.services`: orchestration for draft creation, approval, and rejection.

The `events` app remains responsible only for published event creation.
`events` must not import draft fetch or extraction code.

`core.errors` remains a generic HTTP response helper module only. Domain
exceptions stay inside `drafts` or `events`.

## Data Flow

1. Admin submits `source_url`.
2. The serializer validates basic HTTP/HTTPS URL shape and duplicate source
   URL behavior.
3. `drafts.services` asks `drafts.url_safety` to validate the URL.
4. `drafts.fetching` fetches HTML with a short timeout and bounded response
   size.
5. Each redirect target is safety-checked before the next request.
6. `drafts.extraction` reads the HTML and returns candidate fields.
7. `drafts.services` creates a pending `EventDraft`.
8. The admin receives the draft payload with extracted candidate fields.

## URL Safety Requirements

The first implementation must block:

- Non-HTTP and non-HTTPS schemes.
- Missing hostnames.
- `localhost` and loopback hosts.
- Private, link-local, multicast, unspecified, and reserved IP addresses.
- Hosts resolving only to blocked addresses.
- Redirect targets that fail the same safety checks.

The first implementation may defer full DNS rebinding defense. That risk must
remain documented as deferred hardening.

## Fetch Requirements

The fetcher must:

- Use a clear OshiLog user agent.
- Use a short connect/read timeout.
- Follow only a small number of redirects.
- Revalidate every redirect URL.
- Accept only HTML-like content types.
- Enforce a maximum response body size.
- Avoid storing remote images or binary assets.
- Avoid leaking raw exception messages to public API responses.

## Extraction Requirements

Extraction should be best-effort and deterministic.

The first rule set should extract:

- `raw_title` from `<title>` or Open Graph title.
- `raw_text` from normalized visible text or meta description.
- `extracted_title` from Open Graph title, `<title>`, or heading text.
- `extracted_summary` from meta description or the first useful text snippet.
- Date candidates using simple Korean and ISO-like date patterns.
- Region and location candidates using conservative text rules.
- Category candidate only when obvious keywords match the supported event
  categories.

The extractor must return a controlled failure when no meaningful title or text
can be found.

## Error Handling

API responses should use controlled JSON errors:

- Invalid or unsafe URL: `400`.
- Unsupported content type: `400`.
- Oversized response: `400`.
- Empty extraction result: `400`.
- Timeout or network failure: `503`.
- Unexpected fetch or extraction failure: log internally, return `503`.

Domain exception classes should remain in `drafts`. Views should map them to
HTTP responses through `core.errors` helpers.

## Boundary And Coupling Rules

- `drafts.views` may import `drafts.services`, serializers, models, and
  `core.errors`.
- `drafts.views` must not import `events`.
- `drafts.fetching` and `drafts.extraction` must not import `events`.
- `events` must not import `drafts`.
- Cross-domain publication remains `drafts.services -> events.services`.
- Business rules belong in services or small pure helpers, not HTTP view
  methods.

## Testing Strategy

Use TDD with behavior-first tests.

Required test coverage:

- Admin draft creation fetches HTML and stores extracted fields.
- Non-admin users cannot trigger fetch/extraction.
- Unsafe URLs are rejected without an outbound request.
- Redirects to unsafe URLs are rejected.
- Timeout/network failure returns a controlled error and creates no draft.
- Unsupported content type creates no draft.
- Empty extraction creates no draft.
- Duplicate `source_url` remains rejected.
- Architecture boundary tests prevent `events` from importing `drafts` and
  prevent draft HTTP views from importing `events`.

External network calls must be mocked in tests.

## Deferred Refactoring Note

- Topic: Background URL fetch and extraction worker.
- Why it is not part of the current scope: The first MVP needs one simple
  admin workflow before queue infrastructure is justified.
- Why it may be needed later: Slow websites, retry handling, and higher admin
  throughput may make synchronous request handling too fragile.
- Trigger condition: Fetch/extraction latency exceeds acceptable admin request
  time or retry/state management becomes necessary.
- Expected change location: `drafts.services`, a new worker module, deployment
  configuration, and draft status fields.
- Related tests: Draft creation, fetch retry, fetch status, and admin review
  tests.

## Deferred Refactoring Note

- Topic: DNS rebinding hardening.
- Why it is not part of the current scope: The first implementation can block
  obvious unsafe destinations without adding a full network sandbox.
- Why it may be needed later: Production URL fetching is exposed to changing
  DNS answers and more sophisticated SSRF attempts.
- Trigger condition: Public or high-volume URL submission is introduced, or
  URL fetching moves beyond trusted admins.
- Expected change location: `drafts.url_safety`, `drafts.fetching`, deployment
  network policy, and security tests.
- Related tests: URL safety and redirect safety tests.
