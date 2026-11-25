"""Render an assistant response from a decision packet, and check any response against the packet it cites.

Two kinds of validation are demonstrated, on synthetic data. They answer different questions and must not be confused.

CANONICAL RESPONSE VALIDATION. A deterministic renderer can write the response from a packet with no model at all (a
fallback when the assistant model is unavailable, and a baseline to compare a model against). A response that says it
came from that renderer (``produced_by`` starts with ``template``) is compared statement by statement with what the
renderer produces from its packet. Any difference fails, and a difference that adds or removes a negation, changes a
status word or changes a figure is reported as a change of meaning (RESP102). This verifies the response's content
against a defined template. It does not verify the packet.

STRUCTURAL FREE-TEXT VALIDATION. A response written by a model or a person is checked against named constraints:
it names its packet as a decision packet (``contract_id`` C04); every statement cites packet items of the right kind and
says something (a statement that rests on an item with no text in it is held to the same constraints, against no text);
its figures (with their sign) and currencies (any ISO 4217 code or currency sign), its status words (pass, fail, stale,
revoked, ...), whether it negates them ("did not fail"), and the record identifiers it names (each whole: GR-552 is not
GR-5521) all appear in the items it cites, for a claim, an inference, a conflict, a gap, a recommendation, a proposal and
an obligation alike, and the label of a statement is held to the same status words and certainty as its text; an inference
is labeled and keeps a limitation; a conflict stays open and a gap keeps its missingness label; a recommendation says it
is for review; a proposal is not worded as done; certainty is not added; every conflict, gap, recommendation, proposal and
obligation of the packet is mentioned; and at least MIN_CLAIM_COVERAGE of its supported claims are stated, so that they
cannot all disappear. A claim is counted once, however many of its parts a response cites, and only when a statement that
cites it keeps one of its figures and one of its words (or, when it has no figure, two of its words; a claim with no word
of its own is stated only by a statement that contains it): a bare number does not state a claim. A statement about an
input the reader may not read is exactly the wording the permission decision allows, its label says only where the gap is
("gap 3"), and it cites the gap itself and not a part of it. These constraints catch specific, named
failures. They do NOT show that the prose is
semantically correct: a sentence can satisfy every constraint and still mislead. Where the response is not canonical,
only a person, or a comparison with a canonical rendering, can judge what it means.

LIFECYCLE. A response never defines its own lifecycle. Whether it is ``current`` or ``withdrawn`` comes from the trusted
packet it cites (``trusted_lifecycle``): an active packet gives a current response, an invalidated or superseded one a
withdrawn response. Both validations compare the response with that, so a response cannot call itself current, active,
historical or anything else, and a withdrawn response carries the packet's own reason and nothing else: exactly that reason,
with at most the introduction "This response was withdrawn:" (words added to a reason cannot be checked, so none are
allowed). A withdrawn response also marks its advice (recommendations, proposals, obligations) as withdrawn, and no statement
in it calls anything current or valid unless the packet items it cites do. Advice that says "withdrawn" and takes it back
("never withdrawn", "reinstated") is not marking anything. These too are mechanical constraints; they do
not judge what a free-form sentence means.

Neither validation shows that the packet is right, and neither says anything about how a real model would behave.
"""
from __future__ import annotations

import math
import re
import unicodedata
from typing import Dict, Iterator, List, Optional, Tuple

from .findings import Finding, rel
from .model import Instance, Model, iter_refs, resolve_pointer

DOC = "docs/implementation-guide.md"
DOC_EVIDENCE = "architecture/evidence-semantics.md"
DOC_RESPONSE = "examples/06-assistant-response/README.md"

KIND_PREFIX = {
    "claim": "/supported_claims_references/",
    "inference": "/labeled_inferences/",
    "conflict": "/conflicts_uncertainty/conflicts/",
    "gap": "/coverage_omissions_gaps/missingness/",
    "recommendation": "/recommendations/",
    "proposal": "/action_proposals/",
    "obligation": "/priority_mandatory_obligations/obligation_references/",
    "limitation": "/coverage_omissions_gaps/visible_scoped_limitation_summary",
}
REQUIRED_COVERAGE = ("inference", "conflict", "gap", "recommendation", "proposal", "obligation")
#: Supported claims need not all be repeated, but a response may not let them disappear: it states at least this share of them
#: (rounded up, and never fewer than one). The figure is a documented minimum for this reference check, not a finding about any model.
MIN_CLAIM_COVERAGE = 0.5
FIGURE_CHECKED = ("claim", "inference", "conflict", "recommendation")
#: The statements that tell the reader what to do. In a withdrawn response none of them may read as current advice.
ADVICE_KINDS = ("recommendation", "proposal", "obligation")
#: The only two statuses a response can have. Which one it has is decided by its packet, never by the response.
RESPONSE_STATUSES = ("current", "withdrawn")
DECISION_WORDING = re.compile(r"\b(has|have|had|was|were|been|is|are)\s+(now\s+)?(approved|executed|released|paid|sent|submitted)\b", re.I)
#: A figure, with its sign. A hyphen is a sign unless it follows a word character, a point, a comma, a slash or another hyphen (S-1042, 2026-11-18). A colon
#: after a digit makes a time or a ratio ("13:45"), which is one figure; a colon after a word is a delimiter ("Total:-18,400.00"), and a sign behind it is a sign.
FIGURE = re.compile(r"(?<![\w.,/-])(?<!\d:)-?\d[\d,.:/-]*\d|(?<![\w.,/-])(?<!\d:)-?\d|\d[\d,.:/-]*\d|\d")
#: The alphabetic codes of ISO 4217 (the currencies in circulation) and the common currency signs. A statement may name a currency only
#: if the items it cites do, so that EUR 18,400.00 cannot become CAD 18,400.00 or $18,400.00. Matching is by the uppercase code, whole.
ISO_4217 = frozenset("""
AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BRL BSD BTN BWP BYN BZD CAD CDF CHF CLP CNY COP CRC CUP CVE CZK
DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD GNF GTQ GYD HKD HNL HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES KGS KHR KMF
KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA MKD MMK MNT MOP MRU MUR MVR MWK MXN MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK
PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE SLL SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY TTD TWD TZS UAH
UGX USD UYU UZS VES VND VUV WST XAF XCD XOF XPF YER ZAR ZMW ZWL
""".split())
_ISO_ALTERNATIVES = "|".join(sorted(ISO_4217))
#: Every currency sign Unicode knows (category Sc: $, ¢, £, ¥, €, ₹, ₽, ₩, and signs of the second plane such as U+1ECB0), so that a sign is not left out because a list did
#: not think of it. Unicode keeps its symbols in the first two planes; a test scans the whole range, so that a later version of Unicode that puts one elsewhere is noticed.
_CURRENCY_SIGNS = "".join(re.escape(chr(code)) for code in range(0x20, 0x20000) if unicodedata.category(chr(code)) == "Sc")
CURRENCY = re.compile(r"\b(?:%s)\b|[%s]" % (_ISO_ALTERNATIVES, _CURRENCY_SIGNS))
#: A currency code with a sign right behind it ("EUR-18,400.00", "EUR\u221218,400.00") is a negative amount, not a hyphenated word.
CODE_THEN_SIGN = re.compile(r"\b(%s)(?=[-\u2212]\d)" % _ISO_ALTERNATIVES)
#: A sign right in front of a currency ("\u2212EUR 18,400.00", "-$5") is the sign of the amount that follows it. A hyphen counts only when it touches the
#: currency and is not part of a longer word or number (S-EUR, 5-$3): "100 units - EUR 184.00" is a dash, not a sign. The minus sign (U+2212) always counts.
SIGN_THEN_CURRENCY = re.compile(r"(?:(?<![\w.,/-])(?<!\d:)-|\u2212\s*)((?:%s)\b|[%s])\s*(?=\d)" % (_ISO_ALTERNATIVES, _CURRENCY_SIGNS))

