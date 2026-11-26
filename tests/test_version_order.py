"""Version names are exact, and the order of the versions of one record is never a guess.

The schema allows any non-empty version name. The reference reads the order of the versions of a record from the numbers in their names (v2 before v10, v1 before v1.1) and refuses to guess where
that does not give an order: two different names with the same numbers (v1 and v01) share one place, and a name with no number has none. Such a chain is a finding of the lifecycle check, a grant
whose versions cannot be put in order is not shown to be the one in force, a receipt whose versions cannot be put in order is counted conservatively, and nothing depends on the order in which the
records were read. A name is never changed: a record is found by its exact version.
"""
import copy
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

from eahs import semantics
from eahs.cases import mutate_model
from eahs.gateway import evaluate_commit, grant_in_force, ledger_from_receipts, regressive_receipt_versions, ts
from eahs.model import Instance, Model

HOLD, GRANT = ("ACT-HOLD-0417", "v1"), "GRT-CLASS-HOLD"
AT = "2026-11-23T10:03:00Z"
CHAIN = "C07 RCP-REL-0417-B"


def rep(target, path, value):
    return {"target": target, "ops": [{"op": "replace", "path": path, "value": value}]}


def grant_chain(*versions, replace_stored=False, reverse=False):
    """The example set with more versions of the hold grant: (name, issuance time, a function that edits the copy's data or None). The stored version stays unless `replace_stored`."""
    base = support.example_model()
    stored = base.get("C06", GRANT, "v1")
    instances = {key: inst for key, inst in base.instances.items() if not (replace_stored and key == ("C06", GRANT, "v1"))}
    for name, issued, edit in versions:
        data = copy.deepcopy(stored.data)
        data["identity_principals"]["version"] = name
        data["identity_principals"]["issuance_time"] = issued
        if edit:
            edit(data)
        instances[("C06", GRANT, name)] = Instance("C06", GRANT, name, data, stored.path)
    if reverse:
        instances = dict(reversed(list(instances.items())))
    return Model(instances, base.registry, base.root)


def decide(model, version, at=AT):
    return evaluate_commit(model, model.get("C05", *HOLD), model.get("C06", GRANT, version), ts(at), [])


def outcomes(model, versions, at=AT):
    return {version: (d.allow, tuple(d.codes)) for version in versions for d in [decide(model, version, at)]}


def receipt_chain(names):
    """The example set in which the receipt chain of the corrected release has these names: {new name: stored version whose data it carries}."""
    base = support.example_model()
    instances = {key: inst for key, inst in base.instances.items() if not (key[0] == "C07" and key[1] == "RCP-REL-0417-B")}
    for name, source in names.items():
        stored = base.get("C07", "RCP-REL-0417-B", source)
        data = copy.deepcopy(stored.data)
        data["identity_binding"]["version"] = name
        instances[("C07", "RCP-REL-0417-B", name)] = Instance("C07", "RCP-REL-0417-B", name, data, stored.path)
    return Model(instances, base.registry, base.root)


def held(model, at="2026-11-23T16:30:00Z"):
    return [(e.receipt, e.state, e.quantity) for e in ledger_from_receipts(model, ts(at)) if e.receipt == "RCP-REL-0417-B"]


def order_findings(model):
    return sorted((f.file.replace("\\", "/").rsplit("/", 1)[-1], f.location) for f in semantics.check_lifecycle(model) if f.code == "LIFE006")


class AnOrderableChainIsOrderedByTheNumbersInTheNames(unittest.TestCase):
    def test_the_stored_set_has_no_chain_that_cannot_be_ordered(self):
        self.assertEqual(order_findings(support.example_model()), [])

    def test_a_normal_chain_is_ordered_by_number_and_not_by_text(self):
        model = grant_chain(("v2", "2026-11-23T09:00:00Z", None), ("v10", "2026-11-23T09:30:00Z", None), ("v9", "2026-11-23T09:15:00Z", None))
        self.assertEqual(order_findings(model), [])
        decision = decide(model, "v9")
        self.assertEqual((decision.allow, decision.codes), (False, ["GRANT_SUPERSEDED"]))
        self.assertIn("v10", decision.reasons[0].message)
        self.assertEqual(decide(model, "v10").codes, [])

    def test_the_old_grant_is_valid_immediately_before_its_replacement_is_issued_and_blocked_from_then_on(self):
        model = grant_chain(("v2", "2026-11-23T10:02:00Z", None))
        self.assertEqual(decide(model, "v1", "2026-11-23T10:01:59.999999Z").codes, [])
        for at in ("2026-11-23T10:02:00Z", "2026-11-23T11:02:00+01:00", "2026-11-23T10:03:00Z"):
            with self.subTest(at):
                self.assertEqual(decide(model, "v1", at).codes, ["GRANT_SUPERSEDED"])

    def test_the_new_grant_applies_its_own_limits(self):
        def no_holds(data):
            data["limits_lifecycle"]["per_action_limits"][0]["quantity"] = 0
        model = grant_chain(("v2", "2026-11-23T10:02:00Z", no_holds))
        self.assertEqual(decide(model, "v2").codes, ["PER_ACTION_LIMIT"])
        self.assertEqual(decide(model, "v2", "2026-11-23T10:01:59.999999Z").codes[0], "GRANT_NOT_YET_VALID")

    def test_a_record_is_found_by_its_exact_version(self):
        model = grant_chain(("v01", "2026-11-23T09:00:00Z", None))
        for name in ("v1", "v01"):
            self.assertEqual(model.get("C06", GRANT, name).version, name)
        self.assertIsNone(model.get("C06", GRANT, "v001"))


