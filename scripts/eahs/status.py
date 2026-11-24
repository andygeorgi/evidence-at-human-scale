"""The states a validation stage can end in, and how they combine into one result.

A check that did not look at anything cannot pass. The five states keep "it passed", "it failed", "it was left out",
"there was nothing to look at" and "the input could not be read" apart, so that an empty folder or a skipped stage
is never reported as a success.

    PASS          at least one relevant item was evaluated and every required check passed
    FAIL          evaluated content breaks a rule
    SKIPPED       the stage was left out on purpose (``--only``, ``--skip``) or does not apply
    NOT ASSESSED  the input the stage needs does not exist, so nothing was evaluated
    INPUT ERROR   the input is malformed or incomplete and cannot support the stage
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List

from .findings import Finding

PASS = "PASS"
FAIL = "FAIL"
SKIPPED = "SKIPPED"
NOT_ASSESSED = "NOT ASSESSED"
INPUT_ERROR = "INPUT ERROR"

STATES = (PASS, FAIL, SKIPPED, NOT_ASSESSED, INPUT_ERROR)

#: Exit code of the command for each overall state. Only PASS is zero.
EXIT_CODES = {PASS: 0, FAIL: 1, INPUT_ERROR: 2, NOT_ASSESSED: 3}

#: What a reader should do next, by state.
NEXT_STEP = {
    FAIL: "Each finding names the rule, the file and the contract page to read.",
    NOT_ASSESSED: "Supply the missing input, or run the stages on a folder that has it.",
    INPUT_ERROR: "Fix the input named above, then run the command again. This says nothing about the content.",
}


@dataclass
class StageResult:
    stage: str
    title: str
    status: str
    evaluated: int = 0
    findings: List[Finding] = field(default_factory=list)
    detail: str = ""
    seconds: float = 0.0
    #: set when the stage ran only because a selected stage needs it
    needed_by: str = ""

    @property
    def passed(self) -> bool:
        return self.status == PASS


def overall(results: Iterable[StageResult]) -> str:
    """The state of the whole run: the worst state of any stage that was not skipped.

    INPUT ERROR outranks FAIL (fix the input first), FAIL outranks NOT ASSESSED, and a run in which no stage passed and
    none failed (everything skipped, or nothing to evaluate) is NOT ASSESSED, never PASS.
    """
    states = [r.status for r in results]
    for worst in (INPUT_ERROR, FAIL, NOT_ASSESSED):
        if worst in states:
            return worst
    return PASS if PASS in states else NOT_ASSESSED


def input_finding(code: str, message: str, file: str = "", hint: str = "") -> Finding:
    """A diagnostic for input that cannot be evaluated. The hint says how to fix it."""
    return Finding(code, message, file, hint=hint)
