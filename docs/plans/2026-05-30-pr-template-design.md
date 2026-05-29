# OshiLog PR Template Design

Date: 2026-05-30

## Approved Scope

Create a single GitHub pull request template for the repository.

The template should guide contributors to report:

- what changed,
- what is inside or outside the PR scope,
- what verification was run,
- whether design and code quality gates were checked,
- what documentation changed,
- what deferred work remains.

## Design

Use one repository-level template:

- `.github/pull_request_template.md`

Do not add multiple PR templates yet. A single template is enough for the
current team workflow and avoids unnecessary chooser configuration.

## Template Sections

The template should include:

- Summary
- Scope
- Verification
- Review Checklist
- Documents
- Deferred Work

The checklist should reflect the project operating guide:

- TDD order was followed when code behavior changed.
- Tests verify behavior, not private implementation details.
- Domain boundaries remain explicit.
- Coupling is low and cohesion is high.
- Pythonic design was checked.
- Security, reliability, infra, and UX impacts are addressed or documented.
- Post-work documents are updated when required.

## Verification

Because this is a GitHub metadata/documentation change, application tests are
not required. Verification should confirm:

- the template file exists,
- expected section headings are present,
- `git diff --check` reports no whitespace errors.

## Deferred Work

Deferred Refactoring Note

- Topic: Multiple PR templates by change type.
- Why it is not part of the current scope: A single template is sufficient for
  current OshiLog development.
- Why it may be needed later: The project may later need separate templates for
  feature, bugfix, docs-only, or release PRs.
- Trigger condition: PR authors repeatedly delete irrelevant sections or review
  workflows diverge by PR type.
- Expected change location: `.github/PULL_REQUEST_TEMPLATE/`.
- Related tests: Template presence and heading checks.
