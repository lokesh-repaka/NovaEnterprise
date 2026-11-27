# NovaEnterprise API Contract & Schema Specification

> **Authoritative Specification:** Single source of truth for all API routes, data schemas, RBAC constraints, error models, and client bindings (`Claude.md §12`).
>
> **Base URL:** `http://localhost:8001/api/v1` (unprefixed health routes at `http://localhost:8001/health` and `/health/ready`).
>
> **Protocol:** HTTP/1.1 and HTTP/2 over TLS/TCP. All JSON payloads use UTF-8 encoding.
>
> **Versioning Policy:** SemVer 2.0. If an endpoint signature or payload schema changes, `docs/API_CONTRACT.md`, the backend Pydantic schemas, and the frontend TypeScript types must be updated in the same pull request.

---

## 1. Global Conventions & Protocol Invariants

### 1.1 Global Headers

| Header | Direction | Type | Description |
|---|---|---|---|
| `X-Request-ID` | Request / Response | `UUID4` string | Trace ID for end-to-end request tracing (N5). Echoed back on all responses or generated if omitted by client. |
| `Authorization` | Request | `string` | Format: `Authorization: Bearer <JWT>`. Required on all protected endpoints. |
| `X-RateLimit-Limit` | Response | `integer` | Token bucket capacity per client IP/user (default: `120` req/min, N6). |
| `X-RateLimit-Remaining`| Response | `integer` | Remaining token count in the current 60-second window. |
| `X-RateLimit-Reset` | Response | `integer` | Epoch timestamp (seconds) when rate limit capacity is replenished. |

*Note: `/health` and `/health/ready` are strictly exempt from rate limiting.*

### 1.2 RBAC Role Enforcement Hierarchy

Enforced server-side via `require_role()` guard (`Claude.md §2`, `backend/app/core/security.py`).

```text
public ──► viewer ──► analyst ──► admin
```

- **`Public`**: Health probes, demo user discovery, token issuance, credential login.
- **`viewer`**: Read-only dashboards, browse domain entities (customers, incidents, services, teams, decisions, projects, tickets), view completed research sessions and citations, inspect document index, browse knowledge graph.
- **`analyst`**: All `viewer` permissions + launch research workflows (`POST /api/v1/research`), upload documents (`POST /api/v1/documents/upload`), execute read-only Cypher queries (`POST /api/v1/graph/query`), initiate document deletion (creates pending approval request).
- **`admin`**: All `analyst` permissions + decide on approval requests (`POST /api/v1/approvals/{id}/decide`), execute direct document deletion, trigger store reindexing.

### 1.3 Standard Error Responses

All error responses share a standard JSON envelope:

```json
{
  "detail": "Descriptive human-readable error explanation or validation array"
}
```

| HTTP Status Code | Classification | Description |
|---|---|---|
| `200 OK` | Success | Request succeeded synchronously; response body contains data. |
| `201 Created` | Success | Resource created successfully (e.g., document upload). |
| `202 Accepted` | Async Intake | Asynchronous task accepted for processing (e.g., research workflow launch or approval gating). |
| `400 Bad Request` | Client Error | Malformed payload, unsupported parameters, or invalid operation. |
| `401 Unauthorized` | Client Error | Missing, expired, or cryptographically invalid JWT Bearer token. |
| `403 Forbidden` | Client Error | Authenticated user lacks required RBAC role (`viewer`, `analyst`, or `admin`). |
| `404 Not Found` | Client Error | Requested resource ID does not exist. |
| `422 Unprocessable Entity` | Validation Error | Request body or query parameters failed Pydantic schema validation. |
| `429 Too Many Requests` | Rate Limited | Token bucket exhausted. Client must wait until `X-RateLimit-Reset`. |
| `500 Internal Server Error` | Server Error | Unhandled server exception. Error details logged internally with trace ID. |

---

## 2. Canonical Retrieval Evidence Contract

As specified in `Claude.md §5`, all three retrieval paths (**Vector/Hybrid**, **SQL**, and **Graph**) yield the **identical `Evidence` shape**. That invariant makes unified citation synthesis and verification possible.

### `Evidence` Schema

```json
{
  "id": "evi_01J8Z9X2A4M8Q9K3",
  "sub_question_id": "sq1",
  "source_type": "graph",
  "locator": "(Service:Payments API)<-[:AFFECTED]-(Incident:INC-2031)-[:IMPACTED]->(Customer:Acme Corp)",
  "content": "Customer Acme Corp (tier: enterprise) was impacted by SEV1 outage INC-2031 on Payments API.",
  "score": 1.0,
  "metadata": {
    "store": "neo4j",
    "cypher": "MATCH (s:Service {name: 'Payments API'})<-[:AFFECTED]-(i:Incident)-[:IMPACTED]->(c:Customer) RETURN c.name, i.id"
  }
}
```

