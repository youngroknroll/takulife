# OshiLog Project Status

## Current Focus

Backend follow-up hardening is implemented on the `backend-follow-up` branch.
The change preserves active API contracts while tightening published-event query
reuse, archive service boundaries, draft URL fetch safety, duplicate race
handling, and direct-service update validation.

## Required Reading For Nearby Backend Work

Read in this order:

1. `AGENTS.md`
2. `.docs/plans/2026-06-24-backend-follow-up-design.md`
3. `.docs/plans/2026-06-24-backend-follow-up-implementation-plan.md`
4. `.docs/refactoring/2026-06-24-backend-follow-up-work-log.md`

## Verified

- Focused final regression:
  `106 passed in 10.44s`.
- Full pytest suite:
  `118 passed in 11.93s`.
- Django system check:
  `System check identified no issues (0 silenced).`
- Migration drift check using the worktree virtual environment:
  `No changes detected`.
- `git diff --check`: clean before final documentation.

## Not Verified

- Live external URL fetching against production DNS and network policy.
- PostgreSQL-backed behavior and concurrent duplicate writes on PostgreSQL.
- Manual API calls or browser behavior.
- Docker image build, GitHub Actions, and Render deployment.
- Production `manage.py check --deploy`.

## Deferred Work

- Remove inactive legacy archive models and views from `events` in a dedicated,
  migration-reviewed slice.
- Tune public event queries only after measured performance evidence.
- Introduce broader exception mapping only after the same contract appears in
  at least three active workflows.
- Consider DNS pinning if the deployment network does not provide an outbound
  proxy or egress policy that prevents DNS rebinding between validation and
  connection.
- Production media storage, PostgreSQL-backed CI, observability, and deployment
  work remain pending.

## Latest Documents

- `.docs/plans/2026-06-24-backend-follow-up-design.md`
- `.docs/plans/2026-06-24-backend-follow-up-implementation-plan.md`
- `.docs/refactoring/2026-06-24-backend-follow-up-work-log.md`
- `.docs/plans/2026-06-10-docker-render-deployment-design.md`
- `.docs/plans/2026-06-10-docker-render-deployment-implementation-plan.md`
