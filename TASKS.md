# NovaEnterprise — Task tracker

> Concise checklist for GitHub-visible progress.
> Architecture & Spec: [Claude.md](Claude.md) · System Rules: [GEMINI.md](GEMINI.md) · Git Workflow: [Git_GitHub_Workflow_Guide.md](Git_GitHub_Workflow_Guide.md) · BRD: [docs/BRD.md](docs/BRD.md) · PRD: [docs/PRD.md](docs/PRD.md) · FRD: [docs/FRD.md](docs/FRD.md) · HLD: [docs/HLD.md](docs/HLD.md) · LLD: [docs/LLD.md](docs/LLD.md)

**Branch convention:** `feature/<repo-name>` (one feature branch per sub-task; open the PR against `development`)
**Status:** `Pending ❌` · `Completed ✅`

Sub-tasks in the same phase that do not share files can be open at the same time. Do not stack a branch on another feature branch. Merge the listed predecessor first when a row names one.

> **Where to start today:** Open Phase 1 — no predecessors. P1-1 through P1-4 can all be branched at once since they touch separate files (`config.py`, `main.py`, `conftest.py`, `Makefile`).

---

## Phase 1 — Runtime skeleton

> Depends on: nothing. Unblocks: every later phase.
> Merge order: P1-1 through P1-4 can be opened in parallel; they touch separate files.

| Task | Branch | Proves | Status |
|------|--------|--------|--------|
| P1-1 · Settings and JSON logging | `feature/backend-config-logging` | N1, N2 | Completed ✅ |
| P1-2 · Health routes and request-id middleware | `feature/backend-health-request-id` | N4, N5 | Completed ✅ |
| P1-3 · Offline pytest harness and fake stores | `feature/test-harness-offline` | N1 | Completed ✅ |
| P1-4 · Makefile and `.env.example` | `feature/makefile-env-example` | N1, N4 | Pending ❌ |

---

## Phase 2 — Persistence and domain data

> Depends on: P1-1. Unblocks: Phases 3, 4, 5, 6, 7, and 8.
> Merge order: P2-1 first. P2-2 and P2-3 in parallel after it. P2-4 after P2-3.

| Task | Branch | Needs | Proves | Status |
|------|--------|-------|--------|--------|
| P2-1 · SQLAlchemy models (all entities) | `feature/sqlalchemy-models` | P1-1 | — | Pending ❌ |
| P2-2 · DB schema, migrations, and RLS policies | `feature/db-schema-rls` | P2-1 | — | Pending ❌ |
| P2-3 · Repository layer | `feature/repository-layer` | P2-1 | — | Pending ❌ |
| P2-4 · Sample data seed and fiscal calendar | `feature/sample-data-bootstrap` | P2-3 | F13 | Pending ❌ |

---

## Phase 3 — Identity and request guards

> Depends on: P1-2 and P2-1. Unblocks: protected routes in Phases 4, 10, and 11.
> Merge order: P3-1 and P3-3 in parallel. P3-2 after P3-1. P3-4 last (owns middleware order).

| Task | Branch | Needs | Proves | Status |
|------|--------|-------|--------|--------|
| P3-1 · JWT and `require_role` guard | `feature/jwt-rbac-security` | P2-1 | F1, F17 | Pending ❌ |
| P3-2 · Demo auth routes and token issuance | `feature/auth-demo-tokens` | P3-1 | F1 | Pending ❌ |
| P3-3 · Redis token-bucket rate limit | `feature/rate-limit-redis` | P1-2 | N6 | Pending ❌ |
| P3-4 · Audit middleware and middleware order | `feature/audit-middleware` | P3-1, P3-3 | N5 | Pending ❌ |

---

## Phase 4 — Browse API and core contracts

> Depends on: P2-3 and P3-1. Unblocks: Phase 12 (frontend can start). Does not block Phases 5–9.
> Merge order: P4-1 first (shared written contract). P4-2 and P4-3 in parallel after it.