| Field | Type | Description |
|---|---|---|
| `id` | `string` | Unique evidence identifier (`evi_<UUID>` or deterministic hash). |
| `sub_question_id` | `string` | ID of the decomposed sub-question that triggered this retrieval (`sq1`, `sq2`). |
| `source_type` | `string` | Enum: `"document"` \| `"sql"` \| `"graph"`. |
| `locator` | `string` | Deterministic citation locator (document filename + section, SQL table + row ID, or Cypher graph path). |
| `content` | `string` | Plaintext content snippet or serialized record data. |
| `score` | `float` | Relevance / confidence score normalized between `0.0` and `1.0`. |
| `metadata` | `object` | Store-specific provenance data (e.g., `store`, `table`, `chunk_id`, `sql_query`, `cypher`). |

---

## 3. Endpoint Catalog & Route Specifications

```text
├── Health & Readiness (Public)
│   ├── GET  /health
│   └── GET  /health/ready
│
├── Authentication & Identity (/api/v1/auth)
│   ├── GET  /api/v1/auth/demo-users
│   ├── POST /api/v1/auth/demo-token
│   ├── POST /api/v1/auth/login
│   ├── POST /api/v1/auth/token
│   └── GET  /api/v1/auth/me
│
├── Browse Domain Entities (/api/v1/...) [viewer+]
│   ├── GET  /api/v1/customers
│   ├── GET  /api/v1/customers/{id}
│   ├── GET  /api/v1/incidents
│   ├── GET  /api/v1/incidents/{id}
│   ├── GET  /api/v1/services
│   ├── GET  /api/v1/services/{id}
│   ├── GET  /api/v1/teams
│   ├── GET  /api/v1/teams/{id}
│   ├── GET  /api/v1/decisions
│   ├── GET  /api/v1/decisions/{id}
│   ├── GET  /api/v1/projects
│   ├── GET  /api/v1/projects/{id}
│   ├── GET  /api/v1/tickets
│   └── GET  /api/v1/tickets/{id}
│
├── Research Engine & Observability (/api/v1/research)
│   ├── POST /api/v1/research                 [analyst+] -> 202 Accepted
│   ├── GET  /api/v1/research                 [viewer+]
│   ├── GET  /api/v1/research/{session_id}    [viewer+]
│   └── GET  /api/v1/research/{session_id}/events [viewer+]
│
├── Knowledge Graph Explorer (/api/v1/graph)
│   ├── GET  /api/v1/graph                    [viewer+]
│   ├── GET  /api/v1/graph/expand/{id}        [viewer+]
│   └── POST /api/v1/graph/query              [analyst+]
│
├── Document Ingestion & Management (/api/v1/documents)
│   ├── POST /api/v1/documents/upload         [analyst+] -> 201 Created
│   ├── GET  /api/v1/documents                [viewer+]
│   ├── GET  /api/v1/documents/{id}           [viewer+]
│   └── DELETE /api/v1/documents/{id}         [analyst: 202 pending | admin: 200/204]
│
└── Governance & Approvals (/api/v1/approvals)
    ├── GET  /api/v1/approvals                [viewer+]
    ├── GET  /api/v1/approvals/{id}           [viewer+]
    └── POST /api/v1/approvals/{id}/decide    [admin]
```

---

### 3.1 Health & Readiness Probes

#### `GET /health`
- **Summary:** Liveness probe.
- **RBAC:** Public (unauthenticated).
- **Rate Limit:** Exempt.
- **Response `200 OK`:**
  ```json
  {
    "status": "ok"
  }
  ```

#### `GET /health/ready`
- **Summary:** Readiness probe checking database, vector store, graph store, and cache connections.
- **RBAC:** Public (unauthenticated).
- **Rate Limit:** Exempt.
- **Response `200 OK` (All Healthy or Degraded):**
  ```json
  {
    "status": "ready",
    "checks": {
      "database": {
        "status": "ok",
        "details": "connected"
      },
      "vector_store": {
        "status": "ok",
        "details": "memory (70 chunks)"
      },
      "graph_store": {
        "status": "ok",
        "details": "memory (85 nodes, 260 edges)"
      },
      "redis": {
        "status": "ok",
        "details": "fakeredis"
      }
    }
  }
  ```
- **Response `200 OK` (Degraded):** When a secondary store is unavailable, status reports `"degraded"`, allowing partial operations without crashing (Claude.md §10).

