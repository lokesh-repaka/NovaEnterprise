# Architectural Decision Record (ADR): ADR-043

**Title:** Redis Cluster Multi-Region Caching  
**Status:** Approved  
**Date:** 2026-05-18  
**Context Incident:** INC-2028 (Identity Service Global SSO Latency Spike)  
**Authors:** Dan Kim, Elena Rostova

---

## Context

Cross-region synchronous token verification locks resulted in distributed deadlocks during peak European/US business traffic.

## Decision

Migrate Identity Service session storage and JWKS key caches to active-active replicated Redis Cluster nodes deployed in each primary cloud region.

## Consequences

P99 authentication latency reduced to 12ms. Token verification is served strictly from local regional cache with asynchronous pub/sub cache invalidation.
