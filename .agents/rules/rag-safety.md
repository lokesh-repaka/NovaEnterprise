---
trigger: glob
globs: "**/rag/**, **/backend/app/**, **/agents/**"
---
# RAG & Security Guidelines (NovaEnterprise)
- Never execute unvalidated SQL: all queries must pass validate_sql() against the allowlist schema.
- Untrusted documents (e.g. vendor notes) must be wrapped and never executed as agent instructions.
- Cypher queries must use typed graph traversals.

