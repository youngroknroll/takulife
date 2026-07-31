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

Version-controlled (`docs/`). These survive a clone, a reset, and a working-copy
cleanup. Anything that must not be lost belongs here.

- Current backlog: `docs/backlog.md`
- Deployment runbook: `docs/deploy-runbook.md`
- Operations runbook: `docs/operations-runbook.md`
- Event operations criteria: `docs/event-operations-criteria.md`
- Backend technical records: `docs/BE/` (and `docs/DB/`, `docs/FE/` as they are
  needed) — a record that states a guardrail belongs here, not in `.docs/`

Working notes (`.docs/`). **This tree is git-ignored.** Treat every file in it as
disposable: a file that is missing is routine housekeeping, not a lost artifact,
and must never be reported as an accident or recreated on a guess. Never leave a
rule, an approved decision, or a live backlog here alone — promote it to `docs/`.

- Current backlog and next-action index: `docs/backlog.md`
- Optional local continuity notes: `.docs/project-status.md`
- Product direction: `.docs/proposal/2026-07-13-takulife-product-direction-redefinition.html`
- Backend plans and technical records: `.docs/BE/`
- Database, schema, and migration records: `.docs/DB/`
- Frontend plans and technical records: `.docs/FE/`
- Historical archive, read-only: `.docs/plans/`, `.docs/refactoring/`

New plans and technical records go under `BE/`, `DB/`, or `FE/` by owning area.
The same three names exist under both trees and the choice between them is what
the document does, not what it is about: a draft, a scratch measurement, or a
note only this week needs goes to `.docs/`; a record that states a guardrail a
later worker could break goes to `docs/`, because that is the tree that survives.
Do not add new files to `.docs/plans/` or `.docs/refactoring/`; those hold prior
work and are kept for background only.

### Reference Loading Order

Read only the smallest set that owns the task:

1. Always read this guide.
2. Read `docs/backlog.md` for current priority; add the matching durable
   runbook only for deployment, operations, or event-operations work.
3. Read the active area plan or technical record in `.docs/BE/`, `.docs/DB/`,
   or `.docs/FE/` only when it exists and directly covers the workstream.
4. Read `.docs/plans/` or `.docs/refactoring/` only to understand history.
   They never override this guide or provide a current command, test boundary,
   approval requirement, or acceptance criterion.

Do not load every document by default. A missing local note is normal; verify
the current code and this guide instead of recreating it or inferring a rule.

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

6. **External Git publication and merge authority are separate.**
   - After a planned stage has fresh verification evidence, commit, push, and
     pull-request creation proceed automatically under this project's standing
     approval.
   - A pull request merge requires the user's explicit approval for that pull
     request. The only exception is an expressly granted standing automatic-
     merge approval; its scope and duration must be recorded before use.

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

Backend TDD Coach output contract (see Test Authoring Policy for field
meaning):

```text
Scenario ID:
Business behavior:
Given:
When:
Then:
Next smallest test:
Test name (Korean):
Required verification boundary:
Boundary rationale:
DB/HTTP required:
Expected Red reason:
Minimum Green boundary:
Refactoring allowed: No
Verification command:
```

After Green:

