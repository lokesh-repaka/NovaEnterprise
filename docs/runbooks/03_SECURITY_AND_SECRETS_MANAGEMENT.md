# NovaEnterprise — Security & Secrets Management Runbook (P14-5)

> Document Reference: `docs/runbooks/03_SECURITY_AND_SECRETS_MANAGEMENT.md`  
> Authoritative Specifications: `Claude.md §2, §7, §9, §15` · `docs/01-prd.md`  

---

## 1. Scope & Security Architecture

NovaEnterprise enforces defense-in-depth across identity, cryptographic tokens, data access, and untrusted inputs:
- **RBAC Authentication:** Keycloak / JWT RS256 / HS256 tokens enforcing role gates (`viewer`, `analyst`, `admin`).
- **Prompt Injection Defense (N8):** Automated scanning, classification, and quarantine of external documents.
- **SQL Allowlist Security (F7):** AST verification blocking all mutations (DDL/DML); read-only allowlisted schema.
- **Human-In-The-Loop (HITL) Governance (F17):** Admin approval workflow on destructive document deletion.

---

## 2. Secrets Management & Hierarchy

Production secrets must never be committed to source control or baked into Docker images.
All `.dockerignore` files explicitly exclude `.env*`, `*.pem`, `*.key`, and secret materials.

### 2.1 Secret Store Mapping
| Secret Name | Purpose | Recommended Vault / KMS | Rotation Cadence |
|:---|:---|:---|:---|
| `JWT_SECRET_KEY` | JWT HS256 / RS256 token signing | AWS Secrets Manager / HashiCorp Vault | 90 days |
| `POSTGRES_PASSWORD` | PostgreSQL master credential | AWS Secrets Manager / RDS IAM Auth | 180 days |
| `NEO4J_PASSWORD` | Neo4j Bolt auth credential | AWS Secrets Manager / Vault | 180 days |
| `LLM_API_KEY` | External LLM provider API credentials | Environment injection via Vault/K8s secret | Immediate upon leak |

---

## 3. Secret Rotation Procedures

### 3.1 JWT Secret Key Rotation
1. **Issue Secondary Key:** Update backend to accept tokens signed by previous key while signing new tokens with new key (grace period).
2. **Update Secret:**
   ```bash
   # Update JWT_SECRET_KEY in production secret manager or .env.docker
   export JWT_SECRET_KEY="new-high-entropy-jwt-secret-string"
   docker compose up -d backend
   ```
3. **Revocation:** Invalidate previous active sessions by flushing Redis token cache:
   ```bash
   docker compose exec redis redis-cli KEYS "session:*" | xargs docker compose exec redis redis-cli DEL
   ```

### 3.2 Database Credential Rotation
1. Update database user password in PostgreSQL:
   ```bash
   docker compose exec -T postgres psql -U nova_user -d nova_enterprise -c "ALTER USER nova_user WITH PASSWORD 'new_secure_password';"
   ```
2. Update `DATABASE_URL` in container environment and restart backend service:
   ```bash
   docker compose up -d backend
   ```

---

## 4. Role-Based Access Control (RBAC) & Audit

### 4.1 Role Hierarchy (`Claude.md §2`)
- **`viewer`:** Can read dashboards, browse customers, incidents, decisions, tickets, and read completed research sessions.
- **`analyst`:** Everything `viewer` can + initiate new multi-hop research, upload documents, run read-only Cypher, manage own working/episodic memory.
- **`admin`:** Full capabilities + approve or reject destructive document deletion requests, trigger reindexing, configure global policies.

### 4.2 Audit Logging Invariant
- All requests capture `X-Request-ID` and record user id, client ip, and action in append-only audit tables.
- Destructive document deletions generate an approval request requiring admin sign-off (`F17`).

---

## 5. Untrusted Document Quarantine & Prompt Injection Defense (N8)

External vendor notes, customer records, and uploaded files are treated as untrusted data:
1. **Quarantine Reader:** All external text is scanned by `QuarantinedReader` in `backend/app/core/guardrails.py` using injection heuristic patterns (`ignore previous instructions`, `system prompt`, `<script>`, etc.).
2. **Flagging & Isolation:** Flagged documents receive `flagged_injection=True` in database records and are wrapped in `<untrusted_content>` tags before LLM consumption.
3. **System Prompts Non-Exposure (N9):** Raw prompts, chain-of-thought scratchpads, and API keys are scrubbed and never leaked to API responses or frontend clients.
