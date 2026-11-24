"""A finding is one reportable result of a check: a code, a message, where it happened and where to read about it."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import REPO_ROOT

ERROR = "error"
WARN = "warn"


def rel(path) -> str:
    if path is None:
        return ""
    p = Path(path)
    try:
        return p.resolve().relative_to(REPO_ROOT).as_posix()
    except (ValueError, OSError):
        return p.as_posix()


@dataclass
class Finding:
    code: str
    message: str
    file: str = ""
    location: str = ""
    doc: str = ""
    severity: str = ERROR
    extra: dict = field(default_factory=dict)
    hint: str = ""
    #: the validation stage that produced it, when it belongs to one (set by the command, not by the checks)
    stage: str = ""

    def format(self) -> str:
        where = self.file + (" " + self.location if self.location else "")
        text = "[%s] %s%s" % (self.code, self.message, "  (%s)" % where.strip() if where.strip() else "")
        if self.stage:
            text += "\n        stage: %s" % self.stage
        if self.hint:
            text += "\n        fix: %s" % self.hint
        if self.doc:
            text += "\n        read: %s" % self.doc
        return text


class InputProblem(Exception):
    """A document cannot support the check that reads it. `message` says what is wrong and `hint` how to fix it."""

    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.message, self.hint = message, hint


def describe_error(exc: Exception) -> str:
    """What went wrong, in words, for an exception raised while a check read a malformed document (no Python type names)."""
    if isinstance(exc, InputProblem):
        return exc.message
    if isinstance(exc, RecursionError):
        return "a document is nested too deeply for the check to read"
    if isinstance(exc, KeyError):
        return "a field the check needs is missing: %s" % exc
    if isinstance(exc, IndexError):
        return "a list is shorter than the check needs"
    if isinstance(exc, (TypeError, AttributeError)):
        return "a value has a type the check cannot read (%s)" % exc
    return str(exc) or "the value is not valid"


def doc_for_contract(contract_id: Optional[str]) -> str:
    names = {
        "C01": "contracts/c01-context.md",
        "C02": "contracts/c02-evidence.md",
        "C03": "contracts/c03-selection.md",
        "C04": "contracts/c04-decision-packet.md",
        "C05": "contracts/c05-action-proposal.md",
        "C06": "contracts/c06-delegation.md",
        "C07": "contracts/c07-execution-receipt.md",
    }
    return names.get(contract_id or "", "contracts/README.md")
