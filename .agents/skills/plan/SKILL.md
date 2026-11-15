---
name: plan
description: Design an architectural or implementation plan in docs/plans/ using the planner subagent before writing code for NovaEnterprise.
---

# Plan Workflow (NovaEnterprise)

Use this skill when you need to plan a feature, architectural refactoring, multi-store RAG routing change, or database migration for NovaEnterprise.

## Workflow Steps

1. **Clarify Objectives**:
   - Consult `Claude.md` to confirm system specifications, domain models, and constraints.
   - Check if an existing plan or ADR already covers the topic in `docs/plans/` or `docs/adr/`.

2. **Invoke Planner Subagent**:
   - Spawn the `planner` subagent (`Model: pro`, `Role: planner`).
   - Task Prompt template:
     ```text
     Create a step-by-step implementation plan for <FEATURE/TASK> adhering to NovaEnterprise specifications in Claude.md.
     Write the plan to docs/plans/<task-slug>.md.
     Specify:
     1. Context & Goals
     2. Affected Files across backend/, agents/, rag/, and tests/
     3. Data Contracts & State Schemas
     4. Step-by-Step Task Breakdown with atomic verification criteria
     5. Offline Pytest Strategy (LLM_PROVIDER=fake, in-memory stores)
     ```

3. **Verify Plan**:
   - Ensure the plan adheres to the layer architecture: `api → services → repositories → models`.
   - Confirm offline test fixtures are specified.
   - Present the plan location and summary for review before implementation.

