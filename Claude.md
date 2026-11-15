# CLAUDE.md – Project 2: Enterprise Knowledge & Decision Intelligence Platform

> Single source of truth for architecture, domain models, and system specifications.
> Course docs this file is distilled from: `00-problem.md` · `01-prd.md` · `02-hld.md`
> Optional companions (create when needed): `TASKS.md` · `PLAN.md` · `SKILLS.md` · `MEMORY.md`

This file is the single source of truth for building the "Enterprise Knowledge & Decision Intelligence
Platform". Read it before writing any code. When this file and a phase plan disagree, this file wins;
update it first, then the code.

Anything marked **[TBD]** is not specified in the source docs. Do not invent it silently: decide, then
record the decision here (see section 19).

---

## 1. What we are building

A research platform for a fictional technology company, **NovaEnterprise**. An analyst asks one
enterprise question in natural language and receives a **cited, verified answer** assembled from
documents, database records and a knowledge graph, with the whole retrieval process open to inspection.

```text
Vector RAG  +  Graph RAG  +  SQL  +  Agents  +  Memory
```

**Core idea:** retrieval strategy is a *routing decision*, not a library choice. The system looks at a
question, decides which part is a document question, which is a records question and which is a
relationship question, and picks the store at run time. Never hard-code one retriever.

**The canonical question** (every stage is built around it):

> Which customers were impacted by the Payments API last quarter, what incidents occurred, which teams
> own those services, and what decisions were taken to prevent recurrence?

| Part of the question | Answered from | Why not the others |
|---|---|---|
| which customers were impacted | **graph** `(Service)<-[:AFFECTED]-(Incident)-[:IMPACTED]->(Customer)` | link lives in relationships, not prose |
| what incidents occurred | **SQL** `incidents JOIN services` filtered by date | needs exact records in a date range |
| which teams own those services | **graph** `(Service)-[:OWNED_BY]->(Team)` | one hop; no document says it plainly |
| what decisions prevent recurrence | **hybrid** postmortems + ADRs (+ graph) | rationale is narrative text |

Pipeline every question goes through:

```text
Analyse → Assess complexity → Decompose → Route → Retrieve (vector | SQL | graph | hybrid)
  → Collect evidence → Check missing → Corrective retrieval (bounded) → Verify evidence
  → Synthesize cited answer → Verify citations → Remember
```

Non-goals for v1:
- No write access to enterprise systems of record. Every SQL statement and Cypher query is read-only.
- No autonomous action. The only mutations are document management; destructive ones need approval.
- No fine-tuning or model training.
- Not a general BI tool: SQL is limited to an allowlisted schema.

---

## 2. Users and roles

| Role | Can | Cannot |
|---|---|---|
| `viewer` | read dashboards; browse customers / incidents / decisions / documents; read research sessions | start research, upload, run Cypher |
| `analyst` | everything viewer can + start research, upload documents, run read-only Cypher, manage own memory | delete documents, reindex, approve |
| `admin` | everything + reindex, approve/reject approval requests, delete documents | – |

Enforced by `require_role` in `backend/app/core/security.py`.
Proof: `tests/api/test_api.py::test_auth_required_and_rbac` (a viewer gets `403` on `POST /api/v1/research`).
Auth: JWT (demo login or Supabase). Demo user emails **[TBD]**.

---

## 3. Requirements

### 3.1 Functional (F1–F17)

