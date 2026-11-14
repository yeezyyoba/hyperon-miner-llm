"""Shared pytest fixtures."""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PETTA = ROOT / ".petta" / "run.sh"


@pytest.fixture(scope="session")
def root() -> Path:
    return ROOT


def pytest_collection_modifyitems(config, items):
    """Skip PeTTa-marked tests cleanly when the toolchain is not installed."""
    if PETTA.exists():
        return
    skip = pytest.mark.skip(reason="pinned PeTTa not installed (run ./setup.sh)")
    for item in items:
        if "petta" in item.keywords:
            item.add_marker(skip)
