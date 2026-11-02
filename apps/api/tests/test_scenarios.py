"""Every real-world dispute scenario in bench/scenarios.py must get the outcome its rule expects."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "bench"))
import scenarios  # noqa: E402

ROWS = scenarios.run()


def test_at_least_one_hundred_scenarios():
    assert len(ROWS) >= 100


@pytest.mark.parametrize("row", ROWS, ids=[r["id"] for r in ROWS])
def test_scenario(row):
    assert row["passed"], f"{row['title']} ({row['rule']}): expected {row['want']}, got {row['got']}"
