# Functional Requirements Document (FRD / SRS)
## NovaEnterprise — Enterprise Knowledge & Decision Intelligence Platform

> **Document Status:** Approved / Baseline  
> **Document Owner:** Lead Systems Analyst & Enterprise AI Architect  
> **Target Audience:** Backend & Frontend Developers, AI Engineers, QA & Security Engineers  
> **Methodology Reference:** *The Complete AI Solution Architect Masterclass (NITMONK 2026)* — Foundations: BRD → PRD → FRD → HLD → LLD  
> **Upstream Documents:** [docs/BRD.md](BRD.md) (Business Requirements) · [docs/PRD.md](PRD.md) (Product Requirements)  
> **Downstream Documents:** [docs/HLD.md](HLD.md) (High-Level Design) · [docs/LLD.md](LLD.md) (Low-Level Design) · [Claude.md](../Claude.md) (Single Source of Truth)

---

## 1. Purpose & System Overview

### 1.1 Purpose
This Functional Requirements Document (FRD) / Software Requirements Specification (SRS) translates the business intent from [docs/BRD.md](BRD.md) and user experiences from [docs/PRD.md](PRD.md) into **precise, testable, and unambiguous technical specifications**. It defines the exact inputs, outputs, state transitions, validation rules, data schemas, and error boundaries governing the NovaEnterprise platform.

### 1.2 System Overview
NovaEnterprise is an enterprise multi-agent retrieval and decision intelligence system. It exposes a RESTful API layer (FastAPI) and a Next.js 15 web client, orchestrating a 13-node **LangGraph research workflow**. Retrieval is managed as a dynamic routing decision across three underlying data modalities:
1. **Unstructured Documents (Vector RAG):** Semantic dense embeddings + BM25 keyword search + Reciprocal Rank Fusion (RRF) + Cross-Encoder reranking.
2. **Relational Records (SQL):** AST-validated read-only `SELECT` queries executed against allowlisted tables.
3. **Entity Relationships (Graph RAG):** Typed graph traversals in Neo4j (or in-memory graph) exposing parameterized Cypher queries.

The platform guarantees **100% citation resolution**, **quarantined prompt injection defense**, and **graceful degradation** under partial subsystem outages.

---

## 2. Functional Requirements with Unique IDs (FR-01 to FR-17)

The functional requirements directly formalize requirements `F1` through `F17` from `Claude.md §3.1`:

