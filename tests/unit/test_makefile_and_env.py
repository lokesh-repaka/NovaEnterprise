"""Unit tests for Makefile and .env.example (N1, N4).

Verifies that .env.example specifies all required platform configuration keys
with offline defaults, and that Makefile defines the canonical automation targets.
"""

import subprocess
from pathlib import Path

from backend.app.core.config import Settings


def test_env_example_exists_and_contains_all_settings_fields():
    """Verify that .env.example exists and defines all fields declared in Settings."""
    env_example_path = Path(".env.example")
    assert env_example_path.exists(), ".env.example must exist at the project root"

    content = env_example_path.read_text(encoding="utf-8")
    lines = [
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.startswith("#")
    ]

    env_keys = set()
    for line in lines:
        if "=" in line:
            key = line.split("=", 1)[0].strip()
            env_keys.add(key.upper())

    # Verify all Settings fields are represented in .env.example
    settings_field_names = {name.upper() for name in Settings.model_fields}

    missing_keys = settings_field_names - env_keys
    assert not missing_keys, (
        f".env.example is missing configuration keys: {missing_keys}"
    )


def test_env_example_offline_defaults():
    """Verify that .env.example defaults enforce N1 offline isolation without external services."""
    env_example_path = Path(".env.example")
    content = env_example_path.read_text(encoding="utf-8")

    parsed_vars: dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            parsed_vars[k.strip().upper()] = v.strip().strip("'\"")

    assert parsed_vars.get("LLM_PROVIDER") == "fake"
    assert parsed_vars.get("VECTOR_STORE") == "memory"
    assert parsed_vars.get("GRAPH_STORE") == "memory"
    assert parsed_vars.get("USE_FAKEREDIS", "").lower() in ("true", "1")
    assert "sqlite" in parsed_vars.get("DATABASE_URL", "").lower()


def test_makefile_exists_and_defines_canonical_targets():
    """Verify that Makefile defines all canonical targets required by Claude.md §14."""
    makefile_path = Path("Makefile")
    assert makefile_path.exists(), "Makefile must exist at the project root"

    content = makefile_path.read_text(encoding="utf-8")

    canonical_targets = [
        "setup",
        "demo",
        "ingest",
        "seed-graph",
        "backend",
        "test",
        "lint",
        "clean",
    ]

    for target in canonical_targets:
        assert f"{target}:" in content, f"Makefile is missing target '{target}'"


def test_makefile_syntax_and_dry_run():
    """Verify Makefile syntax by executing dry-run on canonical targets."""
    targets = ["test", "lint", "clean"]
    for target in targets:
        proc = subprocess.run(
            ["make", "--dry-run", target],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, f"make --dry-run {target} failed: {proc.stderr}"
