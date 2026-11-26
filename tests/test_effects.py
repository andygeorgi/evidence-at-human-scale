"""A receipt records effects, and an effect that a verified outcome has recorded is not rewritten by a later version.

Each structured effect of a receipt is for the action and the target of that receipt. Once a version that is verified (completed, or not executed) states an effect, the effect is a verified
fact: a later version may repeat it and may add other effects, and it may not change what the effect says about its action, target, quantity, unit, time or accounting record, nor leave it out.
Times are compared as instants. The free text of an effect or of a verification is not read. What an effect says also counts: a known effect is a lower bound of the capacity an attempt holds,
and nothing is added across units.
"""
import copy
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

from eahs import semantics
from eahs.gateway import evaluate_commit, ledger_from_receipts, ts
from eahs.model import Instance, Model

RELEASE, GRANT = ("ACT-REL-0417", "v2"), ("GRT-APPR-0417-B", "v1")
B = "RCP-REL-0417-B"
CODES = ("AUTH010", "ACC006", "ACC004", "ACC005", "AUTH008")


def stored_effect():
    return copy.deepcopy(support.example_model().get("C07", B, "v2").data["outcome"]["observed_effects"][0])


def chain(*edits, versions=("v1", "v2"), extra=None):
    """The example set in which the receipt of the corrected release has these versions, each a copy of a stored one (`versions`), and `extra` more:
    {new name: (stored version, edit of the data)}. `edits` apply to the second stored version, the completed one."""
    base = support.example_model()
    instances = {k: v for k, v in base.instances.items() if not (k[0] == "C07" and k[1] == B)}
    names = {name: (name, None) for name in versions}
    names.update(extra or {})
    for name, (source, edit) in names.items():
        stored = base.get("C07", B, source)
        data = copy.deepcopy(stored.data)
        data["identity_binding"]["version"] = name
        if edit:
            edit(data)
        if name == "v2":
            for change in edits:
                change(data)
        instances[("C07", B, name)] = Instance("C07", B, name, data, stored.path)
    return Model(instances, base.registry, base.root)


def effect(**fields):
    def edit(data):
        for name, value in fields.items():
            data["outcome"]["observed_effects"][0][name] = value
    return edit


def effects_of(data, effects):
    data["outcome"]["observed_effects"] = effects


def found(model, codes=CODES):
    return sorted((f.code, f.file.replace("\\", "/").rsplit("/", 1)[-1], f.location) for f in semantics.check_authority(model) if f.code in codes)


def repeat(*edits):
    """A third version that repeats the completed one, with `edits` applied to its data."""
    def edit(data):
        for change in edits:
            change(data)
    return {"v3": ("v2", edit)}


E0 = "/outcome/observed_effects/0"


class TheStoredReceiptsAreConsistent(unittest.TestCase):
    def test_the_authority_check_finds_nothing_in_the_stored_receipts(self):
        self.assertEqual(found(support.example_model()), [])

    def test_the_stored_effects_are_for_the_action_and_the_target_of_their_receipt(self):
        model = support.example_model()
        for receipt in model.of("C07"):
            for item in receipt.data["outcome"]["observed_effects"]:
                self.assertEqual(item["action_reference"], receipt.data["identity_binding"]["proposal_reference"])
                self.assertEqual(item["target"], receipt.data["identity_binding"]["target"])


class AnEffectIsForTheActionAndTheTargetOfItsReceipt(unittest.TestCase):
    def test_an_effect_of_another_action_than_the_proposal_of_its_receipt_is_found(self):
        other = {"contract_id": "C05", "id": "ACT-REL-0417", "version": "v1"}
        self.assertEqual(found(chain(effect(action_reference=other))), [("AUTH010", "c07-RCP-REL-0417-B-v2.json", E0 + "/action_reference")])

    def test_an_effect_on_another_target_than_the_target_of_its_receipt_is_found(self):
        self.assertEqual(found(chain(effect(target={"entity_type": "invoice", "entity_id": "INV-2026-9999"}))), [("AUTH010", "c07-RCP-REL-0417-B-v2.json", E0 + "/target")])

    def test_the_finding_names_both_actions(self):
        model = chain(effect(action_reference={"contract_id": "C05", "id": "ACT-REL-0417", "version": "v1"}))
        messages = [f.message for f in semantics.check_authority(model) if f.code == "AUTH010"]
        self.assertEqual(len(messages), 1)
        for part in ("ACT-REL-0417 v1", "ACT-REL-0417 v2", "EFF-REL-0417-B"):
            self.assertIn(part, messages[0])

    def test_an_effect_of_a_receipt_that_is_not_verified_is_held_to_the_same(self):
        def partial(data):
            data["outcome"]["state"] = "partial"
            data["outcome"]["unresolved_conditions"] = ["The remainder is not confirmed."]
            data["outcome"]["observed_effects"][0]["action_reference"]["version"] = "v1"
        self.assertEqual([code for code, _, _ in found(chain(partial), CODES)], ["AUTH010"])


