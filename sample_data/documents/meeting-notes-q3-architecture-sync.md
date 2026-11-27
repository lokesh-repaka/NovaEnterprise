# Meeting Notes: Q3 2026 Architecture & AI Roadmap Sync

**Date:** 2026-07-28  
**Attendees:** Alice Chen, Dan Kim, George Brooks, Maya Lin, Sarah Jenkins

---

## Discussion Highlights

1. **Enterprise Decision Intelligence System (NovaEnterprise):**
   - Evaluated pure Vector RAG limitations on relational metrics and multi-hop service topologies.
   - Validated need for hybrid multi-modal retrieval: Vector RAG for narrative postmortems/ADRs, SQL AST for exact tabular metrics, and Neo4j Cypher for dependency graph hops.
   - Enforced prompt injection quarantine defense: external supplier docs must never execute as instructions.

2. **Fiscal Calendar Time Grounding:**
   - Confirmed queries referencing "last quarter" must resolve via `organizational_memory.json` to Fiscal Q2 (April 1 to June 30, 2026).
