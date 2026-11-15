---
name: review
description: Review git diff, SQL safety, untrusted document sanitization, and architectural contracts in Claude.md using the code-reviewer subagent.
---

# Review Workflow (NovaEnterprise)

Use this skill to audit proposed code changes, git diffs, and security boundaries before merging or finalizing work.

## Workflow Steps

1. **Inspect Git Diff**:
   - Obtain the current diff via `git diff` or review untracked modified files.

2. **Invoke Code Reviewer Subagent**:
   - Spawn the `code-reviewer` subagent (`Model: flash`, `Role: code-reviewer`).
   - Task Prompt template:
     ```text
     Audit the git diff and proposed changes for compliance with NovaEnterprise contracts in Claude.md.
     Audit Checklist:
     1. SQL Injection: Are all SQL queries validated with validate_sql() against an allowlist? Are there any f-strings or raw string interpolations in SQL?
     2. Untrusted Documents: Are external vendor notes or user documents properly wrapped and isolated so they cannot be executed as agent instructions?
     3. Architectural Boundaries: Does the code adhere to api → services → repositories → models without circular imports?
     4. Test Isolation: Are tests strictly offline (LLM_PROVIDER=fake, in-memory stores)?
     Provide a structured review report and clear verdict (APPROVE or REQUEST_CHANGES).
     ```

3. **Triage Findings**:
   - Address any Critical Blockers or Contract Violations before concluding the task.