#: Statement kinds on which each structural constraint is applied. Status consistency covers every kind that states something about
#: the packet: a claim, an inference, a conflict, a gap, a recommendation, a proposal and an obligation.
STATUS_CHECKED = ("claim", "inference", "conflict", "gap", "recommendation", "proposal", "obligation")
IDENTIFIER_CHECKED = ("claim", "inference", "conflict", "gap", "recommendation", "proposal", "obligation")
#: The words that label a response's own lifecycle. In a withdrawn response they mark its advice as withdrawn, so on advice they
#: are not compared with the packet's items.
LIFECYCLE_LABELS = ("withdrawn", "current")

#: Status words a statement may use only if the items it cites use them too: a failed match may not become a passed one.
STATUS_WORDS = {
    "pass": re.compile(r"\bpass(?:es|ed|ing)?\b", re.I),
    "fail": re.compile(r"\bfail(?:s|ed|ing|ure)?\b", re.I),
    "stale": re.compile(r"\bstale\b|\bout of date\b", re.I),
    "current": re.compile(r"\bcurrent\b", re.I),
    "superseded": re.compile(r"\bsuperseded\b", re.I),
    "invalidated": re.compile(r"\binvalidated\b", re.I),
    "revoked": re.compile(r"\brevoked\b", re.I),
    "withdrawn": re.compile(r"\bwithdrawn\b", re.I),
}
NEGATION = re.compile(r"\b(?:no|not|never|none|nothing|nobody|neither|nor|without|cannot)\b|n't\b", re.I)
#: Certainty a statement may add only if the items it cites already say it (a source may say "confirmed"; a model may not).
CERTAINTY = re.compile(r"\b(?:certain(?:ly)?|definite(?:ly)?|undoubted(?:ly)?|guarantee[sd]?|proven|proves?|conclusive(?:ly)?|beyond (?:any )?doubt|without (?:a )?doubt|no doubt|obviously|clearly|confirmed|verified|safe to (?:pay|release))\b", re.I)
#: Wording that closes what the packet keeps open.
CLOSES_CONFLICT = re.compile(r"\bno (?:longer )?(?:a )?(?:material )?conflicts?\b|\bnot (?:a )?conflicts?\b|\bconflicts? (?:is|are|was|were|has been|have been) (?:now )?(?:resolved|settled|closed|reconciled|cleared)\b|\b(?:resolved|reconciled|settled) conflicts?\b|\bsources (?:agree|are consistent)\b|\bno (?:material )?(?:discrepanc\w+|differences?)\b", re.I)
DENIES_GAP = re.compile(r"\bnothing (?:is|was) missing\b|\bno (?:gaps?|omissions?|missing (?:evidence|information))\b|\b(?:fully|completely|entirely) (?:covered|checked|assessed)\b|\ball (?:sources|checks|evidence) (?:were|was|have been) (?:checked|covered|available|retrieved)\b", re.I)
CLOSES_OBLIGATION = re.compile(r"\bno (?:review|obligation|action) (?:is )?(?:required|needed|due)\b|\balready (?:done|met|completed|satisfied|reviewed)\b|\bwaived\b", re.I)
#: Markers a statement must keep so that the uncertainty of what it cites is not lost.
KEEPS_CONFLICT_OPEN = re.compile(r"\bunresolved\b|\bnot (?:yet )?(?:been )?resolved\b|\bnobody has resolved\b|\bdisagree\w*\b|\bdiffer(?:s|ed|ent|ing)?\b|\bcontradict\w*\b|\bstill open\b", re.I)
KEEPS_INFERENCE_LIMITED = re.compile(r"not verified|unverified|model-generated|\blimits?:|\blimitations?\b|common origin|one origin|\bprobabl\w+|\bpossibl\w+|\bmight\b|\bmay\b|\bsuggest\w*|\bappears?\b|\binfers?\b", re.I)
KEEPS_RECOMMENDATION_OPEN = re.compile(r"for review|not a decision", re.I)
#: The words that say each missingness label. A gap statement must use the words of every label it cites.
STATE_WORDS = {
    "missing": re.compile(r"\bmissing\b|\bnot obtained\b|\bno (?:carrier |warehouse )?(?:record|evidence)\b|\bnot (?:been )?(?:received|found)\b", re.I),
    "not_retrieved": re.compile(r"\bnot retrieved\b|\bno relevant\b|\breturned nothing\b|\bempty result\b|\bretrieval\b", re.I),
    "inaccessible": re.compile(r"\binaccessible\b|\bpermissions?\b|\baccess\b", re.I),
    "unavailable": re.compile(r"\bunavailable\b|\bnot available\b|\bdid not (?:answer|respond|recover)\b|\bcould not (?:be )?(?:read|reached|provide)\b", re.I),
    "negative": re.compile(r"\bnone found\b|\bfound nothing\b|\bno (?:match|such|duplicate)\b|\bnot found\b|\bchecked\b", re.I),
    "not_assessed": re.compile(r"\bnot assessed\b|\bno assessment\b|\bwas not (?:assessed|performed)\b", re.I),
    "stale": re.compile(r"\bstale\b|\bout of date\b|\btoo old\b|\bolder than\b", re.I),
}
IDENTIFIER = re.compile(r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9][A-Za-z0-9.]*)+\b")
#: Wording that marks a statement as withdrawn, so that it cannot be read as current advice.
WITHDRAWN_MARKER = re.compile(r"\bwithdrawn\b|\bno longer current\b|\bhistorical\b|\bsuperseded\b|\binvalidated\b", re.I)
#: Wording that undoes a withdrawal. A withdrawal reason that says the packet is still valid contradicts the packet's own state.
UNDOES_WITHDRAWAL = re.compile(
    r"(?:\b(?:not|never|no longer)|n't)\s+(?:(?:actually|really|truly|even|yet|ever|been|be)\s+){0,2}(?:invalidated|superseded|withdrawn)\b"
    r"|\bstill\s+(?:current|valid|active|in force|usable)\b"
    r"|\b(?:packet\s+[\w.-]+\s+v\d+|this\s+packet|the\s+packet|this\s+response|the\s+response|it)\s+(?:is|remains?|stays?)\s+(?:current|valid|active|in force|usable)\b"
    r"|\b(?:reinstated|restored|reactivated|re-activated)\b"
    r"|\bwithdrawal\s+(?:is|was|has been)\s+(?:lifted|cancell?ed|reversed|withdrawn)\b",
    re.I)
ISO_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})")
#: The only words a withdrawal reason may add to the packet's own reason: one fixed introduction. Anything else added to a reason
#: could state a cause, a time or a direction that no mechanical test can tell from the true one, so nothing else is allowed.
REASON_INTRODUCTIONS = ("", "This response was withdrawn: ")
#: Words that call something valid today. In a withdrawn response a statement may not use them, unnegated, more often than the
#: packet items it cites do, so "not current advice" is fine and "This is current advice" is not.
CURRENCY_WORDS = re.compile(r"\b(?:current(?:ly)?|active|valid|in force|up[- ]to[- ]date)\b", re.I)
NEGATED_BEFORE = re.compile(r"\b(?:not(?!\s+(?:only|just|merely)\b)|no longer|never|isn't|aren't|wasn't|weren't)\s+(?:\w+\s+){0,2}$", re.I)
#: A negation just before a status word: "did not fail", "no longer current", "isn't stale", "no failures". "Not only" is no negation: "not only confirmed but documented"
#: says it is confirmed, so "not only", "not just" and "not merely" do not count.
NEGATED_STATUS = re.compile(r"(?:\b(?:not(?!\s+(?:only|just|merely)\b)|no|never|none|nothing|nobody|neither|nor|cannot|without|hardly|barely)\b|n't\b)\s+(?:\w+\s+){0,3}$", re.I)
#: Where the reach of a negation ends: a sentence, a colon, a bracket, and a word that turns to the opposite ("not executed but approved" does not negate "approved").
CLAUSE_END = re.compile(r"[.!?;:(]|\b(?:but|however|although|though|except|whereas|nevertheless|nonetheless)\b", re.I)
_ID = r"[A-Z][A-Z0-9]*(?:-[A-Z0-9][A-Za-z0-9.]*)+"
#: "GR-5521 v1 was superseded by GR-5521 v2": the direction of a supersession that a withdrawal reason states.
SUPERSEDED_BY = re.compile(r"(?<![\w-])(?P<old>%s)\s+(?:version\s+)?(?P<old_version>v\d+)\s+(?:was|were|is|has been|had been)\s+(?:superseded|replaced)\s+by\s+(?P<new>%s)\s+(?:version\s+)?(?P<new_version>v\d+)(?!\w|\.\d)" % (_ID, _ID), re.I)
#: What a statement must share with a claim for the claim to count as stated: one of its quantities, or two of its words.
QUANTITY = re.compile(r"(?<![\w.,/-])-?\d[\d,]*(?:\.\d+)?(?![\w/-]|\.\d)")
STAMP = re.compile(r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)?|(?<![\w.,/-])\d{1,2}:\d{2}(?::\d{2})?(?![\w/-])")
WORD = re.compile(r"[a-z]{4,}")
COMMON_WORDS = frozenset("that this with from have been were which their there than into only also such will would could should these those about above after before while when where what than then them they".split())
CLAIM_ITEM = re.compile(r"/supported_claims_references/(\d+)(?:/|$)")


