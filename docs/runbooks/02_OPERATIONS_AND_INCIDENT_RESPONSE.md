# NovaEnterprise — Operations & Incident Response Runbook (P14-5)

> Document Reference: `docs/runbooks/02_OPERATIONS_AND_INCIDENT_RESPONSE.md`  
> Authoritative Specifications: `Claude.md §14, §15, §16` · `docs/02-hld.md`  

---

## 1. Scope & System Topology Overview

NovaEnterprise integrates four persistent storage engines backing the multi-agent RAG pipeline:
1. **PostgreSQL 16:** Relational entities (customers, services, teams, incidents, decisions, tickets, documents, approval requests, audit logs).
2. **Qdrant v1.12:** Dense vector collections for enterprise documentation chunks with metadata payload filters.
3. **Neo4j 5.26:** Property graph modeling relationships (`Customer`, `Service`, `Team`, `Incident`, `Decision`).
4. **Redis 7:** Token-bucket rate limiting (`120 req/min`) and episodic/working memory session states.

---

## 2. Backup & Disaster Recovery Procedures

### 2.1 PostgreSQL Automated Backup & Restoration
- **Daily Full Backup:**
  ```bash
  # Execute backup container command
  docker compose exec -T postgres pg_dump -U nova_user -d nova_enterprise -Fc > /backups/postgres/nova_$(date +%Y%m%d_%H%M%S).dump
  ```
- **Point-in-Time Recovery (PITR):**
  ```bash
  # Restore database from dump file
  docker compose exec -T postgres dropdb -U nova_user --if-exists nova_enterprise
  docker compose exec -T postgres createdb -U nova_user nova_enterprise
  docker compose exec -T postgres pg_restore -U nova_user -d nova_enterprise /backups/postgres/nova_target.dump
  ```

### 2.2 Qdrant Vector Store Snapshot & Recovery
- **Create Collection Snapshot:**
  ```bash
  curl -X POST "http://localhost:6333/collections/enterprise_chunks/snapshots"
  # Returns: {"result": {"name": "enterprise_chunks-snapshot-*.snapshot"}}
  ```
- **Restore Snapshot:**
  ```bash
  curl -X POST "http://localhost:6333/collections/enterprise_chunks/snapshots/upload?priority=snapshot" \
       -H "Content-Type: multipart/form-data" \
       -F "snapshot=@/backups/qdrant/enterprise_chunks.snapshot"
  ```

### 2.3 Neo4j Knowledge Graph Dump & Load
- **Graph Database Dump:**
  ```bash
  # Stop container or lock database
  docker compose exec neo4j neo4j-admin database dump neo4j --to-path=/backups/neo4j/
  ```
- **Graph Database Restoration:**
  ```bash
  docker compose exec neo4j neo4j-admin database load neo4j --from-path=/backups/neo4j/ --overwrite-destination=true
  docker compose restart neo4j
  ```

### 2.4 Redis Persistence
- Redis RDB snapshots persist periodically to `redis-data` volume.
- Trigger manual background save:
  ```bash
  docker compose exec redis redis-cli BGSAVE
  ```

---

## 3. Data Ingestion & Index Re-hydration

When setting up new nodes, recovering after storage failure, or updating enterprise documentation:

```bash
# 1. Ingest markdown, text, and PDF documents from sample_data/
docker compose exec backend python3 -m rag.ingest

# 2. Seed knowledge graph entities and relationship edges
docker compose exec backend make seed-graph
# Or run direct python seed
docker compose exec backend python3 -m database.seed

# 3. Verify total chunks and graph node count
curl -s http://localhost:8001/api/v1/graph/stats | python3 -m json.tool
```

---

## 4. Incident Response & Troubleshooting Playbooks

### 4.1 Degraded Storage Adapter Alert
- **Symptom:** `/health/ready` returns HTTP 200 with status `"degraded"`.
- **Diagnosis:**
  ```bash
  curl -s http://localhost:8001/health/ready | jq '.checks'
  ```
- **Mitigation:**
  - If `redis` is degraded: Check memory limits (`docker stats nova-redis`). Flush expired keys or restart container (`docker compose restart redis`).
  - If `qdrant` is degraded: Verify disk space on `/qdrant/storage`.
  - If `neo4j` is degraded: Inspect Neo4j logs (`docker compose logs neo4j | tail -n 100`). Verify Bolt port `7687` availability.

### 4.2 Rate Limiter Saturation (`429 Too Many Requests`)
- **Symptom:** Clients receive HTTP 429 status codes.
- **Diagnosis:** Inspect client IP or authenticated user ID headers in `workflow_events`.
- **Mitigation:**
  - Verify if request storm is benign or DDoS.
  - Temporarily adjust rate limits via `RATE_LIMIT_PER_MINUTE=240` in `.env.docker` and reload:
    ```bash
    docker compose up -d backend
    ```

### 4.3 LLM Provider Timeout or Outage
- **Symptom:** Workflow logs report upstream LLM timeout.
- **Mitigation:**
  - NovaEnterprise supports 8 runtime LLM providers via `get_llm()` (`Claude.md §7.1`).
  - Switch provider dynamically via environment variable without code changes:
    ```bash
    # Switch to fallback provider (e.g. Anthropic, Groq, or local Ollama)
    export LLM_PROVIDER=anthropic
    docker compose up -d backend
    ```