| Req ID | Requirement Title | Input Specification | Processing & Execution Logic | Output Specification | Verification Proof |
|---|---|---|---|---|---|
| **FR-01** | **Async Job Intake (202)** | `POST /api/v1/research`<br>`{ "question": string }`<br>(Length: 5–2000 chars) | 1. Validate payload via Pydantic.<br>2. Authenticate JWT & verify role $\ge \text{analyst}$.<br>3. Generate UUID4 `session_id`.<br>4. Insert row in `research_sessions` with status `running`.<br>5. Schedule `BackgroundTask` for LangGraph workflow. | HTTP 202 Accepted:<br>`{ "session_id": "uuid",`<br>`  "status": "running",`<br>`  "created_at": ISO8601 }`<br>Response time $< 500\text{ms}$. | `tests/api/test_api.py::test_research_lifecycle` |
| **FR-02** | **Query Intent & Entity Extraction** | `ResearchState.question` | Node `analyze_query`: Parse query into intent, target entity, temporal filter (mapped via fiscal calendar in `organizational_memory.json`), and retrieval modalities required. | Partial State Update:<br>`{ "intent": str, "entity": str,`<br>`  "time_range": dict,`<br>`  "needs_graph": bool, ... }` | `tests/agents/test_agents.py::test_canonical_question_end_to_end` |
| **FR-03** | **Complexity Classification** | Extracted intent & entity count | Node `assess_complexity`: Evaluate query using deterministic rules (`agents/rules.py`). Classify as `simple`, `moderate`, or `complex`. | Partial State Update:<br>`{ "complexity": "simple" \|`<br>`              "moderate" \|`<br>`              "complex" }` | `tests/agents/test_agents.py::test_simple_question_single_subquestion` |
| **FR-04** | **Sub-Question Decomposition** | Query & Complexity | Node `decompose`: If `simple`, return 1 sub-question. If `complex`, decompose into $\le \text{MAX\_SUBQUESTIONS}$ (default 4). Each sub-question has ID `sq1..sq4`. | Partial State Update:<br>`{ "sub_questions": [`<br>`    { "id": "sq1",`<br>`      "text": str, ... } ] }` | `tests/agents/test_agents.py::test_canonical_question_end_to_end` |
| **FR-05** | **Multi-Store Dynamic Routing** | List of sub-questions | Node `route_retrieval`: Assign each sub-question exactly one retrieval strategy: `vector`, `sql`, `graph`, or `hybrid`. Enforce deterministic routing floors from `rules.py`. | Partial State Update:<br>`sub_question["strategy"] =`<br>`"vector" \| "sql" \|`<br>`"graph" \| "hybrid"` | `tests/rag/test_retrieval_graph.py::test_graph_shape_matches_frontend_assumptions` |
| **FR-06** | **Hybrid Document RAG** | Sub-question text with strategy `vector` or `hybrid` | `rag/retriever.py`: Run dense vector search (k=10) and sparse BM25 (k=10). Blend via Reciprocal Rank Fusion ($k=60$). Apply Cross-Encoder rerank ($top\_n=3$). | Returns `list[Evidence]` with `source_type="document"`, content, and document locator. | `tests/rag/test_retrieval_graph.py` |
| **FR-07** | **Governed SQL Retrieval** | Sub-question text with strategy `sql` | `rag/sql_retrieval.py`: Synthesize SQL query template. Pass through `validate_sql()` against allowlist. Execute on read-only connection. | Returns `list[Evidence]` with `source_type="sql"`, rows, and query string locator. | `tests/unit/test_sql_validator.py` (8 unit tests) |
| **FR-08** | **Typed Graph Traversals** | Sub-question text with strategy `graph` | `rag/graph_store.py`: Match query to typed Cypher traversal pattern. Execute on Neo4j/in-memory graph. Expose both graph results and executed Cypher string. | Returns `list[Evidence]` with `source_type="graph"`, node/edge data, and Cypher locator. | `tests/rag/test_retrieval_graph.py::test_graph_traversals` |
| **FR-09** | **Missing Evidence & Corrective Loop** | Collected `Evidence` list | Node `check_missing_evidence`: Verify each sub-question has $\ge 1$ supporting evidence item. If missing and `corrective_rounds < 1`, trigger `corrective_retrieval`. | Bounded branch:<br>If missing $\rightarrow$ `corrective_retrieval`<br>Else $\rightarrow$ `verify_evidence`. | `tests/agents/test_agents.py::test_corrective_retrieval_triggers_for_unanswerable_part` |
| **FR-10** | **Evidence Claim Verification** | Collected `Evidence` items | Node `verify_evidence`: Cross-check evidence claims for factual conflicts. Discard invalid or contradictory items. Calculate `verification_ratio`. | Partial State Update:<br>`{ "verified_evidence": list,`<br>`  "verification_ratio": float }` | `tests/agents/test_agents.py::test_canonical_question_end_to_end` |
| **FR-11** | **Cited Answer Synthesis** | Verified evidence & sub-questions | Node `synthesize_answer`: Assemble structured context. Prompt model to synthesize comprehensive response embedding numbered citation tokens `[n]`. | Partial State Update:<br>`{ "answer": str,`<br>`  "citations": list[Citation] }` | `tests/agents/test_agents.py::test_multi_hop_citations_and_grounding` |
| **FR-12** | **Citation Resolution Verification** | Synthesized answer text & evidence list | Node `verify_citations`: Scan markdown text for all `[n]` patterns. Verify each index $n$ exists in the evidence array. Strip or correct invalid citations. | Complete state dictionary:<br>`status="completed"`,<br>`unresolved_citations=[]`. | `tests/api/test_api.py::test_research_lifecycle` |
| **FR-13** | **Document Parsing & Ingest** | `POST /api/v1/documents`<br>Multipart form (`.md`, `.txt`, `.pdf`) $\le 5\text{MB}$ | `rag/ingest.py`: Clean text, wrap in untrusted data container, recursive chunking (512 tokens / 64 overlap), extract entities/relations, index in Vector & Graph. | HTTP 201 Created:<br>`{ "document_id": str,`<br>`  "chunks_indexed": int,`<br>`  "entities_extracted": int }` | `tests/api/test_api.py::test_upload_validation_and_ingest` |
| **FR-14** | **Knowledge Graph Exploration** | `GET /api/v1/graph`<br>`GET /api/v1/graph/expand/{id}` | `backend/app/api/graph.py`: Query Neo4j/in-memory store. Return nodes, properties, and directed edge arrays formatted for graph visualizers. | HTTP 200 OK:<br>`{ "nodes": [ {id, label, props} ],`<br>`  "edges": [ {source, target, type} ] }` | `tests/api/test_api.py::test_graph_endpoints` |
| **FR-15** | **Four-Scope Tiered Memory** | Session ID, User ID | `memory/memory_service.py`: Isolate working memory (node-level), episodic memory (session/Redis), semantic memory (user preferences), and organizational memory. | Memory context injected into `ResearchState`; updated at workflow conclusion. | `tests/api/test_api.py::test_research_lifecycle` |
| **FR-16** | **Decision Telemetry & Event Stream** | Node transitions & timings | `backend/app/core/observability.py`: Intercept every node execution with `tracer.node(...)`. Record inputs, outputs, queries, latencies in `workflow_events`. | HTTP 200 OK on `GET /api/v1/research/{id}/events`. Telemetry errors never fail workflow. | API verification at `/api/v1/research/{id}/events` |
| **FR-17** | **Approval Gate for Destructive Actions** | `DELETE /api/v1/documents/{id}`<br>`POST /api/v1/approvals/{id}/decide` | Document deletion requests pause execution and create an entry in `approval_requests`. Only `admin` role can approve/reject. | HTTP 202 Accepted (`pending_approval`) until approved; then HTTP 200 on execution. | `tests/api/test_api.py::test_upload_validation_and_ingest` |