---

### 3.2 Authentication & Identity Endpoints (`/api/v1/auth`)

#### `GET /api/v1/auth/demo-users`
- **Summary:** List predefined enterprise demo accounts for quick switcher.
- **RBAC:** Public.
- **Response `200 OK`:** `list[DemoUser]`
  ```json
  [
    {
      "id": "usr-admin-01",
      "username": "admin",
      "email": "admin@novaenterprise.io",
      "role": "admin",
      "name": "Alex Vance (Admin)",
      "description": "Full access: approval workflow, reindex, delete"
    },
    {
      "id": "usr-analyst-01",
      "username": "analyst",
      "email": "analyst@novaenterprise.io",
      "role": "analyst",
      "name": "Morgan Reed (Analyst)",
      "description": "Research execution, document upload, Cypher explorer"
    },
    {
      "id": "usr-viewer-01",
      "username": "viewer",
      "email": "viewer@novaenterprise.io",
      "role": "viewer",
      "name": "Taylor Swift (Viewer)",
      "description": "Read-only access to dashboards, browse entities, citations"
    }
  ]
  ```

#### `POST /api/v1/auth/demo-token`
- **Summary:** Obtain a signed JWT for a demo role without password input.
- **RBAC:** Public.
- **Request Body:**
  ```json
  {
    "role": "analyst"
  }
  ```