def figures(text: str) -> set:
    """The figures in a text, with their sign: -18,400.00 is not 18,400.00.

    A hyphen counts as a minus only when it is a sign (not the hyphen of S-1042 or of a date). The minus sign (U+2212) is always a sign, and so is
    a hyphen or a minus right behind a currency code or sign ("EUR\u221218,400.00", "EUR-18,400.00") or right in front of one ("\u2212EUR 18,400.00",
    "-$5"): the amount is negative, however it is spaced.
    """
    text = SIGN_THEN_CURRENCY.sub(r"\1 -", text)
    text = CODE_THEN_SIGN.sub(r"\1 ", text).replace("\u2212", " -")
    return {m.rstrip(".,:-/") for m in FIGURE.findall(text)}


def quantities(text: str) -> set:
    """The quantities in a text: numbers that are not part of an identifier, a date or a time (so 100, 184.00 and 18,400.00, not S-1042 or 2026-11-18)."""
    found = set()
    for match in QUANTITY.finditer(STAMP.sub(" ", text.replace("\u2212", "-"))):
        token = match.group(0).replace(",", "")
        try:
            found.add(float(token))
        except ValueError:
            continue
    return found


def content_words(text: str) -> set:
    return {w for w in WORD.findall(text.lower()) if w not in COMMON_WORDS}


def states_claim(claim: str, statement: str) -> bool:
    """True when a statement that cites a claim keeps something concrete of it.

    A claim with a quantity is stated when the statement keeps one of its quantities and at least one of its words: a bare number
    is not the statement of a claim. A claim without a quantity is stated when the statement keeps two of its words (all of them
    if it has fewer). A claim with no word of its own to keep (nothing but figures and short words) is stated only by a statement that
    contains it, as written. This is the least that separates stating a claim from merely citing it. It does not show that the claim is
    stated correctly.
    """
    wanted = quantities(claim)
    words = content_words(claim)
    if not words:
        return bool(_normal(claim)) and _normal(claim) in _normal(statement)
    shared = len(words & content_words(statement))
    if wanted:
        return bool(wanted & quantities(statement)) and shared >= 1
    return shared >= min(2, len(words))


def currency_assertions(text: str) -> int:
    """How many times a text calls something current or valid without negating it ("not current advice" is not such a call).

    Only the words just before each match are read, so a long statement is read in one pass.
    """
    count = 0
    for match in CURRENCY_WORDS.finditer(text):
        clause = CLAUSE_END.split(text[max(0, match.start() - 80):match.start()])[-1]
        if not NEGATED_BEFORE.search(clause):
            count += 1
    return count


def _polarity(pattern, text: str) -> Iterator[Tuple[str, bool]]:
    """Every match of `pattern` in `text` as (the matched words, whether a negation stands just before it).

    "did not fail", "no longer current" and "isn't stale" use the word negated. Only the clause just before each match is read (at most about three
    words back, and not past a full stop, a colon, a semicolon, a bracket or a word that turns to the opposite, such as "but"), so a long text is read
    in one pass.
    """
    for match in pattern.finditer(text):
        clause = CLAUSE_END.split(text[max(0, match.start() - 80):match.start()])[-1]
        yield match.group(0), NEGATED_STATUS.search(clause) is not None


def _uses(pattern, text: str) -> Tuple[bool, bool]:
    """(plain, negated): whether a text uses what `pattern` finds with no negation just before it, and whether it uses it negated: see `_polarity`."""
    plain = negated = False
    for _, is_negated in _polarity(pattern, text):
        if is_negated:
            negated = True
        else:
            plain = True
        if plain and negated:
            break
    return plain, negated


def _undoes_withdrawal(text: str) -> Optional[str]:
    """The first wording in `text` that takes a withdrawal back and that no negation stands before: "Not reinstated" denies it, and "Reinstated" does not."""
    return next((words for words, is_negated in _polarity(UNDOES_WITHDRAWAL, text) if not is_negated), None)


def status_uses(text: str, name: str) -> Tuple[bool, bool]:
    """(plain, negated) for the status word `name`: see `_uses`."""
    return _uses(STATUS_WORDS[name], text)


def _strings(node) -> List[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for v in node.values() for s in _strings(v)]
    if isinstance(node, list):
        return [s for v in node for s in _strings(v)]
    return []


def _tv(value: dict) -> str:
    return value.get("value") or value.get("reason") or ""


def _proposal_strings(model: Model, item) -> List[str]:
    """What a proposal item of a packet stands for: the action of the C05 proposal it references (its kind and its exact target), which is what a statement about the proposal says."""
    ref = _object(_object(item).get("proposal_reference"))
    proposal = model.get("C05", ref.get("id"), ref.get("version"))
    return _strings(_object(proposal.data.get("action"))) if proposal is not None else []


def gap_text(g: dict) -> str:
    """The text for a gap whose own fields the viewer may see. An inaccessible gap is never rendered from its own fields."""
    state, expected = g["state"], g["expected_evidence"]
    if state == "inaccessible":
        raise ValueError("an inaccessible gap is rendered from its permission decision, never from its own fields")
    if state == "missing":
        return "Missing: %s. %s" % (expected, _tv(g["reason"]))
    if state == "not_retrieved":
        return "Not retrieved: %s. Retrieval %s completed with %d relevant records; an empty result does not prove absence." % (
            expected, g["retrieval_reference"]["record_id"], g["relevant_record_count"])
    if state == "unavailable":
        return "Unavailable: %s. %s Nothing was read or assumed." % (expected, _tv(g["reason"]))
    if state == "negative":
        return "Checked, none found: %s. Method: %s; coverage %s for: %s." % (expected, g["method"], g["coverage"]["status"], g["coverage"]["declared_scope"])
    if state == "not_assessed":
        return "Not assessed: %s. No assessment was performed." % expected
    if state == "stale":
        return "Stale: %s %s is out of date. %s" % (g["available_record"]["record_id"], g["available_record"]["version"], g["freshness"]["basis"])
    return "%s: %s" % (state, expected)


def _object(value) -> dict:
    return value if isinstance(value, dict) else {}


def _statements(response: dict) -> list:
    """The statements of a response, or none when the field is not a list (check_structural reports that)."""
    value = response.get("statements", [])
    return value if isinstance(value, list) else []


def _packet_records(packet: Instance) -> set:
    """The (id, version) of every evidence record the packet itself names: the records it rests on, which are the only ones a withdrawal reason may speak of."""
    return {(ref.record_id, ref.version) for ref in iter_refs(packet.data) if ref.kind in ("evidence", "support")}