---

## 3. Business Rules & Validations

```text
┌────────────────────────────────────────────────────────────────────────┐
│                      CORE SYSTEM BUSINESS RULES                        │
├───────────────┬────────────────────────────────────────────────────────┤
│ Rule ID       │ Rule Definition & Enforcement Boundary                 │
├───────────────┼────────────────────────────────────────────────────────┤
│ BR-RULE-01    │ SQL Safety Allowlist: Every generated SQL statement    │
│               │ must be parsed and validated by validate_sql(). Only   │
│               │ read-only SELECT queries on allowlisted tables         │
│               │ (incidents, services, teams, customers, decisions) are │
│               │ permitted. Dynamic string formatting (f-strings) is    │
│               │ strictly forbidden.                                    │
├───────────────┼────────────────────────────────────────────────────────┤
│ BR-RULE-02    │ Cypher Read-Only Enforcement: Graph queries must use   │
│               │ parameterized, typed traversals. User-submitted Cypher │
│               │ must not contain write clauses (CREATE, MERGE, SET,    │
│               │ DELETE, REMOVE).                                       │
├───────────────┼────────────────────────────────────────────────────────┤
│ BR-RULE-03    │ Untrusted Document Quarantining: Ingested documents    │
│               │ (especially third-party vendor notes) must be wrapped   │
│               │ in <untrusted_document_data> tags and scanned for      │
│               │ injection heuristics. Prompt text in documents must be │
│               │ indexed strictly as text data, never as instructions.  │
├───────────────┼────────────────────────────────────────────────────────┤
│ BR-RULE-04    │ Bounded Execution Caps: MAX_SUBQUESTIONS = 4;          │
│               │ MAX_CORRECTIVE_ROUNDS = 1. Agent workflows must never  │
│               │ loop indefinitely. If missing evidence persists after   │
│               │ round 1, synthesize answer using available evidence.   │
├───────────────┼────────────────────────────────────────────────────────┤
│ BR-RULE-05    │ Citation Inviolability: An answer must NEVER be shipped│
│               │ containing a citation marker [n] that does not resolve │
│               │ to an existing Evidence item in the payload.           │
├───────────────┼────────────────────────────────────────────────────────┤
│ BR-RULE-06    │ Store Failure Graceful Degradation: An outage in one   │
│               │ store (e.g., Neo4j unreachable) must record a degraded │
│               │ error status on that specific sub-question. It must    │
│               │ NEVER throw an unhandled exception or abort the run.   │
├───────────────┼────────────────────────────────────────────────────────┤
│ BR-RULE-07    │ Role Hierarchy Enforcement:                            │
│               │ • Viewer: 403 Forbidden on POST /research, uploads.    │
│               │ • Analyst: 403 Forbidden on document deletion, reindex.│
│               │ • Admin: Exclusive authority to resolve approvals.     │
├───────────────┼────────────────────────────────────────────────────────┤
│ BR-RULE-08    │ Deterministic Routing Floor: Deterministic rules in    │
│               │ agents/rules.py take precedence over probabilistic LLM │
│               │ routing outputs to guarantee test reproducibility.     │
└───────────────┴────────────────────────────────────────────────────────┘
```