| Task | Branch | Needs | Proves | Status |
|------|--------|-------|--------|--------|
| P4-1 · API contract doc (`docs/API_CONTRACT.md`) | `feature/api-contract-docs` | P3-1 | — | Pending ❌ |
| P4-2 · Customer, incident, service, and team endpoints | `feature/api-browse-entities` | P4-1 | F14 | Pending ❌ |
| P4-3 · Decisions (ADR) and project/ticket endpoints | `feature/api-browse-decisions` | P4-1 | F14 | Pending ❌ |

---

## Phase 5 — Storage protocols and RAG ingestion

> Depends on: P2-4. Parallel with: Phases 3, 4, 7, and 8. Unblocks: Phase 6.
> Merge order: P5-1 → P5-2 → P5-3 → P5-4. This phase is a sequential pipeline.

| Task | Branch | Needs | Proves | Status |
|------|--------|-------|--------|--------|
| P5-1 · `VectorStoreService` and `GraphStoreService` protocols | `feature/rag-storage-protocols` | P2-4 | N3 | Pending ❌ |
| P5-2 · Document parsing and semantic chunking | `feature/rag-document-chunking` | P5-1 | F13 | Pending ❌ |
| P5-3 · Entity and relationship extraction | `feature/rag-entity-extraction` | P5-2 | F13 | Pending ❌ |
| P5-4 · Ingest command and document upload API | `feature/rag-ingest-api` | P5-3 | F13, N7 | Pending ❌ |

---

## Phase 6 — Multi-store retrieval paths

> Depends on: P5-1. Unblocks: Phase 9. Parallel with: Phases 3, 4, 7, and 8.
> Merge order: P6-1 first (shared Evidence shape). P6-2, P6-3, and P6-4 in parallel after it.

| Task | Branch | Needs | Proves | Status |
|------|--------|-------|--------|--------|
| P6-1 · Common `Evidence` schema and locators | `feature/rag-evidence-schema` | P5-1 | F5–F8 | Pending ❌ |
| P6-2 · SQL retrieval with `validate_sql()` and templates | `feature/rag-sql-retrieval` | P6-1 | F7 | Pending ❌ |
| P6-3 · Graph retrieval with typed Cypher traversals | `feature/rag-graph-retrieval` | P6-1 | F8, F14 | Pending ❌ |
| P6-4 · Hybrid retriever — semantic + BM25 + RRF + rerank | `feature/rag-hybrid-retriever` | P6-1 | F6 | Pending ❌ |

---

## Phase 7 — Rules and guardrails

> Depends on: P2-1. Parallel with: Phases 4, 5, 6, and 8. Unblocks: Phase 9.
> Merge order: all four branches can be open together — separate modules, no shared files.

| Task | Branch | Needs | Proves | Status |
|------|--------|-------|--------|--------|
| P7-1 · Complexity and routing rules (`agents/rules.py`) | `feature/policy-routing-rules` | P2-1 | F3, F5 | Pending ❌ |
| P7-2 · Injection isolation and vendor note flagging | `feature/guardrails-injection-isolation` | P2-1 | N8 | Pending ❌ |
| P7-3 · Upload validation and secret scrub | `feature/guardrails-upload-scrub` | P2-1 | N7, N8 | Pending ❌ |
| P7-4 · Observability tracer (`observability.py`) | `feature/observability-tracer` | P2-1 | F16, N9 | Pending ❌ |

---

## Phase 8 — Tiered memory system

> Depends on: P2-3 and P7-3. Parallel with: Phases 4, 5, and 6. Unblocks: Phase 9.
> Merge order: P8-1 and P8-2 in parallel. P8-3 after both.

| Task | Branch | Needs | Proves | Status |
|------|--------|-------|--------|--------|
| P8-1 · Four-scope memory schemas and protocols | `feature/memory-tier-schemas` | P2-3 | F15 | Pending ❌ |
| P8-2 · Redis conversation memory and org memory loader | `feature/memory-redis-org` | P7-3 | F15 | Pending ❌ |
| P8-3 · Unified memory recall and update service | `feature/memory-service` | P8-1, P8-2 | F15 | Pending ❌ |

---

## Phase 9 — Specialist agents and workflow nodes