def _replaced(model: Model, link, packet: Instance) -> List[Instance]:
    """The C02 records that the trusted data says `link` superseded, among those the packet itself names.

    A record that the packet does not name is not part of the packet's story, and it may be one the reader may not know of (its purpose, its tenant): the
    reason a response gives for a withdrawal is built from what the packet rests on and not from a scan of every record that happens to be superseded.
    """
    rests_on = _packet_records(packet)
    return [r for r in model.of("C02") if _object(r.data.get("lifecycle")).get("state") == "superseded" and r.data["lifecycle"].get("replacement_reference") == link and (r.id, r.version) in rests_on]


def trusted_lifecycle(model: Model, packet: Instance) -> Tuple[str, str]:
    """The lifecycle a response about `packet` must carry, taken from the packet's own state and the records it names.

    A response never defines this itself. An active packet gives ("current", ""). An invalidated or superseded packet
    gives ("withdrawn", the reason its own history supports): when it was invalidated and which records caused it.
    """
    from .semantics import packet_active
    if packet_active(packet):
        return "current", ""
    history = _object(packet.data.get("review_version_history"))
    when = _object(history.get("time")).get("value")
    text = "Packet %s %s was %s%s" % (packet.id, packet.version, history.get("state"), " at %s" % when if when else "")
    causes: List[str] = []
    for link in history.get("challenge_links", []):
        replaced = _replaced(model, link, packet)
        if replaced:
            causes += ["%s %s was superseded by %s %s" % (r.id, r.version, link["record_id"], link["version"]) for r in replaced]
        else:
            causes.append("%s %s challenged it" % (link["record_id"], link["version"]))
    return "withdrawn", text + (" because %s" % "; ".join(causes) if causes else "") + "."


def render_response(model: Model, packet: Instance, produced_by: str = "template-fallback-1") -> dict:
    """The deterministic response for a packet. Its status and withdrawal reason come from the packet, not from the caller."""
    d = packet.data
    status, reason = trusted_lifecycle(model, packet)
    withdrawn = status == "withdrawn"
    statements: List[dict] = []

    def add(kind: str, label: str, text: str, pointer: str) -> None:
        statements.append({"kind": kind, "label": label, "text": text, "refs": [pointer]})

    for i, c in enumerate(d["supported_claims_references"]):
        add("claim", c["claim_id"], c["text"], "%s%d" % (KIND_PREFIX["claim"], i))
    for i, inf in enumerate(d["labeled_inferences"]):
        add("inference", inf["inference_id"], "Inference (model-generated, not verified): %s Limits: %s" % (inf["text"], " ".join(inf["limitations"])), "%s%d" % (KIND_PREFIX["inference"], i))
    for i, c in enumerate(d["conflicts_uncertainty"]["conflicts"]):
        add("conflict", c["conflict_id"], "Unresolved conflict %s: %s Materiality: %s." % (c["conflict_id"], c["reason"], c["materiality"].replace("_", " ")), "%s%d" % (KIND_PREFIX["conflict"], i))
    from .semantics import permitted_wording
    shown_gaps = 0
    for i, g in enumerate(d["coverage_omissions_gaps"]["missingness"]):
        if g["state"] == "inaccessible":
            # Rendered from the permission decision, not from the packet's entry: the viewer is shown the permitted wording only,
            # and nothing at all if no decision bound to this viewer lets them know that the input exists.
            wording = permitted_wording(model, packet, g.get("permission_decision_reference", {}))
            if wording is None:
                continue
            text = "Inaccessible: %s" % wording
        else:
            text = gap_text(g)
        # Numbered in the order shown, not by position in the packet, so that a gap the viewer may not know of leaves no gap in the numbering.
        shown_gaps += 1
        add("gap", "gap %d (%s)" % (shown_gaps, g["state"]), text, "%s%d" % (KIND_PREFIX["gap"], i))
    for i, r in enumerate(d["recommendations"]):
        lead = "Recommendation from the withdrawn packet (not current advice; for review, not a decision)" if withdrawn else "Recommendation (for review, not a decision)"
        add("recommendation", r["recommendation_id"], "%s: %s Basis: %s Requires: %s" % (lead, r["text"], r["basis"], r["accountable_review_requirement"]), "%s%d" % (KIND_PREFIX["recommendation"], i))
    for i, p in enumerate(d["action_proposals"]):
        ref = p["proposal_reference"]
        prop = model.get("C05", ref["id"], ref["version"])
        what = "%s on %s %s" % (prop.data["action"]["action_kind"].replace("_", " "), prop.data["action"]["exact_target"]["entity_type"], prop.data["action"]["exact_target"]["entity_id"]) if prop else "an action"
        lead = "Proposal from the withdrawn packet (not current advice; not executed or approved)" if withdrawn else "Proposed (not executed or approved)"
        add("proposal", "%s %s" % (ref["id"], ref["version"]), "%s: %s (proposal %s %s)." % (lead, what, ref["id"], ref["version"]), "%s%d" % (KIND_PREFIX["proposal"], i))
    for i, o in enumerate(d["priority_mandatory_obligations"]["obligation_references"]):
        sel = model.get("C03", o["selection_reference"]["id"], o["selection_reference"]["version"])
        ob = next((x for x in sel.data["obligations"] if x["obligation_id"] == o["obligation_id"]), None) if sel else None
        name = "Obligation %s from the withdrawn packet (not current advice)" % o["obligation_id"] if withdrawn else "Obligation %s" % o["obligation_id"]
        text = "%s: due %s, owner %s." % (name, ob["deadline"], ob["owner"]) if ob else "%s." % name
        add("obligation", o["obligation_id"], text, "%s%d" % (KIND_PREFIX["obligation"], i))
    add("limitation", "limits", d["coverage_omissions_gaps"]["visible_scoped_limitation_summary"], KIND_PREFIX["limitation"])
    out = {
        "response_id": "RESP-%s-%s-%s" % (packet.id.split("-")[-1], packet.version, "template" if produced_by.startswith("template") else "model"),
        "synthetic": True,
        "packet_reference": {"contract_id": "C04", "id": packet.id, "version": packet.version},
        "as_of": d["decision_context_as_of"]["as_of"],
        "produced_by": produced_by,
        "status": status,
        "statements": statements,
    }
    if withdrawn:
        out["status_reason"] = reason
    return out


def render_markdown(response: dict) -> str:
    ref = response["packet_reference"]
    order = [("claim", "What the sources say"), ("inference", "Inferences (model-generated, not verified)"), ("conflict", "Conflicts nobody has resolved"),
             ("gap", "What could not be checked"), ("recommendation", "Recommendations (for review)"), ("proposal", "Proposed actions (none is executed or approved)"),
             ("obligation", "Obligations"), ("limitation", "Limits of this view")]
    lines = ["# Review aid from packet %s %s" % (ref["id"], ref["version"]), "",
             "*Written by: %s. As of %s. Status: **%s**.*" % (response["produced_by"], response["as_of"], response["status"])]
    if response.get("status_reason"):
        lines += ["", "> **Withdrawn.** %s" % response["status_reason"]]
    lines += ["", "This is a review aid. It is not a decision, an approval or an instruction."]
    for kind, title in order:
        items = [s for s in response["statements"] if s["kind"] == kind]
        if not items:
            continue
        lines += ["", "## " + title, ""]
        for s in items:
            lines.append("- %s `[%s]`" % (s["text"], s["label"]))
    return "\n".join(lines) + "\n"


def _status_findings(shown: str, cited_text: str, kind: str, withdrawn: bool, file: str, loc: str, where: str) -> List[Finding]:
    """A status word, and a negation of it, may appear in what the reader sees only if the cited items say it the same way.

    A failed match may not become a passed one, and a failed match may not become one that "did not fail" either. `where` is
    the part of the statement that is read: its text or its label, which the reader sees next to the text.
    """
    out: List[Finding] = []
    for name in STATUS_WORDS:
        if withdrawn and kind in ADVICE_KINDS and name in LIFECYCLE_LABELS:
            continue
        plain, negated = status_uses(shown, name)
        if not (plain or negated):
            continue
        cited_plain, cited_negated = status_uses(cited_text, name)
        if not (cited_plain or cited_negated):
            out.append(Finding("RESP012", "the status word %r is not in the items this statement cites: rewording may not change a status%s" % (name, " (it is in the label)" if where == "label" else ""), file, loc, DOC_RESPONSE))
        elif negated and not cited_negated:
            out.append(Finding("RESP012", "the %s negates the status word %r, but the items this statement cites say it without a negation: rewording may not change a status" % (where, name), file, loc, DOC_RESPONSE))
        elif plain and not cited_plain:
            out.append(Finding("RESP012", "the %s says %r, but the items this statement cites say it only negated: rewording may not change a status" % (where, name), file, loc, DOC_RESPONSE))
    return out


