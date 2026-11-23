"""Shared helpers for the test suite: put `scripts/` on the path and load the example model once."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
EXAMPLES = REPO / "examples"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from eahs.model import load_model  # noqa: E402
from eahs.schema import load_schema  # noqa: E402

_CACHE = {}


def example_model():
    if "model" not in _CACHE:
        model, problems = load_model(EXAMPLES)
        assert not problems, problems
        _CACHE["model"] = model
    return _CACHE["model"]


def schema():
    if "schema" not in _CACHE:
        _CACHE["schema"] = load_schema()
    return _CACHE["schema"]


def read_json(relative):
    return json.loads((EXAMPLES / relative).read_text(encoding="utf-8"))
