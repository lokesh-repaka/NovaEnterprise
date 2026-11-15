---
name: implement
description: Implement approved code changes across backend/, agents/, and rag/ following a plan in docs/plans/ using the implementer subagent.
---

# Implement Workflow (NovaEnterprise)

Use this skill to execute code changes that have an approved plan in `docs/plans/` or a clear contract in `Claude.md`.

## Workflow Steps

1. **Locate Plan & Prerequisites**:
   - Verify that an implementation plan exists in `docs/plans/<task-slug>.md` and has been approved.
   - Read the affected source files and domain models before initiating modifications.

2. **Invoke Implementer Subagent**:
   - Spawn the `implementer` subagent (`Model: flash`, `Role: implementer`).
   - Task Prompt template:
     ```text
     Implement the code changes outlined in docs/plans/<task-slug>.md.
     Requirements:
     - Adhere strictly to the layer architecture: api → services → repositories → models.
     - Keep external integrations (vector store, graph store, LLM) encapsulated behind app.core abstractions.
     - Never execute raw unsanitized SQL; use validate_sql() with allowlisted schemas.
     - Verify Python syntax on all edited files (python3 -m py_compile <path>).
     - Report all modified files and any unaddressed tasks.
     ```

3. **Post-Implementation Verification**:
   - Run syntax verification (`python3 -m py_compile`).
   - Trigger the `test` workflow to run unit and integration tests against modified modules.

