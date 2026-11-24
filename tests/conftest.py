"""Shared test fixtures."""

from collections.abc import Callable
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_html() -> Callable[[str], str]:
    """Load a synthetic HTML fixture page by filename."""

    def laden(name: str) -> str:
        return (FIXTURES / name).read_text(encoding="utf-8")

    return laden