```text
Scenario ID:
Green evidence:
Regression impact:
Test List status: Green | Refactored
Refactoring allowed: Yes | No
Permitted refactoring scope:
Newly discovered scenarios:
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

Backend completion checklist (in addition to the acceptance-criteria matrix
above), per the Test Authoring Policy:

- Do test names match the actual behavior of their assertions?
- Does every new or changed test link to a Scenario ID in the Test List?
- Does the Test List's Given-When-Then match the actual arrange, act, and
  assert in the test?
- Does every completed scenario have Red-for-the-expected-reason and fresh
  Green evidence?
- Is every unimplemented scenario marked `Deferred` with a reason, not left
  blank?
- Does the test pin implementation details it does not need to pin?
- Could the same behavior be proven at a lower, faster boundary?
- Is the same business rule duplicated at another layer?
- Does a fixture hide an important precondition?
- Do deleted or merged tests retain evidence that the protected behavior
  still holds?
- Do overall runtime and stability targets hold?
- Is test-only configuration kept outside the production boundary?
- Do all test commands and package changes follow the `uv`-only policy?

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
- For frontend implementation, produces an experience specification before
  editing and a source-grounded conformance verdict after browser verification.
- Does not review JavaScript state-machine robustness in isolation; that belongs
  to the Browser Interaction Reviewer.

### Browser Interaction Reviewer

- Owns runtime browser behavior between static design and backend response.
- Reviews async state and retry behavior, transition fallbacks, focus and scroll
  management, keyboard operation, live regions, touch targets, sticky and
  z-index geometry, reduced motion, and empty-state recovery.
- Grounds every defect in `file:line` evidence and a concrete failure scenario.
- Searches repeated patterns repository-wide before calling a defect local.
- For frontend implementation, produces interaction criteria before editing and
  a source-grounded conformance verdict after browser verification.
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
   - Read this guide, the relevant version-controlled backlog or runbook, the
     active canonical plan, and relevant code. Read local continuity notes only
     when they are present and directly relevant.
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
   - Reuse the existing canonical plan for the workstream whenever one exists.
     Do not create a date-named plan for each subtask. A new plan is allowed
     only when no relevant canonical plan exists, and it becomes the future
     update target for that workstream.
   - The plan is the implementation boundary and must include:
     - approved scope and explicit exclusions
     - acceptance criteria
     - Activated Roles and Not Activated
     - exact files and implementation steps
     - Frontend Review Evidence for frontend implementation
     - Domain Boundary and Dependency Direction
     - Coupling and Cohesion Review
     - Pythonic Code Design for backend work
     - TDD checkpoints for backend work
     - verification commands and expected evidence
     - deferred work
     - documentation target and handoff-critical conditions

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
   - Record information only when a later worker could otherwise make a
     mistake: a user decision, non-obvious rationale, contract boundary,
     unresolved risk, verification limitation, or other durable constraint.
   - Update the existing technical document for the affected subject. Do not
     create a routine work log. Create a new subject document only when no
     relevant canonical document exists; it then becomes the update target.
   - Keep each handoff record compact. Include only applicable fields:
     `Current fact`, `Decision`, `Guardrail`, `Known gap`, and `Evidence`.
   - Update `docs/backlog.md` only when the durable current state or next action
     changes. Keep it a concise index with links, not a task diary.
   - Put major changes, decisions, and unresolved problems in the related
     subject document under `docs/`; local `.docs/` notes may supplement a
     handoff but are not the only copy of a durable fact.
   - Review-only tasks do not edit files. They report findings in chat or in a
     separately approved review artifact.

## Code Comment Policy

This policy applies to ordinary code comments and docstrings. The test-specific
Given-When-Then guidance in the Test Authoring Policy remains separate.

**Code comes before comments.** Code that needs a comment to be understood is
code to rewrite, not code to annotate. Reach for a clearer name, a smaller
function, or a better structure first. The best outcome for most comments is
deletion.

A comment is still warranted in four cases:

- the code is unavoidably complex;
- a detail is needed for precision;
- the context lives outside the code (another repository, package, or external
  specification);
- ambiguity has to be removed.

When one is warranted:

- Use short, plain Korean that a non-developer can understand. If a technical
  term is unavoidable, explain its meaning in the surrounding words.
- Keep one comment to one or two lines. Put longer design rationale in the
  approved canonical technical document under `docs/` instead.
- Do not translate a name, condition, loop, or other self-evident statement
  into prose.
- Preserve the reason behind non-obvious security, privacy, data-preservation,
  external-integration, performance, and temporary-compatibility decisions
  when that reason would otherwise be lost. Code cannot carry these.
- Do not use a comment as a change history, and do not use one to excuse
  unclear or wrong code — rewrite the code. Update or remove a comment
  whenever its related code changes.

### TODO Markers

- `TODO(<scope>):` marks **a place, not a task**: "this is where X attaches".
  It belongs in the code because its whole value is the location.
- Anything carrying scope, priority, or a schedule is a work item and belongs
  in `docs/backlog.md`. Do not grow a second backlog inside the code.
- Do not copy TODO locations into any document. A `file:line` list goes stale
  on the next edit above it — backlog F2 was exactly that failure, and it was
  resolved by deleting the line numbers. Find them with `rg "TODO\("` instead.
- **Do not use `FIXME`.** Knowing code is wrong and leaving a marker is the
  excuse this policy forbids. Fix it, or open a backlog item.

Example — avoid a code translation:

```python
# 사용자가 로그인했는지 확인한다.
if request.user.is_authenticated:
```

Prefer a brief explanation of the user-facing reason:

```python
# 수집 기록은 소유자만 볼 수 있어 다른 사람에게 노출되지 않는다.
if item.owner_id == request.user.id:
```

## Test Authoring Policy

This policy binds every backend test. Historical test-policy records may explain
past measurements, but this section is the current test boundary and workflow.

### Automated Tests Cover Backend Logic Only (2026-07-22 user decision)

Automated tests exist for backend logic: domain rules, services, persistence,
HTTP request/response behavior, authorization, and settings or migration
contracts. Nothing else is a test target.

- Do not write browser or end-to-end tests. The `e2e` marker, `tests/e2e/`,
  the `pytest-playwright` plugin, and the CI e2e job were deleted on
  2026-07-22.
- Do not test templates, CSS, browser JavaScript, layout, spacing, sizing,
  visual state, transition, animation, or touch-target geometry.
- Browser behavior is verified by driving a real browser and reported as
  evidence in the handoff or technical record, never encoded as a regression
  test.
- **Playwright remains installed as a verification tool, not a test
  framework.** Reviewers drive Chromium with it - ad-hoc scripts against the
  local dev server, or the Chrome DevTools MCP tools - to measure geometry,
  overflow, focus, and interaction state. What is forbidden is committing that
  measurement as a test; running it to produce evidence is expected.
- When a defect is browser-observable but caused by backend logic, descend to
  the owning backend layer and test it there.

### Test List Is The Starting Point

A backend behavior change starts from a `Test List` in the approved
implementation plan, not from a test or production function. The Test List
breaks a requirement into executable examples; it is not a fully designed test
suite written up front. Each entry carries at least these fields:

| Field | Meaning |
|---|---|
| Scenario ID | Stable identifier linking the plan and the test |
| Business behavior | One sentence a user could understand |
| Given | State relevant to the behavior |
| When | The one behavior under test |
| Then | The externally observable result |
| Verification boundary | One of `unit`, `domain`, `web`, `contract`, `slow` |
| Boundary rationale | Why a higher-cost boundary is required, or why a lower boundary suffices |
| Test name | The actual Korean pytest function name or parametrized case ID |
| Status | `Pending`, `Red`, `Green`, `Refactored`, `Deferred` |
| Evidence | Red/Green commands and key results, or a pointer to the handoff or technical record |

The default relationship is one scenario to one test. Only these exceptions
are allowed:

1. Same-rule data variations may be expressed as one parametrized test with
   Korean `ids`.
2. If one scenario must be verified at more than one layer, list each test's
   owned contract as a separate Test List entry.
3. Split the scenario when it has a distinct core `When` or an independent
   observable result.

Before renaming, moving, merging, or deleting an existing test, first restore
the behavior it currently protects into a domain Test List entry (Scenario ID
mapped to the existing pytest node ID). Do not attach a scenario after the
fact just to make an existing test look compliant with this policy.

### Given-When-Then Is A Meaning Rule

Given-When-Then describes how a scenario and its test connect meaning, not a
mandatory comment format.

- **Given** holds only the state needed to understand the core behavior; do
  not hide an important precondition inside a fixture default or helper.
- **When** holds exactly one business behavior per test; the core behavior
  must not run implicitly inside a helper.
- **Then** holds observable results — return values, public responses,
  persisted state, or an allowed side effect; do not hide the core assertion
  inside a helper.
- Multiple assertions are allowed only when they describe one result state;
  independent results get separate scenarios.
- Exception and rejection tests still express `When` as the attempted
  behavior and `Then` as the observed failure contract.
- Do not force `# Given` / `# When` / `# Then` comments on short, self-evident
  tests. Use them when setup is long or the boundary call spans multiple
  lines and the three parts would otherwise be unclear.