class TwoNamesWithOneNumberAreOneAmbiguousChain(unittest.TestCase):
    """v1 and v01 are two versions with one place in the order. Which of them replaced the other cannot be told, and no insertion order, file order or spelling decides it."""

    def chain(self, reverse=False):
        return grant_chain(("v01", "2026-11-23T09:00:00Z", None), reverse=reverse)

    def test_the_older_grant_used_after_the_other_was_issued_is_not_in_force_in_either_order(self):
        for reverse in (False, True):
            for version in ("v1", "v01"):
                with self.subTest(reverse=reverse, version=version):
                    decision = decide(self.chain(reverse), version)
                    self.assertEqual((decision.allow, decision.codes), (False, ["GRANT_SUPERSEDED"]))

    def test_the_decision_is_the_same_in_every_order_of_the_records(self):
        self.assertEqual(outcomes(self.chain(False), ("v1", "v01")), outcomes(self.chain(True), ("v1", "v01")))

    def test_the_reason_says_that_the_versions_cannot_be_put_in_order(self):
        message = decide(self.chain(), "v1").reasons[0].message
        for part in ("v1", "v01", "order"):
            self.assertIn(part, message)

    def test_the_grant_in_force_is_not_picked_by_a_guess(self):
        with self.assertRaises(ValueError) as refused:
            grant_in_force(self.chain(), GRANT, ts(AT))
        self.assertIn("v01", str(refused.exception))

    def test_the_lifecycle_check_finds_both_names_where_they_stand(self):
        self.assertEqual(order_findings(self.chain()), [("c06-GRT-CLASS-HOLD-v1.json", "/identity_principals/version")] * 2)
        findings = [f for f in semantics.check_lifecycle(self.chain()) if f.code == "LIFE006"]
        self.assertTrue(any("v01" in f.message for f in findings) and any("v1" in f.message for f in findings))

    def test_a_chain_of_other_records_is_held_to_the_same_rule(self):
        """The rule is about every record with versions. The two summaries of the examples are two records, and two selections are two versions of one."""
        base = support.example_model()
        stored = base.get("C03", "SEL-0417", "v1")
        data = copy.deepcopy(stored.data)
        data["identity_scope"]["version"] = "v01"
        instances = dict(base.instances)
        instances[("C03", "SEL-0417", "v01")] = Instance("C03", "SEL-0417", "v01", data, stored.path)
        found = order_findings(Model(instances, base.registry, base.root))
        self.assertEqual([location for _, location in found], ["/identity_scope/version"] * 2)

    def test_other_pairs_with_one_number_are_the_same_chain_problem(self):
        for second in ("1", "V1", "v001", "ver-1", "v1-"):
            with self.subTest(second):
                self.assertEqual(len(order_findings(grant_chain((second, "2026-11-23T09:00:00Z", None)))), 2)

    def test_a_dotted_version_is_not_the_number_without_its_dot(self):
        """v1.2 and v12 are two places in the order, not one: nothing is made of the digits as one number."""
        self.assertEqual(order_findings(grant_chain(("v1.2", "2026-11-23T09:00:00Z", None), ("v12", "2026-11-23T09:30:00Z", None))), [])
        model = grant_chain(("v1.2", "2026-11-23T09:00:00Z", None), ("v12", "2026-11-23T09:30:00Z", None))
        self.assertEqual(decide(model, "v1.2").codes, ["GRANT_SUPERSEDED"])
        self.assertEqual(decide(model, "v12").codes, [])


class ANameWithNoNumberHasNoPlaceInTheOrder(unittest.TestCase):
    def test_a_grant_chain_with_such_a_name_is_not_shown_to_have_a_version_in_force(self):
        model = grant_chain(("latest", "2026-11-23T09:00:00Z", None))
        for version in ("v1", "latest"):
            with self.subTest(version):
                decision = decide(model, version)
                self.assertEqual((decision.allow, decision.codes), (False, ["GRANT_SUPERSEDED"]))
        self.assertEqual(order_findings(model), [("c06-GRT-CLASS-HOLD-v1.json", "/identity_principals/version")])

    def test_only_the_name_without_a_number_is_found(self):
        findings = [f for f in semantics.check_lifecycle(grant_chain(("latest", "2026-11-23T09:00:00Z", None))) if f.code == "LIFE006"]
        self.assertEqual(len(findings), 1)
        self.assertIn("latest", findings[0].message)
        self.assertIn("no number", findings[0].message)

    def test_a_digit_of_another_script_is_a_character_and_not_a_number(self):
        for name in ("v\u00b2", "v\u0662", "v\uff12"):
            with self.subTest(name):
                self.assertEqual(len(order_findings(grant_chain((name, "2026-11-23T09:00:00Z", None)))), 1)

    def test_a_record_that_is_the_only_version_needs_no_order(self):
        model = grant_chain(("latest", "2026-11-23T07:45:00Z", None), replace_stored=True)
        self.assertEqual(order_findings(model), [])
        self.assertEqual(decide(model, "latest").codes, [])