| ID | Requirement | Location | Proven by |
|---|---|---|---|
| F1 | Accept a NL question, return a session id immediately (**202**) | `backend/app/api/research.py` | `test_research_lifecycle` |
| F2 | Analyse intent, entities, time range, need for relationships / aggregation | `agents/nodes/analyze_query.py` | `test_canonical_question_end_to_end` |
| F3 | Classify complexity `simple / moderate / complex` | `agents/nodes/assess_complexity.py`, `agents/rules.py` | `test_simple_question_single_subquestion` |
| F4 | Decompose complex question into ≤ `MAX_SUBQUESTIONS` (default 4) | `agents/nodes/decompose.py` | `test_canonical_question_end_to_end` |
| F5 | Route each sub-question to vector, SQL, graph or hybrid | `agents/nodes/route_retrieval.py` | `test_graph_shape_matches_frontend_assumptions` |
| F6 | Hybrid document retrieval: semantic + BM25 + RRF + rerank | `rag/retriever.py` | `tests/rag/test_retrieval_graph.py` |
| F7 | SQL retrieval restricted to a read-only allowlist | `rag/sql_retrieval.py` | `tests/unit/test_sql_validator.py` (8 tests) |
| F8 | Graph retrieval via typed traversals that also expose their Cypher | `rag/graph_store.py` | `test_graph_traversals` |
| F9 | Detect missing evidence; ≤ `MAX_CORRECTIVE_ROUNDS` corrective retrievals | `check_missing_evidence.py`, `corrective_retrieval.py` | `test_corrective_retrieval_triggers_for_unanswerable_part` |
| F10 | Verify each claim against collected evidence before answering | `agents/nodes/verify_evidence.py` | `test_canonical_question_end_to_end` |
| F11 | Answer carries `[n]` citation markers resolvable to evidence | `agents/nodes/synthesize_answer.py` | `test_multi_hop_citations_and_grounding` |
| F12 | Verify every citation resolves; report invalid ones | `agents/nodes/verify_citations.py` | `test_research_lifecycle` |
| F13 | Ingest md / txt / PDF; chunk, extract entities + relationships, index into vector + DB + graph | `rag/ingest.py` | `test_upload_validation_and_ingest` |
| F14 | Browse the knowledge graph and expand nodes | `backend/app/api/graph.py` | `test_graph_endpoints` |
| F15 | Four separated memory scopes surfaced per session | `memory/memory_service.py` | `test_research_lifecycle` |
| F16 | Expose every node transition, tool call, query and timing | `backend/app/core/observability.py` | `GET /api/v1/research/{id}/events` |
| F17 | Approval gate on destructive admin actions (document delete) | `backend/app/api/documents.py`, `services/approval_service.py` | `test_upload_validation_and_ingest` |

### 3.2 Non-functional (N1–N9)

| ID | Requirement | Target / mechanism |
|---|---|---|
| N1 | Runs with **no API key and no external service** | `LLM_PROVIDER=fake`, `VECTOR_STORE=memory`, `GRAPH_STORE=memory`, SQLite, fakeredis |
| N2 | Provider-agnostic AI | 8 providers via `get_llm()` / `get_embedding_model()` in `backend/app/core/llm.py` |
| N3 | Replaceable stores | `VectorStoreService` and `GraphStoreService` protocols |
| N4 | Canonical question completes offline | ~7 s (fake provider, memory stores) |
| N5 | Every response carries `X-Request-ID` | `backend/app/middleware/request_context.py` |
| N6 | Rate limiting | `RATE_LIMIT_PER_MINUTE` (default 120), Redis token bucket |
| N7 | Uploads validated | ≤ `MAX_UPLOAD_MB` (5), extension allowlist |
| N8 | Untrusted content never becomes instructions | wrapped + scanned + flagged (`backend/app/core/guardrails.py`) |
| N9 | No hidden reasoning exposed | only decisions, queries, evidence, timings |

### 3.3 Success metrics (measured, enforced in CI)

`tests/evaluation/evaluate.py` over `tests/evaluation/datasets/eval_cases.json`:

| Metric | CI threshold | Observed offline |
|---|---|---|
| retrieval relevance | ≥ 0.80 | 1.00 |
| SQL correctness | = 1.00 | 1.00 |
| graph correctness | = 1.00 | 1.00 |
| multi-hop coverage | ≥ 0.66 | 1.00 |
| citation support | = 1.00 | 1.00 |
| answer grounding | ≥ 0.50 | 1.00 |

Thresholds are deliberately below observed scores: an eval suite should fail on regression, not noise.

---

## 4. Architecture

Next.js 15 frontend → FastAPI backend → LangGraph research workflow → **four stores** behind replaceable
interfaces. The design question that matters is **which store answers which part of a question**.

