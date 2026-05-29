# OshiLog Agent Definition Plan

Date: 2026-05-28
Project root: `/Users/yeongroksong/Desktop/study/project/taku`

## Approved Scope

Create Claude-style project agent definition files based on `AGENTS.md`.

In scope:

- Add `.claude/agents/` definitions for every default role in `AGENTS.md`.
- Preserve the project operating boundaries for analyst and implementer roles.
- Keep analyst agents read-only by instruction and by limited tool declarations.
- Keep implementer agents constrained to approved scope, TDD, verification, and
  post-work documentation.
- Update project documentation with verification evidence.

Out of scope:

- Changing application source code.
- Changing tests or runtime behavior.
- Creating new project workflow rules beyond `AGENTS.md`.
- Adding generalized automation around agent dispatch.

## Acceptance Criteria

- `.claude/agents/` contains one agent file for each default role:
  - PO / General Manager
  - Tech Lead / Architect
  - TDD Expert
  - Infra / DevOps
  - QA
  - Security / Reliability
  - Web UX / UI Designer
  - Web Frontend Developer
  - Senior Dev / Codex
- Each agent file tells the role to read and follow project `AGENTS.md`.
- Each agent file declares the model assigned in `AGENTS.md`.
- Analyst agents explicitly state that they must not edit files.
- Implementer agents explicitly state their approved write boundaries.
- Verification uses fresh filesystem checks for the created files.

## Implementation Steps

1. Create `.claude/agents/` if absent.
2. Add one Markdown agent definition per default role.
3. Add the role model from `AGENTS.md` to each agent frontmatter.
4. Make the agent descriptions specific enough for automatic selection.
5. Add a refactoring/work log for this task.
6. Update `docs/project-status.md`.
7. Run fresh verification commands.

## TDD Checkpoints

This task creates agent configuration and documentation only. It does not change
production behavior, so there is no application behavior test to drive first.

Verification checkpoint:

- First verify the target agent files are absent or incomplete.
- Add the agent definition files.
- Verify the expected count and frontmatter names with shell commands.

## Verification Commands

```bash
find .claude/agents -maxdepth 1 -type f -name '*.md' | sort
```

```bash
rg '^name:|^description:' .claude/agents docs/plans/2026-05-28-oshilog-agent-definition-plan.md docs/refactoring/2026-05-28-agent-definition-work-log.md docs/project-status.md
```

```bash
rg '^model:' .claude/agents
```

## Deferred Work

No deferred refactoring is required for this task. Future agent automation or
agent memory conventions should be proposed separately if needed.
