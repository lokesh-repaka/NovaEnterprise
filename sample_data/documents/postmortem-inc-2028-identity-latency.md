# Incident Postmortem: INC-2028 Identity Service Global SSO Latency Spike

**Incident Reference:** INC-2028  
**Severity:** SEV1  
**Target Service:** Identity Service (`svc-identity`)  
**Owning Team:** Identity (`team-identity`)  
**Occurred:** 2026-05-02 13:00:00 UTC  
**Resolved:** 2026-05-02 14:30:00 UTC  
**Duration:** 90 minutes  
**Lead Investigator:** Dan Kim (Senior Security Engineer)

---

## Summary & Impact

During European and American business overlap, global SSO token generation and JWKS validation experienced 8,000ms latency spikes, causing login timeouts for corporate employees and enterprise clients.
Impacted enterprise accounts:
- **Stark Industries** (`cust-stark`): Failed engineer logins across defense development portals.
- **Cyberdyne Systems** (`cust-cyberdyne`): Automated API client credential authentication rejected.

## Root Cause

Distributed Redis session locking deadlock between AWS US-East-1 and EU-West-1 primary regions. Cross-region network jitter exceeded synchronous session replication timeouts.

## Remediation

Approved **ADR-043 (Redis Cluster Multi-Region Caching)** to migrate session management to asynchronous active-active Redis replication with localized JWT signature verification.
