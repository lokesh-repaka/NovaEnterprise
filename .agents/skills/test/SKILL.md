---
name: test
description: Run targeted offline pytest suites with fake LLM providers and in-memory stores using the test-engineer subagent.
---

# Test Workflow (NovaEnterprise)

Use this skill to execute unit, integration, or regression tests in `tests/` with strict offline isolation.

## Workflow Steps

1. **Target Selection**:
   - Identify targeted test files or directories (e.g., `tests/test_routing.py`, `tests/rag/`).
   - If no target is specified, default to fast unit tests: `tests/unit/`.

2. **Invoke Test Engineer Subagent**:
   - Spawn the `test-engineer` subagent (`Model: flash`, `Role: test-engineer`).
   - Task Prompt template:
     ```text
     Execute targeted pytest tests for <TARGET_PATH>.
     Environment:
     - LLM_PROVIDER=fake
     - VECTOR_STORE=memory
     - GRAPH_STORE=memory
     Command:
     pytest -v <TARGET_PATH>
     
     Verify:
     1. Exact citation resolution and evidence shapes on RAG endpoints.
     2. Zero external network calls or unmocked API attempts.
     3. Report all passing tests, failures, and error tracebacks.
     ```

3. **Handle Failures**:
   - If tests fail with long, noisy traces, invoke `log-triage` (`Model: flash_lite`) to distill failure locations into a clean `file:line` list.
   - Dispatch distilled failure locations to `implementer` to remediate regressions.