---

## 4. Detailed Use Cases & Step-by-Step System Flows

### 4.1 Use Case UC-01: Research Query Execution (Canonical Flow)
- **Primary Actor:** Enterprise Analyst (Priya)
- **Preconditions:** User is authenticated via JWT with role `analyst`.
- **Main Success Scenario:**
  1. User submits natural language question via web client: `POST /api/v1/research`.
  2. System validates payload, persists `research_sessions` row, and returns `202 Accepted` with `session_id`.
  3. Client initiates polling against `GET /api/v1/research/{session_id}` every 2 seconds.
  4. System executes LangGraph workflow:
     - Node 1 (`analyze_query`): Detects target entity `Payments API` and maps `last quarter` to fiscal Q2 dates.
     - Node 2 (`assess_complexity`): Flags cross-domain join as `complex`.
     - Node 3 (`decompose`): Splits query into 4 sub-questions (SQ1: customer impact; SQ2: incident dates; SQ3: team ownership; SQ4: recurrence decisions).
     - Node 4 (`route_retrieval`): Assigns SQ1 $\rightarrow$ `graph`, SQ2 $\rightarrow$ `sql`, SQ3 $\rightarrow$ `graph`, SQ4 $\rightarrow$ `hybrid`.
     - Node 5–7 (Retrieval Execution): Executes parallel lookups across Graph, SQL, and Vector stores.
     - Node 8 (`collect_evidence`): Merges 9 retrieved items into standardized `Evidence` schemas.
     - Node 9 (`check_missing_evidence`): Confirms all 4 sub-questions have supporting evidence.
     - Node 10 (`verify_evidence`): Verifies factual claims and computes `verification_ratio = 1.00`.
     - Node 11 (`synthesize_answer`): Generates grounded text containing citation markers `[1]` through `[9]`.
     - Node 12 (`verify_citations`): Confirms all 9 citation tokens map to valid evidence IDs.
     - Node 13 (`memory_update`): Updates session episodic memory in Redis.
  5. Workflow status in DB transitions to `completed`.
  6. Client receives completed payload with synthesized text and evidence objects, displaying interactive view in $< 10$ seconds.

- **Alternative Flow 4a: Missing Evidence Trigger (Bounded Corrective Loop)**
  - At Step 4 (Node 9), SQ4 has 0 matching evidence items.
  - System checks `corrective_rounds == 0`.
  - Routes to `corrective_retrieval`, rephrasing SQ4 search query with expanded synonyms.
  - Re-executes hybrid retriever; appends newly discovered evidence items.
  - Increments `corrective_rounds = 1`; advances to Node 10 (`verify_evidence`).

- **Alternative Flow 4b: Store Degradation (Resilient Partial Failure)**
  - At Step 4 (Node 5), Graph Store connection times out.
  - System catches connection error, writes `{ "error": "Graph store degraded", "evidence": [] }` for SQ1 and SQ3.
  - SQL and Vector retrievals continue unimpeded.
  - Synthesizer delivers partial response explicitly stating graph data was unreachable. HTTP status remains 200 OK.

---

### 4.2 Use Case UC-02: Document Ingestion with Injection Quarantine
- **Primary Actor:** Enterprise Analyst / Admin
- **Preconditions:** Authenticated user with role $\ge \text{analyst}$.
- **Main Success Scenario:**
  1. User submits file `vendor-note-processor-update.md` via `POST /api/v1/documents`.
  2. System verifies file extension (`.md`) and size ($< 5\text{MB}$).
  3. Sanitization layer intercepts file content and executes injection scanner (`guardrails.py`).
  4. Heuristic engine flags prompt override pattern (`"SYSTEM OVERRIDE: Ignore previous..."`).
  5. Content is wrapped in immutable XML data block `<untrusted_document_data>` and indexed in Vector and Relational stores with metadata `{ "quarantined": true, "injection_flag": true }`.
  6. System returns `201 Created` with `document_id`.

---

