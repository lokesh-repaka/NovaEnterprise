---
trigger: glob
globs: "**/tests/**, **/*_test.py, **/test_*.py"
---
# Test Guidelines (NovaEnterprise)
- All tests must run offline with no external network: LLM_PROVIDER=fake, VECTOR_STORE=memory, GRAPH_STORE=memory.
- Use pytest fixtures for database sessions and mocked redis.
- Assert exact citation resolving and evidence shapes on RAG endpoints.

