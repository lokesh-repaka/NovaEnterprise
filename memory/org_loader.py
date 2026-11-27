"""Organizational memory loader and enterprise ground truth cache for NovaEnterprise (P8-2, F15, Claude.md §7.4).

Provides OrganizationalMemoryLoader conforming to OrganizationalMemoryStore protocol:
- Loads corporate facts, fiscal calendar, SLAs, and service ownership from JSON
- Supports quarter resolution (direct codes e.g. '2026-Q2' and relative aliases e.g. 'last_quarter')
- Thread-safe in-memory caching with reload capability
- Graceful fallbacks on missing or corrupt files (never crashes workflow)
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from backend.app.core.logging import get_logger
from memory.schemas import (
    CompanyInfo,
    FiscalCalendar,
    FiscalQuarter,
    OrganizationalMemory,
    ServiceTier,
)

logger = get_logger("memory.org_loader")

DEFAULT_ORG_MEMORY_PATH = Path("sample_data/organizational_memory.json")


class OrganizationalMemoryLoader:
    """Enterprise organizational memory loader and cache (F15).

    Conforms to the OrganizationalMemoryStore protocol.
    """

    def __init__(self, file_path: Path | str | None = None) -> None:
        self.file_path = Path(file_path) if file_path else DEFAULT_ORG_MEMORY_PATH
        self._lock = threading.Lock()
        self._cached_memory: OrganizationalMemory | None = None

    def load(self) -> OrganizationalMemory:
        """Retrieve the cached OrganizationalMemory model, loading from file if not cached."""
        with self._lock:
            if self._cached_memory is not None:
                return self._cached_memory.model_copy(deep=True)

            loaded = self._read_from_source()
            self._cached_memory = loaded
            return loaded.model_copy(deep=True)

    def reload(self) -> OrganizationalMemory:
        """Clear the cached instance and re-read from the source file."""
        with self._lock:
            self._cached_memory = None
            loaded = self._read_from_source()
            self._cached_memory = loaded
            return loaded.model_copy(deep=True)

    def _read_from_source(self) -> OrganizationalMemory:
        """Internal helper to read and validate the JSON file with safe fallbacks."""
        if not self.file_path.exists():
            logger.warning(
                "Organizational memory file '%s' not found; using default enterprise constants.",
                self.file_path,
            )
            return OrganizationalMemory()

        try:
            with self.file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return OrganizationalMemory.from_dict(data)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to parse organizational memory from '%s': %s. Falling back to defaults.",
                self.file_path,
                exc,
            )
            return OrganizationalMemory()

    def get_fiscal_calendar(self) -> FiscalCalendar:
        """Retrieve corporate fiscal calendar."""
        return self.load().fiscal_calendar

    def get_service_owner(self, service_id: str) -> str | None:
        """Retrieve team ID owning a specific service."""
        return self.load().get_service_owner(service_id)

    def get_service_tier(self, tier_id: str) -> ServiceTier | None:
        """Retrieve SLA specifications for a service tier."""
        return self.load().get_service_tier(tier_id)

    def resolve_quarter(self, identifier: str) -> FiscalQuarter | None:
        """Resolve a quarter by code (e.g. '2026-Q1') or relative alias (e.g. 'last_quarter')."""
        return self.load().fiscal_calendar.resolve_quarter(identifier)

    def get_company_info(self) -> CompanyInfo:
        """Retrieve basic corporate identity metadata."""
        return self.load().company_info


# =====================================================================
# Global Singleton & Functional Helper
# =====================================================================

_org_loader_instance: OrganizationalMemoryLoader | None = None
_loader_lock = threading.Lock()


def get_org_memory_loader(
    file_path: Path | str | None = None,
) -> OrganizationalMemoryLoader:
    """Retrieve application-wide organizational memory loader singleton."""
    global _org_loader_instance
    if _org_loader_instance is None:
        with _loader_lock:
            if _org_loader_instance is None:
                _org_loader_instance = OrganizationalMemoryLoader(file_path=file_path)
    return _org_loader_instance


def load_organizational_memory(
    file_path: Path | str | None = None,
) -> OrganizationalMemory:
    """Convenience helper to retrieve current organizational memory model."""
    loader = get_org_memory_loader(file_path=file_path)
    return loader.load()


def reset_org_memory_loader() -> None:
    """Reset the global singleton loader (for test isolation)."""
    global _org_loader_instance
    with _loader_lock:
        _org_loader_instance = None