```text
Browser (:3001) ─JWT, REST /api/v1, X-Request-ID─▶ FastAPI (:8001)
                                                    │ middleware: request-id, rate limit, audit
                                                    │ LangGraph research workflow (13 nodes)
        ┌──────────────────────┬────────────────────┼──────────────────────┐
        ▼                      ▼                    ▼                      ▼
 PostgreSQL / SQLite    Qdrant / in-memory    Neo4j / in-memory     Redis / fakeredis
 records, chunks,       chunk vectors         entities +            cache, conversation
 sessions, audit                              relationships         memory, rate limit
                                  LLM provider (any of 8) via get_llm()
```

Managed production forms: Supabase (Postgres + Auth + Storage + RLS), Qdrant Cloud, Neo4j Aura.

### 4.1 Request flow – one research question

1. UI `POST /api/v1/research {question}` (Pydantic: 5..2000 chars) → `api/research.py`
2. `research_service.create_session()` writes a `research_sessions` row, returns **202** `{session_id, status:"running"}`
3. A `BackgroundTask` runs `agents/graph.py` `StateGraph(ResearchState)`
4. Each of the 13 nodes is wrapped in `tracer.node(...)`; state is persisted after **every** node
   (`research_service._persist`); every transition goes to `workflow_events`
5. UI polls `GET /api/v1/research/{id}` every **2 s**; `GET /api/v1/research/{id}/events` shows the trace

The frontend never waits on a long request. **The state in the database is the progress bar.**

### 4.2 Layering rules

Import direction is one-way: `api → services → repositories → models`, and `agents / rag / memory → app.core`.

| Layer | Folder | Responsibility | MUST NOT |
|---|---|---|---|
| API | `backend/app/api/` | HTTP shape, auth, validation, status codes | contain business logic |
| Services | `backend/app/services/` | run the graph, persist state, approvals, seed | know about HTTP |
| Repositories | `backend/app/repositories/` | all SQL via SQLAlchemy | be imported by agents directly |
| Core | `backend/app/core/` | config, llm, db, redis, security, logging, guardrails, observability | import from `agents/` (cycle) |
| Agents | `agents/` | graph, nodes, specialists, deterministic rules | talk to HTTP or the browser |
| RAG | `rag/` | parsing, chunking, extraction, vector store, graph store, retrievers, SQL retrieval | know about FastAPI |
| Memory | `memory/` | the four memory scopes | be mixed with retrieval |
| Integrations | `integrations/` | protocols + mock adapters + MCP server | be required for the demo |
| Frontend | `frontend/` | pages, components, typed API client | hold the service-role key |

### 4.3 Folder layout (`project-02-enterprise-intelligence/`)

```text
backend/app/   main.py · api/ · core/ · middleware/ · models/ · schemas/ · repositories/ · services/
agents/        graph.py · rules.py · nodes/ · specialists/ (SQLAgent, GraphAgent, ...)
rag/           ingest.py · retriever.py · vector_store.py · graph_store.py · sql_retrieval.py
memory/        memory_service.py
integrations/  protocols.py (DocumentSource) · mock adapters · MCP server
frontend/      Next.js 15 App Router: /search · /research/[id] · /knowledge-graph · /documents
database/      rls_policies.sql (Supabase RLS) · schema / seed [TBD exact files]
sample_data/   teams, employees, services, customers, incidents, decisions, projects, tickets (.json)
               organizational_memory.json · documents/*.md (15 documents)
tests/         unit/ · api/ · rag/ · agents/ · evaluation/ (datasets/eval_cases.json)
docs/          API_CONTRACT.md · FRONTEND_ASSUMPTIONS.md
data/          (git-ignored) enterprise.db
```

`backend/app/main.py` is the app factory + lifespan: creates tables, seeds, builds the graph, ingests documents.

---

## 5. The three retrieval paths

```text
sub-question ─▶ route_retrieval ─┬─ vector / hybrid ─▶ rag/retriever.py      semantic + BM25 + RRF + rerank
                                 ├─ sql ─────────────▶ rag/sql_retrieval.py   validate_sql() + templates
                                 └─ graph ───────────▶ rag/graph_store.py     typed traversals + Cypher templates
                                              ▼
                                   collect_evidence (merge + dedupe + id)
```

All three produce the **same `Evidence` shape** (`backend/app/schemas/common.py`), differing only in
`source_type` (`document` / `sql` / `graph`) and `locator`. That is what makes one citation list possible.
Never create a retrieval path that returns a different shape.