def _names(text: str, ident: str) -> bool:
    """True when a text holds `ident` as a whole identifier: GR-552 is not in GR-5521, and not in GR-552-B."""
    return re.search(r"(?<![\w-])%s(?![\w-]|\.\w)" % re.escape(ident), text) is not None


def _stated(word: str, cited: set) -> bool:
    """True when the items a statement cites state this certainty word themselves (a word and its inflection count as one: certain, certainly)."""
    return any(held == word or held.startswith(word) or word.startswith(held) for held in cited)


#: The two things a proposal must say it is not. Each must be said as a negation ("not executed or approved", "no execution and no approval"), and neither may be
#: asserted plainly ("Approved (not executed)"). The first pattern finds either form of the word, the second only the one that asserts it: "approval is required" does not.
PROPOSAL_NOT = {"executed": (re.compile(r"\bexecut(?:ed|ion)\b", re.I), re.compile(r"\bexecuted\b", re.I)),
                "approved": (re.compile(r"\bapprov(?:ed|al)\b", re.I), re.compile(r"\bapproved\b", re.I))}


def _free_text_findings(kind: str, text: str, label: str, cited_text: str, pointers: List[str], packet: dict, file: str, loc: str, withdrawn: bool = False, exact_wording: bool = False) -> List[Finding]:
    """The named constraints of structural free-text validation, for one statement.

    Each constraint is a specific, mechanical test. None of them proves that the statement means what its packet means.
    The label is shown to the reader beside the text, so the status words, the certainty, the claim of being current and the
    wording that closes what the packet keeps open that the text may not add are held against the label as well, and the text and the label
    together may not call something current more often than the cited items do. A statement that rests on a packet item with no text in it (a number,
    a flag) is held to the same constraints, against no text: it may add nothing. A statement that is exactly the wording a permission
    decision allows for an input the reader may not read (`exact_wording`) is not asked to use the words of the missingness label.
    """
    out: List[Finding] = []
    if not pointers:
        return out
    if kind in FIGURE_CHECKED:
        for code in sorted({m.group(0) for m in CURRENCY.finditer(text)} - {m.group(0) for m in CURRENCY.finditer(cited_text)}):
            out.append(Finding("RESP002", "the currency %s does not appear in the cited packet items" % code, file, loc, DOC_EVIDENCE))
    if kind in STATUS_CHECKED:
        out += _status_findings(text, cited_text, kind, withdrawn, file, loc, "statement")
        out += _status_findings(label, cited_text, kind, withdrawn, file, loc, "label")
    # A certainty word is licensed only by the same word stated plainly in what is cited: "not verified" or "not independently verified" in a source does not license "Verified".
    stated = {words.lower() for words, is_negated in _polarity(CERTAINTY, cited_text) if not is_negated}
    for shown, where in ((text, "statement"), (label, "label")):
        for words, is_negated in _polarity(CERTAINTY, shown):
            if not is_negated and not _stated(words.lower(), stated):
                out.append(Finding("RESP011", "the %s adds certainty (%r) that the cited items do not state" % (where, words), file, loc, DOC_RESPONSE))
    if withdrawn:
        # The statement and its label are read together by the reader, so together they may call something current or valid no more often than the cited items do.
        in_text, in_label, allowed = currency_assertions(text), currency_assertions(label), currency_assertions(cited_text)
        called_current = in_text + in_label > allowed
        if called_current:
            where = "statement and its label" if in_text and in_label else "label" if in_label else "statement"
            out.append(Finding("RESP016", "this %s calls something current or valid in its %s, but the packet is withdrawn and the items it cites do not say so: mark it withdrawn or no longer current" % (kind, where), file, loc, DOC_RESPONSE))
        # Advice that names the withdrawal and then takes it back ("this advice was reinstated") says the opposite of what the packet's state is.
        # A text that does not say it is withdrawn at all has been refused already, so it is not refused twice. A label has no duty to say it, but it may not take it back.
        if kind in ADVICE_KINDS and not called_current:
            for shown, where in ((text, "statement"), (label, "label")):
                undone = _undoes_withdrawal(shown) if where == "label" or says_withdrawn(text) else None
                if undone:
                    out.append(Finding("RESP016", "this %s undoes the withdrawal in its %s (%r): the packet is withdrawn, and a response cannot reinstate it" % (kind, where, undone), file, loc, DOC_RESPONSE))
                    break
    if kind in IDENTIFIER_CHECKED:
        # A label is shown to the reader beside the text, so a record named in it is held to the same rule: it may not name a record that the cited items do not rest on.
        # An identifier is held whole: GR-552 is not GR-5521.
        for ident in sorted(set(IDENTIFIER.findall(text)) | set(IDENTIFIER.findall(label))):
            if not _names(cited_text, ident):
                where = "label" if ident in IDENTIFIER.findall(label) and ident not in IDENTIFIER.findall(text) else "statement"
                out.append(Finding("RESP013", "the %s names %s, which the cited packet items do not rest on: a statement may not attribute its content to another record" % (where, ident), file, loc, DOC_RESPONSE))
    if kind == "conflict":
        if CLOSES_CONFLICT.search(text) or CLOSES_CONFLICT.search(label):
            out.append(Finding("RESP008", "wording closes a conflict that the packet keeps open", file, loc, DOC_RESPONSE))
        if not KEEPS_CONFLICT_OPEN.search(text):
            out.append(Finding("RESP010", "a conflict statement must say that the conflict is unresolved", file, loc, DOC_RESPONSE))
    elif kind == "gap":
        if DENIES_GAP.search(text) or DENIES_GAP.search(label):
            out.append(Finding("RESP008", "wording denies or closes a gap that the packet keeps open", file, loc, DOC_RESPONSE))
        for pointer in pointers:
            try:
                state = resolve_pointer(packet, pointer).get("state")
            except (KeyError, IndexError, ValueError, TypeError, AttributeError):
                continue
            pattern = STATE_WORDS.get(state)
            if pattern is not None and not exact_wording and not pattern.search(text):
                out.append(Finding("RESP009", "the packet labels this gap %s, but the statement does not say so in words" % state, file, loc, DOC_RESPONSE))
    elif kind == "inference":
        if not KEEPS_INFERENCE_LIMITED.search(text):
            out.append(Finding("RESP010", "an inference must keep its limits: say that it is not verified, name its limits or hedge it", file, loc, DOC_RESPONSE))
    elif kind == "recommendation":
        if not KEEPS_RECOMMENDATION_OPEN.search(text):
            out.append(Finding("RESP010", "a recommendation must say that it is for review and not a decision", file, loc, DOC_RESPONSE))
    elif kind == "obligation":
        if CLOSES_OBLIGATION.search(text) or CLOSES_OBLIGATION.search(label):
            out.append(Finding("RESP008", "wording closes an obligation that the packet keeps open", file, loc, DOC_RESPONSE))
    return out