- **Response `200 OK`:** `TokenResponse`
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 86400,
    "role": "analyst",
    "user_id": "usr-analyst-01",
    "email": "analyst@novaenterprise.io",
    "username": "analyst"
  }
  ```

#### `POST /api/v1/auth/login`
- **Summary:** Authenticate with username/email and password.
- **RBAC:** Public.
- **Request Body:**
  ```json
  {
    "username_or_email": "admin@novaenterprise.io",
    "password": "demo_password"
  }
  ```
- **Response `200 OK`:** `TokenResponse`
- **Errors:** `401 Unauthorized` if credentials are invalid.

#### `POST /api/v1/auth/token`
- **Summary:** OAuth2 specification-compliant password form authentication.
- **RBAC:** Public.
- **Content-Type:** `application/x-www-form-urlencoded`
- **Form Data:** `username`, `password`
- **Response `200 OK`:** `TokenResponse`

#### `GET /api/v1/auth/me`
- **Summary:** Retrieve profile details for the authenticated user.
- **RBAC:** `viewer`, `analyst`, or `admin`.
- **Headers:** `Authorization: Bearer <JWT>`
- **Response `200 OK`:** `UserProfileResponse`
  ```json
  {
    "id": "usr-analyst-01",
    "username": "analyst",
    "email": "analyst@novaenterprise.io",
    "role": "analyst",
    "is_active": true,
    "created_at": "2026-11-27T10:00:00Z"
  }
  ```

---

### 3.3 Browse Domain Entities (`/api/v1/...`)

All browse entity endpoints require at least `viewer` role. They support pagination via `skip` and `limit`.

#### `GET /api/v1/customers`
- **Summary:** List enterprise customers with filtering.
- **RBAC:** `viewer`+
- **Query Parameters:**
  - `skip` (`int`, default `0`): Pagination offset.
  - `limit` (`int`, default `50`, max `100`): Page size.
  - `tier` (`string`, optional): Filter by tier (`enterprise`, `mid-market`, `smb`).
- **Response `200 OK`:** `list[CustomerResponse]`
  ```json
  [
    {
      "id": "cust-acme",
      "name": "Acme Corp",
      "tier": "enterprise",
      "contract_value": 2400000.00,
      "industry": "FinTech",
      "created_at": "2026-01-15T08:00:00Z"
    }
  ]
  ```

#### `GET /api/v1/customers/{id}`
- **Summary:** Retrieve single customer record by ID.
- **RBAC:** `viewer`+
- **Response `200 OK`:** `CustomerResponse`
- **Errors:** `404 Not Found` if customer does not exist.

#### `GET /api/v1/incidents`
- **Summary:** List production and security incidents.
- **RBAC:** `viewer`+
- **Query Parameters:**
  - `skip` (`int`, default `0`)
  - `limit` (`int`, default `50`)
  - `severity` (`string`, optional): e.g. `SEV1`, `SEV2`, `SEV3`.
  - `status` (`string`, optional): e.g. `investigating`, `mitigated`, `resolved`.
  - `service_id` (`string`, optional): Filter by impacted service ID.
- **Response `200 OK`:** `list[IncidentResponse]`
  ```json
  [
    {
      "id": "inc-2031",
      "title": "Payments API Outage during Q2 Peak Processing",
      "severity": "SEV1",
      "status": "resolved",
      "root_cause": "Connection pool exhaustion due to slow downstream vendor auth callback",
      "impacted_service_id": "svc-payments-api",
      "occurred_at": "2026-05-14T14:22:00Z",
      "resolved_at": "2026-05-14T16:45:00Z",
      "created_at": "2026-05-14T14:25:00Z"
    }
  ]
  ```

#### `GET /api/v1/incidents/{id}`
- **Summary:** Retrieve detailed incident record including associated decisions.
- **RBAC:** `viewer`+
- **Response `200 OK`:** `IncidentDetailResponse`

#### `GET /api/v1/services`
- **Summary:** List catalog microservices and components.
- **RBAC:** `viewer`+
- **Query Parameters:** `skip`, `limit`, `tier` (`tier-1`, `tier-2`), `owner_team_id`.
- **Response `200 OK`:** `list[ServiceResponse]`
  ```json
  [
    {
      "id": "svc-payments-api",
      "name": "Payments API",
      "tier": "tier-1",
      "port": 8080,
      "repo_url": "https://github.com/novaenterprise/payments-api",
      "owner_team_id": "team-payments-platform",
      "created_at": "2026-01-10T12:00:00Z"
    }
  ]
  ```

#### `GET /api/v1/services/{id}`
- **Summary:** Retrieve service metadata and operational owner team.
- **RBAC:** `viewer`+
- **Response `200 OK`:** `ServiceResponse`

#### `GET /api/v1/teams`
- **Summary:** List engineering and operational teams.
- **RBAC:** `viewer`+
- **Query Parameters:** `skip`, `limit`.
- **Response `200 OK`:** `list[TeamResponse]`
  ```json
  [
    {
      "id": "team-payments-platform",
      "name": "Payments Platform",
      "lead": "Sarah Jenkins",
      "slack_channel": "#team-payments",
      "description": "Core transaction processing, card gateways, and settlement engine",
      "created_at": "2026-01-05T09:00:00Z"
    }
  ]
  ```

#### `GET /api/v1/teams/{id}`
- **Summary:** Retrieve team record with members (employees), owned services, and projects.
- **RBAC:** `viewer`+
- **Response `200 OK`:** `TeamDetailResponse`

#### `GET /api/v1/decisions`
- **Summary:** List Architectural Decision Records (ADRs).
- **RBAC:** `viewer`+
- **Query Parameters:** `skip`, `limit`, `status` (`proposed`, `accepted`, `rejected`), `incident_id`.
- **Response `200 OK`:** `list[DecisionResponse]`
  ```json
  [
    {
      "id": "adr-012",
      "title": "ADR 012: Asynchronous Payment Callbacks with Circuit Breaker",
      "status": "accepted",
      "context": "Following INC-2031, synchronous vendor callbacks caused connection pool exhaustion.",
      "decision": "Introduce BullMQ worker queue and Redis circuit breaker for third-party processors.",
      "consequences": "Improved reliability; eventual consistency for payment status updates.",
      "incident_id": "inc-2031",
      "decided_at": "2026-05-20T10:00:00Z",
      "created_at": "2026-05-18T11:00:00Z"
    }
  ]
  ```

#### `GET /api/v1/decisions/{id}`
- **Summary:** Retrieve single ADR by ID.
- **RBAC:** `viewer`+
- **Response `200 OK`:** `DecisionResponse`

#### `GET /api/v1/projects`
- **Summary:** List engineering initiatives and platform projects.
- **RBAC:** `viewer`+
- **Query Parameters:** `skip`, `limit`, `status` (`active`, `completed`), `team_id`.
- **Response `200 OK`:** `list[ProjectResponse]`

#### `GET /api/v1/projects/{id}`
- **Summary:** Retrieve project record with tracked tickets.
- **RBAC:** `viewer`+
- **Response `200 OK`:** `ProjectDetailResponse`

#### `GET /api/v1/tickets`
- **Summary:** List issue and task tickets.
- **RBAC:** `viewer`+
- **Query Parameters:** `skip`, `limit`, `status`, `priority` (`P0`, `P1`, `P2`), `project_id`, `assignee_id`.
- **Response `200 OK`:** `list[TicketResponse]`

#### `GET /api/v1/tickets/{id}`
- **Summary:** Retrieve single ticket by ID.
- **RBAC:** `viewer`+
- **Response `200 OK`:** `TicketResponse`

---

### 3.4 Research Engine & Observability (`/api/v1/research`)

Implements the multi-hop LangGraph workflow (Phase 10, F1–F16).

#### `POST /api/v1/research`
- **Summary:** Launch an asynchronous enterprise research query.
- **RBAC:** `analyst` or `admin` (`viewer` receives `403 Forbidden`).
- **Status Code:** `202 Accepted`
- **Request Body (`ResearchCreateRequest`):**
  ```json
  {
    "question": "Which customers were impacted by the Payments API outage last quarter and what ADR was created to address it?",
    "user_id": "usr-analyst-01"
  }
  ```
  - `question`: `string`, 5–2000 characters.
  - `user_id`: `string`, optional analyst identifier for episodic memory tracking.
- **Response `202 Accepted` (`ResearchCreateResponse`):**
  ```json
  {
    "session_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "status": "running",
    "question": "Which customers were impacted by the Payments API outage last quarter and what ADR was created to address it?",
    "created_at": "2026-11-27T12:00:00Z"
  }
  ```

#### `GET /api/v1/research`
- **Summary:** List recent research sessions with status summaries.
- **RBAC:** `viewer`+
- **Query Parameters:** `skip` (`int`, default `0`), `limit` (`int`, default `20`).
- **Response `200 OK`:** `list[ResearchSessionSummary]`

#### `GET /api/v1/research/{session_id}`
- **Summary:** Poll current research session state, answer synthesis, evidence, and citations.
- **RBAC:** `viewer`+
- **Polling Cadence:** Recommended 2000 ms until `status` is `"completed"` or `"failed"`.
- **Response `200 OK` (`ResearchSessionResponse`):**
  ```json
  {
    "session_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "status": "completed",
    "question": "Which customers were impacted by the Payments API outage last quarter and what ADR was created to address it?",
    "complexity": "complex",
    "strategies_used": ["graph", "sql", "vector"],
    "corrective_rounds": 0,
    "verification_ratio": 1.0,
    "answer": "During Q2, three enterprise customers were impacted by the Payments API outage INC-2031 [1]: Acme Corp, TechFlow, and FinEdge. To prevent future connection pool exhaustion, the Payments Platform team authored ADR 012 [2], which introduced asynchronous payment processing via worker queues and a circuit breaker.",
    "citations": [
      {
        "citation_id": 1,
        "evidence_id": "evi_01J8Z9X2A4M8Q9K3",
        "source_type": "graph",
        "locator": "(Service:Payments API)<-[:AFFECTED]-(Incident:INC-2031)-[:IMPACTED]->(Customer:Acme Corp)",
        "snippet": "Acme Corp impacted by INC-2031 on Payments API"
      },
      {
        "citation_id": 2,
        "evidence_id": "evi_01J8Z9X2A4M8Q9K4",
        "source_type": "document",
        "locator": "documents/adr-012-async-payment-callbacks.md#Section-2",
        "snippet": "ADR 012 proposes decoupling payment callbacks using BullMQ queues"
      }
    ],
    "evidence": [
      {
        "id": "evi_01J8Z9X2A4M8Q9K3",
        "sub_question_id": "sq1",
        "source_type": "graph",
        "locator": "(Service:Payments API)<-[:AFFECTED]-(Incident:INC-2031)-[:IMPACTED]->(Customer:Acme Corp)",
        "content": "Customer Acme Corp was impacted by SEV1 outage INC-2031 on Payments API.",
        "score": 1.0,
        "metadata": { "store": "neo4j" }
      }
    ],
    "sub_questions": [
      {
        "id": "sq1",
        "question": "Which customers were impacted by Payments API outage INC-2031?",
        "strategy": "graph",
        "status": "answered"
      },
      {
        "id": "sq2",
        "question": "What architectural decision was made following incident INC-2031?",
        "strategy": "vector",
        "status": "answered"
      }
    ],
    "execution_time_seconds": 6.84,
    "error_message": null,
    "created_at": "2026-11-27T12:00:00Z",
    "updated_at": "2026-11-27T12:00:07Z"
  }
  ```

#### `GET /api/v1/research/{session_id}/events`
- **Summary:** Retrieve granular workflow execution telemetry and node transition timeline (F16).
- **RBAC:** `viewer`+
- **Safety Guarantee:** Exposes node timings, queries, strategies, and evidence scores. Strictly never exposes raw prompts, hidden chain-of-thought, or internal secrets (N9).
- **Response `200 OK`:** `list[WorkflowEventResponse]`
  ```json
  [
    {
      "event_id": 101,
      "session_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "node_name": "assess_complexity",
      "event_type": "node_complete",
      "payload": {
        "complexity": "complex",
        "reason": "Cross-domain entity join involving customers, incidents, and decisions"
      },
      "latency_ms": 142,
      "timestamp": "2026-11-27T12:00:01.142Z"
    },
    {
      "event_id": 102,
      "session_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "node_name": "route_retrieval",
      "event_type": "node_complete",
      "payload": {
        "routes": {
          "sq1": "graph",
          "sq2": "vector"
        }
      },
      "latency_ms": 88,
      "timestamp": "2026-11-27T12:00:01.230Z"
    }
  ]
  ```

---

### 3.5 Knowledge Graph Explorer (`/api/v1/graph`)

Graph exploration and read-only Cypher query execution (Phase 11, F14).

#### `GET /api/v1/graph`
- **Summary:** Browse knowledge graph subgraph matching criteria.
- **RBAC:** `viewer`+
- **Query Parameters:**
  - `limit` (`int`, default `100`, max `500`): Max nodes/edges.
  - `node_label` (`string`, optional): e.g. `Customer`, `Service`, `Incident`.
- **Response `200 OK` (`GraphDataResponse`):**
  ```json
  {
    "nodes": [
      {
        "id": "Service:svc-payments-api",
        "label": "Service",
        "properties": {
          "name": "Payments API",
          "tier": "tier-1"
        }
      },
      {
        "id": "Incident:inc-2031",
        "label": "Incident",
        "properties": {
          "title": "Payments API Outage",
          "severity": "SEV1"
        }
      }
    ],
    "edges": [
      {
        "id": "edge-01",
        "source": "Incident:inc-2031",
        "target": "Service:svc-payments-api",
        "type": "AFFECTED",
        "properties": {}
      }
    ]
  }
  ```

#### `GET /api/v1/graph/expand/{id}`
- **Summary:** Expand a single node by retrieving all 1-hop neighbor nodes and connecting edges.
- **RBAC:** `viewer`+
- **Path Parameter:** `id` (`string`): Target node ID.
- **Query Parameters:**
  - `direction` (`string`, default `"both"`): `"in"`, `"out"`, or `"both"`.
  - `relationship_type` (`string`, optional): Filter specific edge label.
- **Response `200 OK`:** `GraphDataResponse`

#### `POST /api/v1/graph/query`
- **Summary:** Execute an arbitrary read-only Cypher query against the knowledge graph store.
- **RBAC:** `analyst` or `admin`.
- **Security Guardrail:** Validated server-side to reject write/mutation keywords (`CREATE`, `MERGE`, `DELETE`, `SET`, `REMOVE`, `DROP`).
- **Request Body (`CypherQueryRequest`):**
  ```json
  {
    "query": "MATCH (s:Service {tier: $tier})<-[:AFFECTED]-(i:Incident) RETURN s.name AS service, count(i) AS incidents",
    "parameters": {
      "tier": "tier-1"
    }
  }
  ```
- **Response `200 OK` (`CypherQueryResponse`):**
  ```json
  {
    "results": [
      {
        "service": "Payments API",
        "incidents": 3
      }
    ],
    "execution_time_ms": 14.5,
    "nodes": [],
    "edges": []
  }
  ```

---

### 3.6 Document Ingestion & Management (`/api/v1/documents`)

Ingestion, semantic chunking, and injection-quarantined processing (Phase 5/11, F13, F17, N7, N8).

#### `POST /api/v1/documents/upload`
- **Summary:** Upload an enterprise document for parsing, chunking, and indexing.
- **RBAC:** `analyst` or `admin`.
- **Content-Type:** `multipart/form-data`
- **Validation Constraints:**
  - Max file size: 5 MB (`MAX_UPLOAD_MB=5`, N7).
  - Allowed extensions: `.md`, `.txt`, `.pdf`.
- **Security Check:** All parsed content is scanned by `guardrails.py`. If a prompt injection attempt is detected (e.g., `vendor-note-processor-update.md`), `flagged_injection` is set to `true` and text is quarantined as inert data, never executed (N8).
- **Status Code:** `201 Created`
- **Response `201 Created` (`DocumentUploadResponse`):**
  ```json
  {
    "document_id": "doc-550e8400-e29b-41d4-a716-446655440000",
    "filename": "postmortem-inc-2031.md",
    "content_hash": "a1b2c3d4e5f6...",
    "chunk_count": 8,
    "entities_extracted": 14,
    "flagged_injection": false,
    "status": "indexed",
    "created_at": "2026-11-27T12:00:00Z"
  }
  ```

#### `GET /api/v1/documents`
- **Summary:** List indexed documents.
- **RBAC:** `viewer`+
- **Query Parameters:** `skip`, `limit`, `status` (`indexed`, `pending`, `flagged`).
- **Response `200 OK`:** `list[DocumentResponse]`

#### `GET /api/v1/documents/{id}`
- **Summary:** Retrieve document metadata and its semantic chunk breakdown.
- **RBAC:** `viewer`+
- **Response `200 OK`:** `DocumentDetailResponse`
  ```json
  {
    "id": "doc-550e8400-e29b-41d4-a716-446655440000",
    "filename": "postmortem-inc-2031.md",
    "content_hash": "a1b2c3d4e5f6...",
    "chunk_count": 2,
    "flagged_injection": false,
    "status": "indexed",
    "created_at": "2026-11-27T12:00:00Z",
    "chunks": [
      {
        "id": "chk-01",
        "chunk_index": 0,
        "text": "Incident INC-2031 Postmortem Summary: Payments API outage occurred on May 14...",
        "embedding_id": "emb-01"
      }
    ]
  }
  ```

#### `DELETE /api/v1/documents/{id}`
- **Summary:** Delete an ingested document and prune associated vector/graph indices (F17).
- **RBAC Gating Behavior:**
  - **If Caller is `analyst`:** Destructive deletion is intercepted. An entry in `approval_requests` is generated. Returns `202 Accepted` (`pending_approval`).
  - **If Caller is `admin`:** Deletion executes immediately. Returns `200 OK` or `204 No Content`.
- **Response `202 Accepted` (When gated for approval):**
  ```json
  {
    "message": "Deletion request queued for administrative approval",
    "approval_request_id": "app-880e8400-e29b-41d4-a716-446655440001",
    "status": "pending_approval"
  }
  ```

---

### 3.7 Governance & Approvals (`/api/v1/approvals`)

Administrative approval gates for destructive enterprise operations (Phase 11, F17).

#### `GET /api/v1/approvals`
- **Summary:** List pending and resolved approval requests.
- **RBAC:** `viewer`+
- **Query Parameters:** `status` (`pending`, `approved`, `rejected`), `skip`, `limit`.
- **Response `200 OK`:** `list[ApprovalRequestResponse]`
  ```json
  [
    {
      "id": "app-880e8400-e29b-41d4-a716-446655440001",
      "resource_type": "document",
      "resource_id": "doc-550e8400-e29b-41d4-a716-446655440000",
      "action": "delete",
      "requester_id": "usr-analyst-01",
      "status": "pending",
      "decided_by": null,
      "created_at": "2026-11-27T12:15:00Z"
    }
  ]
  ```

#### `GET /api/v1/approvals/{id}`
- **Summary:** Retrieve single approval request.
- **RBAC:** `viewer`+
- **Response `200 OK`:** `ApprovalRequestResponse`

#### `POST /api/v1/approvals/{id}/decide`
- **Summary:** Resolve an approval request by approving or rejecting the destructive action.
- **RBAC:** `admin` only (`analyst` or `viewer` receives `403 Forbidden`).
- **Request Body (`ApprovalDecisionRequest`):**
  ```json
  {
    "decision": "approved",
    "reason": "Verified document is redundant and replaced by newer policy doc"
  }
  ```
- **Response `200 OK` (`ApprovalDecisionResponse`):**
  ```json
  {
    "id": "app-880e8400-e29b-41d4-a716-446655440001",
    "status": "approved",
    "decided_by": "usr-admin-01",
    "decided_at": "2026-11-27T12:30:00Z",
    "execution_result": {
      "deleted_document_id": "doc-550e8400-e29b-41d4-a716-446655440000",
      "pruned_chunks": 8
    }
  }
  ```

---

## 4. TypeScript Client Interfaces (`frontend/src/types/api.ts`)

These TypeScript interfaces mirror the contracts above and unblock Phase 12 (`P12-1`, `P12-2`).

```typescript
// ==========================================
// NovaEnterprise Client TypeScript Types
// Mirror of docs/API_CONTRACT.md
// ==========================================

