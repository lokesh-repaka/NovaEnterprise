# Architectural Decision Record (ADR): ADR-042

**Title:** Adopt PgBouncer for Connection Pooling  
**Status:** Approved  
**Date:** 2026-05-20  
**Context Incident:** INC-2031 (Payments API Latency Spike and Outage)  
**Authors:** Alice Chen (Staff Software Engineer), Marcus Vance (Engineering Lead)  
**Approvers:** David O'Connor (Head of Site Reliability), Rajiv Patel (Data Platform Lead)

---

## Context & Problem Statement

During incident INC-2031 on May 14, 2026, the Payments API experienced complete service outage due to PostgreSQL connection exhaustion. When horizontal pod autoscalers (HPA) spun up 12 instances, direct database connections reached 360, immediately breaching the PostgreSQL server maximum connection limit of 200.

Direct connections from application pods in Kubernetes are anti-patterns in high-throughput transactional environments because connection handshakes, backend process allocations, and memory footprints consume up to 10MB of RAM per idle connection.

---

## Decision

We will deploy **PgBouncer** as a transaction-mode connection pooler sidecar proxy container alongside every Payments API service deployment pod in Kubernetes.

1. **Transaction Pooling Mode:** Client connections hold server connections strictly for the duration of a transaction, multiplexing thousands of client connections onto a small fixed pool of backend connections.
2. **Server Connection Ceiling:** Capped at 60 active PostgreSQL backend connections across the cluster.
3. **Client Multiplexing:** Configured to accept up to 5,000 active incoming application connections.
4. **Health Check Probes:** Liveness and readiness probes integrated with Kubernetes Pod disruption budgets.

---

## Consequences & Evaluation

- **Positive:** Maximum active server connections capped safely below 100 under any traffic surge.
- **Positive:** Idle connection memory overhead eliminated.
- **Positive:** Latency spikes during HPA pod spin-up reduced from > 4,000ms to < 8ms.
- **Negative:** Prepared statements require special named statement handling or protocol-level configuration in transaction mode.
