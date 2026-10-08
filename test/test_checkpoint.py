"""Offline checks for honest incomplete checkpoints and provenance boundaries."""
from contextlib import ExitStack
import copy
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import collect_receipts as collector
import publish_checkpoint as checkpoint


class CheckpointTest(unittest.TestCase):
    def setUp(self):
        self.address, self.sender = "0x" + "aa" * 20, "0x" + "bb" * 20
        self.tx, self.pending_tx = "0x" + "11" * 32, "0x" + "22" * 32
        self.policy = {"min_rounds": 2, "write_bond": 1000, "challenge_bond": 2000, "cascade_depth": 3, "admit_ttl": 1000}
        self.seed = {"space": self.policy, "entries": [
            {"id": "honest-one", "class": "honest", "claim": "The registry lists ACME as active.", "source_url": "https://example.org/a"},
            {"id": "honest-two", "class": "honest", "claim": "The registry lists BETA as active.", "source_url": "https://example.org/b"}]}
        self.envelopes = [checkpoint.candidate_envelope(item, 0) for item in self.seed["entries"]]
        self.hashes = [collector.envtool.envelope_hash(item) for item in self.envelopes]
        self.manifest = [{"id": item["id"], "tx": tx, "address": self.address, "sender": self.sender, "envelope_hash": fingerprint, "consensus_max_rotations": 0}
                         for item, tx, fingerprint in zip(self.seed["entries"], [self.tx, self.pending_tx], self.hashes)]
        self.metadata = {"address": self.address, "chain_id": 4221, "deployment_tx": "0x" + "33" * 32, "protocol": {"initial_validators": 5, "max_rotations": 0}}
        excerpt = "The registry lists ACME as active."
        self.entry = {"entry_id": 0, "space_id": 0, "claim": self.envelopes[0]["claim"], "source_url": self.envelopes[0]["source_url"], "entry_class": "honest", "supports": [], "envelope_hash": self.hashes[0], "snapshot_hash": hashlib.sha256(excerpt.encode()).hexdigest(), "status": "ADMITTED", "votes": {"a": "yes", "b": "yes", "conflict": "none"}, "rounds": 2, "bond": 1000, "bond_state": "LOCKED", "admitted_at": 1}
        self.row = dict(self.entry, id="honest-one", tx=self.tx, envelope=self.envelopes[0], snapshot_verified=True, snapshot_excerpt=excerpt, snapshot_provenance={"trace_transaction_id": self.tx}, min_rounds=2)
        self.receipts = {self.tx: self.receipt(self.tx, 5, 1), self.pending_tx: self.receipt(self.pending_tx, 9, 0)}

    def receipt(self, tx, status, result):
        stored = {"id": tx, "status": status, "result": result, "recipient": self.address, "sender": self.sender, "numOfInitialValidators": "5", "initialRotations": "0"}
        return {"status_basis": "getTransactionAllData", "consensus_version": "2.0.0", "stored_receipt": stored, "recipient": self.address, "sender": self.sender, "statusName": "ACCEPTED", "resultName": "MAJORITY_AGREE", "numOfInitialValidators": "5", "numOfRounds": "3", "currentTimestamp": "123", "lastRound": {"round": "3", "votesCommitted": "11", "votesRevealed": "10"}, "stored_block": {"number": "10", "timestamp": "123"}, "projected_receipt": {"statusName": "ACCEPTED"}}

    def test_unverified_runtime_version_cannot_publish_checkpoint(self):
        for version in (None, "0.6.0"):
            self.receipts[self.tx]["consensus_version"] = version
            with self.assertRaisesRegex(ValueError, "verified consensus version"):
                self.build()

    def build(self, rows=None, history=None):
        def read_call(endpoint, address, method, args, timeout):
            return {"get_space": self.policy, "entry_count": 1, "solvency": {"balanced": True}, "report": {"entries": 1, "honest_attempts": 1, "classes": [{"class": "honest", "attempts": 1}]}}[method]
        with ExitStack() as stack:
            stack.enter_context(patch.object(collector, "read_call", side_effect=read_call))
            stack.enter_context(patch.object(collector, "scan_entries", return_value=({self.hashes[0]: self.entry}, [])))
            stack.enter_context(patch.object(collector, "read_entry", return_value=self.entry))
            stack.enter_context(patch.object(collector, "lookup_receipt", side_effect=lambda explorer, endpoint, tx, timeout: self.receipts[tx]))
            return checkpoint.build_checkpoint(self.seed, self.metadata, self.manifest, [self.row] if rows is None else rows, history or [], [])

    def test_appeal_remains_unresolved_without_defence_conclusion(self):
        result = self.build()
        self.assertFalse(result["complete"])
        self.assertIsNone(result["defence_conclusion"])
        self.assertEqual(result["coverage"]["judged"], 1)
        self.assertEqual(result["coverage"]["unresolved"], 1)
        self.assertEqual(result["infrastructure_failures"], [])
        self.assertEqual(result["pending"][0]["status"], "APPEAL_REVEALING")

    def test_only_finalized_timeout_is_failure_and_history_survives(self):
        self.receipts[self.pending_tx] = self.receipt(self.pending_tx, 7, 3)
        history = [{"id": "honest-two", "tx": self.pending_tx, "envelope_hash": self.hashes[1], "entry_class": "honest", "status": "VALIDATORS_TIMEOUT", "reason": "original capture"}]
        result = self.build(history=history)
        self.assertEqual(result["infrastructure_failures"][0]["status"], "FINALIZED")
        self.assertEqual(result["infrastructure_history"][0]["reason"], "original capture")
        self.receipts[self.pending_tx] = self.receipt(self.pending_tx, 11, 3)
        self.assertEqual(self.build(history=history)["infrastructure_failures"], [])

    def test_foreign_deployment_and_rotation_policy_are_rejected(self):
        self.manifest[0]["address"] = "0x" + "cc" * 20
        with self.assertRaisesRegex(ValueError, "another deployment"):
            self.build()
        self.manifest[0]["address"] = self.address
        self.manifest[0]["consensus_max_rotations"] = 3
        with self.assertRaisesRegex(ValueError, "rotation limit"):
            self.build()

    def test_stale_projected_acceptance_cannot_publish_a_record(self):
        self.receipts[self.tx] = self.receipt(self.tx, 13, 0)
        with self.assertRaisesRegex(ValueError, "accepted stored consensus"):
            self.build()

    def test_tampered_snapshot_and_foreign_trace_are_rejected(self):
        row = dict(self.row, snapshot_excerpt="different bytes")
        with self.assertRaisesRegex(ValueError, "do not reproduce"):
            self.build(rows=[row])
        row = dict(self.row, snapshot_provenance={"trace_transaction_id": self.pending_tx})
        with self.assertRaisesRegex(ValueError, "another transaction"):
            self.build(rows=[row])

    def test_conflicting_round_answers_are_not_discarded(self):
        self.entry.update(status="INCONCLUSIVE", votes={"a": "yes", "b": "no", "conflict": "none"}, admitted_at=0)
        row = dict(self.row, **self.entry, rounds_detail={"support_a": False, "support_b": True, "conflict": -1, "fetched": True})
        with self.assertRaisesRegex(ValueError, "round answers disagree"):
            self.build(rows=[row])

    def test_recovered_history_is_retained_but_not_counted_as_failure(self):
        history = [{"id": "honest-one", "tx": self.tx, "envelope_hash": self.hashes[0], "entry_class": "honest", "status": "VALIDATORS_TIMEOUT", "reason": "earlier timeout"}]
        result = self.build(history=history)
        self.assertEqual(result["coverage"]["judged"], 1)
        self.assertEqual(result["infrastructure_failures"], [])
        self.assertEqual(result["infrastructure_history"][0]["status"], "VALIDATORS_TIMEOUT")


if __name__ == "__main__":
    unittest.main()