class AVerifiedEffectIsNotRewrittenByALaterVersion(unittest.TestCase):
    def codes(self, *edits):
        return [(code, location) for code, _, location in found(chain(extra=repeat(*edits)))]

    def test_an_identical_terminal_repeat_is_valid(self):
        self.assertEqual(self.codes(), [])

    def test_a_later_terminal_version_that_changes_the_quantity_of_the_same_effect_is_found(self):
        self.assertEqual(self.codes(effect(quantity=18500)), [("ACC006", E0 + "/quantity")])

    def test_nor_may_it_change_the_unit_the_time_or_the_accounting_record(self):
        self.assertEqual(self.codes(effect(units="USD")), [("ACC006", E0 + "/units")])
        self.assertEqual(self.codes(effect(observed_at="2026-11-23T16:07:00.000001Z")), [("ACC006", E0 + "/observed_at")])
        self.assertEqual(self.codes(effect(accounting_reference={"record_id": "ACCT-CHARGE-OTHER", "version": "v1"})), [("ACC006", E0 + "/accounting_reference")])

    def test_nor_may_it_change_the_action_or_the_target_which_is_also_not_the_action_or_the_target_of_the_receipt(self):
        action = {"contract_id": "C05", "id": "ACT-REL-0417", "version": "v1"}
        self.assertEqual(self.codes(effect(action_reference=action)), [("ACC006", E0 + "/action_reference"), ("AUTH010", E0 + "/action_reference")])
        target = {"entity_type": "invoice", "entity_id": "INV-2026-9999"}
        self.assertEqual(self.codes(effect(target=target)), [("ACC006", E0 + "/target"), ("AUTH010", E0 + "/target")])

    def test_a_later_version_that_leaves_the_verified_effect_out_contradicts_it(self):
        self.assertEqual(self.codes(lambda data: effects_of(data, [])), [("ACC006", "/outcome/observed_effects")])

    def test_the_finding_names_the_effect_the_fact_and_the_version_that_verified_it(self):
        model = chain(extra=repeat(effect(quantity=18500)))
        messages = [f.message for f in semantics.check_authority(model) if f.code == "ACC006"]
        self.assertEqual(len(messages), 1)
        for part in ("EFF-REL-0417-B", "18400", "18500", "v2"):
            self.assertIn(part, messages[0])

    def test_the_same_instant_written_another_way_and_the_same_number_written_another_way_are_the_same_fact(self):
        self.assertEqual(self.codes(effect(observed_at="2026-11-23T17:07:00+01:00")), [])
        self.assertEqual(self.codes(effect(observed_at="2026-11-23T16:07:00.000Z")), [])
        self.assertEqual(self.codes(effect(quantity=18400.0)), [])

    def test_a_different_effect_is_neither_a_correction_nor_a_contradiction_of_the_verified_one(self):
        def another(data):
            extra = stored_effect()
            extra["effect_id"] = "EFF-REL-0417-B-FEE"
            extra["quantity"] = 12
            data["outcome"]["observed_effects"].append(extra)
        self.assertEqual(self.codes(another), [])

    def test_the_free_text_is_not_read(self):
        self.assertEqual(self.codes(effect(description="The payment was booked.")), [])
        self.assertEqual(self.codes(lambda data: data["verification_recovery"]["verification"].update(method="A different method, written differently")), [])

    def test_the_order_of_the_effects_does_not_matter(self):
        def two(data):
            extra = stored_effect()
            extra["effect_id"] = "EFF-OTHER"
            data["outcome"]["observed_effects"] = [extra, data["outcome"]["observed_effects"][0]]
        self.assertEqual([code for code, _, _ in found(chain(two, extra=repeat(two)))], [])

    def test_an_effect_that_a_receipt_that_was_not_yet_verified_states_may_still_change_when_it_is_verified(self):
        """The unknown version states no effect and the completed one does. A partial version may state an effect that the completed one corrects: only a verified effect is fixed."""
        def partial(data):
            data["outcome"]["state"] = "partial"
            data["outcome"]["unresolved_conditions"] = ["The remainder is not confirmed."]
            data["outcome"]["observed_effects"][0]["quantity"] = 6000
        self.assertEqual(found(chain(versions=("v2",), extra={"v1": ("v2", partial)})), [])

    def test_a_terminal_state_that_goes_back_is_still_the_finding_it_always_was(self):
        def unknown(data):
            data["outcome"]["state"] = "unknown"
        self.assertEqual([code for code, _, _ in found(chain(extra={"v3": ("v1", unknown)}))], ["ACC005"])

    def test_the_other_verified_state_has_no_effects_to_contradict(self):
        self.assertEqual(support.example_model().get("C07", "RCP-REL-0417-A", "v1").data["outcome"]["observed_effects"], [])