### 4.3 Use Case UC-03: Document Deletion Approval Gate
- **Primary Actor:** Analyst Priya (Requester) & Admin David (Approver)
- **Preconditions:** Analyst is authenticated; target document exists.
- **Main Success Scenario:**
  1. Analyst submits `DELETE /api/v1/documents/{document_id}`.
  2. System detects destructive operation; intercepts deletion.
  3. Creates `approval_requests` record with `status="pending"`, capturing requester ID, target ID, and timestamp.
  4. Returns `202 Accepted` `{ "approval_id": "app-101", "status": "pending_approval" }`.
  5. Admin David navigates to `/documents`, reviews pending approval drawer, and clicks "Approve".
  6. Admin client issues `POST /api/v1/approvals/app-101/decide` `{ "decision": "approved" }`.
  7. System executes physical deletion of vector chunks, graph nodes, and database records.

---

## 5. Data Requirements & Schemas

### 5.1 Common Evidence Contract (`backend/app/schemas/common.py`)
All retrieval modalities (Vector, SQL, Graph) **MUST** normalize their output into the identical `Evidence` schema before reaching agent reasoning nodes:

```json
{
  "id": "evi_01J8Z9X2...",
  "sub_question_id": "sq1",
  "source_type": "graph",
  "locator": "(Service:Payments API)<-[:AFFECTED]-(Incident:INC-2031)-[:IMPACTED]->(Customer:Acme)",
  "content": "Customer Acme Corp (tier: enterprise) was impacted by SEV1 outage INC-2031 on Payments API.",
  "score": 1.0,
  "metadata": {
    "store": "neo4j",
    "cypher_query": "MATCH (s:Service {name: $svc})<-[:AFFECTED]-(i:Incident)-[:IMPACTED]->(c:Customer) RETURN c.name, i.id"
  }
}
```

### 5.2 Research State Schema (`ResearchState`)
The LangGraph state dictionary passed between all 13 nodes:

| Field Name | Type | Description |
|---|---|---|
| `session_id` | `str` (UUID) | Unique research execution identifier. |
| `question` | `str` | Original user natural language question. |
| `complexity` | `Literal["simple", "moderate", "complex"]` | Classified complexity rating. |
| `intent` | `str` | Identified query intent. |
| `entity` | `str` | Primary extracted enterprise entity. |
| `time_range` | `dict[str, str]` | Resolved start and end ISO dates. |
| `sub_questions` | `list[dict]` | List of decomposed sub-questions with assigned strategies. |
| `evidence` | `list[Evidence]` | Aggregate collected evidence items across all stores. |
| `corrective_rounds` | `int` | Counter tracking corrective iterations (max 1). |
| `verification_ratio` | `float` | Proportion of claims successfully verified against evidence. |
| `answer` | `str` | Synthesized Markdown text with embedded `[n]` citations. |
| `citations` | `list[Citation]` | Array of citation mappings linking `[n]` to `evidence.id`. |
| `errors` | `list[str]` | Recorded non-fatal subsystem or store degradation messages. |
| `status` | `Literal["running", "completed", "failed"]` | Overall workflow execution state. |

---