| Path | Safety by construction |
|---|---|
| SQL | Templates + `validate_sql()` allowlist; LLM-generated SQL only as an *addition*; read-only `SELECT`; injection and destructive statements are impossible, not unlikely |
| Graph | Typed traversals that *also return their Cypher*; free-form generated Cypher is not used; the analyst "run Cypher" feature is read-only |
| Documents | Hybrid semantic + BM25, RRF fusion, rerank; all content wrapped as untrusted |

---

## 6. Domain data (NovaEnterprise, `sample_data/`)

| File | Contents |
|---|---|
| `teams.json` | 6 teams: Payments Platform, Identity, Data Platform, Customer Success, SRE, Analytics |
| `employees.json` | 20 employees with titles and team membership |
| `services.json` | 8 services: Payments API, Identity Service, Data Pipeline, Analytics Dashboard, Notification Service, Billing Engine, Customer Portal, Search Service |
| `customers.json` | 10 customers across enterprise / mid-market / SMB tiers |
| `incidents.json` | 12 incidents across three quarters, with root causes and impacted customers |
| `decisions.json` | 8 ADRs addressing those incidents |
| `projects.json`, `tickets.json` | 6 projects, 15 tickets |
| `organizational_memory.json` | curated shared facts (e.g. the fiscal calendar) |
| `documents/*.md` | 15 docs: 4 postmortems, 3 ADRs, 3 policies, 2 meeting notes, 1 runbook, 1 quarterly reliability summary, **1 hostile vendor note** |

Key documents:
- `documents/postmortem-inc-2031-payments-api-outage.md` – the SEV1 the canonical question is about.
- `documents/vendor-note-processor-update.md` – contains a **deliberate prompt-injection attempt**. It must be
  **indexed as data and flagged**, never obeyed.

**Graph schema (known edges):** `(Service)<-[:AFFECTED]-(Incident)`, `(Incident)-[:IMPACTED]->(Customer)`,
`(Service)-[:OWNED_BY]->(Team)`. Full node/edge type list **[TBD]**. Demo graph size: ~85 nodes, ~260 edges;
~70 vector chunks (memory stores).

**"Last quarter" depends on the fiscal calendar** held in `organizational_memory.json`. Resolve time ranges
through that, not by assuming calendar quarters.

---

## 7. Agents and workflow

### 7.1 Specialists

| Specialist | Role |
|---|---|
| `SQLAgent` | builds and runs a validated read-only `SELECT` |
| `GraphAgent` | runs typed Cypher traversals in Neo4j / in-memory graph |
| Hybrid retriever | vector + BM25 + RRF + rerank over postmortems and ADRs |

Full specialist list and output schemas **[TBD]**: record them here once defined. Every agent must return a
Pydantic model.

### 7.2 The rules-plus-LLM pattern (non-negotiable)

`agents/rules.py` holds the **deterministic** analysis, decomposition and routing rules, applied *on top of*
LLM output. Reasons: the demo must work with `LLM_PROVIDER=fake`, and rules stop a relationship question
being sent to vector-only retrieval. Rules decide policy and routing floors; the LLM adds judgement in grey
areas only.

### 7.3 LangGraph (`agents/graph.py`)

13 nodes, exposed as `GRAPH_NODES` / `GRAPH_EDGES` and built by `build_graph()`. Known nodes:

```text
analyze_query → assess_complexity → decompose → route_retrieval → (retrieval execution per strategy)
  → collect_evidence → check_missing_evidence ─┬─ missing & rounds left → corrective_retrieval ─┐
                                               └─ ok ──────────────────────────────────────────┴→
  → verify_evidence → synthesize_answer → verify_citations → (memory update) → END
```

The exact 13-node list and edge set **[TBD]**: `GRAPH_NODES` in `agents/graph.py` is the authority once
written; copy it here. `tests/.../test_graph_shape_matches_frontend_assumptions` guards the shape the UI
renders (`docs/FRONTEND_ASSUMPTIONS.md`).

Rules:
- Every node is wrapped in `tracer.node(...)`, returns a **partial** state dict, and never lets telemetry raise.
- **Bounded corrective loop:** `MAX_CORRECTIVE_ROUNDS=1`. Agent loops must terminate. Corrective retrieval
  cannot fix a decomposition that was never allowed to happen (`MAX_SUBQUESTIONS`).
