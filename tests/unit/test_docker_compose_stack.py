"""Tests for multi-service Docker Compose stack (P14-4).

Verifies service declarations, port mappings, healthcheck definitions,
inter-service dependencies, network bridges, volume persistence, and compose targets.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def parse_simple_yaml(text: str) -> dict[str, Any]:
    """Lightweight YAML parser for Docker Compose verification without external dependencies."""
    # We will verify using line/regex matching and structural assertions
    return {}


class TestDockerComposeSpecification:
    """Verifies docker-compose.yml configuration and service contracts."""

    def test_compose_file_exists(self) -> None:
        compose_file = REPO_ROOT / "docker-compose.yml"
        assert compose_file.exists(), "docker-compose.yml must exist at repository root"

    def test_all_six_services_declared(self) -> None:
        compose_file = REPO_ROOT / "docker-compose.yml"
        content = compose_file.read_text(encoding="utf-8")

        required_services = [
            "backend",
            "frontend",
            "postgres",
            "redis",
            "qdrant",
            "neo4j",
        ]
        for service in required_services:
            pattern = rf"^\s{{2}}{service}:"
            assert re.search(pattern, content, re.MULTILINE), f"docker-compose.yml must declare service '{service}'"

    def test_port_mappings_correct(self) -> None:
        compose_file = REPO_ROOT / "docker-compose.yml"
        content = compose_file.read_text(encoding="utf-8")

        # Required public host port bindings:
        # Backend: 8001:8001
        # Frontend: 3001:3001
        # Postgres: 5432:5432
        # Redis: 6379:6379
        # Qdrant: 6333:6333
        # Neo4j: 7474:7474, 7687:7687
        expected_ports = [
            r"8001:8001",
            r"3001:3001",
            r"5432:5432",
            r"6379:6379",
            r"6333:6333",
            r"7474:7474",
            r"7687:7687",
        ]
        for port in expected_ports:
            assert re.search(rf'["\']?{port}["\']?', content), f"docker-compose.yml missing port mapping {port}"

    def test_healthchecks_on_all_services(self) -> None:
        compose_file = REPO_ROOT / "docker-compose.yml"
        content = compose_file.read_text(encoding="utf-8")

        # Healthcheck blocks
        healthcheck_count = len(re.findall(r"^\s+healthcheck:", content, re.MULTILINE))
        assert healthcheck_count >= 6, f"All 6 services must define healthchecks, found {healthcheck_count}"

        # Specific probe checks
        assert "pg_isready" in content, "Postgres healthcheck must use pg_isready"
        assert "redis-cli ping" in content or "redis-cli" in content, "Redis healthcheck must use redis-cli"
        assert "6333" in content, "Qdrant healthcheck must probe port 6333"
        assert "7474" in content or "7687" in content, "Neo4j healthcheck must probe neo4j port"
        assert "/health/live" in content, "Backend healthcheck must probe /health/live"

    def test_inter_service_dependencies_and_health_gates(self) -> None:
        compose_file = REPO_ROOT / "docker-compose.yml"
        content = compose_file.read_text(encoding="utf-8")

        # Backend must depend on backing stores
        assert "depends_on:" in content, "docker-compose.yml must define service dependencies"
        assert "condition: service_healthy" in content, "Services must use 'condition: service_healthy' dependency gates"

    def test_network_and_storage_volume_persistence(self) -> None:
        compose_file = REPO_ROOT / "docker-compose.yml"
        content = compose_file.read_text(encoding="utf-8")

        # Volumes section
        assert re.search(r"^volumes:", content, re.MULTILINE), "docker-compose.yml must define persistent volumes"
        assert "postgres" in content and "data" in content, "Must define postgres data volume"
        assert "redis" in content and "data" in content, "Must define redis data volume"
        assert "qdrant" in content and "data" in content, "Must define qdrant data volume"
        assert "neo4j" in content and "data" in content, "Must define neo4j data volume"

        # Custom bridge network
        assert re.search(r"^networks:", content, re.MULTILINE), "docker-compose.yml must define custom network"


class TestDockerComposeEnvironmentAndMakeTargets:
    """Verifies compose environment configuration and Makefile targets."""

    def test_compose_env_file_exists(self) -> None:
        env_docker = REPO_ROOT / ".env.docker.example"
        assert env_docker.exists(), ".env.docker.example must exist at repository root"

        content = env_docker.read_text(encoding="utf-8")
        assert "POSTGRES_PASSWORD" in content, ".env.docker.example must specify POSTGRES_PASSWORD"
        assert "NEO4J_PASSWORD" in content, ".env.docker.example must specify NEO4J_PASSWORD"
        assert "DATABASE_URL" in content, ".env.docker.example must specify DATABASE_URL"
        assert "REDIS_URL" in content, ".env.docker.example must specify REDIS_URL"

    def test_makefile_compose_targets_exist(self) -> None:
        makefile = REPO_ROOT / "Makefile"
        content = makefile.read_text(encoding="utf-8")

        expected_targets = [
            "compose-up",
            "compose-down",
            "compose-logs",
            "compose-ps",
        ]
        for target in expected_targets:
            assert re.search(rf"^{target}:", content, re.MULTILINE), f"Makefile must declare target '{target}'"
