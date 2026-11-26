"""Evidence at Human Scale: schema, example and semantic checks for the documentation contracts.

Small, dependency-light helpers (one third-party dependency: jsonschema). Not an implementation of the
architecture: they validate the structure of the contracts and run deterministic checks on synthetic examples.
"""
from pathlib import Path

__version__ = "1.0.6"
REPO_ROOT = Path(__file__).resolve().parents[2]