def with_cap(cap, per_action=None):
    def edit(model):
        base = model
        grant = base.get("C06", *GRANT)
        data = copy.deepcopy(grant.data)
        data["limits_lifecycle"]["cumulative_limits"][0]["quantity"] = cap
        if per_action is not None:
            data["limits_lifecycle"]["per_action_limits"][0]["quantity"] = per_action
        instances = dict(base.instances)
        instances[("C06",) + GRANT] = Instance("C06", GRANT[0], GRANT[1], data, grant.path)
        return Model(instances, base.registry, base.root)
    return edit


def second_attempt(model, at="2026-11-23T16:30:00Z"):
    """The decision on the same release under the same grant, after the receipt was written."""
    return evaluate_commit(model, model.get("C05", *RELEASE), model.get("C06", *GRANT), ts(at), ledger_from_receipts(model, ts(at)))


def counted(model, at="2026-11-23T16:30:00Z"):
    return [(e.receipt, e.state, e.units, e.quantity) for e in ledger_from_receipts(model, ts(at)) if e.receipt == B]


KEEP = object()


def verified(quantity=KEEP, **fields):
    def edit(data):
        if quantity is not KEEP:
            data["outcome"]["observed_effects"][0]["quantity"] = quantity
        for name, value in fields.items():
            data["outcome"]["observed_effects"][0][name] = value
    return edit


def partially(quantity, observed="2026-11-23T16:07:00Z", more=()):
    def edit(data):
        data["outcome"]["state"] = "partial"
        data["outcome"]["unresolved_conditions"] = ["The remainder is not confirmed."]
        data["verification_recovery"]["verification"]["state"] = "pending"
        data["outcome"]["observed_effects"][0].update(quantity=quantity, observed_at=observed)
        for extra in more:
            data["outcome"]["observed_effects"].append(extra)
    return edit