> Depends on: Phases 6, 7, and 8. Unblocks: Phase 10.
> Merge order: P9-1 first (shared state). P9-2–P9-5 in parallel. P9-6–P9-8 in parallel after them.

| Task | Branch | Needs | Proves | Status |
|------|--------|-------|--------|--------|
| P9-1 · `ResearchState` schema and fake LLM provider | `feature/workflow-state-schemas` | P6-1, P7-1, P8-3 | N1, N2 | Pending ❌ |
| P9-2 · Query analysis and complexity assessment node | `feature/agent-nodes-analyze` | P9-1 | F2, F3 | Pending ❌ |
| P9-3 · Sub-question decomposition node | `feature/agent-nodes-decompose` | P9-1 | F4 | Pending ❌ |
| P9-4 · Retrieval routing and execution node | `feature/agent-nodes-retrieval` | P9-1 | F5, F6, F7, F8 | Pending ❌ |
| P9-5 · Evidence collection and missing-evidence node | `feature/agent-nodes-evidence` | P9-1 | F9 | Pending ❌ |
| P9-6 · Bounded corrective retrieval loop node | `feature/agent-nodes-corrective` | P9-2, P9-3, P9-4, P9-5 | F9 | Pending ❌ |
| P9-7 · Evidence verification and citation synthesis | `feature/agent-nodes-synthesis` | P9-5, P9-6 | F10, F11 | Pending ❌ |
| P9-8 · Citation verification and memory update node | `feature/agent-nodes-verification` | P9-7 | F12, F15 | Pending ❌ |

---

## Phase 10 — LangGraph research workflow engine

> Depends on: Phase 9. Unblocks: Phase 11 and Phase 13.
> Merge order: P10-1 first (graph topology). P10-2, P10-3, and P10-4 in parallel after it.

| Task | Branch | Needs | Proves | Status |
|------|--------|-------|--------|--------|
| P10-1 · `StateGraph` wiring — 13 nodes and conditional edges | `feature/langgraph-workflow-wiring` | Phase 9 ✓ | F1–F12 | Pending ❌ |
| P10-2 · Node telemetry and per-node state persistence | `feature/workflow-tracer-persistence` | P10-1 | F16 | Pending ❌ |
| P10-3 · `BackgroundTask` runner and 202 session API | `feature/api-research-lifecycle` | P10-1, P3-1 | F1 | Pending ❌ |
| P10-4 · Status polling and event stream API | `feature/api-research-events` | P10-2, P10-3 | F1, F16 | Pending ❌ |

---

## Phase 11 — Graph explorer, documents, and approvals API

> Depends on: P3-1, P5-4, P6-3, and Phase 10. Unblocks: Phase 13 and `make demo`.
> Merge order: P11-1 and P11-2 in parallel. P11-3 after both.

| Task | Branch | Needs | Proves | Status |
|------|--------|-------|--------|--------|
| P11-1 · Graph browsing, node expansion, and read-only Cypher | `feature/api-graph-explorer` | P6-3, P3-1 | F14 | Pending ❌ |
| P11-2 · Document delete approval gate and admin workflow | `feature/api-approval-workflow` | P5-4, P3-1 | F17 | Pending ❌ |
| P11-3 · `make demo` — canonical question end-to-end runner | `feature/cli-demo-runner` | P11-1, P11-2, P10-4 | N4 | Pending ❌ |

---

## Phase 12 — Frontend console shell

> Depends on: P4-1 and P3-2. Parallel with: Phases 5–11. Unblocks: Phase 13.
> Merge order: P12-1 and P12-2 in parallel. P12-3 after both. P12-4 after P12-3.

| Task | Branch | Needs | Proves | Status |
|------|--------|-------|--------|--------|
| P12-1 · Next.js 15 App Router, layout, and navigation | `feature/frontend-app-shell` | P4-1 | — | Pending ❌ |
| P12-2 · Typed API client mirroring `docs/API_CONTRACT.md` | `feature/frontend-api-client` | P4-1 | — | Pending ❌ |
| P12-3 · Auth state, JWT handling, and role-aware UI | `feature/frontend-auth-layout` | P12-1, P12-2, P3-2 | — | Pending ❌ |
| P12-4 · Read-only browse views (customers, incidents, decisions) | `feature/frontend-browse-views` | P12-3 | — | Pending ❌ |

