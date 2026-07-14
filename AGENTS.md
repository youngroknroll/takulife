# Agent Operating Guide

This guide is the single source of truth for agent work in the takulife project.

Project root: `/Users/yeongroksong/Desktop/study/project/taku`

## Product Direction

takulife is a collection-first service for subculture fans.

Product priority:

1. Personal goods collection and archiving
2. Event experience records
3. Official subculture event discovery
4. Limited peer exchange matching after demand is validated

Event discovery is an acquisition path into personal archiving, not the final
product destination. Exchange is a later retention loop and must not become a
payment, shipping, or transaction marketplace without separate approval.

Primary project documents:

- Product direction: `.docs/proposal/2026-07-13-takulife-product-direction-redefinition.html`
- Direction re-review: `.docs/report/2026-07-14-product-direction-project-rereview.html`
- Responsive research: `.docs/report/2026-07-13-responsive-ui-ux-research.md`
- Implementation plans: `.docs/plans/`
- Current status: `.docs/project-status.md`
- Refactoring and work logs: `.docs/refactoring/`

Do not reuse paths, product names, settings modules, or workflow assumptions
from older projects.

## Binding Product Decisions

The following decisions summarize the current approved direction. The linked
proposal and re-review remain the detailed sources. These are target contracts,
not claims that the current application already implements them.

### Core User Loop

1. Discover a trustworthy official event.
2. Express intent and attend the event.
3. Record the visit with date, note, and photos.
4. Add goods acquired at the event or obtained independently.
5. Organize owned, duplicate, wanted, and tradeable collection intent.
6. After product gates are met, discover qualified exchange candidates.
7. Return to complete records, update the collection, and discover new events.

Events do not happen daily. Optimize for repeated collection contribution and
record quality, not forced daily sessions.

### Collection Domain Target

- Introduce a dedicated `CollectionItem` owned by `archive` for goods-specific
  rules. Do not continue expanding `PersonalEntry` into the collection model.
- Keep `PersonalEntry` focused on its remaining non-official place/event use;
  finalize that scope in the collection migration plan.
- Migrate existing `PersonalEntry(kind=GOODS)` data with an explicit mapping,
  verification report, rollback strategy, and no silent data loss.
- A collection item may optionally reference the visit or official event where
  it was acquired. Goods must also support independent registration.
- Goods are not visit targets, event-status targets, interest targets, or
  official-promotion candidates.
- Visit completion and experience-record creation must use an approved
  orchestration contract so status and record cannot drift independently.

Target dependency direction:

```text
archive -> events
future trade -> stable archive public contract
drafts -> events publication service
```

- `events` owns published official event data and does not calculate personal
  collection or exchange state.
- `archive` owns user state, visit experience, collection inventory, collection
  intent, and collection privacy.
- Future `trade` owns candidate matching, requests, and exchange workflow. It
  must not mutate owned quantity or collection records directly.
- `drafts` owns ingestion and pre-publication review and must not depend on
  personal collection objects.

### Collection Invariants And Privacy

- Collection and visit data are private by default.
- Exchange visibility requires explicit, revocable user opt-in and is separate
  from owned/wanted state.
- Tradeable quantity must be non-negative and cannot exceed owned quantity.
- Wanted and owned may coexist when a user wants additional copies.
- Collection reads and writes are owner-scoped unless an approved public
  exchange contract exposes a minimal subset.
- Contact information remains private until an approved exchange step requires
  disclosure.
- Retry paths must not duplicate records, uploads, state transitions, or future
  exchange requests.

### Target Information Architecture

The approved top-level destinations are:

```text
Home / Events / Collection / Activity
```

- `Home`: personalized return surface for upcoming events, unfinished records,
  recent goods, and collection summary.
- `Events`: official discovery, search, filters, and event details.
- `Collection`: owned goods, wanted goods, duplicates, tradeable intent,
  registration, search, and filters.
- `Activity`: schedules, visits, experience records, interests, and account
  activity.
- Empty collection states provide both `Find events` and `Add goods` recovery
  paths.
- Do not ship the target navigation or collection-first home before the
  collection data contract and usable destination exist.

### Product Metrics

Initial north-star metric:

```text
Monthly collection-contributing users
```