def _lifecycle_findings(model: Model, response: dict, packet: Instance, file: str) -> List[Finding]:
    """The response's status, withdrawal reason and as-of time against the packet it cites.

    The lifecycle is the packet's, not the response's: `trusted_lifecycle` says what the status must be, and the
    response can only agree with it. Every test here is mechanical. None of them judges what a free-form sentence means.
    """
    out: List[Finding] = []
    expected, trusted_reason = trusted_lifecycle(model, packet)
    state = _object(packet.data.get("review_version_history")).get("state")
    status = response.get("status")
    if not isinstance(status, str) or not status.strip():
        out.append(Finding("RESP014", "the response states no status: it must say %s" % " or ".join(RESPONSE_STATUSES), file, "/status", DOC_RESPONSE))
    elif status not in RESPONSE_STATUSES:
        out.append(Finding("RESP014", "status %r is not a response status (%s): the packet decides which one applies" % (status, " or ".join(RESPONSE_STATUSES)), file, "/status", DOC_RESPONSE))
    elif status != expected:
        if expected == "withdrawn":
            out.append(Finding("RESP006", "presented as %s, but packet %s %s has been %s: the response must be withdrawn, and the packet's state decides, not the response" % (status, packet.id, packet.version, state), file, "/status", DOC_RESPONSE))
        else:
            out.append(Finding("RESP006", "marked %s, but packet %s %s is active: a response cannot withdraw itself from an active packet" % (status, packet.id, packet.version), file, "/status", DOC_RESPONSE))
    as_of = response.get("as_of")
    if not isinstance(as_of, str) or not as_of.strip():
        out.append(Finding("RESP006", "the response states no as-of time: it must say which snapshot of the packet it speaks about", file, "/as_of", DOC_RESPONSE))
    elif as_of != packet.data["decision_context_as_of"]["as_of"]:
        out.append(Finding("RESP006", "the response's as-of time differs from the packet's", file, "/as_of", DOC_RESPONSE))
    out.extend(_reason_findings(model, response, packet, expected, trusted_reason, file))
    if expected == "withdrawn":
        for i, st in enumerate(_statements(response)):
            if not (isinstance(st, dict) and st.get("kind") in ADVICE_KINDS):
                continue
            text = str(st.get("text", ""))
            if not says_withdrawn(text):
                out.append(Finding("RESP016", "this %s is phrased as current advice, but packet %s %s is withdrawn: say that it is withdrawn or no longer current" % (st["kind"], packet.id, packet.version), file, "/statements/%d" % i, DOC_RESPONSE))
    return out


def says_withdrawn(text: str) -> bool:
    """True when a text says, affirmatively, that something is withdrawn, no longer current, historical, superseded or invalidated.

    "This advice was never withdrawn" and "not superseded" name the word and say the opposite, so a marker with a negation just
    before it does not count. Only the clause just before each marker is read (at most about three words back).
    """
    return any(not is_negated for _, is_negated in _polarity(WITHDRAWN_MARKER, text))


def _reason_findings(model: Model, response: dict, packet: Instance, expected: str, trusted_reason: str, file: str) -> List[Finding]:
    """The withdrawal reason is the packet's own and nothing else: exactly the trusted reason, with at most one fixed introduction.

    The more specific checks come first, so that a reason that contradicts the withdrawal, names another record, gives another time
    or reverses a supersession says so; the last check is the one that decides: whatever else a reason adds cannot be checked.
    """
    reason = response.get("status_reason")
    present = isinstance(reason, str) and reason.strip() != ""
    if expected == "current":
        if reason not in (None, ""):
            return [Finding("RESP015", "a response about an active packet has no withdrawal reason, and this one carries one: a response cannot declare its own lifecycle", file, "/status_reason", DOC_RESPONSE)]
        return []
    if not present:
        return [Finding("RESP015", "a withdrawn response must give the reason from its packet (%s %s was %s); this one gives none" % (packet.id, packet.version, _object(packet.data.get("review_version_history")).get("state")), file, "/status_reason", DOC_RESPONSE)]
    out: List[Finding] = []
    history = _object(packet.data.get("review_version_history"))
    packet_id, version = re.escape(packet.id), re.escape(packet.version)
    bare = re.escape(packet.version.lstrip("vV"))
    named = re.search(r"(?<![\w-])%s(?![\w-])[\s,:(]*(?:%s(?![\w.])|version\s+v?%s(?![\w.]))" % (packet_id, version, bare), reason)
    if not named:
        out.append(Finding("RESP015", "the withdrawal reason does not name the packet it withdraws (%s %s)" % (packet.id, packet.version), file, "/status_reason", DOC_RESPONSE))
    if not re.search(r"\b%s\b" % re.escape(str(history.get("state"))), reason, re.I):
        out.append(Finding("RESP015", "the withdrawal reason does not say what happened to the packet: its own history says it was %s" % history.get("state"), file, "/status_reason", DOC_RESPONSE))
    undone = UNDOES_WITHDRAWAL.search(reason)
    if undone:
        out.append(Finding("RESP015", "the withdrawal reason contradicts the withdrawal (%r): the packet's state is %s" % (undone.group(0), history.get("state")), file, "/status_reason", DOC_RESPONSE))
    allowed = {packet.id}
    for link in history.get("challenge_links", []):
        allowed.add(link["record_id"])
        allowed |= {r.id for r in _replaced(model, link, packet)}
    for ident in sorted(set(IDENTIFIER.findall(reason)) - allowed):
        out.append(Finding("RESP015", "the withdrawal reason names %s, which is not part of the packet's own history: it may not give another cause" % ident, file, "/status_reason", DOC_RESPONSE))
    times = {_object(history.get("time")).get("value"), packet.data["decision_context_as_of"]["as_of"]}
    for stamp in sorted(set(ISO_TIME.findall(reason)) - times):
        out.append(Finding("RESP015", "the withdrawal reason gives the time %s, which is neither when the packet was withdrawn nor its as-of time" % stamp, file, "/status_reason", DOC_RESPONSE))
    trusted_pairs = {(r.id.upper(), r.version.lower(), link["record_id"].upper(), link["version"].lower()) for link in history.get("challenge_links", []) for r in _replaced(model, link, packet)}
    for found in SUPERSEDED_BY.finditer(reason):
        pair = (found.group("old").upper(), found.group("old_version").lower(), found.group("new").upper(), found.group("new_version").lower())
        if pair not in trusted_pairs:
            out.append(Finding("RESP015", "the withdrawal reason says %s %s was superseded by %s %s, which the packet's own history does not say: it may not reverse or invent a supersession" % (
                found.group("old"), found.group("old_version"), found.group("new"), found.group("new_version")), file, "/status_reason", DOC_RESPONSE))
    if _normal(reason) not in {_normal(lead + trusted_reason) for lead in REASON_INTRODUCTIONS}:
        out.append(Finding("RESP015", "the withdrawal reason must be exactly the packet's own reason, %r, with at most the introduction %r: words added to it cannot be checked, so none are allowed" % (
            trusted_reason, REASON_INTRODUCTIONS[-1].strip()), file, "/status_reason", DOC_RESPONSE))
    return out