---

## Phase 13 — Research and graph UI screens

> Depends on: Phase 11 and Phase 12. The only UI phase that waits on the agent graph.
> Merge order: P13-1 first. P13-2 and P13-3 in parallel after it. P13-4 after both.

| Task | Branch | Needs | Proves | Status |
|------|--------|-------|--------|--------|
| P13-1 · Research interface and active session view | `feature/frontend-research-view` | Phase 11 ✓, Phase 12 ✓ | F1 | Pending ❌ |
| P13-2 · Live event tracer, node timeline, and progress poll | `feature/frontend-event-timeline` | P13-1 | F16 | Pending ❌ |
| P13-3 · Knowledge Graph visualizer and node expansion canvas | `feature/frontend-graph-canvas` | P13-1 | F14 | Pending ❌ |
| P13-4 · Document manager, upload dropzone, and approval modal | `feature/frontend-documents-approvals` | P13-1 | F13, F17 | Pending ❌ |

---

## Phase 14 — Evaluation, testing, and delivery

> Depends on: Phase 10 and Phase 11. Image and compose files do not import the graph.
> Merge order: P14-1 and P14-2 after Phase 10/11. P14-3 and P14-4 in parallel. P14-5 last.

| Task | Branch | Needs | Proves | Status |
|------|--------|-------|--------|--------|
| P14-1 · Evaluation harness over `eval_cases.json` (6 CI thresholds) | `feature/eval-metrics-suite` | Phase 10 ✓ | §3.3 | Pending ❌ |
| P14-2 · Full offline integration test suite (`make test`) | `feature/test-suite-integration` | Phase 11 ✓ | F1–F17, N1–N9 | Pending ❌ |
| P14-3 · Backend and frontend Dockerfiles | `feature/docker-container-images` | P14-2 | — | Pending ❌ |
| P14-4 · Multi-service Docker Compose stack | `feature/docker-compose-stack` | P14-3 | — | Pending ❌ |
| P14-5 · CI workflow configs and production runbooks | `feature/delivery-ci-runbooks` | P14-3, P14-4 | — | Pending ❌ |

---

## Dependency overview

```text
P1 Runtime skeleton
  └─► P2 Persistence and domain data
        ├─► P3 Identity & guards ──► P4 Browse API ──► P12 Console shell ─────┐
        │                                                                      │
        ├─► P5 Storage protocols ──► P5→ RAG ingest                           │
        │          └──────────────────────────────────────────────► P6 Retrieval
        │                                                                      │
        ├─► P7 Rules & guardrails ─────────────────────────────────────────────┤
        │                                                                      │
        └─► P8 Memory ──────────────────────────────────────────────────────► P9 Workflow nodes
                                                                               │
                                                                      P10 LangGraph engine
                                                                               │
                                                              ┌────────────────┘
                                                              ▼
                                                     P11 Graph / Docs / Approvals API
                                                              │
                                                     P13 Research & Graph UI ◄──────── P12 Console shell
                                                              │
                                                     P14 Evaluation & delivery
```

**Key parallel windows:**
- Phases 3, 5, 7, and 8 all start the moment Phase 2 merges.
- Phase 4 unblocks Phase 12 early so frontend work runs alongside agent development.
- Phases 6 and 8 converge at Phase 9; Phase 9 converges with Phase 12 at Phase 13.

---

## PRD requirement coverage

Every F-requirement and N-requirement from `Claude.md §3` must be covered by at least one task before Phase 14 closes.

