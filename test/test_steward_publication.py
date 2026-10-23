"""Publication must fail closed if a required lifecycle effect is missing."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from checkpoint_steward_http import validate_lifecycle


class StewardPublication(unittest.TestCase):
    def setUp(self):
        self.state = {"entries": [{"status": "UNSOURCED"}] + [{"status": "ADMITTED", "stored_status": "ADMITTED"} for _ in range(4)],
                      "deferred": [], "solvency": {"balanced": True}}
        expired = copy.deepcopy(self.state)
        expired["entries"][1]["status"] = "EXPIRED"
        for i in (2, 3, 4):
            expired["entries"][i]["status"] = "TAINTED"
        self.history = [
            {"id": "expire-root", "after": expired, "transaction": {"method": "expire"}},
            {"id": "direct-rejudge-deep", "before": copy.deepcopy(expired), "after": self.state, "transaction": {"method": "rejudge"}},
            {"id": "rejudge-root", "after": self.state, "transaction": {"method": "rejudge"}},
            {"id": "deferred-clear-00", "after": self.state, "transaction": {"method": "process_deferred"}}]
        self.initial = [{"entry_id": 0, "status": "UNSOURCED", "claim": "same", "author": "writer", "source_url": "old"},
                        {"entry_id": 1, "status": "ADMITTED", "claim": "same", "author": "writer", "source_url": "new"}]
        self.initial += [{"entry_id": i, "supports": [i - 1]} for i in (2, 3, 4)]
        self.challenge = {"entry_id": 1, "outcome": "REJECTED"}

    def validate(self):
        return validate_lifecycle(self.history, self.initial, self.state, self.challenge)

    def test_complete_observed_effects(self):
        self.assertEqual(self.validate()["direct_unswept_rejudge"], "ADMITTED")

    def test_different_claim_is_not_a_correction(self):
        self.initial[1]["claim"] = "different"
        with self.assertRaisesRegex(ValueError, "same-claim"):
            self.validate()

    def test_still_trusted_deep_descendant_blocks_publication(self):
        self.history[0]["after"]["entries"][4]["status"] = "ADMITTED"
        with self.assertRaisesRegex(ValueError, "remained trusted"):
            self.validate()

    def test_missing_direct_rejudge_effect_blocks_publication(self):
        self.history[1]["after"] = copy.deepcopy(self.state)
        self.history[1]["after"]["entries"][4]["status"] = "TAINTED"
        with self.assertRaisesRegex(ValueError, "direct rejudge"):
            self.validate()

    def test_nonempty_queue_blocks_publication(self):
        self.state["deferred"] = [3]
        with self.assertRaisesRegex(ValueError, "completion"):
            self.validate()

    def test_unrelated_entries_are_not_a_deep_dependency_chain(self):
        self.initial[4]["supports"] = []
        with self.assertRaisesRegex(ValueError, "dependency chain"):
            self.validate()

    def test_different_challenge_outcome_is_not_relabelled(self):
        self.challenge["outcome"] = "UPHELD"
        with self.assertRaisesRegex(ValueError, "intended outcome"):
            self.validate()

    def test_unbalanced_liabilities_block_publication(self):
        self.state["solvency"]["balanced"] = False
        with self.assertRaisesRegex(ValueError, "solvency"):
            self.validate()


if __name__ == "__main__":
    unittest.main()
