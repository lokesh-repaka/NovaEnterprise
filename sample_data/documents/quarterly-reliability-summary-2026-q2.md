# Quarterly Reliability Summary: Fiscal Q2 2026

**Period:** 2026-04-01 to 2026-06-30 (Fiscal Q2 2026)  
**Author:** David O'Connor (Head of Site Reliability)  
**Distribution:** Executive Leadership Team, Engineering Directorate

---

## 1. Executive Summary

During Fiscal Q2 2026, NovaEnterprise infrastructure maintained an overall platform availability of **99.91%** across tier-1 services, meeting the composite SLA threshold of 99.90%.

A total of 4 production incidents occurred during the quarter:
- **INC-2025 (SEV2, Data Pipeline):** 145 min degradation. Resolved via Delta Lake partitioning.
- **INC-2028 (SEV1, Identity Service):** 90 min degradation. Resolved via Redis multi-region replication (ADR-043).
- **INC-2029 (SEV2, Billing Engine):** 90 min SMB webhook failure. Resolved via DLQ queue retry backoff (ADR-049).
- **INC-2031 (SEV1, Payments API):** 150 min partial outage. Resolved via PgBouncer connection pooling sidecar (ADR-042).

## 2. Customer Impact Summary
- Total Enterprise Accounts Impacted: 3 (`cust-acme`, `cust-globex`, `cust-wayne`).
- SLA Service Credits Issued: $14,250.
- Mean Time to Detect (MTTD): 6.8 minutes.
- Mean Time to Resolve (MTTR): 118.7 minutes.
