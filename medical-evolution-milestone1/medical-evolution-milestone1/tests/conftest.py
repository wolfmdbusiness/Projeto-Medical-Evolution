import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GOLDEN_STATE_PATH = ROOT / "golden_samples" / "golden_001" / "golden_001_state.json"
GOLDEN_EXPECTED_PATH = ROOT / "golden_samples" / "golden_001" / "golden_001_expected.txt"


def load_golden_state_dict() -> dict:
    return json.loads(GOLDEN_STATE_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def golden_state_dict() -> dict:
    """A fresh, independent copy of the Golden Sample 001 state dict for
    every test that needs to mutate it (e.g. to exercise the renderability
    gate or strict-model validation) without touching the file on disk or
    leaking state between tests."""
    return load_golden_state_dict()


def load_golden_state_number(number: str) -> dict:
    """Load golden_samples/golden_0XX/golden_0XX_state.json by number
    ("002".."008"). Used by the SEMANTIC_RENDER_REFERENCE test suites
    (Milestone 1.2) which never compare a whole document byte-for-byte."""
    path = ROOT / "golden_samples" / f"golden_{number}" / f"golden_{number}_state.json"
    return json.loads(path.read_text(encoding="utf-8"))