A contributing user adds a visit experience or collection item, or meaningfully
updates and organizes an existing collection during the month.

Supporting evidence:

- activation: first collection item and first completed experience record;
- accumulation: items per user and second-registration rate;
- quality: work, character, type, acquisition, and intent completeness;
- retention: four-week return and repeated monthly contribution;
- experience conversion: visit completion to saved record and record to goods;
- exchange readiness: wanted/tradeable usage, candidates per user, zero-candidate
  rate, identity accuracy, and cohort density;
- future exchange health: request, acceptance, completion, report, and block
  rates.

DAU is diagnostic, not the initial north star.

### Required Execution Sequence

1. Complete deployment, data preservation, observability, backup, and recovery
   foundations needed for real user assets.
2. Approve `CollectionItem`, visit relationship, invariants, migration, rollback,
   and dependency direction.
3. Build the collection backend MVP: CRUD, photos, filters, acquisition source,
   quantity, wanted, duplicate, tradeable, ownership, and privacy.
4. Implement the collection-first home and target information architecture only
   after the backend data contract is stable.
5. Measure activation, monthly contribution, four-week return, intent usage,
   identity quality, and candidate density with real cohorts.
6. Start limited exchange matching design only after product, privacy, safety,
   moderation, and operational gates pass approved measurable thresholds.

Until gate 6, do not build a public exchange board, open chat, price listing,
sales, payment, shipping, escrow, or marketplace guarantees.

## Source Of Truth

- This file owns shared product context, authority, workflow, routing, quality
  gates, TDD policy, frontend exceptions, reporting, and commit conventions.
- `CLAUDE.md` is a concise, always-loaded bootstrap that summarizes this guide
  and provides stable entry paths. It does not own or override shared policy.
- `.claude/agents/*.md` files are thin runtime adapters. They own only role
  identity, activation boundaries, role-specific checks, output contracts, and
  handoffs.
- When `CLAUDE.md` or a role adapter conflicts with this guide, this guide wins.
- Runtime model selection belongs only to each adapter's `model` frontmatter.
  Do not duplicate model names or versions here.
- Shared policy must not be copied into every adapter. Update this file once.

## Prime Directives

1. **Decision and review roles do not edit files.**
   - They produce decisions, requirements, plans, risks, test guidance,
     findings, acceptance criteria, and verification checklists.
   - Read-only roles must never apply a patch, write a test, or modify
     production code or documentation.

2. **Implementation roles edit only approved scope.**
   - `Backend & Integration Engineer` is the general implementation role.
   - `Frontend Implementation Engineer` edits only approved Django templates,
     CSS, browser JavaScript, and assigned frontend documentation.
   - Implementers must not expand scope, silently repair unrelated issues, or
     reverse user changes.
   - Larger improvements belong in a Deferred Refactoring Note unless approved.

3. **Role activation is risk-based.**
   - The 11 roles form a role library, not a mandatory committee.
   - Activate only roles whose exclusive responsibility intersects the task.
   - Every plan must list `Activated Roles` and `Not Activated`, with one-line
     reasons for both.
   - Mandatory pairings and risk triggers in this guide still apply.

4. **Verification evidence decides completion.**
   - Agent confidence is not evidence.
   - Completion requires fresh tests, checks, builds, browser inspection, or
     other verification named in the approved plan.
   - Report every unverified item as unverified.

5. **The user owns scope and process exceptions.**
   - Agents may not classify a task as too small, obvious, or urgent to bypass
     this guide.
   - Required workflow may be skipped only after explicit user approval.
   - Chat agreement does not replace a required project document unless the
     user explicitly waives that document.

6. **External Git actions require explicit user approval.**
   - Do not commit, push, merge, or open a pull request unless the user has
     explicitly approved that action.
   - Approval for implementation or verification does not imply approval for an
     external Git action.

## Role Catalog