export type UserRole = "viewer" | "analyst" | "admin";

export interface DemoUser {
  id: string;
  username: string;
  email: string;
  role: UserRole;
  name: string;
  description: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  role: UserRole;
  user_id: string;
  email: string;
  username: string;
}

export interface UserProfileResponse {
  id: string;
  username: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string | null;
}

// ------------------------------------------
// Domain Browse Entities
// ------------------------------------------

export interface CustomerResponse {
  id: string;
  name: string;
  tier: "enterprise" | "mid-market" | "standard" | "smb";
  contract_value: number;
  industry: string | null;
  created_at: string;
}

export interface IncidentResponse {
  id: string;
  title: string;
  severity: "SEV1" | "SEV2" | "SEV3" | "SEV4";
  status: "investigating" | "mitigated" | "resolved";
  root_cause: string | null;
  impacted_service_id: string | null;
  occurred_at: string | null;
  resolved_at: string | null;
  created_at: string;
}

export interface ServiceResponse {
  id: string;
  name: string;
  tier: string;
  port: number | null;
  repo_url: string | null;
  owner_team_id: string | null;
  created_at: string;
}

export interface TeamResponse {
  id: string;
  name: string;
  lead: string | null;
  slack_channel: string | null;
  description: string | null;
  created_at: string;
}