## 6. Interface & Integration Specifications

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL SYSTEM INTERFACES                      │
├────────────────────┬───────────────────────────────────────────────────┤
│ Interface          │ Protocol & Integration Contract                   │
├────────────────────┼───────────────────────────────────────────────────┤
│ Relational DB      │ SQLAlchemy Core/ORM over PostgreSQL / SQLite.     │
│                    │ Read-only pool, parameterized binds, strict RLS.  │
├────────────────────┼───────────────────────────────────────────────────┤
│ Vector Store       │ VectorStoreService Protocol:                      │
│                    │ search(vector, k, filters) -> list[Chunk]         │
│                    │ Qdrant REST/gRPC (Cloud) or In-Memory (Local).    │
├────────────────────┼───────────────────────────────────────────────────┤
│ Graph Store        │ GraphStoreService Protocol:                       │
│                    │ query(cypher, params) -> list[Node/Edge]          │
│                    │ Neo4j Bolt protocol (Aura) or In-Memory NetworkX. │
├────────────────────┼───────────────────────────────────────────────────┤
│ LLM Gateway        │ get_llm(provider, model) -> BaseChatModel         │
│                    │ Supports 8 providers + FakeProvider for offline.  │
├────────────────────┼───────────────────────────────────────────────────┤
│ Cache & Epistemic  │ Redis 7.0+ / fakeredis.                           │
│ Memory             │ Token bucket rate limiting, session working state.│
└────────────────────┴───────────────────────────────────────────────────┘
```

---

## 7. Error Handling & Exception Catalog

| Error Code | HTTP Status | Trigger Condition | System Behavior & Mitigation |
|---|---|---|---|
| `ERR_AUTH_FORBIDDEN` | 403 Forbidden | User role insufficient (e.g. Viewer triggers research). | Abort request immediately. Log security audit event. |
| `ERR_INVALID_SQL` | 400 Bad Request | Generated SQL fails `validate_sql()` allowlist check. | Intercept execution. Record sub-question error. Fall back to vector search. |
| `ERR_INJECTION_DETECTED` | 200 / 201 (Handled) | Document ingestion contains prompt injection. | Quarantine document in `<untrusted_document_data>` container; index as passive data only. |
| `ERR_STORE_UNAVAILABLE` | 200 (Degraded) | Vector or Graph backing store unreachable. | Catch network timeout. Record store degradation in `errors` list. Synthesize partial answer. |
| `ERR_RATE_LIMIT_EXCEEDED` | 429 Too Many Requests | Client exceeds 120 requests/minute. | Return 429 with `Retry-After: 60` header. |
| `ERR_CORRECTIVE_EXHAUSTED` | 200 (Handled) | Evidence still missing after 1 corrective round. | Terminate loop. Synthesize best-effort response explicitly noting missing data facets. |

---

## 8. Requirements Traceability Matrix (RTM)

| BRD Ref | PRD Epic | FRD ID | Architectural Component | Pytest Verification Proof |
|---|---|---|---|---|
| BR-01 | Epic 1 | **FR-01** | `backend/app/api/research.py` | `tests/api/test_api.py::test_research_lifecycle` |
| BR-02 | Epic 2 | **FR-02** | `agents/nodes/analyze_query.py` | `tests/agents/test_agents.py::test_canonical_question_end_to_end` |
| BR-02 | Epic 2 | **FR-03** | `agents/nodes/assess_complexity.py` | `tests/agents/test_agents.py::test_simple_question_single_subquestion` |
| BR-02 | Epic 2 | **FR-04** | `agents/nodes/decompose.py` | `tests/agents/test_agents.py::test_canonical_question_end_to_end` |
| BR-02 | Epic 2 | **FR-05** | `agents/nodes/route_retrieval.py` | `tests/rag/test_retrieval_graph.py::test_graph_shape_matches_frontend_assumptions` |
| BR-02 | Epic 3 | **FR-06** | `rag/retriever.py` | `tests/rag/test_retrieval_graph.py` |
| BR-02 | Epic 3 | **FR-07** | `rag/sql_retrieval.py` | `tests/unit/test_sql_validator.py` (8 tests) |
| BR-02 | Epic 3 | **FR-08** | `rag/graph_store.py` | `tests/rag/test_retrieval_graph.py::test_graph_traversals` |
| BR-04 | Epic 4 | **FR-09** | `agents/nodes/check_missing_evidence.py` | `tests/agents/test_agents.py::test_corrective_retrieval_triggers_for_unanswerable_part` |
| BR-04 | Epic 4 | **FR-10** | `agents/nodes/verify_evidence.py` | `tests/agents/test_agents.py::test_canonical_question_end_to_end` |
| BR-03 | Epic 4 | **FR-11** | `agents/nodes/synthesize_answer.py` | `tests/agents/test_agents.py::test_multi_hop_citations_and_grounding` |
| BR-03 | Epic 4 | **FR-12** | `agents/nodes/verify_citations.py` | `tests/api/test_api.py::test_research_lifecycle` |
| BR-06 | Epic 5 | **FR-13** | `rag/ingest.py` | `tests/api/test_api.py::test_upload_validation_and_ingest` |
| BR-02 | Epic 5 | **FR-14** | `backend/app/api/graph.py` | `tests/api/test_api.py::test_graph_endpoints` |
| BR-08 | Epic 5 | **FR-15** | `memory/memory_service.py` | `tests/api/test_api.py::test_research_lifecycle` |
| BR-09 | Epic 5 | **FR-16** | `backend/app/core/observability.py` | `GET /api/v1/research/{id}/events` |
| BR-07 | Epic 5 | **FR-17** | `backend/app/api/documents.py` | `tests/api/test_api.py::test_upload_validation_and_ingest` |

---
*Next in Document Chain:* → **[docs/HLD.md](HLD.md)** (High-Level Design: C1/C2 Architecture & Integration Views)
