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
- Read only the current plan, relevant status section, code, and domain sources.
- Treat `.docs/project-status.md` as continuity context, not current source code.
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
- Tests and docs: `tests/<domain>/`, `tests/e2e/`, `.docs/plans/`,
  `.docs/refactoring/`, `.docs/project-status.md`

Start with these stable paths. Use `rg` when the exact location is still unknown
or the task requires a repository-wide repeated-pattern check.

## Stack And Commands
- Python 3.13, Django 5.2, Django REST Framework, PostgreSQL, `uv`
- Sync: `uv sync`
- Django check: `uv run python manage.py check`
- Migration drift: `uv run python manage.py makemigrations --check --dry-run`
- Targeted test: `uv run pytest -q <test-path>`
- Backend regression: `uv run pytest -q -m "not e2e"`
- Browser e2e: `uv run pytest -m e2e -q`
- Local server: `uv run python manage.py runserver`

Run e2e only when the plan requires browser evidence. During Red-Green, run the
targeted test before broad regression.

## Working Method
1. Inspect `git status` and preserve existing user changes.
2. Read `AGENTS.md` before planning, task classification, or role routing.
3. Classify task shape and risk, then activate the smallest sufficient role set.
4. Read the approved plan before editing.
5. Backend behavior follows the Backend TDD Coach's one-test-at-a-time Kent Beck
   Red-Green-Refactor contract.
6. Frontend changes require both frontend reviewers' pre-implementation outputs
   and post-implementation verdicts; listing the roles alone is not evidence.
7. Implement only approved scope; record larger ideas as deferred work.
8. Run fresh verification and read complete output before claiming completion.

## Engineering Guardrails
- Prefer current repository patterns and framework-native Django/DRF APIs.
- Keep business rules in owning models, domain functions, or application services.
- Avoid speculative abstractions, adjacent cleanup, silent mutation, and broad
  refactors.
- Use `rg` for search and `apply_patch` for manual edits.
- Never revert unrelated changes or overwrite `prompt_plan.md` unless assigned.
- Do not commit, push, merge, or open a PR without explicit user approval.
- Report failed and unverified checks directly; confidence is not evidence.

## Instruction Placement
- `CLAUDE.md`: facts and gates needed in almost every session
- `AGENTS.md`: detailed product constraints, workflow, roles, and review gates
- `.claude/agents/`: local role adapters
- `.docs/plans/`, `.docs/refactoring/`: task boundaries and completion evidence
- Deterministic restrictions belong in settings or hooks, not advisory prose.
- Repeated procedures become skills or path-scoped rules only after demonstrated
  need.

## Session Continuity
After an implementation task changes files, its owning implementation role
updates the required work log and `.docs/project-status.md`.
Recover a fresh session from the plan, Git diff, status, and verification logs.