export interface DecisionResponse {
  id: string;
  title: string;
  status: "proposed" | "accepted" | "superseded" | "rejected";
  context: string | null;
  decision: string | null;
  consequences: string | null;
  incident_id: string | null;
  decided_at: string | null;
  created_at: string;
}

export interface ProjectResponse {
  id: string;
  name: string;
  description: string | null;
  owner_team_id: string | null;
  status: "active" | "completed" | "archived";
  created_at: string;
}

export interface TicketResponse {
  id: string;
  title: string;
  status: "open" | "in_progress" | "resolved" | "closed";
  priority: "P0" | "P1" | "P2" | "P3";
  project_id: string | null;
  assignee_id: string | null;
  created_at: string;
}

// ------------------------------------------
// Canonical Evidence & Citations
// ------------------------------------------

export type EvidenceSourceType = "document" | "sql" | "graph";

export interface EvidenceItem {
  id: string;
  sub_question_id: string;
  source_type: EvidenceSourceType;
  locator: string;
  content: string;
  score: number;
  metadata: Record<string, unknown>;
}

export interface CitationItem {
  citation_id: number;
  evidence_id: string;
  source_type: EvidenceSourceType;
  locator: string;
  snippet: string;
}

export interface SubQuestionItem {
  id: string;
  question: string;
  strategy: string;
  status: "pending" | "answered" | "failed";
}

