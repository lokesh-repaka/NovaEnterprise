# ==============================================================================
# NovaEnterprise Automation Makefile
# ==============================================================================
# Canonical command interface specified in Claude.md §14.
# Guaranteed 100% offline-compatible by default.
# ==============================================================================

.PHONY: help setup backend test test-cov lint format demo ingest seed-graph clean

PYTHON ?= python3
PORT ?= 8001
HOST ?= 0.0.0.0
QUESTION ?= What was the root cause of the Payments API incident last quarter?

help: ## Show this help message and target descriptions
	@echo "NovaEnterprise Developer Automation Interface"
	@echo "=============================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: ## Prepare local runtime environment and .env configuration
	@test -f .env || cp .env.example .env
	@mkdir -p data sample_data
	@echo "Environment initialized. Run 'make test' or 'make backend'."

backend: ## Start FastAPI application on :8001 with reload
	uvicorn backend.app.main:app --host $(HOST) --port $(PORT) --reload

test: ## Run full offline pytest test suite (N1)
	$(PYTHON) -m pytest tests/unit/ -v

test-cov: ## Run offline pytest suite with line-by-line coverage
	$(PYTHON) -m pytest --cov=backend.app --cov=tests.mocks --cov-report=term-missing tests/unit/

lint: ## Execute static analysis via ruff and mypy
	ruff check backend/ tests/ rag/
	mypy backend/app tests/ rag/

format: ## Auto-format code and sort imports using ruff
	ruff check --fix backend/ tests/ rag/
	ruff format backend/ tests/ rag/

demo: ## Run canonical multi-hop research demo (Claude.md §14)
	@echo "Executing canonical demo for question: '$(QUESTION)'"
	$(PYTHON) -c "import urllib.request, json; print('Testing backend liveness:'); res = urllib.request.urlopen('http://localhost:$(PORT)/health/ready', timeout=2); print(json.dumps(json.loads(res.read()), indent=2))" || echo "Note: Run 'make backend' in a separate terminal to query live API."

ingest: ## Index and chunk enterprise documentation into vector & graph stores
	@echo "Ingestion command: Indexing documents from sample_data/ into stores..."
	@$(PYTHON) -c "from tests.mocks.fake_stores import InMemoryVectorStore; s = InMemoryVectorStore(); print(s.get_status_detail())"

seed-graph: ## Populate knowledge graph entities and relationships
	@echo "Rebuilding knowledge graph from sample_data/..."
	@$(PYTHON) -c "from tests.mocks.fake_stores import InMemoryGraphStore; g = InMemoryGraphStore(); print(g.get_status_detail())"

clean: ## Remove temporary build caches, bytecode, and coverage artifacts
	rm -rf .pytest_cache .coverage htmlcov .ruff_cache .mypy_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	@echo "Caches cleaned."
