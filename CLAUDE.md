# Claude Code Project Context

This is takulife's concise, always-loaded bootstrap. Following current Claude
Code guidance, the project target is to keep this file under 200 lines.
Detailed governance lives in `AGENTS.md` and is read just in time. If this
summary conflicts with `AGENTS.md`, `AGENTS.md` wins.

## Product
takulife is a collection-first service for subculture fans.

Priority:
1. Personal goods collection and archiving
2. Event experience records
3. Official subculture event discovery
4. Limited peer exchange matching after demand is validated

Core loop: discover an event, record the experience, add acquired or independent
goods, maintain intent, then find exchange candidates. Collection drives return.

## Binding Product Decisions
- Create a dedicated `CollectionItem`; do not keep expanding `PersonalEntry`
  into the goods collection aggregate.
- `archive` may reference `events`; future `trade` depends on stable `archive`
  contracts and never mutates collection inventory directly.
- Collection and visit data are private by default. Exchange visibility requires
  explicit opt-in and must be independently revocable.
- Tradeable quantity cannot exceed owned quantity. Goods cannot be visit/status targets or official-promotion candidates.
- Target IA is `Home / Events / Collection / Activity`, but navigation changes
  must wait for the approved collection data contract.
- Initial north star: monthly collection-contributing users, supported by first
  and second registration, four-week return, and matching-density measures.
- Execution order: deployment foundation, collection domain and migration,
  backend MVP, target IA, real-use validation, then exchange gate review.
- Do not start exchange matching until density, identity quality, privacy,
  reporting, blocking, moderation, and operations gates are approved.
- Sales, payments, shipping, escrow, unrestricted chat, and a public marketplace are out of scope.

## Context Loading
- Do not preload every plan, report, or governance document.
- Before planning, role routing, or editing, read `AGENTS.md`.
- Read only the current plan, relevant `docs/backlog.md` or runbook, code, and
  domain sources. Read `docs/pr-log.md` only when merged-PR history is directly
  relevant; it is a rolling log, never current source code or durable project
  state.
- Verify repository facts from code and configuration before relying on prose.
- Local role adapters live in `.claude/agents/` and load only when activated.
- Do not duplicate detailed role contracts or import all of `AGENTS.md` here.

## Project Map
- `config/`: Django configuration and root routing
- `accounts/`: authentication and account lifecycle
- `events/`, `drafts/`: published events and pre-publication ingestion/review
- `archive/`: personal state, visits, and collection groundwork
- `staff/`: staff console and moderation workflows
- `core/`: shared web flows, queries, services, and LLM helpers
- `templates/`, `static/`, `tests/`: web UI, browser assets, and verification

## Stable Entry Paths
- Runtime: `manage.py`, `pyproject.toml`, `pytest.ini`, `config/settings.py`,
  `config/urls.py`
- Accounts: `accounts/models.py`, `accounts/forms.py`, `accounts/views.py`
- Collection and visits: `archive/models.py`, `archive/services.py`,
  `archive/queries.py`, `archive/serializers.py`, `archive/urls.py`
- Published events: `events/models.py`, `events/services.py`,
  `events/queries.py`, `events/serializers.py`, `events/urls.py`
- Ingestion and review: `drafts/models.py`, `drafts/services.py`,
  `drafts/queries.py`, `drafts/urls.py`
- Staff and shared web: `staff/services.py`, `staff/queries.py`, `staff/views/`,
  `core/urls.py`, `core/views.py`
- Frontend: `templates/base.html`, `templates/core/`, `templates/staff/`,
  `static/css/`, `static/js/`
- Backlog, PR history, runbooks, technical records (version-controlled):
  `docs/backlog.md`, `docs/pr-log.md`, `docs/deploy-runbook.md`,
  `docs/operations-runbook.md`, `docs/event-operations-criteria.md`, `docs/BE/`
- Tests and optional local working notes: `tests/<domain>/`, `.docs/BE/`,
  `.docs/DB/`, `.docs/FE/`

Start with these stable paths. Use `rg` when the exact location is still unknown
or the task requires a repository-wide repeated-pattern check.