| Req | Description (short) | Covered by |
|-----|----------------------|------------|
| F1 | Accept NL question, return 202 | P10-3, P10-4, P13-1 |
| F2 | Analyse intent, entities, time range | P9-2 |
| F3 | Classify complexity simple/moderate/complex | P7-1, P9-2 |
| F4 | Decompose into ≤ MAX_SUBQUESTIONS | P9-3 |
| F5 | Route sub-question to correct store | P7-1, P9-4 |
| F6 | Hybrid retrieval — semantic + BM25 + RRF + rerank | P6-4 |
| F7 | SQL restricted to read-only allowlist | P6-2 |
| F8 | Graph retrieval — typed Cypher traversals | P6-3 |
| F9 | Detect missing evidence; bounded corrective loop | P9-5, P9-6 |
| F10 | Verify claims against evidence | P9-7 |
| F11 | Answer carries `[n]` citation markers | P9-7 |
| F12 | Every citation resolves; invalid ones reported | P9-8 |
| F13 | Ingest md / txt / PDF; chunk, extract, index | P5-2, P5-3, P5-4 |
| F14 | Browse graph; expand nodes | P4-2, P6-3, P11-1, P13-3 |
| F15 | Four separated memory scopes per session | P8-1, P8-2, P8-3, P9-8 |
| F16 | Expose every node transition, timing, and query | P7-4, P10-2, P10-4, P13-2 |
| F17 | Approval gate on destructive admin actions | P3-1, P11-2, P13-4 |
| N1 | Runs offline — no key, no external service | P1-3, P1-4, P14-2 |
| N2 | Provider-agnostic AI via `get_llm()` | P1-1, P9-1 |
| N3 | Replaceable stores via protocols | P5-1 |
| N4 | Canonical question completes ≤ ~7 s offline | P1-4, P11-3 |
| N5 | Every response carries `X-Request-ID` | P1-2, P3-4 |
| N6 | Rate limiting via Redis token bucket | P3-3 |
| N7 | Uploads validated — size cap and extension list | P5-4, P7-3 |
| N8 | Untrusted content never becomes instructions | P7-2, P7-3 |
| N9 | No hidden reasoning exposed in API or UI | P7-4 |

---

## Map to `Claude.md`

| This file | Phase in `Claude.md §19` |
|-----------|--------------------------|
| Phase 1 | Phase 1 — Runtime skeleton |
| Phase 2 | Phase 2 — Persistence and demo data |
| Phase 3 | Phase 3 — Identity and request guards |
| Phase 4 | Phase 10 — Browse routes (pulled forward to unblock frontend) |
| Phase 5 | Phase 4 — Ingestion pipeline |
| Phase 6 | Phase 5 — Retrieval paths |
| Phase 7 | Phase 6 — Rules and guardrails |
| Phase 8 | Phase 9 — Memory (pulled forward of the graph) |
| Phase 9 | Phase 7 — Workflow nodes |
| Phase 10 | Phase 7 & 8 — LangGraph engine and research API |
| Phase 11 | Phase 10 — Graph explorer, documents, approvals |
| Phase 12 | Phase 11 — Frontend console shell |
| Phase 13 | Phase 11 — Research and graph UI screens |
| Phase 14 | Phase 12 — Evaluation and delivery |

---

## Progress summary

| Phase | Name | Tasks | Done |
|-------|------|-------|------|
| 1 | Runtime skeleton | 4 | 1 ⏳ |
| 2 | Persistence and domain data | 4 | 0 ❌ |
| 3 | Identity and request guards | 4 | 0 ❌ |
| 4 | Browse API and core contracts | 3 | 0 ❌ |
| 5 | Storage protocols and RAG ingestion | 4 | 0 ❌ |
| 6 | Multi-store retrieval paths | 4 | 0 ❌ |
| 7 | Rules and guardrails | 4 | 0 ❌ |
| 8 | Tiered memory system | 3 | 0 ❌ |
| 9 | Specialist agents and workflow nodes | 8 | 0 ❌ |
| 10 | LangGraph research workflow engine | 4 | 0 ❌ |
| 11 | Graph explorer, documents, and approvals API | 3 | 0 ❌ |
| 12 | Frontend console shell | 4 | 0 ❌ |
| 13 | Research and graph UI screens | 4 | 0 ❌ |
| 14 | Evaluation, testing, and delivery | 5 | 0 ❌ |
| **Total** | | **56** | **1 (2%)** |