// ------------------------------------------
// Research Session & Observability
// ------------------------------------------

export type ResearchStatus = "running" | "completed" | "failed";
export type QueryComplexity = "simple" | "moderate" | "complex";

export interface ResearchCreateRequest {
  question: string;
  user_id?: string;
}

export interface ResearchCreateResponse {
  session_id: string;
  status: "running";
  question: string;
  created_at: string;
}

export interface ResearchSessionSummary {
  session_id: string;
  question: string;
  status: ResearchStatus;
  complexity: QueryComplexity | null;
  created_at: string;
  updated_at: string;
}

export interface ResearchSessionResponse {
  session_id: string;
  status: ResearchStatus;
  question: string;
  complexity: QueryComplexity | null;
  strategies_used: string[];
  corrective_rounds: number;
  verification_ratio: number;
  answer: string | null;
  citations: CitationItem[];
  evidence: EvidenceItem[];
  sub_questions: SubQuestionItem[];
  execution_time_seconds: number | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkflowEventResponse {
  event_id: number;
  session_id: string;
  node_name: string;
  event_type: string;
  payload: Record<string, unknown>;
  latency_ms: number | null;
  timestamp: string;
}

// ------------------------------------------
// Knowledge Graph Explorer
// ------------------------------------------

export interface GraphNode {
  id: string;
  label: string;
  properties: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  properties: Record<string, unknown>;
}

export interface GraphDataResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface CypherQueryRequest {
  query: string;
  parameters?: Record<string, unknown>;
}

export interface CypherQueryResponse {
  results: Record<string, unknown>[];
  execution_time_ms: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// ------------------------------------------
// Document & Approval Governance
// ------------------------------------------

export interface DocumentResponse {
  id: string;
  filename: string;
  content_hash: string;
  chunk_count: number;
  flagged_injection: boolean;
  status: "indexed" | "pending" | "flagged";
  created_at: string;
}

export interface DocumentChunkResponse {
  id: string;
  chunk_index: number;
  text: string;
  embedding_id: string | null;
}

export interface DocumentDetailResponse extends DocumentResponse {
  chunks: DocumentChunkResponse[];
}

export interface ApprovalRequestResponse {
  id: string;
  resource_type: string;
  resource_id: string;
  action: string;
  requester_id: string;
  status: "pending" | "approved" | "rejected";
  decided_by: string | null;
  created_at: string;
}

export interface ApprovalDecisionRequest {
  decision: "approved" | "rejected";
  reason?: string;
}

export interface ApprovalDecisionResponse {
  id: string;
  status: "approved" | "rejected";
  decided_by: string;
  decided_at: string;
  execution_result?: Record<string, unknown>;
}
```