class AKnownEffectIsALowerBoundOfWhatAnAttemptHolds(unittest.TestCase):
    CAP = 36800

    def model(self, *edits, extra=None):
        return with_cap(self.CAP)(chain(*edits, extra=extra))

    def test_the_stored_receipts_count_what_the_proposal_states(self):
        model = support.example_model()
        self.assertEqual(counted(model, "2026-11-23T16:10:00Z"), [(B, "reserved", "EUR", 18400)])
        self.assertEqual(counted(model, "2026-11-23T16:30:00Z"), [(B, "consumed", "EUR", 18400)])

    def test_a_verified_effect_larger_than_the_amount_of_the_proposal_is_held_in_full(self):
        model = self.model(verified(18500))
        self.assertEqual(counted(model), [(B, "consumed", "EUR", 18500)])

    def test_a_second_action_that_would_fit_the_nominal_amount_but_not_the_known_effect_blocks(self):
        """The cap is 36,800: 18,400 held and 18,400 asked would just fit. 18,500 held does not."""
        self.assertNotIn("CUMULATIVE_LIMIT", second_attempt(self.model()).codes)
        decision = second_attempt(self.model(verified(18500)))
        self.assertIn("CUMULATIVE_LIMIT", decision.codes)
        self.assertFalse(decision.allow)

    def test_a_known_partial_effect_larger_than_the_reservation_is_held_in_full_and_stays_reserved(self):
        model = self.model(partially(20000))
        self.assertEqual(counted(model), [(B, "reserved", "EUR", 20000)])
        self.assertIn("CUMULATIVE_LIMIT", second_attempt(model).codes)

    def test_an_effect_that_equals_the_amount_changes_nothing(self):
        self.assertEqual(counted(self.model(verified(18400))), [(B, "consumed", "EUR", 18400)])

    def test_a_smaller_known_effect_does_not_release_the_conservative_reservation(self):
        for quantity in (12000, 0):
            with self.subTest(quantity):
                self.assertEqual(counted(self.model(verified(quantity))), [(B, "consumed", "EUR", 18400)])

    def test_a_reservation_before_the_effect_is_observed_is_the_nominal_amount(self):
        model = self.model(partially(20000))
        self.assertEqual(counted(model, "2026-11-23T16:06:59.999999Z"), [(B, "reserved", "EUR", 18400)])
        self.assertEqual(counted(model, "2026-11-23T16:07:00Z"), [(B, "reserved", "EUR", 20000)])

    def test_the_unknown_version_holds_the_nominal_amount_until_the_verified_one_is_available(self):
        model = self.model(verified(18500))
        self.assertEqual(counted(model, "2026-11-23T16:10:00Z"), [(B, "reserved", "EUR", 18400)])

    def test_effects_of_one_attempt_are_added_once_each(self):
        def second(effect_id, quantity):
            item = stored_effect()
            item.update(effect_id=effect_id, quantity=quantity)
            return item
        two = self.model(partially(10000, more=[second("EFF-OTHER", 9000)]))
        self.assertEqual(counted(two), [(B, "reserved", "EUR", 19000)])
        same_twice = self.model(partially(10000, more=[second("EFF-REL-0417-B", 10000)]))
        self.assertEqual(counted(same_twice), [(B, "reserved", "EUR", 18400)])

    def test_a_known_effect_stays_known_when_a_later_unresolved_version_no_longer_states_it(self):
        def silent(data):
            data["outcome"]["state"] = "partial"
            data["outcome"]["unresolved_conditions"] = ["The remainder is not confirmed."]
            data["verification_recovery"]["verification"]["state"] = "pending"
            data["outcome"]["observed_effects"] = []
        model = self.model(partially(20000), extra={"v3": ("v2", silent)})
        self.assertEqual(counted(model), [(B, "reserved", "EUR", 20000)])

    def test_an_effect_in_another_unit_is_not_combined_with_the_amount(self):
        model = self.model(verified(20000, units="USD"))
        self.assertEqual(counted(model), [(B, "consumed", "EUR", 18400)])
        self.assertNotIn("CUMULATIVE_LIMIT", second_attempt(model).codes)

    def test_an_effect_that_is_not_for_the_action_or_the_target_of_the_receipt_is_not_counted(self):
        elsewhere = {"contract_id": "C05", "id": "ACT-REL-0417", "version": "v1"}
        self.assertEqual(counted(self.model(verified(30000, action_reference=elsewhere))), [(B, "consumed", "EUR", 18400)])
        self.assertEqual(counted(self.model(verified(30000, target={"entity_type": "invoice", "entity_id": "INV-2026-9999"}))), [(B, "consumed", "EUR", 18400)])

    def test_an_effect_in_the_unit_of_the_limit_whose_quantity_cannot_be_read_cannot_be_shown_to_be_small(self):
        for unreadable in ("many", None, True, -5, float("nan")):
            with self.subTest(repr(unreadable)):
                model = self.model(verified(unreadable))
                self.assertEqual(counted(model)[0][3], float("inf"))
                self.assertIn("CUMULATIVE_LIMIT", second_attempt(model).codes)

    def test_an_effect_that_other_receipts_state_does_not_touch_the_allowance_of_this_grant(self):
        """The hold receipt states an effect of 1 hold. It is the hold grant's, and the payment grant's ledger does not hold it."""
        model = self.model(verified(18400))
        self.assertEqual({(e.grant_id, e.units) for e in ledger_from_receipts(model, ts("2026-11-23T16:30:00Z"))}, {("GRT-CLASS-HOLD", "holds"), ("GRT-APPR-0417-B", "EUR")})

    def test_the_stored_scenarios_keep_their_decisions(self):
        decision = second_attempt(support.example_model(), "2026-11-23T16:30:00Z")
        self.assertEqual(decision.codes, ["PRECONDITION_FAILED", "CUMULATIVE_LIMIT"])


if __name__ == "__main__":
    unittest.main()