def check_structural(model: Model, response: dict, path) -> List[Finding]:
    """STRUCTURAL FREE-TEXT VALIDATION: named constraints on any response. It does not prove that the prose is correct."""
    file = rel(path)
    if not isinstance(response, dict):
        return [Finding("RESP001", "a response must be a JSON object with a status, an as-of time and a list of statements, and this is not an object", file, "/", DOC)]
    findings: List[Finding] = []
    ref = response.get("packet_reference")
    ref = ref if isinstance(ref, dict) else {}
    if ref.get("contract_id") != "C04":
        findings.append(Finding("RESP007", "the packet reference must name a decision packet (\"contract_id\": \"C04\"): this one names %r" % (ref.get("contract_id"),), file, "/packet_reference/contract_id", DOC))
    packet = model.get("C04", ref.get("id"), ref.get("version"))
    if packet is None:
        return findings + [Finding("RESP007", "the response cites packet %s %s, which does not exist" % (ref.get("id"), ref.get("version")), file, "/packet_reference", DOC)]
    d = packet.data
    findings.extend(_lifecycle_findings(model, response, packet, file))
    withdrawn = trusted_lifecycle(model, packet)[0] == "withdrawn"
    cited: Dict[str, set] = {k: set() for k in KIND_PREFIX}
    stated_claims: set = set()
    if not isinstance(response.get("statements", []), list):
        findings.append(Finding("RESP001", "the statements of a response must be a list of statement objects", file, "/statements", DOC))
    for i, st in enumerate(_statements(response)):
        loc = "/statements/%d" % i
        if not isinstance(st, dict):
            findings.append(Finding("RESP001", "a statement must be an object with a kind, a text and the packet items it cites", file, loc, DOC))
            continue
        kind, refs, text, label = st.get("kind"), st.get("refs", []), st.get("text", ""), st.get("label", "")
        if not isinstance(refs, list) or not all(isinstance(r, str) for r in refs) or not isinstance(text, str) or not isinstance(label, str):
            findings.append(Finding("RESP001", "a statement's text and label must be strings and its refs a list of packet pointers", file, loc, DOC))
            continue
        if not isinstance(kind, str) or kind not in KIND_PREFIX:
            findings.append(Finding("RESP001", "unknown statement kind %r" % kind, file, loc, DOC))
            continue
        if not text.strip():
            findings.append(Finding("RESP001", "a %s statement must say something: this one has no text" % kind, file, loc, DOC))
            continue
        if not refs:
            findings.append(Finding("RESP001", "a statement must cite the packet items it rests on: this one cites nothing (%s)" % text[:60], file, loc, DOC_EVIDENCE))
            continue
        subtree: List[str] = []
        resolved: List[str] = []
        for r in refs:
            if not r.startswith(KIND_PREFIX[kind]):
                findings.append(Finding("RESP001", "a %s statement cannot rest on %s (that is not a %s item)" % (kind, r, kind), file, loc, DOC_EVIDENCE))
                continue
            try:
                node = resolve_pointer(d, r)
            except (KeyError, IndexError, ValueError, TypeError):
                findings.append(Finding("RESP001", "%s does not resolve in the packet" % r, file, loc, DOC_EVIDENCE))
                continue
            cited[kind].add(r)
            resolved.append(r)
            subtree += _strings(node)
            if kind == "proposal":
                subtree += _proposal_strings(model, node)
            if kind == "claim":
                item = CLAIM_ITEM.match(r)
                claim = d["supported_claims_references"][int(item.group(1))] if item else None
                if item and states_claim(str(_object(claim).get("text", "")), text):
                    stated_claims.add(int(item.group(1)))
        if kind in FIGURE_CHECKED and subtree:
            extra = figures(text) - figures(" ".join(subtree))
            if extra:
                findings.append(Finding("RESP002", "figures %s do not appear in the cited packet items" % ", ".join(sorted(extra)), file, loc, DOC_EVIDENCE))
        if kind == "inference" and not text.lower().startswith("inference"):
            findings.append(Finding("RESP003", "an inference must be labeled as one (start with \"Inference\")", file, loc, DOC_EVIDENCE))
        if kind == "proposal":
            # A proposal says it is neither executed nor approved, each as a negation: "Approved (not executed)" says only half, and what it says first is the opposite.
            # Its label is read beside the text, so it may not say that the proposal is executed or approved either.
            for name, (either_form, asserting_form) in PROPOSAL_NOT.items():
                if _uses(asserting_form, text)[0]:
                    findings.append(Finding("RESP005", "a proposal is not %s, and this one says it is, or says it without a negation" % name, file, loc, "contracts/c05-action-proposal.md"))
                elif not _uses(either_form, text)[1]:
                    findings.append(Finding("RESP005", "a proposal must say it is not executed or approved: this one does not say it is not %s" % name, file, loc, "contracts/c05-action-proposal.md"))
                if _uses(asserting_form, label)[0]:
                    findings.append(Finding("RESP005", "a proposal is not %s, and the label of this one says it is" % name, file, loc, "contracts/c05-action-proposal.md"))
        if kind not in ("claim", "conflict") and DECISION_WORDING.search(text):
            findings.append(Finding("RESP005", "wording presents an action as approved or done, which the packet does not support", file, loc, "contracts/c05-action-proposal.md"))
        exact = _is_permitted_wording(model, packet, text, resolved) if kind == "gap" else False
        findings += _free_text_findings(kind, text, label, " . ".join(subtree), resolved, d, file, loc, withdrawn, exact)
        if kind == "gap":
            findings += _unreadable_gap_findings(model, packet, text, label, resolved, file, loc)
    claims_total = len(d["supported_claims_references"])
    if claims_total:
        needed = max(1, math.ceil(claims_total * MIN_CLAIM_COVERAGE))
        if len(stated_claims) < needed:
            findings.append(Finding("RESP004", "the response states %d of the packet's %d supported claims: it may be shorter than its packet, but it must state at least %d (%d%%, rounded up) and may not let its claims disappear. "
                                    "A claim counts once however many of its parts are cited, and only when a statement that cites it keeps one of its figures and one of its words, or two of its words if it has no figure" % (
                                        len(stated_claims), claims_total, needed, int(MIN_CLAIM_COVERAGE * 100)), file, "/statements", DOC))
    sections = {
        "inference": len(d["labeled_inferences"]), "conflict": len(d["conflicts_uncertainty"]["conflicts"]), "gap": len(d["coverage_omissions_gaps"]["missingness"]),
        "recommendation": len(d["recommendations"]), "proposal": len(d["action_proposals"]), "obligation": len(d["priority_mandatory_obligations"]["obligation_references"]),
    }
    for kind in REQUIRED_COVERAGE:
        for i in range(sections[kind]):
            pointer = "%s%d" % (KIND_PREFIX[kind], i)
            if kind == "gap" and _withheld_gap(model, packet, d["coverage_omissions_gaps"]["missingness"][i]):
                continue
            if pointer not in cited[kind]:
                findings.append(Finding("RESP004", "the packet's %s item %d is not mentioned: a response may be shorter than its packet but may not drop a %s" % (kind, i + 1, kind), file, "/statements", DOC))
    if KIND_PREFIX["limitation"] not in cited["limitation"]:
        findings.append(Finding("RESP004", "the response does not state the packet's coverage limitation", file, "/statements", DOC))
    return findings


def _withheld_gap(model: Model, packet: Instance, gap: dict) -> bool:
    """True for an inaccessible gap that no permission decision bound to this viewer lets them know about: nothing about it may be said."""
    from .semantics import permitted_wording
    return isinstance(gap, dict) and gap.get("state") == "inaccessible" and permitted_wording(model, packet, _object(gap.get("permission_decision_reference"))) is None


def _normal(text: str) -> str:
    return " ".join(text.lower().split())


#: A pointer into one gap of the packet, whatever part of the gap it points at: a citation of a part of a gap is a citation of the gap.
GAP_ITEM = re.compile(r"(/coverage_omissions_gaps/missingness/\d+)(?:/|$)")
#: The labels a statement about an unreadable input may carry besides the permitted wording itself: where it is, and the missingness label.
NEUTRAL_GAP_LABEL = re.compile(r"gap\s+\d+(?:\s*\(\s*inaccessible\s*\))?|inaccessible", re.I)


def _unreadable(model: Model, packet: Instance, pointers: List[str]) -> Tuple[List[Tuple[str, object]], bool]:
    """The inaccessible gaps that `pointers` cite, whole or by a part: ([(the gap's pointer, the wording a decision bound to the viewer allows for it, or None)], whether a part of one is cited)."""
    from .semantics import permitted_wording
    found: List[Tuple[str, object]] = []
    parts = False
    for pointer in pointers:
        match = GAP_ITEM.match(pointer)
        if not match:
            continue
        parent = match.group(1)
        try:
            gap = resolve_pointer(packet.data, parent)
        except (KeyError, IndexError, ValueError, TypeError):
            continue
        if not isinstance(gap, dict) or gap.get("state") != "inaccessible":
            continue
        if parent not in [p for p, _ in found]:
            found.append((parent, permitted_wording(model, packet, _object(gap.get("permission_decision_reference")))))
        parts = parts or match.group(0) != parent
    return found, parts


def _cited_gaps(pointers: List[str]) -> int:
    """How many different gaps `pointers` cite, whatever part of each they point at."""
    return len({match.group(1) for match in map(GAP_ITEM.match, pointers) if match})


