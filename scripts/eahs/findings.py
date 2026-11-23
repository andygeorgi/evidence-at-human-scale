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

    def format(self) -> str:
        where = self.file + (" " + self.location if self.location else "")
        text = "[%s] %s%s" % (self.code, self.message, "  (%s)" % where.strip() if where.strip() else "")
        if self.doc:
            text += "\n        read: %s" % self.doc
        return text


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
