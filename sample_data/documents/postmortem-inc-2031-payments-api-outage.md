# Incident Postmortem: INC-2031 Payments API Latency Spike & Outage

**Incident Reference:** INC-2031  
**Severity:** SEV1  
**Target Service:** Payments API (`svc-payments-api`)  
**Owning Team:** Payments Platform (`team-payments`)  
**Occurred:** 2026-05-14 09:15:00 UTC  
**Resolved:** 2026-05-14 11:45:00 UTC  
**Total Downtime / Degradation:** 150 minutes  
**Lead Investigator:** Alice Chen (Staff Software Engineer)  
**Executive Summary Sign-off:** Marcus Vance (Engineering Lead)

---

## Executive Summary

On May 14, 2026, at 09:15 UTC, the Payments API experienced a critical degradation and subsequent partial outage lasting 2 hours and 30 minutes. The root cause was PostgreSQL database connection pool exhaustion triggered by an unthrottled flash-sale transaction surge from enterprise customer Acme Corp. 

During the incident window, active server connections saturated the database limit of 200, resulting in `FATAL: remaining connection slots are reserved for non-replication superuser connections`. 

Three major enterprise customers suffered service disruption:
1. **Acme Corp** (`cust-acme`): 14,280 failed payment checkouts ($182,000 estimated GMV impact).
2. **Globex Corp** (`cust-globex`): Intermittent webhook callback timeouts and delayed fulfillment.
3. **Wayne Enterprises** (`cust-wayne`): Batch B2B settlement failure requiring end-of-day reconciliation.

---

## Technical Root Cause Analysis

Payments API instances were configured with direct PostgreSQL connections using a maximum client pool size of 30 per pod across 12 horizontal pod autoscalers (HPA). When traffic surged from 450 req/sec to 2,100 req/sec:
1. Pod autoscaling rapidly scaled out from 4 to 12 replicas.
2. 12 pods x 30 connections = 360 attempted concurrent backend connections.
3. PostgreSQL server connection ceiling (200) was breached immediately.
4. Active transactions blocked waiting for available sockets, leading to thread exhaustion and cascading 504 Gateway Timeouts across the API gateway.

---

## Permanent Corrective Decisions (Recurrence Prevention)

To permanently resolve database connection saturation and prevent recurrence:
- **ADR-042 (Adopt PgBouncer for Connection Pooling):** Approved and deployed. PgBouncer was introduced in transaction pooling mode as a Kubernetes sidecar proxy, capping backend server connections to 60 while supporting up to 5,000 multiplexed client connections.
- **Connection Rate Limiting:** Enforced strict per-client burst rate limiting at the API gateway layer.
- **Circuit Breaking:** Integrated resilience circuit breakers for all payment processing database queries.

---

## Resolution Timeline

- **09:15 UTC:** Automated PagerDuty alert fires on P99 latency breach (> 4,500ms).
- **09:22 UTC:** SRE on-call escalates to SEV1; incident bridge opened.
- **09:45 UTC:** Alice Chen identifies PostgreSQL connection pool exhaustion.
- **10:15 UTC:** Database connection limit temporarily increased from 200 to 400.
- **10:45 UTC:** Payments API pod replicas throttled to stabilize connection volume.
- **11:30 UTC:** Database CPU and connection pool return to baseline nominal state.
- **11:45 UTC:** All transaction queues cleared; incident formally marked resolved.