def _is_permitted_wording(model: Model, packet: Instance, text: str, pointers: List[str]) -> bool:
    """True when a statement is exactly the wording a decision bound to the viewer allows for the one unreadable gap it cites, and cites nothing else."""
    unreadable, parts = _unreadable(model, packet, pointers)
    if len(unreadable) != 1 or _cited_gaps(pointers) != 1 or parts or unreadable[0][1] is None:
        return False
    wording = unreadable[0][1]
    return _normal(text) in (_normal(wording), _normal("Inaccessible: " + wording))


def _unreadable_gap_findings(model: Model, packet: Instance, text: str, label: str, pointers: List[str], file: str, loc: str) -> List[Finding]:
    """A statement about an input the viewer may not read is exactly the permitted wording, or it says nothing about it.

    Where no decision bound to the viewer lets them know the input exists, the statement may not cite it at all. Where one
    does, the statement is that decision's wording and nothing else (it may start with the missingness label, "Inaccessible:"),
    it cites the gap itself and no part of it, and it does not share its citation with another gap. Its label is shown beside it,
    so the label carries only the place of the gap ("gap 3", "gap 3 (inaccessible)"), the missingness label or that wording. A
    statement that is exactly the permitted wording is not asked to use the words of the missingness label as well. Words added to the
    statement or to its label, a part of the gap cited with it (its expected evidence, its scope), or the words of a neighbouring gap,
    could carry what the reader may not know, and a mechanical test cannot tell the two apart. These are mechanical tests: they do
    not read prose that does not cite the input for what it hides.
    """
    out: List[Finding] = []
    allowed: List[str] = []
    unreadable, parts = _unreadable(model, packet, pointers)
    for _, wording in unreadable:
        if wording is None:
            out.append(Finding("RESP017", "this statement tells the reader about an input that no permission decision bound to them lets them know exists: it may not be mentioned", file, loc, DOC_RESPONSE))
        else:
            allowed += [_normal(wording), _normal("Inaccessible: " + wording)]
    if allowed and (_cited_gaps(pointers) != 1 or parts or _normal(text) not in allowed):
        out.append(Finding("RESP017", "a statement about an input the reader may not read must be exactly the wording the permission decision allows, alone, citing the gap itself and no part of it, with nothing added and no other gap in the same statement: %r" % allowed[0], file, loc, DOC_RESPONSE))
    if allowed and _normal(label) not in allowed and not NEUTRAL_GAP_LABEL.fullmatch(_normal(label)):
        out.append(Finding("RESP017", "the label of a statement about an input the reader may not read names only where the gap is (\"gap 3\", \"gap 3 (inaccessible)\") or is the permitted wording: this label says more", file, loc, DOC_RESPONSE))
    return out


# ---------------------------------------------------------------------------------------------- canonical validation
def is_canonical(response: dict) -> bool:
    """A response that says a deterministic renderer wrote it is held to that renderer's output."""
    return str(response.get("produced_by", "")).startswith("template")


def meaning_changes(expected: str, actual: str) -> List[str]:
    """What a difference between two renderings does to the meaning: negation, status words, figures, certainty, open or closed."""
    changes: List[str] = []
    negations = (len(NEGATION.findall(expected)), len(NEGATION.findall(actual)))
    if negations[0] != negations[1]:
        changes.append("negation (%d, expected %d)" % (negations[1], negations[0]))
    said = lambda text: sorted(name for name, pattern in STATUS_WORDS.items() if pattern.search(text))  # noqa: E731
    if said(expected) != said(actual):
        changes.append("status words %s, expected %s" % (said(actual) or "none", said(expected) or "none"))
    if figures(expected) != figures(actual):
        changes.append("figures")
    if bool(KEEPS_CONFLICT_OPEN.search(expected)) != bool(KEEPS_CONFLICT_OPEN.search(actual)) or bool(CLOSES_CONFLICT.search(actual)):
        changes.append("open or resolved")
    if sorted(m.group(0).lower() for m in CERTAINTY.finditer(expected)) != sorted(m.group(0).lower() for m in CERTAINTY.finditer(actual)):
        changes.append("certainty")
    return changes


def _short(text: str, limit: int = 120) -> str:
    return text if len(text) <= limit else text[:limit - 3] + "..."


def check_canonical(model: Model, response: dict, packet: Instance, file: str) -> List[Finding]:
    """CANONICAL RESPONSE VALIDATION: the response must equal what the renderer writes from its packet.

    A statement that differs fails (RESP101). A difference that adds or removes a negation, changes a status word or a
    figure, or opens or closes a conflict is reported as a change of meaning (RESP102). The status and the withdrawal
    reason are part of what is compared, and the renderer takes them from the packet, not from the response.
    """
    out: List[Finding] = []
    expected = render_response(model, packet, produced_by=str(response.get("produced_by", "template-fallback-1")))
    compared = ("response_id", "synthetic", "packet_reference", "as_of", "produced_by", "status", "status_reason")
    for key in compared:
        if response.get(key) != expected.get(key):
            out.append(Finding("RESP101", "%s differs from the canonical rendering: expected %r, found %r" % (key, expected.get(key), response.get(key)), file, "/" + key, DOC_RESPONSE))
    for key in sorted(set(response) - set(expected) - set(compared)):
        out.append(Finding("RESP101", "the response has a field %r that the canonical rendering does not have" % key, file, "/" + str(key), DOC_RESPONSE))
    by_key = {(s["kind"], s["label"]): s for s in expected["statements"]}
    seen = set()
    for i, st in enumerate(_statements(response)):
        loc = "/statements/%d" % i
        if not isinstance(st, dict):
            out.append(Finding("RESP101", "a statement must be an object, as the canonical rendering writes it", file, loc, DOC_RESPONSE))
            continue
        key = (st.get("kind"), st.get("label"))
        named = isinstance(key[0], str) and isinstance(key[1], str)   # only text can name a statement of the rendering
        canonical = by_key.get(key) if named else None
        if canonical is None or key in seen:
            out.append(Finding("RESP101", "the %s statement %r is not in the canonical rendering of this packet" % key, file, loc, DOC_RESPONSE))
            continue
        seen.add(key)
        for extra in sorted(set(st) - set(canonical)):
            out.append(Finding("RESP101", "the %s statement %r has a field %r that the canonical rendering does not have" % (key[0], key[1], extra), file, "%s/%s" % (loc, extra), DOC_RESPONSE))
        if st.get("text") != canonical["text"]:
            changes = meaning_changes(canonical["text"], str(st.get("text", "")))
            code = "RESP102" if changes else "RESP101"
            lead = "the statement changes what the packet requires (%s)" % "; ".join(changes) if changes else "the statement differs from the canonical rendering"
            out.append(Finding(code, "%s. Canonical: %s | Found: %s" % (lead, _short(canonical["text"]), _short(str(st.get("text", "")))), file, loc + "/text", DOC_RESPONSE))
        if st.get("refs") != canonical["refs"]:
            out.append(Finding("RESP101", "the citations differ from the canonical rendering: expected %s, found %s" % (canonical["refs"], st.get("refs")), file, loc + "/refs", DOC_RESPONSE))
    for key in by_key:
        if key not in seen:
            out.append(Finding("RESP101", "the canonical rendering has a %s statement %r that the response omits" % key, file, "/statements", DOC_RESPONSE))
    order = [(s.get("kind"), s.get("label")) for s in _statements(response) if isinstance(s, dict) and isinstance(s.get("kind"), str) and isinstance(s.get("label"), str) and (s["kind"], s["label"]) in by_key]
    if not out and order != [(s["kind"], s["label"]) for s in expected["statements"]]:
        out.append(Finding("RESP101", "the statements are in a different order from the canonical rendering", file, "/statements", DOC_RESPONSE))
    return out


def check_response(model: Model, response: dict, path) -> List[Finding]:
    """Validate a response: structural constraints for every response, and the canonical comparison when it claims to be rendered."""
    findings = check_structural(model, response, path)
    if isinstance(response, dict) and is_canonical(response):
        ref = response.get("packet_reference")
        ref = ref if isinstance(ref, dict) else {}
        packet = model.get("C04", ref.get("id"), ref.get("version"))
        if packet is not None:
            findings += check_canonical(model, response, packet, rel(path))
    return findings
