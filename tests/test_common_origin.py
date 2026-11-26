"""Records that wrap the same immutable source record share one origin.

Agreement between records is not independent corroboration when the records rest on one origin. A source record assertion with no parent is a root, and what it was taken from is declared
in `original_source`: the source system, the locator of the record in it, and one immutable version (an original version or an immutable snapshot). Two such records with the same declared
source, locator and version are one origin, whatever their C02 identities are. Nothing is matched loosely: a different locator, or a different version, is a different origin, and a root that is
not a source record assertion is counted by its own record.
"""
import copy
import unittest

import support  # noqa: F401  (puts scripts/ on the path)

from eahs import semantics
from eahs.cases import mutate_model
from eahs.model import Instance, Model

ALIAS = "GR-5521-ALIAS"
SNAPSHOT = {"record_id": "SNAP-WMS-5521", "version": "v1"}
COMMON = ("COR001", "COR002")


def rep(target, path, value):
    return {"target": target, "ops": [{"op": "replace", "path": path, "value": value}]}


def alias_model(source=("C02", "GR-5521", "v1"), alias_id=ALIAS, edit_alias=None, mutations=()):
    """The example set with one more C02 record: a copy of `source` that has another identity, with `edit_alias` applied to the copy."""
    base, _ = mutate_model(support.example_model(), list(mutations))
    original = base.get(*source)
    data = copy.deepcopy(original.data)
    data["identity_schema"]["record_id"] = alias_id
    if edit_alias:
        edit_alias(data)
    instances = dict(base.instances)
    instances[("C02", alias_id, source[2])] = Instance("C02", alias_id, source[2], data, original.path)
    return Model(instances, base.registry, base.root)


def re_source(**fields):
    """An edit of the declared source of a record: the fields given replace those that are there, and a field given as None is removed."""
    def edit(data):
        for name, value in fields.items():
            if value is None:
                data["original_source"].pop(name, None)
            else:
                data["original_source"][name] = value
    return edit


def rest_on_alias(inference_index=1):
    """The mutation after which the second summary rests on the alias of the receipt, and the first one on the receipt."""
    return rep("C02 SUM-B-0417 v1", "/lineage/parent_references", [{"record_id": ALIAS, "version": "v1"}])


def corroboration(model, packet=("C04", "PKT-0417", "v1")):
    pkt = model.get(*packet)
    return sorted((f.code, f.location) for f in semantics._check_corroboration(model, pkt))


def without_common_origin(index=0):
    return rep("C04 PKT-0417 v1", "/labeled_inferences/%d/limitations" % index, ["Model output; not verified against any source."])


def independent(refs, index=0):
    """A mutation after which one inference says that its sources corroborate each other independently, and cites `refs` (record id and version pairs) as the sources."""
    stored = support.example_model().get("C04", "PKT-0417", "v1").data["labeled_inferences"][index]["supporting_references"][0]
    cited = []
    for record_id, version in refs:
        ref = copy.deepcopy(stored)
        ref.update(record_id=record_id, version=version)
        cited.append(ref)
    return [rep("C04 PKT-0417 v1", "/labeled_inferences/%d/text" % index, "Independently corroborated: two records agree."),
            rep("C04 PKT-0417 v1", "/labeled_inferences/%d/supporting_references" % index, cited)]


class TheStoredExamplesBehaveAsBefore(unittest.TestCase):
    def test_the_two_summaries_share_the_origin_of_the_receipt_and_say_so(self):
        model = support.example_model()
        self.assertEqual(corroboration(model), [])
        self.assertEqual(corroboration(model, ("C04", "PKT-0417", "v2")), [])

    def test_two_summaries_of_one_record_that_do_not_say_so_are_found_as_they_always_were(self):
        mutated, _ = mutate_model(support.example_model(), [without_common_origin()])
        self.assertEqual([code for code, _ in corroboration(mutated)], ["COR002"])

    def test_a_claim_that_cites_one_record_twice_is_not_independent_corroboration(self):
        mutated, _ = mutate_model(support.example_model(), independent([("GR-5521", "v1"), ("GR-5521", "v1")]))
        self.assertEqual([code for code, _ in corroboration(mutated)], ["COR001"])


