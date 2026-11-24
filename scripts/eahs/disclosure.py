"""Permission before disclosure: the decision list of Figure F09, written as code.

An expected input that is not in front of a requester is described to that requester only after two permission questions
have been answered, and only as far as the answers allow:

1. May the requester know that the input exists? If not, nothing about it is shown. It adds nothing to the output except
   the one coverage statement that every output carries, whether or not anything is withheld.
2. May the requester read it? If not, and its existence may be disclosed, the entry is ``inaccessible``, in the words the
   permission decision allows and no others: no name, type, count, state or age.
3. Only for an input the requester may read is it classified as stale, not assessed, unavailable, missing, negative or
   not retrieved, and only then is anything about its state shown.

The order is the point. Classifying first ("it is stale") and filtering afterwards would tell a requester that a record
exists, and how old it is, before anyone asked whether they may know. The functions here are a reference for that order,
used by the tests; they are not an implementation of the architecture.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

NO_ENTRY = "no entry"
#: The questions in the order they are asked. The first two are about permission and come before any classification.
DECISION_ORDER = (NO_ENTRY, "inaccessible", "stale", "not_assessed", "unavailable", "missing", "negative", "not_retrieved")


@dataclass(frozen=True)
class ExpectedInput:
    """One input a task expected, with what the system knows about it and what the requester may be told."""
    name: str
    requester_may_know_it_exists: bool
    requester_may_read_it: bool
    #: the wording a permission decision allows for an input the requester may know about but not read
    permitted_disclosure: str = ""
    record_available: bool = False
    record_fresh: bool = True
    check_performed: bool = True
    source_answered: bool = True
    retrieval_completed: bool = True
    absence_observed_with_complete_coverage: bool = False


@dataclass(frozen=True)
class Entry:
    label: str
    text: str


def classify(item: ExpectedInput) -> str:
    """The label the requester sees for an expected input, asking the questions in order. NO_ENTRY means nothing is shown."""
    if not item.requester_may_know_it_exists:
        return NO_ENTRY
    if not item.requester_may_read_it:
        return "inaccessible"
    if item.record_available and not item.record_fresh:
        return "stale"
    if not item.check_performed:
        return "not_assessed"
    if not item.source_answered:
        return "unavailable"
    if not item.retrieval_completed:
        return "missing"
    if item.absence_observed_with_complete_coverage:
        return "negative"
    return "not_retrieved"


def disclose(item: ExpectedInput) -> Optional[Entry]:
    """What the requester is told about one input, or None. An unreadable input is described by its permitted wording only."""
    label = classify(item)
    if label == NO_ENTRY:
        return None
    if label == "inaccessible":
        return Entry(label, item.permitted_disclosure)
    return Entry(label, "%s: %s" % (label, item.name))


def project(items: Sequence[ExpectedInput], coverage_statement: str) -> List[Entry]:
    """The requester's view of a task: an entry for each input they may know about, then the coverage statement every output carries."""
    return [entry for entry in (disclose(item) for item in items) if entry is not None] + [Entry("coverage", coverage_statement)]