### DAMP Over DRY

- Prefer duplication that reveals meaning over abstraction that hides it.
- Keep the core precondition, user behavior, and observed result directly in
  the test body.
- Extract only meaningless setup noise (object creation, login, image byte
  generation) into fixtures or factories.
- Never hide the behavior under test or its core assertion inside a helper.
- A shared fixture's default value must never hide an important business
  precondition.
- One test describes one business behavior; multiple assertions are allowed
  only for one result state.

### Result-Oriented Verification

- Verify return values, responses, persisted state, and allowed side effects
  over internal function calls.
- Do not pin internal function names, call order, private APIs, or ORM
  authoring style as an external contract in an ordinary behavior test.
- Use mocks to cut external boundaries, inject failures, or control
  time/network — not to assert that an implementation function was called.

The following remain legitimate to verify directly, because the interaction
itself is the contract. Mark these `contract` rather than treating them as
ordinary behavior tests:

- domain dependency direction and forbidden imports;
- transactions, atomicity, and idempotency;
- prevention of personal-data leakage;
- blocking outbound network or LLM calls;
- exactly-once audit or analytics events;
- approved query counts or performance budgets;
- settings, migration, and deployment contracts.

### Korean, Behavior-Centered Naming

- Test function names are written in Korean.
- Base grammar: `상황에서_행위하면_관찰가능한_결과가_된다`.
- Use domain language (user, staff, event, visit record, collection, and so
  on).