- **Evidence verification and citation verification are separate nodes** so each guarantee can be pointed at
  and tested alone.
- Complexity drives shape: `simple` → exactly one sub-question, no SQL, no Cypher, `strategies_used`
  contains only `vector`.
- A store failure (e.g. Neo4j down) records an **error on that sub-question**; it must never crash the workflow.

### 7.4 Memory (`memory/`)

Four **separated** memory scopes, surfaced per session (F15). Scope names and TTLs **[TBD]**. Rules known so
far: memory is never mixed with retrieval; conversation memory lives in Redis; shared organisational facts
come from `organizational_memory.json`; users manage only their **own** memory (analyst role).

---

## 8. RAG

Pipeline: `sample_data/documents/*.md` → parse → chunk → entity + relationship extraction → index into
**vector store + relational DB + graph** → `retrieve()`.

- **Vector store protocol:** `VectorStoreService`; `InMemory` or `Qdrant` chosen by `VECTOR_STORE`. Nothing else knows which.
- **Graph store protocol:** `GraphStoreService`; `memory` or `neo4j` chosen by `GRAPH_STORE`.
- **Retrieval:** semantic ∪ BM25 → reciprocal rank fusion → rerank.
- **Ingest formats:** markdown, text, PDF. Chunk size / overlap **[TBD]**.
- Changing the embedding model requires a reindex (admin only).
- Documents are the source for narrative claims (decisions, rationale, policy). Cite them.

---

## 9. Guardrails and security

- **Prompt injection (N8):** all document, upload and tool content is wrapped, scanned and flagged in
  `backend/app/core/guardrails.py`. The vendor note must be indexed, flagged, and **never** change the
  workflow.
- **SQL safety (F7):** `validate_sql()` allows read-only `SELECT` on an allowlisted schema only.
- **Cypher safety:** typed traversals; user-run Cypher is read-only.
- **Uploads (N7):** extension allowlist and `MAX_UPLOAD_MB` size cap enforced in `api/documents.py`.
- **Approval (F17):** document deletion needs an approval request resolved by an `admin`.
- **No hidden reasoning (N9):** never expose raw prompts or chain-of-thought.
- **Secrets:** only `.env` (git-ignored) and `.env.example` (committed, placeholders only).
- **Rate limit (N6)**, **request IDs (N5)**, **audit** of state-changing requests. Middleware order **[TBD]**.
- **RLS:** `database/rls_policies.sql` shows the Supabase side; backend uses the service-role key server-side only.

---

## 10. Backend conventions

- Stack: Python, FastAPI, Pydantic v2, SQLAlchemy (SQLite demo / Postgres cloud), LangGraph, pytest.
  Exact Python version **[TBD]**.
- Routers under `/api/v1`. Health routes unprefixed: `/health`, `/health/ready`.
- `/health/ready` reports per-store status with real adapter detail (e.g. `sqlite`, `qdrant http://…`,
  `neo4j bolt://…`, or `memory (70 chunks)` / `memory (85 nodes, 260 edges)`). Same code, different
  adapters. A down store makes it `degraded`, not an outage.
- `Settings` is cached with `@lru_cache`: **restart the server after editing `.env`.**
- Background workflows run in-process for v1. Production extension: worker (Celery / Cloud Tasks / SQS) +
  `langgraph-checkpoint-postgres`.
- Ports: backend `:8001`, frontend `:3001`. Two servers on 8001 (container + local `uvicorn`) give
  confusing results; check `docker ps`.

### 10.1 Environment variables (`.env.example` must list every one)

```text
LLM_PROVIDER            fake (default) | one of 8 providers
VECTOR_STORE            memory | qdrant
GRAPH_STORE             memory | neo4j
MAX_SUBQUESTIONS        default 4
MAX_CORRECTIVE_ROUNDS   default 1
RATE_LIMIT_PER_MINUTE   default 120
MAX_UPLOAD_MB           default 5
```

Also needed **[TBD names]**: database URL, Redis URL / fakeredis flag, JWT + Supabase secrets, LLM key/model,
embedding provider/model, Qdrant URL/key/collection, Neo4j URI/user/password, CORS origins, sample data dir.