class TwoRecordsThatWrapOneSourceRecordAreOneOrigin(unittest.TestCase):
    def test_summaries_resting_on_two_wrappers_of_one_source_record_must_say_that_they_share_the_origin(self):
        model = alias_model(mutations=[rest_on_alias(), without_common_origin()])
        self.assertEqual([code for code, _ in corroboration(model)], ["COR002"])

    def test_the_stored_wording_is_enough_for_the_two_wrappers_as_it_is_for_one(self):
        self.assertEqual(corroboration(alias_model(mutations=[rest_on_alias()])), [])

    def test_two_wrappers_that_wrap_one_source_record_do_not_corroborate_each_other(self):
        model = alias_model(mutations=independent([("GR-5521", "v1"), (ALIAS, "v1")]))
        self.assertEqual([code for code, _ in corroboration(model)], ["COR001"])

    def test_the_same_holds_when_the_source_is_pinned_by_an_immutable_snapshot_instead_of_a_version(self):
        pinned = re_source(original_version=None, immutable_snapshot_reference=SNAPSHOT)
        original = rep("C02 GR-5521 v1", "/original_source", {"source_id": "src:wms-receiving", "record_locator": "wms:receipt/5521", "immutable_snapshot_reference": SNAPSHOT})
        model = alias_model(edit_alias=pinned, mutations=[original, *independent([("GR-5521", "v1"), (ALIAS, "v1")])])
        self.assertEqual([code for code, _ in corroboration(model)], ["COR001"])

    def test_the_finding_says_which_source_record_the_wrappers_share(self):
        model = alias_model(mutations=independent([("GR-5521", "v1"), (ALIAS, "v1")]))
        messages = [f.message for f in semantics._check_corroboration(model, model.get("C04", "PKT-0417", "v1")) if f.code == "COR001"]
        self.assertEqual(len(messages), 1)
        for part in ("src:wms-receiving", "wms:receipt/5521", "rev-1", "GR-5521 v1", ALIAS):
            self.assertIn(part, messages[0])

    def test_the_origins_of_a_record_are_the_declared_identities_of_its_roots(self):
        model = alias_model()
        found = semantics.origins(model, model.get("C02", "SUM-A-0417", "v1"))
        self.assertEqual(len(found), 1)
        (identity, wrappers), = found.items()
        self.assertEqual(identity, ("source", "src:wms-receiving", "wms:receipt/5521", "original_version", "rev-1"))
        self.assertEqual([(r.id, r.version) for r in wrappers], [("GR-5521", "v1")])
        again = semantics.origins(model, model.get("C02", ALIAS, "v1"))
        self.assertEqual(set(again), set(found))


class WhatIsNotTheSameDeclaredSourceStaysDistinct(unittest.TestCase):
    def independent_pair(self, edit_alias=None, mutations=()):
        model = alias_model(edit_alias=edit_alias, mutations=[*independent([("GR-5521", "v1"), (ALIAS, "v1")]), *mutations])
        return [code for code, _ in corroboration(model)]

    def test_another_record_in_the_same_source_system_is_another_origin(self):
        self.assertEqual(self.independent_pair(re_source(record_locator="wms:receipt/5522")), [])

    def test_another_version_of_the_same_source_record_is_another_origin(self):
        self.assertEqual(self.independent_pair(re_source(original_version="rev-2")), [])

    def test_another_source_system_is_another_origin(self):
        self.assertEqual(self.independent_pair(re_source(source_id="src:wms-receiving-eu")), [])

    def test_a_version_and_a_snapshot_are_not_matched_with_each_other(self):
        self.assertEqual(self.independent_pair(re_source(original_version=None, immutable_snapshot_reference=SNAPSHOT)), [])

    def test_two_snapshots_are_the_same_origin_only_when_they_name_the_same_record_and_version(self):
        original = rep("C02 GR-5521 v1", "/original_source", {"source_id": "src:wms-receiving", "record_locator": "wms:receipt/5521", "immutable_snapshot_reference": SNAPSHOT})
        other = re_source(original_version=None, immutable_snapshot_reference={"record_id": "SNAP-WMS-5521", "version": "v2"})
        self.assertEqual(self.independent_pair(other, [original]), [])

    def test_the_summaries_of_two_distinct_origins_need_not_say_that_they_share_one(self):
        model = alias_model(edit_alias=re_source(record_locator="wms:receipt/5522"), mutations=[rest_on_alias(), without_common_origin()])
        self.assertEqual(corroboration(model), [])

    def test_a_root_that_is_not_a_source_record_assertion_is_counted_by_its_own_record(self):
        """The screening is a deterministic finding of a producer that computes over data outside the records. A copy that declares the same source is another record, as before."""
        model = alias_model(source=("C02", "SCR-S1042", "v1"), alias_id="SCR-ALIAS")
        a, b = (model.get("C02", record_id, "v1") for record_id in ("SCR-S1042", "SCR-ALIAS"))
        self.assertEqual(a.data["original_source"], b.data["original_source"])
        self.assertEqual(a.data["identity_schema"]["kind"], "deterministic_finding")
        self.assertEqual(semantics.origins(model, a).keys() & semantics.origins(model, b).keys(), set())

    def test_a_declared_source_that_does_not_pin_a_version_is_counted_by_its_own_record(self):
        """Nothing is guessed. A record whose source names no original version and no snapshot cannot be shown to wrap the same record as another."""
        def unpinned(data):
            data["original_source"].pop("original_version", None)
        model = alias_model(edit_alias=unpinned, mutations=[rep("C02 GR-5521 v1", "/original_source", {"source_id": "src:wms-receiving", "record_locator": "wms:receipt/5521"})])
        a, b = (model.get("C02", record_id, "v1") for record_id in ("GR-5521", ALIAS))
        self.assertEqual(semantics.origins(model, a).keys() & semantics.origins(model, b).keys(), set())


if __name__ == "__main__":
    unittest.main()
