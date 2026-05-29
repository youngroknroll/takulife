# Event Index API Contract Design Log

Date: 2026-05-28
Design document: `docs/plans/2026-05-28-oshilog-event-index-api-contract-design.md`

## What Changed

- Added a backend API contract design for the Event Index slice.
- Used PO, Tech Lead, TDD, Security / Reliability, and QA subagent analysis.
- Corrected project agent definitions to include role-specific `model`
  frontmatter from `AGENTS.md`.
- Recorded public event, admin draft, permission, error, TDD, migration, and
  deferred refactoring decisions.

## Verification

This task changed documentation and agent configuration only. Verification uses
filesystem and text checks rather than application tests.

Commands:

```bash
rg '^name:|^description:|^model:' .claude/agents
```

```bash
test -f docs/plans/2026-05-28-oshilog-event-index-api-contract-design.md
```

Application verification was not run because no application code or tests were
changed.

## Remaining Risks

- The design chooses public `category` as the API field while older documents
  mention `event_type`; implementation must keep the public contract consistent.
- Infra / DevOps could not run as a parallel subagent because of the active
  subagent limit. Migration and verification concerns were still documented.
- URL fetch and SSRF defenses are intentionally deferred until real fetch logic
  enters scope.

## Deferred Refactoring

Deferred notes are recorded in the design document.
