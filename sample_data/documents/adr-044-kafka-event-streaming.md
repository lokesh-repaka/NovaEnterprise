# Architectural Decision Record (ADR): ADR-044

**Title:** Kafka Event Streaming for Payment Notifications  
**Status:** Accepted  
**Date:** 2026-02-15  
**Context Incident:** INC-2022 (Notification Delivery Queue Backpressure)  
**Authors:** Carol Diaz, Rajiv Patel

---

## Context

Direct API and synchronous in-memory queuing resulted in packet drops and worker exhaustion during high-volume transactional bursts.

## Decision

Adopt Apache Kafka distributed event streaming with partitioned topics for all transaction and notification dispatch workflows.

## Consequences

Enables decoupled consumption, backpressure buffering, and 3-day replay capability for failed customer notification events.
