# Enterprise Policy: Incident Severity Classification and SLA Framework

**Policy Reference:** POL-OPS-003  
**Category:** Platform Operations & Site Reliability  
**Effective Date:** 2026-01-01  
**Version:** 4.1  
**Owner:** David O'Connor (Head of Site Reliability)

---

## Severity Levels

- **SEV1 (Critical Outage):** Complete failure or catastrophic degradation of a mission-critical tier-1 service impacting revenue, data integrity, or core user authentication. Response SLA: 15 minutes. Updates every 30 minutes.
- **SEV2 (Major Degradation):** Partial failure or severe performance degradation of tier-1 or tier-2 services where redundancy is compromised or key workflows are impaired. Response SLA: 30 minutes.
- **SEV3 (Minor Issue):** Low-impact degradation, cosmetic defect, or failure of non-critical tier-3 internal tooling. Response SLA: 120 minutes.

All SEV1 and SEV2 incidents require an executive postmortem and an Architectural Decision Record (ADR) within 7 business days.