- Do not use implementation-centered names such as `returns_200`,
  `calls_service`, `uses_query`, or `response_has_context`.
- Include an HTTP status code in the name only when it is essential to
  distinguish a public protocol contract.
- Parametrized `ids` are also Korean case names.
- File names stay ASCII `test_*.py` for pytest discovery and tooling
  compatibility.

### Verification Boundaries

Prove a behavior at the lowest, fastest boundary that can prove it.

| Layer | Owns | Default resources |
|---|---|---|
| `unit` | Pure functions, parsing, value rules | No DB or HTTP |
| `domain` | Model/service business behavior and invariants | DB as needed |
| `web` | HTTP request/response, auth, permission, and error translation | Django/DRF test client |
| `contract` | Architecture, settings, migration, and performance | Minimum resources per contract |
| `slow` | Security lockouts, real files, and abnormal-recovery scenarios | Explicit opt-in |

There is no browser layer. `web` is the highest boundary; behavior that only a
real browser could observe is verified manually, not by an automated test.

Do not repeat the same business rule across layers:

- domain tests prove the rule itself;
- web tests add only the HTTP translation of auth, input, and domain errors.

A lower layer's happy path may be re-confirmed at a higher layer, but do not
repeat every boundary value and exception at every layer above it.

### Speed And Isolation

- A global autouse fixture must never promote every test to DB access; DB
  dependencies are declared explicitly (`pytest.mark.django_db`, or the `db`
  or `transactional_db` fixture).
- A plain user factory defaults to an unusable password unless a test needs a
  real, working password.
- Authentication-behavior tests run under the test-only fast password hasher
  (`config/settings_test.py`). Production `config/settings.py` never sets a
  fast hasher.
- Test settings must never be loadable from a production entry point or
  deploy config; enforced by `tests/core/test_test_settings_boundary.py`.

## Backend TDD Cycle

This cycle is mandatory for backend behavior changes and follows Canon TDD:
build the Test List, take one item to Red, make it Green, refactor only if
needed, then fold anything newly discovered back into the Test List.

1. Select one item from the implementation plan's Test List — the smallest,
   most informative scenario not yet Green.
2. The Backend TDD Coach defines that scenario as one smallest observable
   behavior test.
3. The Backend & Integration Engineer writes only that test.
4. Run it and confirm it fails for the coach's expected reason (Red).
5. If it fails for another reason, repair the test or setup before production
   changes.
6. Implement the minimum behavior needed for Green.
7. Run the targeted test and relevant regression slice.
8. The coach reviews evidence and decides whether refactoring is allowed.
9. Refactor only while tests remain Green; refactoring is optional and scoped
   to the current scenario.
10. Record any newly discovered scenario in the Test List instead of folding
    it into the current test.
