---
name: consult-rag
description: Ask the rag-consultant subagent for guidance on hybrid query routing, Cypher graph traversals, SQL allowlists, or cross-encoder reranking.
---

# Consult RAG Specialist Workflow (NovaEnterprise)

Use this skill when you encounter ambiguities in multi-modal retrieval routing, graph query construction, or hybrid search weighting.

## Workflow Steps

1. **Formulate Technical Inquiry**:
   - Frame the specific retrieval dilemma (e.g. "How should a query requesting customer churn risk and transaction history be routed between Graph and SQL?").
   - Gather relevant entity schemas or Cypher query snippets.

2. **Invoke RAG Consultant Subagent**:
   - Spawn the `rag-consultant` subagent (`Model: pro`, `Role: rag-consultant`).
   - Task Prompt template:
     ```text
     Consultation question for NovaEnterprise retrieval system:
     <QUESTION>
     
     Provide an architectural recommendation in under 300 words covering:
     1. Routing breakdown (Vector vs. Graph vs. SQL)
     2. Exact Cypher traversal or SQL validation pattern
     3. Reranking or evidence combination strategy
     ```

3. **Incorporate Guidance**:
   - Embed the recommended routing rules and query patterns into the relevant implementation plan or router module.