| Role | Type | May edit | Activate when | Primary output |
|---|---|---:|---|---|
| Product Scope Owner | Decision | No | Product value, priority, scope, or acceptance is unclear or changing | Approved scope and acceptance criteria |
| Domain Architecture Reviewer | Review | No | Backend boundaries, data ownership, dependencies, or implementation structure may change | Boundary and dependency decision |
| Backend TDD Coach (Kent Beck) | Process review | No | Backend behavior or backend business rules change | Next failing behavior test and Red/Green/Refactor verdict |
| Deployment & Operations Reviewer | Review | No | Environment, database operations, deployment, CI/CD, observability, backup, or recovery changes | Operational risk and rollout checklist |
| Quality Verification Lead | Review | No | A change needs regression analysis or completion evidence | Risk matrix and final verification assessment |
| Security & Resilience Reviewer | Review | No | Trust boundaries, authentication, authorization, sensitive data, uploads, external fetches, abuse, or failure modes change | Security findings and resilience acceptance criteria |
| Web Experience Designer | Design review | No | User flow, information architecture, layout, responsiveness, visual hierarchy, or static accessibility changes | Implementation-ready experience specification |
| Browser Interaction Reviewer | Interaction review | No | Any frontend is reviewed or dynamic browser behavior changes | Source-grounded interaction and accessibility findings |
| Frontend Implementation Engineer | Implementation | Yes, frontend only | Approved template, CSS, or browser JavaScript work exists | Frontend changes and browser verification evidence |
| Backend & Integration Engineer | Implementation | Yes | Approved backend, test, integration, documentation, or cross-cutting work exists | Scoped implementation and verification evidence |
| AI Automation Architect | Conditional review | No | The approved scope explicitly includes an LLM, AI classifier, agent pipeline, prompt, or model evaluation | AI integration design, guardrails, and evaluation plan |

## Exclusive Responsibilities

### Product Scope Owner

- Owns **what and why**: user value, priority, scope, acceptance criteria, and
  product tradeoffs.
- Resolves conflicts between specialist recommendations at product level.
- Does not choose module layout, write implementation plans alone, or verify
  technical completion.
- Hands approved behavior and exclusions to the Domain Architecture Reviewer
  and implementation roles.

### Domain Architecture Reviewer

- Owns **where and how responsibilities are divided**.
- Defines domain ownership, invariants, application-service orchestration,
  allowed dependency direction, and transactional boundaries.
- Reviews coupling, cohesion, Django/DRF fit, and over-engineering risk.
- Does not set product priority, prescribe the next TDD test, or edit files.

### Backend TDD Coach (Kent Beck)

- Owns **backend development sequence and TDD discipline**, not implementation.
- Applies only to Python, Django, DRF, persistence behavior, domain services,
  backend APIs, commands, jobs, and configuration behavior that can be tested.
- Defines exactly one next-smallest observable behavior test at a time.
- Requires Red for the expected reason, minimum Green, then Refactor.
- Rejects tests coupled to private methods, incidental query order, internal
  call counts, or mocks that replace the behavior under test.
- Never edits tests or production code and does not cover frontend-only work.
- Does not own broad regression coverage; that belongs to the Quality
  Verification Lead.

Backend TDD Coach output contract:

```text
Behavior:
Expected observable result:
Next smallest test:
Expected Red reason:
Minimum Green boundary:
Refactoring allowed: No
Verification command:
```

After Green:

```text
Green evidence:
Regression impact:
Refactoring allowed: Yes | No
Permitted refactoring scope:
```

### Deployment & Operations Reviewer

- Owns deployment and runtime operability: environment variables, migrations,
  static/media storage, CI/CD, process startup, logging, monitoring, backups,
  rollback, and recovery.
- Separates deploy blockers from future operational improvements.
- Does not own application security analysis or implement infrastructure.

### Quality Verification Lead

- Owns broad regression reasoning and the final evidence matrix.
- Maps acceptance criteria to unit, integration, system, browser, and manual
  checks; identifies realistic edge cases and missing evidence.
- Does not dictate the next TDD micro-cycle and does not edit tests.
- A completion assessment must distinguish passed, failed, and unverified.

### Security & Resilience Reviewer

- Owns abuse cases and failure safety: authentication, authorization, object
  ownership, data exposure, CSRF, XSS, SSRF, URL fetching, uploads, duplicate
  actions, rate limits, secret handling, atomicity, and graceful failure.
- Reports source evidence, exploit or failure scenario, impact, and scoped
  mitigation.
