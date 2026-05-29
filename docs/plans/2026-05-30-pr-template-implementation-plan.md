# PR Template Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a repository-level GitHub pull request template that enforces OshiLog's review and verification habits.

**Architecture:** Store the template in GitHub's conventional `.github/pull_request_template.md` location. Keep it as a single Markdown file with concise sections aligned to `AGENTS.md`; do not add multiple template variants.

**Tech Stack:** GitHub pull request template Markdown.

---

## Approved Scope

Create:

- `.github/pull_request_template.md`

Do not modify application code.

Do not change existing unrelated worktree changes, including the current
`.gitignore` modification.

## Acceptance Criteria

- The PR template exists at `.github/pull_request_template.md`.
- The template includes these sections:
  - Summary
  - Scope
  - Verification
  - Review Checklist
  - Documents
  - Deferred Work
- The checklist reflects:
  - TDD behavior-first discipline,
  - domain boundary checks,
  - low coupling and high cohesion,
  - Pythonic design,
  - security/reliability/infra/UX impact review,
  - documentation updates.
- `git diff --check` reports no whitespace errors.

## Task 1: Add PR Template

**Files:**

- Create: `.github/pull_request_template.md`

**Step 1: Create the template**

Add a concise Markdown template with the approved sections.

**Step 2: Verify file content**

Run:

```bash
rg -n "Summary|Scope|Verification|Review Checklist|Documents|Deferred Work" .github/pull_request_template.md
```

Expected: every required heading is present.

**Step 3: Verify whitespace**

Run:

```bash
git diff --check
```

Expected: no output.

## Task 2: Commit Template Work

**Files:**

- Add: `.github/pull_request_template.md`
- Add: `docs/plans/2026-05-30-pr-template-design.md`
- Add: `docs/plans/2026-05-30-pr-template-implementation-plan.md`

**Step 1: Review status**

Run:

```bash
git status --short
```

Expected: only the PR template and plan documents are included in this task.
The unrelated `.gitignore` change remains unstaged.

**Step 2: Commit**

Run:

```bash
git add .github/pull_request_template.md docs/plans/2026-05-30-pr-template-design.md docs/plans/2026-05-30-pr-template-implementation-plan.md
git commit -m "docs(github): Add PR template"
```
