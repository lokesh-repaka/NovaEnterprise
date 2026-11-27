# Incident Postmortem: INC-2022 Notification Delivery Queue Backpressure

**Incident Reference:** INC-2022  
**Severity:** SEV3  
**Target Service:** Notification Service (`svc-notifications`)  
**Owning Team:** Payments Platform (`team-payments`)  
**Occurred:** 2026-02-05 14:10:00 UTC  
**Resolved:** 2026-02-05 16:00:00 UTC  
**Duration:** 110 minutes  
**Lead Investigator:** Carol Diaz (Software Engineer II)

---

## Summary & Root Cause

An in-memory Redis priority queue experienced backpressure due to a downstream SMS provider rate limit. Unacknowledged message payloads accumulated in memory, causing evictions of low-priority marketing alerts.

## Corrective Decision

Adopted **ADR-044 (Kafka Event Streaming for Payment Notifications)** to decouple notification event producers from delivery workers using distributed Kafka topics with 3-day retention.
