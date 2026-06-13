"""Collectors: one module per source. Each returns normalized, provenance-bearing
records and FAILS LOUDLY (SourceDriftError) if a live source changed shape.

In offline/fixture mode every collector reads from data/cache or tests/fixtures
and performs ZERO live requests (idempotency guarantee, §6)."""
from .base import (
    SourceDriftError,
    Collector,
    load_fixture,
    provenance_for,
)

__all__ = ["SourceDriftError", "Collector", "load_fixture", "provenance_for"]
