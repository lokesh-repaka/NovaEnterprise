# Incident Postmortem: INC-2025 Data Pipeline Consumer Lag and Memory Spike

**Incident Reference:** INC-2025  
**Severity:** SEV2  
**Target Service:** Data Pipeline (`svc-data-pipeline`)  
**Owning Team:** Data Platform (`team-data`)  
**Occurred:** 2026-04-12 16:45:00 UTC  
**Resolved:** 2026-04-12 19:10:00 UTC  
**Duration:** 145 minutes  
**Lead Investigator:** George Brooks (Senior Data Engineer)

---

## Summary & Root Cause

Apache Spark streaming consumers processing financial audit ledgers experienced severe consumer lag exceeding 1.2 million unread records. Unpartitioned write jobs to object storage created hundreds of small files, exhausting executor heap memory and triggering garbage collection thrashing.

Impacted customer: **Massive Dynamic** (`cust-massive`), whose real-time inventory ingestion was delayed by 3 hours.

## Corrective Decision

Adopted **ADR-046 (Incremental Snapshotting for Data Lake Pipelines)**, transitioning all ingestion jobs to Delta Lake with automatic compaction and Z-order partitioning.