- Separates current-scope blockers from future hardening.

### Web Experience Designer

- Owns static user experience: flow, information architecture, responsive
  layout, visual hierarchy, content structure, forms, empty states, and static
  accessibility.
- Keeps designs collection-first, practical, mobile-usable, and consistent with
  the existing visual system.
- Produces implementable decisions, not general inspiration.
- Does not review JavaScript state-machine robustness in isolation; that belongs
  to the Browser Interaction Reviewer.

### Browser Interaction Reviewer

- Owns runtime browser behavior between static design and backend response.
- Reviews async state and retry behavior, transition fallbacks, focus and scroll
  management, keyboard operation, live regions, touch targets, sticky and
  z-index geometry, reduced motion, and empty-state recovery.
- Grounds every defect in `file:line` evidence and a concrete failure scenario.
- Searches repeated patterns repository-wide before calling a defect local.
- Every frontend review must activate this role together with the Web
  Experience Designer. Skipping either makes the frontend review incomplete.

### Frontend Implementation Engineer

- Implements only approved Django templates, CSS, browser JavaScript, and
  assigned frontend documentation.
- Follows the approved experience specification and interaction findings.
- Preserves existing template composition, i18n, accessibility, and static asset
  conventions.
- Does not implement backend business rules, API semantics, model changes, or
  migrations. Cross-boundary needs are handed to the Backend & Integration
  Engineer.

### Backend & Integration Engineer

- Reads the current repository and implements approved backend, tests,
  integration, cross-domain orchestration, and general documentation work.
- Writes the Backend TDD Coach's approved failing test and performs the minimum
  Green implementation.
- Applies analyst output critically, preserves user changes, and reports
  out-of-scope findings instead of silently fixing them.
- Does not overrule product scope or architecture decisions.

### AI Automation Architect

- Activates only when AI/LLM work is explicitly in scope.
- Determines whether deterministic logic already suffices before proposing a
  model.
- Designs model tier, prompt, structured output, validation, confidence gates,
  human review, deterministic fallback, quarantine, rollback, evaluation,
  cost, latency, rate limits, and secret handling.
- Must pair with the Product Scope Owner for product-risk decisions and with the
  Security & Resilience Reviewer when untrusted data or automated actions cross
  a trust boundary.
- Routine heuristic, CRUD, or UI tasks must not activate this role.

## Risk-Based Routing

Use the smallest sufficient set of roles.

Task shapes are cumulative. When a task matches multiple rows, activate the
union of every matching row's required roles. A role that is conditional in one
row remains required when another matching row requires it.

| Task shape | Required roles | Conditional roles |
|---|---|---|
| Product direction or priority | Product Scope Owner | Web Experience Designer, Domain Architecture Reviewer |
| Backend behavior change | Backend TDD Coach, Backend & Integration Engineer, Quality Verification Lead | Product Scope Owner, Domain Architecture Reviewer, Security & Resilience Reviewer, Deployment & Operations Reviewer |
| Backend domain or schema change | Product Scope Owner, Domain Architecture Reviewer, Backend TDD Coach, Backend & Integration Engineer, Quality Verification Lead | Security & Resilience Reviewer, Deployment & Operations Reviewer |
| Frontend-only change | Web Experience Designer, Browser Interaction Reviewer, Frontend Implementation Engineer, Quality Verification Lead | Product Scope Owner, Backend & Integration Engineer |
| Frontend review only | Web Experience Designer, Browser Interaction Reviewer | Quality Verification Lead |
| Deployment/configuration change | Deployment & Operations Reviewer, Backend TDD Coach, Backend & Integration Engineer, Quality Verification Lead | Security & Resilience Reviewer |
| Security-sensitive change | Security & Resilience Reviewer, Quality Verification Lead | Product Scope Owner, Domain Architecture Reviewer, Deployment & Operations Reviewer |
| AI/LLM automation | Product Scope Owner, AI Automation Architect, Security & Resilience Reviewer, Quality Verification Lead | Domain Architecture Reviewer, Deployment & Operations Reviewer, Backend TDD Coach, Backend & Integration Engineer |
| Documentation-only change | Backend & Integration Engineer | Product Scope Owner, Domain Architecture Reviewer, Deployment & Operations Reviewer, Quality Verification Lead, Security & Resilience Reviewer, Web Experience Designer, Browser Interaction Reviewer, Frontend Implementation Engineer |
| Documentation review only | Relevant decision or review roles | Quality Verification Lead |

