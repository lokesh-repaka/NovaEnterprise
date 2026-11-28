"""Tests for CI workflow configurations and production runbooks (P14-5).

Verifies GitHub Actions workflow specifications, CI gates (ruff, mypy, pytest, eval, vitest),
release automation (git SHA tagging), and operational runbook coverage.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestGitHubActionsWorkflows:
    """Verifies GitHub Actions CI/CD workflow configurations."""

    def test_ci_workflow_exists_and_triggers_correctly(self) -> None:
        ci_file = REPO_ROOT / ".github" / "workflows" / "ci.yml"
        assert ci_file.exists(), ".github/workflows/ci.yml must exist"

        content = ci_file.read_text(encoding="utf-8")

        # Triggers verification on long-lived branches
        assert "pull_request:" in content, "CI workflow must trigger on pull_request"
        assert "push:" in content, "CI workflow must trigger on push"
        assert "development" in content, "CI workflow must cover development branch"
        assert "testing" in content, "CI workflow must cover testing branch"
        assert "main" in content, "CI workflow must cover main branch"

    def test_ci_workflow_backend_job_gates(self) -> None:
        ci_file = REPO_ROOT / ".github" / "workflows" / "ci.yml"
        content = ci_file.read_text(encoding="utf-8")

        # Backend lint, typecheck, unit/integration test, and eval harness
        assert "ruff check" in content, "CI workflow must execute ruff linter"
        assert "mypy" in content, "CI workflow must execute mypy type checker"
        assert "pytest" in content or "make test" in content, "CI workflow must execute offline pytest suite"
        assert "evaluate" in content or "make eval" in content, "CI workflow must execute CI evaluation harness"
        assert "python" in content.lower(), "CI workflow must configure Python runtime"

    def test_ci_workflow_frontend_job_gates(self) -> None:
        ci_file = REPO_ROOT / ".github" / "workflows" / "ci.yml"
        content = ci_file.read_text(encoding="utf-8")

        # Frontend lint, typecheck, vitest, and standalone build
        assert "node" in content.lower(), "CI workflow must configure Node.js runtime"
        assert "npm ci" in content or "npm install" in content, "CI workflow must install npm dependencies"
        assert "type-check" in content or "tsc" in content, "CI workflow must execute frontend TypeScript checks"
        assert "test" in content, "CI workflow must execute frontend vitest suite"
        assert "build" in content, "CI workflow must verify frontend production build"

    def test_release_workflow_exists_and_tags_images_with_sha(self) -> None:
        release_file = REPO_ROOT / ".github" / "workflows" / "release.yml"
        assert release_file.exists(), ".github/workflows/release.yml must exist"

        content = release_file.read_text(encoding="utf-8")
        assert "main" in content or "tags" in content, "Release workflow must trigger on main branch or release tags"
        assert "sha" in content.lower() or "github.sha" in content, "Release workflow must tag images with git SHA (Claude.md §15)"
        assert "docker" in content.lower(), "Release workflow must build container images"


class TestProductionRunbooks:
    """Verifies operational production runbooks and disaster recovery documentation."""

    def test_deployment_runbook_exists_and_covers_procedures(self) -> None:
        runbook = REPO_ROOT / "docs" / "runbooks" / "01_DEPLOYMENT_RUNBOOK.md"
        assert runbook.exists(), "01_DEPLOYMENT_RUNBOOK.md must exist in docs/runbooks/"

        content = runbook.read_text(encoding="utf-8")
        assert "promotion" in content.lower(), "Runbook must document branch promotion gates"
        assert "docker" in content.lower(), "Runbook must document containerized deployment"
        assert "/health/ready" in content, "Runbook must document /health/ready readiness check"
        assert "rollback" in content.lower(), "Runbook must document deployment rollback steps"

    def test_operations_runbook_exists_and_covers_disaster_recovery(self) -> None:
        runbook = REPO_ROOT / "docs" / "runbooks" / "02_OPERATIONS_AND_INCIDENT_RESPONSE.md"
        assert runbook.exists(), "02_OPERATIONS_AND_INCIDENT_RESPONSE.md must exist in docs/runbooks/"

        content = runbook.read_text(encoding="utf-8")
        assert "backup" in content.lower(), "Runbook must document backup procedures"
        assert "restore" in content.lower() or "recovery" in content.lower(), "Runbook must document recovery procedures"
        assert "postgres" in content.lower(), "Runbook must cover PostgreSQL data operations"
        assert "neo4j" in content.lower(), "Runbook must cover Neo4j graph operations"
        assert "qdrant" in content.lower(), "Runbook must cover Qdrant vector store operations"
        assert "ingest" in content.lower(), "Runbook must document document ingestion recovery"

    def test_security_runbook_exists_and_covers_secret_management(self) -> None:
        runbook = REPO_ROOT / "docs" / "runbooks" / "03_SECURITY_AND_SECRETS_MANAGEMENT.md"
        assert runbook.exists(), "03_SECURITY_AND_SECRETS_MANAGEMENT.md must exist in docs/runbooks/"

        content = runbook.read_text(encoding="utf-8")
        assert "jwt" in content.lower() or "token" in content.lower(), "Runbook must document JWT key management"
        assert "rotation" in content.lower(), "Runbook must document secret rotation"
        assert "rbac" in content.lower() or "roles" in content.lower(), "Runbook must document RBAC roles"
        assert "prompt injection" in content.lower() or "quarantine" in content.lower(), "Runbook must document untrusted input quarantine (N8)"