11. Repeat one behavior at a time until the Test List is empty.

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
  viewports, interaction click-through, and console inspection appropriate to
  scope. Drive the browser with Playwright or the Chrome DevTools MCP tools and
  report the measurements as evidence; the run itself is the verification, and
  its output is never committed as a test.
- Do not write browser or end-to-end tests. The e2e suite was deleted on
  2026-07-22 by user decision; overflow budgets, touch-target sizes, line-clamp
  heights, and focus targets are measured on demand, not enforced by a gate.
- Any backend endpoint, validation, persistence, or business rule introduced for
  frontend work still follows the Backend TDD Cycle.
- Every frontend review includes both the Web Experience Designer and Browser
  Interaction Reviewer.
- The shared design-rule protocol is abolished (2026-07-22 user decision; the
  former `.docs/design-rules.md` §1-§3, since deleted). Brand contrast ratios,
  the 44px touch-target
  duty layer, and the motion pause contract are no longer compliance gates, and
  no reviewer may require a documented "user-approved exception" to build what
  the design intent specifies. Design intent - the mock and the user's
  instruction - is the standard. Reviewers may still note these topics as
  information, and functional defects such as broken layout, overflow,
  keyboard-unreachable controls, focus traps, and unreadable text remain
  defects.
- Frontend implementation requires an approved plan and a completed technical
  record under `.docs/FE/` unless the user explicitly approves a different
  document location. The former `.docs/frontend-integration-changelog.md` was
  deleted; do not recreate it.
- The design-review queue and every backlog derived from the superseded mocks
  are abolished (2026-07-29 user decision) together with the mock rework. Do not
  recreate `.docs/design-review-queue.md`, and do not schedule work from a
  mock-derived backlog without first confirming the item against current code.

### Frontend Dual Review Gate

Every frontend implementation requires actual output from both the Web
Experience Designer and Browser Interaction Reviewer before and after editing.
Listing a role under `Activated Roles` is routing evidence, not review evidence.

Before implementation:

1. The integrated plan selects a review depth and explains why.
2. The Web Experience Designer provides an implementation-ready experience
   specification.
3. The Browser Interaction Reviewer provides interaction and accessibility
   criteria.
4. The Frontend Implementation Engineer must not edit until both outputs exist.

After implementation and the planned browser verification:

1. The Web Experience Designer reviews the implementation against the approved
   experience specification.
2. The Browser Interaction Reviewer reviews the implementation against the
   approved interaction criteria.
3. Each reviewer returns `Conforms`, `Deviates`, or `Unverified` with the
   evidence reviewed. A `Deviates` verdict requires a deviation from the
   approved specification or a functional defect; abolished design-rule topics
   (contrast ratio, 44px touch target, motion pause) cannot produce `Deviates`
   and are reported as information only.
4. The Quality Verification Lead must not mark the frontend task complete unless
   both verdicts are `Conforms`, or the user explicitly accepts the stated
   residual risk for a `Deviates` or `Unverified` verdict.

Review depth is proportional to risk, but neither reviewer nor either verdict
may be skipped:

- `Light`: copy, isolated color, or similarly narrow changes. A concise
  no-impact or conformance statement is sufficient.
- `Standard`: component, form, layout, or responsive changes. Review relevant
  viewports, static accessibility, focus and keyboard implications, and
  recovery.
- `High`: navigation, information architecture, async state, modal, sticky
  geometry, upload, or cross-page pattern changes. Review repository-wide
  patterns and full browser evidence appropriate to the risk.

Every frontend implementation plan includes a `Frontend Review Evidence`
section containing:

- review depth and rationale;
- Web Experience Designer pre-implementation specification;
- Browser Interaction Reviewer pre-implementation criteria;
- planned browser evidence;
- both post-implementation verdicts and their evidence;
- Quality Verification Lead completion decision.

For frontend review-only tasks, both reviewers must each deliver their normal
review output. No implementation-phase fields are required, but role names alone
still do not count as review evidence.

## Package And Command Policy (uv-only)

Python packages, virtual environments, and command execution are managed only
with `uv`. This section is the current command policy.

