# Enterprise Policy: Role-Based Access Control (RBAC) Governance

**Policy Reference:** POL-SEC-002  
**Category:** Information Security & Access Management  
**Effective Date:** 2026-01-15  
**Version:** 2.0  
**Owner:** Dan Kim (Senior Security Engineer)

---

## 1. Role Hierarchy & Permissions

NovaEnterprise enforces strict role separation across API endpoints, database views, and UI features:

- **`viewer`:** Read-only access to published executive dashboards, completed research session results, and high-level service health metrics. Forbidden from initiating research workflows or modifying data.
- **`analyst`:** Standard operational access. Permitted to launch multi-hop research sessions, query knowledge graphs via typed traversals, upload markdown/PDF documentation, and manage personal episodic memories.
- **`admin`:** Full administrative governance. Authorized to approve destructive actions, execute re-indexing pipelines, inspect security audit trails, and manage user identities.

## 2. Token Security & Lifetime

All user requests must present a signed Keycloak RS256 JWT bearer token containing `sub`, `roles`, and `aud` claims. Token expiry is capped at 15 minutes with token-bucket rate limiting on refresh endpoints.