class TheVersionsOfAReceiptAreNotPickedByTheSpellingOfTheirNames(unittest.TestCase):
    """The corrected release has an unknown version and a completed one. Which of the names v02 and v2 carries which must not decide what the ledger holds."""

    A = {"v1": "v1", "v02": "v2", "v2": "v1"}    # the completed state is under v02, the unknown one under v2
    B = {"v1": "v1", "v02": "v1", "v2": "v2"}    # the other way round

    def test_the_stored_chain_is_ordered_and_replays_as_before(self):
        model = support.example_model()
        self.assertEqual(held(model, "2026-11-23T16:10:00Z"), [("RCP-REL-0417-B", "reserved", 18400)])
        self.assertEqual(held(model, "2026-11-23T16:30:00Z"), [("RCP-REL-0417-B", "consumed", 18400)])

    def test_the_ledger_does_not_depend_on_which_name_comes_first(self):
        self.assertEqual(held(receipt_chain(self.A)), held(receipt_chain(self.B)))

    def test_one_attempt_is_held_once_and_conservatively_while_its_versions_cannot_be_put_in_order(self):
        for names in (self.A, self.B):
            with self.subTest(names):
                self.assertEqual(held(receipt_chain(names)), [("RCP-REL-0417-B", "reserved", 18400)])

    def test_the_lifecycle_check_finds_both_names_that_share_a_place(self):
        for names in (self.A, self.B):
            with self.subTest(names):
                model = receipt_chain(names)
                self.assertEqual([location for _, location in order_findings(model)], ["/identity_binding/version"] * 2)
                messages = [f.message for f in semantics.check_lifecycle(model) if f.code == "LIFE006"]
                self.assertTrue(any("v02" in message for message in messages) and any("version v2 " in message for message in messages))

    def test_no_state_is_said_to_go_back_while_the_order_is_not_known(self):
        for names in (self.A, self.B):
            with self.subTest(names):
                model = receipt_chain(names)
                self.assertEqual(regressive_receipt_versions(model), [])
                self.assertEqual([f.code for f in semantics.check_authority(model) if f.code == "ACC005"], [])

    def test_the_authority_check_still_runs_on_the_other_receipts(self):
        model = receipt_chain(self.A)
        self.assertIsInstance(semantics.check_authority(model), list)

    def test_the_replay_of_the_stored_attempt_in_another_chain_is_not_changed_by_it(self):
        model = receipt_chain(self.A)
        self.assertEqual([(e.receipt, e.state) for e in ledger_from_receipts(model, ts("2026-11-23T16:30:00Z")) if e.receipt == "RCP-HOLD-0417"], [("RCP-HOLD-0417", "consumed")])


class AReplacementIsALaterVersionByTheNumbersInTheNames(unittest.TestCase):
    def superseded(self, name, replacement):
        base = support.example_model()
        old, new = base.get("C02", "GR-5521", "v1"), base.get("C02", "GR-5521", "v2")
        data = copy.deepcopy(old.data)
        data["identity_schema"]["version"] = name
        data["lifecycle"]["replacement_reference"] = {"record_id": "GR-5521", "version": replacement}
        data2 = copy.deepcopy(new.data)
        data2["identity_schema"]["version"] = replacement
        instances = {k: v for k, v in base.instances.items() if k[:2] != ("C02", "GR-5521")}
        instances[("C02", "GR-5521", name)] = Instance("C02", "GR-5521", name, data, old.path)
        instances[("C02", "GR-5521", replacement)] = Instance("C02", "GR-5521", replacement, data2, new.path)
        model = Model(instances, base.registry, base.root)
        return [f.code for f in semantics.check_lifecycle(model) if f.code in ("LIFE001", "LIFE006")]

    def test_a_replacement_must_be_later_and_the_numbers_decide(self):
        self.assertEqual(self.superseded("v9", "v10"), [])
        self.assertEqual(self.superseded("v1", "v2"), [])
        self.assertEqual(self.superseded("v10", "v9"), ["LIFE001"])

    def test_a_replacement_with_the_same_number_is_not_later_and_the_chain_is_ambiguous(self):
        found = self.superseded("v1", "v01")
        self.assertIn("LIFE001", found)
        self.assertEqual(found.count("LIFE006"), 2)


if __name__ == "__main__":
    unittest.main()