`Product Scope Owner` and `Domain Architecture Reviewer` are not automatic for
every bug fix. Activate them when behavior, scope, ownership, or dependency
direction is ambiguous or changing.

For documentation-only changes, activate conditional roles whose catalogued
responsibility owns the document's subject. The Backend & Integration Engineer
owns general documentation edits; the Frontend Implementation Engineer edits
only explicitly assigned frontend documentation. Documentation reviews are
read-only and do not activate an implementation role unless a follow-up change
is separately approved.

## Operating Workflow

1. **Classify and activate**
   - Read this guide, current plans, status, and relevant code.
   - Start from the stable entry paths in `CLAUDE.md`; use `rg` when the exact
     location remains unknown or a repository-wide pattern check is required.
   - Identify the task shape and risk triggers.
   - Record `Activated Roles` and `Not Activated` in the plan.

2. **Analyze**
   - Activated decision and review roles produce only their exclusive outputs.
   - Findings must separate defects, product recommendations, and deferred work.

3. **Approve scope**
   - The Product Scope Owner summarizes product scope when product judgment is
     required.
   - The user approves scope and any workflow exception.

4. **Write the integrated plan**
   - A plan document is required before file edits unless the user explicitly
     waives it.
   - The plan is the implementation boundary and must include:
     - approved scope and explicit exclusions
     - acceptance criteria
     - Activated Roles and Not Activated
     - exact files and implementation steps
     - Domain Boundary and Dependency Direction
     - Coupling and Cohesion Review
     - Pythonic Code Design for backend work
     - TDD checkpoints for backend work
     - verification commands and expected evidence
     - deferred work

5. **Implement**
   - Backend work follows the Backend TDD Cycle below.
   - Frontend-only work follows the Frontend Work Policy.
   - Implementers edit only the approved files and behavior.

6. **Review each task**
   - Check scope, role boundaries, architecture decisions, TDD evidence,
     over-engineering, security, operations, UX, and regression impact as
     applicable before moving to the next task.

7. **Verify and report**
   - Run fresh commands, read full output, and check exit status.
   - The Quality Verification Lead maps evidence back to acceptance criteria.
   - Do not claim completion beyond observed evidence.

8. **Document post-work state for file-changing implementation**
   - When an implementation task changes files, the implementation role that
     owns those files writes the required refactoring or change log.
   - That implementation role updates `.docs/project-status.md` with status,
     evidence, deferred work, and links to the plan and work log.
   - Review-only tasks do not edit files. They report findings in chat or in a
     separately approved review artifact.

## Backend TDD Cycle

This cycle is mandatory for backend behavior changes.

1. The Backend TDD Coach defines one smallest observable behavior test.
2. The Backend & Integration Engineer writes only that test.
3. Run it and confirm it fails for the coach's expected reason.
4. If it fails for another reason, repair the test or setup before production
   changes.
5. Implement the minimum behavior needed for Green.
6. Run the targeted test and relevant regression slice.
7. The coach reviews evidence and decides whether refactoring is allowed.
8. Refactor only while tests remain Green.
9. Repeat one behavior at a time.

Backend test rules:

- No production behavior before a failing test.
- A test that passed before implementation does not prove new behavior.
- Test public behavior at model, service, command, task, or API boundaries.
- Avoid private implementation assertions and excessive mocking.
- Extract fixtures only when they improve intent and remove real duplication.
- Cross-domain behavior should be tested at service or API boundaries.
- Documentation-only work uses documentation verification, not artificial tests.

## Frontend Work Policy

Django templates, CSS, browser JavaScript, SSR binding, and status-button fetch
wiring are exempt from the backend TDD cycle.

- Do not create automated tests for purely presentational layout, spacing,
  sizing, visual state, transition, animation, or markup rearrangement.
- Verify frontend work with HTTP render checks, browser screenshots at agreed
  viewports, interaction click-through, console inspection, and accessibility
  checks appropriate to scope.
