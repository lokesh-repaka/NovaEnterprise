# Enterprise Policy: Data Retention and Archival Governance

**Policy Reference:** POL-DAT-001  
**Category:** Governance, Compliance & Data Security  
**Effective Date:** 2026-01-01  
**Version:** 3.2  
**Owner:** Elena Rostova (Security & Identity Lead)

---

## 1. Overview & Scope

This document specifies the enterprise data retention schedules, cryptographic deletion standards, and archival lifecycles across NovaEnterprise systems. It applies to all structured databases, document repositories, and telemetry event stores.

## 2. Retention Schedules

1. **Transactional Payment Records:** Retained for 7 years in immutable PostgreSQL / Aurora cold storage to comply with SOX and PCI-DSS requirements.
2. **System Telemetry & Access Logs:** Retained in hot storage for 90 days, then moved to S3 Glacier Deep Archive for 365 days before automated purging.
3. **Research Sessions & Multi-Agent Telemetry:** Retained in active operational databases for 180 days.
4. **Temporary Document Chunks & Vector Embeddings:** Purged immediately upon verified source document deletion approval.

## 3. Cryptographic Erasure & Compliance

Destructive document deletions require dual-admin cryptographic authorization under Human-in-the-Loop (HITL) governance gates (F17).