---

## 11. Frontend conventions

- Next.js 15 App Router. Pages: `/search`, `/research/[id]`, `/knowledge-graph`, `/documents`, plus browse
  pages for customers / incidents / decisions and a dashboard **[TBD exact routes]**.
- Backend is reached **only** through a typed API client that mirrors `docs/API_CONTRACT.md`.
- Poll research status every 2 s; the UI renders what is in the database.
- **Role-aware UI:** viewers see disabled research / upload / Cypher controls.
- `docs/FRONTEND_ASSUMPTIONS.md` lists the extra guarantees the UI depends on; breaking one is a breaking change.

---

## 12. API contract

`docs/API_CONTRACT.md` is the source of truth for routes and types. Known groups: `/auth` · `/research`
(+ `/{id}`, `/{id}/events`) · `/documents` (upload, delete with approval) · `/graph` (browse, expand,
read-only Cypher) · browse routes for customers / incidents / decisions · approvals · `/health`.

Rule: if an endpoint changes, update `API_CONTRACT.md`, the backend schemas, and the frontend types in the
same change.

---

## 13. Testing and evaluation

Tests run **fully offline** (no API key, no Docker): `LLM_PROVIDER=fake`, `VECTOR_STORE=memory`,
`GRAPH_STORE=memory`, SQLite, fakeredis.

| Folder | Proves |
|---|---|
| `tests/unit/` | SQL validator (8 tests), guardrails, rules |
| `tests/api/` | auth + RBAC 403s, research lifecycle (202 → poll → complete), upload validation + ingest + approval, graph endpoints |
| `tests/rag/` | `test_retrieval_graph.py`, graph traversals |
| `tests/agents/` | canonical question end-to-end, simple question, corrective retrieval, multi-hop citations + grounding, graph shape |
| `tests/evaluation/` | threshold metrics over `datasets/eval_cases.json` (section 3.3) |

Adding an eval case: append to `eval_cases.json`, add the metric to `evaluate.py`, confirm it fails before tuning.
Every PRD requirement must map to at least one test; add the mapping when you add a feature.

---

## 14. Commands

```bash
make setup            # .venv + deps + .env
make demo             # asks the canonical question and prints every stage
make demo QUESTION="What is our data retention policy?"   # single-store path: simple, vector only
make ingest           # (re)index documents; or delete data/enterprise.db and re-run make demo
make seed-graph       # rebuild the graph if running a script directly
make backend          # FastAPI on :8001
make test             # every requirement, offline
.venv/Scripts/python.exe -m tests.evaluation.evaluate     # the metrics table
curl -s localhost:8001/health/ready | python -m json.tool
```

Windows: use `.venv/Scripts/python.exe`. Frontend and Docker Compose commands **[TBD]**.

**`make demo` must print, in order:** analysis (complexity `complex`, entity `Payments API`, time range
`last quarter`) → four sub-questions, one strategy each (`graph`, `sql`, `graph`, `hybrid`) → the SQL that
ran → three Cypher traversals → nine pieces of evidence → verification ratio → cited answer →
`strategies_used: graph, sql, vector (corrective rounds: 0)`.

---

## 15. Containers, infrastructure, delivery

Details are **not** specified in the source docs. Known: Docker Compose runs real Postgres/SQLite-backed
backend + Qdrant + Neo4j + Redis; Supabase, Qdrant Cloud and Neo4j Aura are the managed forms; image tags
should be the git SHA.

### 15.1 Honest status rule

Track **implemented**, **validated locally**, **needs credentials**, and **actually deployed** separately.
Do not write "deployed" or "passes in CI" until it has.

---

## 16. Observability

- Every node transition, tool call, query and timing is recorded in `workflow_events` (F16) via
  `backend/app/core/observability.py`, readable at `GET /api/v1/research/{id}/events`.
- Telemetry must never break a run.
- **Exposed:** decisions, SQL and Cypher executed, evidence with scores, node timings, errors.
  **Never exposed:** raw prompts, hidden chain-of-thought, secrets.

---

## 17. Production extensions (not v1 scope)

