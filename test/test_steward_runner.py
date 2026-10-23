"""A provisional protocol timeout must not trigger a new paid intent."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from steward_live import Campaign


def receipt(status, result=0, execution=0):
    code = {"LEADER_TIMEOUT": 13, "REVEALING": 4, "VALIDATORS_TIMEOUT": 12, "ACCEPTED": 5, "FINALIZED": 7}[status]
    return {"statusName": status, "consensus_version": "2.0.0",
            "stored_receipt": {"status": code, "result": result, "txExecutionResult": execution}}


class StewardRunner(unittest.TestCase):
    def test_leader_replacement_and_validator_timeout_resume_same_id(self):
        history = [receipt("LEADER_TIMEOUT"), receipt("REVEALING"),
                   receipt("VALIDATORS_TIMEOUT"), receipt("ACCEPTED", 1, 1)]
        with tempfile.TemporaryDirectory() as directory, \
             patch("steward_live.collector.lookup_receipt", side_effect=history) as lookup, \
             patch("steward_live.time.sleep"), \
             patch.object(Campaign, "send", side_effect=AssertionError("unexpected write")):
            result = Campaign(Path(directory)).wait({"id": "original", "tx": "0x" + "11" * 32})
        self.assertEqual(result, history[-1])
        self.assertEqual(lookup.call_count, 4)
        self.assertEqual(len({call.args[2] for call in lookup.call_args_list}), 1)

    def test_accepted_application_error_stops_without_waiting_or_resending(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch("steward_live.collector.lookup_receipt", return_value=receipt("ACCEPTED", 1, 2)), \
             patch("steward_live.time.sleep", side_effect=AssertionError("unexpected wait")):
            with self.assertRaisesRegex(RuntimeError, "application execution error"):
                Campaign(Path(directory)).wait({"id": "original", "tx": "0x" + "11" * 32})

    def test_finalized_timeout_is_not_a_successful_application_call(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch("steward_live.collector.lookup_receipt", return_value=receipt("FINALIZED", 3, 1)):
            with self.assertRaisesRegex(RuntimeError, "did not establish successful application execution"):
                Campaign(Path(directory)).wait({"id": "original", "tx": "0x" + "11" * 32})


if __name__ == "__main__":
    unittest.main()