## Stack And Commands
- Python 3.13, Django 5.2, Django REST Framework, PostgreSQL, `uv`
- Sync: `uv sync`
- Django check: `uv run python manage.py check`
- Migration drift: `uv run python manage.py makemigrations --check --dry-run`
- Targeted test: `uv run pytest -q <test-path>`
- Backend regression: `uv run pytest -q`
- Local server: `uv run python manage.py runserver`

Automated tests cover backend logic only — there is no browser/e2e suite
(deleted 2026-07-22). Browser behavior is verified by driving Chromium with
Playwright or the Chrome DevTools MCP tools against the local dev server;
Playwright stays installed as a verification tool, never as a test framework.
During Red-Green, run the targeted test before broad regression.

## Working Method
1. Inspect `git status` and preserve existing user changes.
2. Read `AGENTS.md` before planning, task classification, or role routing.
3. Classify task shape and risk, then activate the smallest sufficient role set.
4. Orchestrator claims follow `AGENTS.md` "Orchestrator Contract": verify
   before stating, review before reporting.
5. Read the approved plan before editing.
6. Backend behavior follows the Backend TDD Coach's one-test-at-a-time Kent Beck
   Red-Green-Refactor contract.
7. Frontend changes require both frontend reviewers' pre-implementation outputs
   and post-implementation verdicts; listing the roles alone is not evidence.
8. Implement only approved scope; record larger ideas as deferred work.
9. Run fresh verification and read complete output before claiming completion.

## Engineering Guardrails
- Prefer current repository patterns and framework-native Django/DRF APIs.
- Keep business rules in owning models, domain functions, or application services.
- Avoid speculative abstractions, adjacent cleanup, silent mutation, and broad
  refactors.
- Write code comments and docstrings only for non-obvious intent or constraints;
  use one or two short lines of plain Korean a non-developer can follow, never
  a translation of the code. The detailed standard is in `AGENTS.md`.
- Use `rg` for search and `apply_patch` for manual edits.
- Never revert unrelated changes or overwrite `prompt_plan.md` unless assigned.
- After planned verification, commit, push, and PR creation are automatic.
  Merge needs per-PR user approval unless an expressly recorded standing
  automatic-merge approval applies. `AGENTS.md` owns the detailed contract.
- Small defects of the same kind found mid-track are not deferred to the
  backlog: report the finding, then fix it inside the same track (and the same
  PR) before merge. Open a backlog item only when the finding is a different
  kind of work or exceeds the track's scale. Standing user decision
  (2026-08-25) — avoiding work accumulation outranks strict scope minimalism
  here, and the report-first step keeps this compatible with the surgical rule.
- Report failed and unverified checks directly; confidence is not evidence.
- Every number written into a document must name its unit and say whether it
  was measured or read, and must be re-measured before it sizes any work.
  `AGENTS.md` "Numbers In Documents" is binding and lists the four counts that
  already misdirected work here.

## Instruction Placement
- `CLAUDE.md`: facts and gates needed in almost every session
- `AGENTS.md`: detailed product constraints, workflow, roles, and review gates
- `.claude/agents/`: local role adapters
- `docs/`: the only durable document tree — backlog, the rolling merged-PR log
  (`docs/pr-log.md`), runbooks, and any technical record stating a guardrail
  (`docs/BE/`, and `DB/`/`FE/` when needed)
- `.docs/BE/`, `.docs/DB/`, `.docs/FE/`: drafts and working measurements.
  **`.docs/` is git-ignored**; a missing file there is housekeeping, not a loss
- Deterministic restrictions belong in settings or hooks, not advisory prose.
- Repeated procedures become skills or path-scoped rules only after demonstrated
  need.

## Session Continuity
After an implementation task changes files, its owning implementation role
records only handoff-critical facts: update `docs/backlog.md` when durable
current state changes and the existing relevant technical document when a later
worker could otherwise make a mistake. Do not create routine work logs; read
only the needed section.
Recover a fresh session from the plan, Git diff, status, and verification logs.
