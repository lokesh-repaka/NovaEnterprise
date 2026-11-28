"""Tests for container configurations and Dockerfile invariants (P14-3).

Verifies multi-stage builds, non-root user execution, port exposures,
health checks, dependency specifications, and .dockerignore patterns.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestRequirementsTxt:
    """Verifies backend requirements.txt specification."""

    def test_requirements_file_exists_and_valid(self) -> None:
        req_file = REPO_ROOT / "requirements.txt"
        assert req_file.exists(), "requirements.txt must exist at repository root"

        lines = [
            line.strip()
            for line in req_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert len(lines) >= 10, "requirements.txt must specify core dependencies"

        pkg_names = {re.split(r"[\[><=~;]", line)[0].strip().lower() for line in lines}

        essential = {
            "fastapi",
            "uvicorn",
            "pydantic",
            "sqlalchemy",
            "networkx",
            "langgraph",
            "pyjwt",
            "redis",
            "fakeredis",
            "pypdf",
            "sqlparse",
            "bcrypt",
        }
        missing = essential - pkg_names
        assert not missing, f"requirements.txt missing essential packages: {missing}"


class TestBackendDockerfile:
    """Verifies backend Dockerfile multi-stage build and security invariants."""

    def test_backend_dockerfile_exists(self) -> None:
        dockerfile = REPO_ROOT / "Dockerfile.backend"
        root_dockerfile = REPO_ROOT / "Dockerfile"
        assert dockerfile.exists(), "Dockerfile.backend must exist at repository root"
        assert root_dockerfile.exists(), "Dockerfile must exist at repository root"

    def test_backend_multistage_and_non_root(self) -> None:
        dockerfile = REPO_ROOT / "Dockerfile.backend"
        content = dockerfile.read_text(encoding="utf-8")

        # Multi-stage verification
        from_instructions = re.findall(r"^FROM\s+(\S+)(?:\s+[aA][sS]\s+(\S+))?", content, re.MULTILINE)
        assert len(from_instructions) >= 2, "Backend Dockerfile must implement multi-stage build (>= 2 FROM stages)"

        # Base image verification: python slim
        builder_image = from_instructions[0][0].lower()
        runtime_image = from_instructions[-1][0].lower()
        assert "python" in builder_image and "slim" in builder_image, f"Builder must use python-slim base: {builder_image}"
        assert "python" in runtime_image and "slim" in runtime_image, f"Runtime must use python-slim base: {runtime_image}"

        # Virtual environment separation
        assert "/opt/venv" in content, "Backend Dockerfile must utilize /opt/venv for clean dependency isolation"
        assert "COPY --from=" in content, "Runtime stage must copy artifacts from builder stage"

        # Non-root user verification
        user_matches = re.findall(r"^USER\s+(\S+)", content, re.MULTILINE)
        assert user_matches, "Backend Dockerfile must specify a USER instruction"
        final_user = user_matches[-1].strip().lower()
        assert final_user not in ("root", "0"), f"Backend container must run as non-root user, found: {final_user}"

        # Port and command verification
        assert re.search(r"^EXPOSE\s+8001", content, re.MULTILINE), "Backend Dockerfile must EXPOSE port 8001"
        assert re.search(r"uvicorn.*backend\.app\.main:app", content), "Backend Dockerfile CMD/ENTRYPOINT must run backend.app.main:app"
        assert "8001" in content, "Backend Dockerfile must bind to port 8001"

        # Healthcheck
        assert "HEALTHCHECK" in content, "Backend Dockerfile must define a HEALTHCHECK"
        assert "/health/live" in content or "8001" in content, "HEALTHCHECK must probe live health endpoint"


class TestFrontendDockerfile:
    """Verifies frontend Dockerfile multi-stage build and security invariants."""

    def test_frontend_dockerfiles_exist(self) -> None:
        root_fe = REPO_ROOT / "Dockerfile.frontend"
        fe_dir = REPO_ROOT / "frontend" / "Dockerfile"
        assert root_fe.exists(), "Dockerfile.frontend must exist at repository root"
        assert fe_dir.exists(), "frontend/Dockerfile must exist in frontend directory"

    def test_frontend_multistage_and_non_root(self) -> None:
        fe_dockerfile = REPO_ROOT / "frontend" / "Dockerfile"
        content = fe_dockerfile.read_text(encoding="utf-8")

        # Multi-stage verification: deps, builder, runner
        from_instructions = re.findall(r"^FROM\s+(\S+)(?:\s+[aA][sS]\s+(\S+))?", content, re.MULTILINE)
        assert len(from_instructions) >= 3, "Frontend Dockerfile must implement multi-stage build (deps, builder, runner)"

        # Base image: node alpine or slim
        for img, stage in from_instructions:
            assert "node" in img.lower(), f"Stage {stage} must use node base image: {img}"

        # Next.js standalone runner artifacts
        assert ".next/standalone" in content, "Frontend Dockerfile must copy .next/standalone output"
        assert ".next/static" in content, "Frontend Dockerfile must copy .next/static output"

        # Non-root user verification
        user_matches = re.findall(r"^USER\s+(\S+)", content, re.MULTILINE)
        assert user_matches, "Frontend Dockerfile must specify a USER instruction"
        final_user = user_matches[-1].strip().lower()
        assert final_user not in ("root", "0"), f"Frontend container must run as non-root user, found: {final_user}"

        # Port and command verification
        assert re.search(r"^EXPOSE\s+3001", content, re.MULTILINE), "Frontend Dockerfile must EXPOSE port 3001"
        assert "server.js" in content, "Frontend Dockerfile must launch server.js"
        assert "HEALTHCHECK" in content, "Frontend Dockerfile must define a HEALTHCHECK"


class TestDockerignoreFiles:
    """Verifies repository and frontend .dockerignore exclusion rules."""

    def test_root_dockerignore_exists_and_covers_artifacts(self) -> None:
        ignore_file = REPO_ROOT / ".dockerignore"
        assert ignore_file.exists(), ".dockerignore must exist at repository root"

        content = ignore_file.read_text(encoding="utf-8")
        patterns = {line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")}

        essential_excludes = {
            ".git",
            ".venv",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "node_modules",
        }
        for pattern in essential_excludes:
            assert any(pattern in p for p in patterns), f"Root .dockerignore must ignore {pattern}"

    def test_frontend_dockerignore_exists_and_covers_artifacts(self) -> None:
        ignore_file = REPO_ROOT / "frontend" / ".dockerignore"
        assert ignore_file.exists(), "frontend/.dockerignore must exist"

        content = ignore_file.read_text(encoding="utf-8")
        patterns = {line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")}

        essential_excludes = {
            "node_modules",
            ".next",
            ".git",
        }
        for pattern in essential_excludes:
            assert any(pattern in p for p in patterns), f"frontend/.dockerignore must ignore {pattern}"