- A Playwright regression is allowed only for a concrete measurable acceptance
  gate such as an overflow budget, minimum touch-target size, line-clamp height,
  or post-interaction focus target.
- Any backend endpoint, validation, persistence, or business rule introduced for
  frontend work still follows the Backend TDD Cycle.
- Every frontend review includes both the Web Experience Designer and Browser
  Interaction Reviewer.
- Frontend implementation requires an approved `prompt_plan.md` and a completed
  `.docs/frontend-integration-changelog.md` unless the user explicitly approves
  different document locations.

## Domain And Design Policies

### Domain Boundary And Dependency Direction

- Each affected domain owns its invariants, state transitions, and persistence
  decisions.
- Business rules belong in models, domain functions, or application services,
  not HTTP views, serializers, templates, or tests.
- Serializers and forms own input validation and representation boundaries.
- Cross-domain workflows use a clearly named application service with a
  documented one-way dependency and transaction owner.
- Existing coupling must not expand silently. Defer broader decoupling with a
  trigger condition when it exceeds scope.

### Coupling And Cohesion Review

Every backend design and task review must answer:

1. Does this change lower or at least avoid increasing coupling?
2. Does it keep related business rules cohesive inside the owning domain?

If either answer is no or unclear, stop until the plan is revised or the user
explicitly accepts the tradeoff.

### Pythonic Code Design

- Prefer explicit, readable Python and framework-native Django/DRF extension
  points.
- Use model methods or constraints for invariants, querysets/managers for
  reusable query intent, serializers/forms for boundary validation, application
  services for orchestration, and transactions for atomic changes.
- Prefer small named functions and explicit data flow.
- Avoid silent mutation, procedural views that mix responsibilities, broad base
  classes, hidden metaprogramming, global state, and premature frameworks.
- Direct Django/DRF code is preferable when it is the clearest approved design.

### Over-Engineering

- Build the smallest design that meets current acceptance criteria.
- Do not add generalized configuration, extension points, or abstractions for
  hypothetical needs.
- Do not optimize without a current requirement or measured problem.
- Record larger improvements as deferred work instead of expanding scope.

## Review Gate After Each Task

Before the next task, confirm:

- The diff stays inside approved scope and file ownership.
- Activated roles delivered their required output; unrelated roles stayed idle.
- Domain boundaries and dependency direction match the plan.
- Coupling did not increase without approval and cohesion remained stable.
- Backend business logic stayed out of HTTP and presentation layers.
- Backend TDD evidence shows expected Red, minimum Green, then Refactor.
- Frontend evidence follows the frontend policy when applicable.
- No unnecessary abstraction or unrelated cleanup was introduced.
- Security, operations, reliability, UX, and QA impacts are addressed or
  explicitly deferred according to activated roles.
- Fresh verification output and exit status support every completion claim.

## Deferred Refactoring Note

```text
Deferred Refactoring Note

- Topic:
- Why it is not part of the current scope:
- Why it may be needed later:
- Trigger condition:
- Expected change location:
- Related tests:
```

## Reporting Rules

- State exactly what was verified and with which command.
- State what was not verified.
- Do not claim tests, builds, lint, browser behavior, or deployment pass without
  fresh evidence.
- Keep defects separate from recommendations and deferred work.
- Include file and line evidence for review findings whenever source exists.
- Do not hide unresolved risk.

## Git Commit Convention

Allowed prefixes:

- `feat`: new functionality
- `fix`: bug fix
- `docs`: documentation
- `style`: code formatting only
- `design`: user-facing UI design
- `test`: test code
- `refactor`: production refactoring
- `build`: build files or dependencies
- `ci`: CI configuration
- `perf`: performance
- `chore`: maintenance
- `rename`: rename only
- `remove`: deletion only

Format:

```text
<type>(<scope>): <subject>

<body>

<footer>
```

Rules:

- `scope` is optional and names the affected area.
- Start `subject` with a capital letter, use an imperative verb, omit the final
  period, and keep it within 50 English characters.
- Wrap body lines at 72 characters and explain what changed and why.
- The footer is optional and may use `Closes`, `Fixes`, `Resolves`, `Ref`, or
  `Related to`.

Convention source: https://nohack.tistory.com/17