- Real sources via `integrations/protocols.py` (`DocumentSource`): Confluence, SharePoint, Google Drive,
  ticketing API. Retrieval and agents stay identical; only ingestion adapters change.
- Per-tenant isolation: row-level filters in SQL, tenant-scoped graph labels, Qdrant payload filters.
- Worker-based execution with a Postgres checkpointer so any worker can resume any run.

---

## 18. Coding rules for this project

1. **Read before you write.** Check `API_CONTRACT.md`, the relevant PRD row and the existing test first.
2. **Keep layers clean** (4.2). `core` never imports `agents`. Agents never import repositories directly.
3. **Retrieval is a routing decision.** Never hard-code a single retriever; extend the router.
4. **Rules first, LLM second.** Routing floors and policy are deterministic in `agents/rules.py` and tested.
5. **One `Evidence` shape** for every retrieval path. No store-specific leakage into agent code.
6. **Read-only always.** SQL goes through `validate_sql()`; Cypher is typed or read-only. No exceptions.
7. **Structured outputs.** Every agent returns a Pydantic model; no free-text parsing.
8. **Injection-safe by default.** Anything from a document, upload or tool is untrusted data.
9. **Offline first.** New behaviour must pass `make test` with `LLM_PROVIDER=fake` and in-memory stores.
10. **Bounded loops.** Every retry or corrective loop has a config-driven maximum.
11. **Verify before shipping an answer.** Evidence verification and citation verification stay separate nodes.
12. **Failures degrade, not crash.** A store outage becomes a recorded sub-question error.
13. **Never commit** `.env`, `data/`, `*.db`, or any real key.
14. **Migrations are additive.** Never edit an applied migration.
15. **One change, one commit, one test.** Map each feature to a PRD row.
16. **Demo before production.** `make demo` must still work at the end of every stage.
17. **Say what is not done.** Keep honest status (15.1) current.

### 18.1 Things that must never happen

- An answer shipped with a citation `[n]` that does not resolve to evidence.
- A non-`SELECT` SQL statement or a write Cypher query executing.
- The vendor-note injection changing routing, tools or the answer.
- A `viewer` able to start research, upload or run Cypher (must return `403`).
- A document deleted without a recorded admin approval.
- An analyst reaching reindex / delete / approve.
- Raw prompts or hidden reasoning appearing in the API or the UI.
- An unbounded corrective loop.

---

## 19. Phase plan

| Phase | Name | Status |
|---|---|---|
| 1 | Runtime skeleton (config, llm factory, protocols, health) | not started |
| 2 | Persistence and demo data (models, seed `sample_data/`) | not started |
| 3 | Identity and request guards (JWT, RBAC, request-id, rate limit, audit) | not started |
| 4 | Ingestion (parse, chunk, extract, vector + DB + graph) | not started |
| 5 | Retrieval paths (hybrid, SQL + validator, graph traversals) | not started |
| 6 | Rules and guardrails (`rules.py`, injection handling) | not started |
| 7 | Research workflow (13 nodes, corrective loop, verification) | not started |
| 8 | Research API (202 + background task + polling + events) | not started |
| 9 | Memory (four scopes) | not started |
| 10 | Documents, graph and approval APIs | not started |
| 11 | Frontend (search, research, knowledge graph, documents) | not started |
| 12 | Evaluation and delivery | not started |

Phase boundaries are proposed from the dependency order in this file; adjust and record the change here.

---

## 20. Known gaps and open questions

- The source docs reference `05-rag.md`, `06-tools.md` and `16-observability.md` and a `README.md`, none of
  which were supplied. Tool design, memory scopes and observability details are **[TBD]**.
- The 13 node names, the memory scope names, graph node/edge types, chunking parameters, demo user
  emails, and the full env var list are not in the supplied docs. Fill them in as the code is written.
- `agents/nodes/` names in section 3.1 come from the PRD; `GRAPH_NODES` is the authority for the final list.
- PRD says "70 chunks / 85 nodes / 260 edges" for the in-memory run; treat these as observed values, not
  requirements.
- `MAX_SUBQUESTIONS`, `MAX_CORRECTIVE_ROUNDS` and the `.env` caching behaviour are the two most common
  causes of "why is the answer incomplete / why did my setting not apply".