- The dependency source of truth is `pyproject.toml`; the lock source of truth
  is `uv.lock`.
- Add a runtime dependency with `uv add <package>`.
- Add a dev or test dependency with `uv add --group dev <package>`.
- Remove a dependency with `uv remove <package>`.
- Sync the environment with `uv sync`.
- Run tests, Django commands, and management commands with `uv run ...`.
- CI and deployment one-off Python expressions also use `uv run python ...`.
- CI and deployment use `uv sync --frozen` (add `--no-dev` for a production
  image where appropriate).
- `pip install`, `python -m pip`, manual `site-packages` edits, and a parallel
  `requirements.txt` are forbidden.
- Verify a dependency change in `pyproject.toml` and `uv.lock` together, in the
  same change.
- A new test-convenience package requires an approved plan and explicit user
  approval; do not add one to solve a problem existing tooling already solves.

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

### Error Handling And Logging

- Translate expected domain failures at the HTTP boundary. Do not use broad
  exception handling to hide an unknown failure.
- A catch-all handler must log, re-raise, or carry an `# except-ok: <reason>`
  marker explaining the deliberate suppression. Bare `except:` is forbidden.
- Production code does not use `print()`. Module loggers use
  `logging.getLogger(__name__)`, English-ASCII messages, and lazy `%`-style
  formatting for the first message argument. User-facing Korean messages are
  not logger messages and are outside this rule.
- `tests/core/test_error_logging_policy.py` enforces these deterministic rules
  as an AST contract guard. Historical policy plans are background only.

## Review Gate After Each Task

Before the next task, confirm:

- The diff stays inside approved scope and file ownership.
- Activated roles delivered their required output; unrelated roles stayed idle.
- Domain boundaries and dependency direction match the plan.
- Coupling did not increase without approval and cohesion remained stable.
- Backend business logic stayed out of HTTP and presentation layers.
- Backend TDD evidence shows expected Red, minimum Green, then Refactor.
- Frontend evidence follows the frontend policy when applicable.
- Frontend editing did not start before both required pre-implementation review
  outputs existed.
- Frontend completion evidence includes both post-implementation verdicts and
  the Quality Verification Lead's decision.
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

### Numbers In Documents (binding)

A count written in a document is a claim, and four of them have already
misdirected work here: `docs/backlog.md` A3 said 8 unguarded sites and
measurement found 2; A4 said 41 risky assertions and measurement found 1; A1
read as not started while its fix had merged hours earlier; the boundary-guard
record said 34 entries over 41 files when the truth was 18 unique files and 48.
Every one of them read as fact. Three of the four were written by an
orchestrator who had already run commands that session, so recent measurement
elsewhere is not protection.

- **Name the unit.** `34` meant registrations, not files. A bare count that
  does not say what it counts is not evidence and must not size work.
- **Mark how it was obtained.** `[실측]` for a number produced by running a
  command; `[코드]` for one read from source. A `[코드]` number is an estimate.
- **Record the reproducing command** whenever it is short enough to inline.
- **Re-measure before acting on any number an earlier session wrote**,
  including your own from earlier in the same session. Documents go stale
  within hours.
- **When measurement contradicts the document, correct it in the same commit**
  and keep the original text marked as the pre-measurement record. The gap
  between the two is what makes the next reader check instead of trust.

Prefer a set operation over a hand count: `git show <ref>:<file>` parsed with
`ast`, then compared against the live set, settles in seconds what an estimate
gets wrong.

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

### Commit And PR Cadence

- Commit per small, self-contained feature: each commit passes tests on its
  own and can be reverted independently. Separate rename, move, delete, and
  behavior changes into their own commits.
- Open a pull request automatically at the completion of each large stage
  (a planned track, phase, or a coherent group of small-feature commits) —
  a per-PR approval prompt is not required. Keep unrelated concerns in
  separate stages, and therefore separate PRs.
- Standing approval covers commit, push, and opening the PR after fresh planned
  verification. Merging still requires per-PR user approval unless the user has
  expressly granted and recorded standing automatic-merge approval.
- `prompt_plan.md` and other pre-existing uncommitted changes not produced by
  the current task stay unstaged; stage files explicitly, never `git add -A`.
