# NovaEnterprise – Antigravity Workspace Guidelines

> Authoritative reference: `Claude.md` (single source of truth for domain models, architecture, and system specifications). When this file and `Claude.md` disagree, `Claude.md` wins.

---

## 1. Core Architecture & Layer Rules

NovaEnterprise is an enterprise Knowledge & Decision Intelligence platform combining **Vector RAG**, **Graph RAG**, **SQL**, **LangGraph multi-agent workflows**, and **tiered memory**.

Strictly preserve the domain layering:
- `api` → `services` → `repositories` → `models`
- Subsystems (`agents/`, `rag/`, `memory/`) must encapsulate internal dependencies and integrate via `app.core` contracts.
- **Retrieval is a routing decision**: A single retriever is never hard-coded. Questions must be dynamically decomposed into document (Vector), records (SQL), and relationship (Graph) queries.

---

## 2. Security & Guardrails

- **SQL Safety**: Never execute raw or f-string SQL. Every query must pass `validate_sql()` against the schema allowlist.
- **Untrusted Documents**: External inputs (vendor notes, customer records) must be wrapped in isolated data objects; never interpolate untrusted text directly into LLM system prompts as executable instructions.
- **Graph Queries**: Cypher queries must use typed graph traversals and parameterized properties.

---

## 3. Testing Rules

- **Offline Isolation**: All tests in `tests/` must run without external network or live LLM credentials:
  - `LLM_PROVIDER=fake`
  - `VECTOR_STORE=memory`
  - `GRAPH_STORE=memory`
- Assert exact citation shapes, evidence resolution, and source tracing on RAG endpoints.

---

## 4. Model Tiers & Subagents

Antigravity operates with three designated model tiers:
- **`pro`**: Reserved for high-complexity design (`architect`, `planner`, `rag-consultant`). Enforced by `.agents/hooks/agent_guard.py`.
- **`flash`**: Standard workhorse for code generation, FastAPI routes, and pytest suites (`implementer`, `test-engineer`, `code-reviewer`).
- **`flash_lite`**: Fast log distillation and codebase indexing (`log-triage`, `explorer`).

---

## 5. Quick Workflow Routing

| Task | Slash Command / Skill | Primary Agent |
|---|---|---|
| Plan complex RAG or architectural features | `/plan` | `planner` (`pro`) |
| Implement approved changes from plans | `/implement` | `implementer` (`flash`) |
| Run targeted offline pytest suites | `/test` | `test-engineer` (`flash`) |
| Inspect diff, security, and contracts | `/review` | `code-reviewer` (`flash`) |
| Resolve multi-modal RAG routing ambiguity | `/consult-rag` | `rag-consultant` (`pro`) |
| Audit subagent usage and model tier limits | `/cost-report` | Local log analyzer |

