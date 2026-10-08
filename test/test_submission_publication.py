"""Saved-source engineering guard fixtures: no network, signer, models or live data."""
from collections import Counter
from contextlib import ExitStack, redirect_stdout
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import collect_receipts as collector
import publish_live as publisher
import run_live as runner


class SubmissionPublicationTest(unittest.TestCase):
    def setUp(self):
        self.address, self.sender = "0x" + "aa" * 20, "0x" + "bb" * 20
        self.policy = {"min_rounds": 2, "write_bond": 1000, "challenge_bond": 2000, "cascade_depth": 3, "admit_ttl": 1000}
        self.seed = {"space": self.policy, "entries": []}
        self.rows, self.manifest, self.history, self.refused = [], [], [], []
        self.entries, self.receipts = {}, {}
        for index in range(20):
            self.add_candidate("honest-" + str(index), "honest", judged=True)
        self.add_candidate("unsupported", "source_forgery", judged=True)
        citation = self.add_candidate("impossible-citation", "citation_laundering", submitted=False, supports=[999999])
        self.refused.append({"id": citation["id"], "class": citation["class"], "envelope_hash": self.fingerprint(citation),
                             "refused_at": "write", "reason": "supports names an entry that does not exist", "consensus_rounds_spent": 0})
        self.metadata = {"address": self.address, "chain_id": 4221, "deployment_tx": "0x" + "cc" * 32,
                         "source_sha256": hashlib.sha256((ROOT / "contracts/hearsay.py").read_bytes()).hexdigest(),
                         "deployment_source_sha256": "2125f18b442bface1d2538563ff9d4fb40bb6e3f690ff8b42a3d5916ffece97c",
                         "protocol": {"initial_validators": 5, "max_rotations": 3}}

    def envelope(self, candidate):
        result = {"version": "hearsay/1", "space_id": 0, "entry_class": candidate["class"],
                  "claim": candidate["claim"], "source_url": candidate["source_url"]}
        if candidate.get("supports"):
            result["supports"] = candidate["supports"]
        return result

    def fingerprint(self, candidate):
        return collector.envtool.envelope_hash(self.envelope(candidate))

    def add_candidate(self, name, klass, *, judged=False, submitted=True, supports=None):
        index = len(self.seed["entries"])
        candidate = {"id": name, "class": klass, "claim": "Fixture company %d is active." % index,
                     "source_url": "https://example.org/fixture/" + str(index)}
        if supports:
            candidate["supports"] = supports
        self.seed["entries"].append(candidate)
        if not submitted:
            return candidate
        envelope, fingerprint = self.envelope(candidate), self.fingerprint(candidate)
        tx = "0x" + format(index + 1, "064x")
        self.manifest.append({"id": name, "tx": tx, "address": self.address, "sender": self.sender,
                              "envelope_hash": fingerprint, "consensus_max_rotations": 3})
        stored = {"id": tx, "status": 5 if judged else 9, "result": 1 if judged else 0,
                  "txExecutionResult": 1 if judged else 0, "recipient": self.address, "sender": self.sender,
                  "numOfInitialValidators": "5", "initialRotations": "3"}
        self.receipts[tx] = {"status_basis": "getTransactionAllData", "consensus_version": "2.0.0", "stored_receipt": stored,
                             "recipient": self.address, "sender": self.sender, "statusName": "ACCEPTED",
                             "resultName": "MAJORITY_AGREE", "txExecutionResultName": "FINISHED_WITH_RETURN",
                             "currentTimestamp": "123", "stored_block": {"number": "10", "timestamp": "123"}}
        if judged:
            supported = klass == "honest"
            excerpt = "Dummy source bytes for engineering fixture " + name
            entry = {"entry_id": len(self.entries), "space_id": 0, "entry_class": klass,
                     "claim": candidate["claim"], "source_url": candidate["source_url"], "supports": [],
                     "envelope_hash": fingerprint, "snapshot_hash": hashlib.sha256(excerpt.encode()).hexdigest(),
                     "status": "ADMITTED" if supported else "UNSOURCED",
                     "votes": {"a": "yes" if supported else "no", "b": "yes" if supported else "no", "conflict": "none"},
                     "rounds": 2, "bond": 1000, "bond_state": "LOCKED" if supported else "SLASHED",
                     "admitted_at": index + 1 if supported else 0}
            self.entries[fingerprint] = entry
            self.rows.append(dict(entry, id=name, tx=tx, envelope=envelope, snapshot_verified=True,
                                  snapshot_excerpt=excerpt, snapshot_provenance={"trace_transaction_id": tx}, min_rounds=2))
        return candidate

    def publish(self, expected_error=None, receipt_override=None):
        with tempfile.TemporaryDirectory(prefix="hearsay-submission-publication-") as temporary:
            folder = Path(temporary)
            for name, data in (("seed.json", self.seed), ("deployment.json", self.metadata),
                               ("live/infrastructure-failures.json", self.history), ("live/refused.json", self.refused)):
                path = folder / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data))
            for name, rows in (("bradbury.jsonl", self.manifest), ("verified-records.jsonl", self.rows)):
                (folder / name).write_text("".join(json.dumps(row) + "\n" for row in rows))
            counts = Counter(entry["entry_class"] for entry in self.entries.values())
            honest = [entry for entry in self.entries.values() if entry["entry_class"] == "honest"]
            report = {"entries": len(self.entries), "honest_attempts": len(honest),
                      "honest_admitted": sum(entry["status"] == "ADMITTED" for entry in honest),
                      "false_rejection_milli": 0, "classes": [{"class": name, "attempts": count} for name, count in sorted(counts.items())]}
            def read_call(endpoint, address, method, args, timeout):
                self.assertEqual(address, self.address)
                return {"get_space": self.policy, "report": report, "solvency": {"balanced": True}, "entry_count": len(self.entries)}[method]
            def receipt(explorer, endpoint, tx, timeout):
                return receipt_override(tx) if receipt_override else self.receipts[tx]
            argv = ["publish_live.py", "--address", self.address, "--run-dir", str(folder), "--seed", str(folder / "seed.json"),
                    "--records", str(folder / "verified-records.jsonl"), "--deployment", str(folder / "deployment.json")]
            with ExitStack() as stack:
                for context in (patch.object(sys, "argv", argv), patch.object(collector, "ROOT", folder),
                                patch.object(collector, "read_call", side_effect=read_call),
                                patch.object(collector, "scan_entries", return_value=(self.entries, [])),
                                patch.object(collector, "read_entry", side_effect=lambda endpoint, address, eid, timeout: next(entry for entry in self.entries.values() if entry["entry_id"] == eid)),
                                patch.object(collector, "lookup_receipt", side_effect=receipt),
                                patch.object(publisher, "build_page", return_value="<html>Engineering fixture only</html>"),
                                redirect_stdout(io.StringIO())):
                    stack.enter_context(context)
                if expected_error:
                    with self.assertRaisesRegex(ValueError, expected_error):
                        publisher.main()
                else:
                    publisher.main()
            if expected_error:
                self.assertFalse((folder / "web/live-corpus.json").exists())
                self.assertFalse((folder / "web/live.html").exists())
                return None
            return json.loads((folder / "web/live-corpus.json").read_text())

    def test_complete_current_fixture_has_twenty_honest_and_construction_only_citation(self):
        published = self.publish()
        self.assertEqual(published["report"]["honest_attempts"], 20)
        self.assertEqual(len(published["entries"]), 21)
        self.assertEqual(published["refused_at_write"][0]["consensus_rounds_spent"], 0)
        self.assertEqual(published["report"]["classes"], [{"class": "honest", "attempts": 20}, {"class": "source_forgery", "attempts": 1}])
        self.assertIn("provisional", published["health_warning"])

    def test_omitted_manifest_attempt_cannot_disappear_from_declared_seed(self):
        candidate = self.add_candidate("hidden-attempt", "honest")
        self.seed["entries"].remove(candidate)
        self.publish("manifest differs from seed")

    def test_record_transaction_must_be_in_full_manifest(self):
        self.rows[0]["tx"] = "0x" + "ee" * 32
        self.publish("absent from this deployment manifest")

    def test_manifest_recipient_cannot_belong_to_foreign_contract(self):
        self.manifest[0]["address"] = "0x" + "ee" * 20
        self.publish("another deployment")

    def test_stored_id_sender_recipient_bind_to_manifest(self):
        for field, value, error in (("id", "0x" + "ee" * 32, "transaction ID mismatch"),
                                    ("sender", "0x" + "ee" * 20, "sender mismatch"),
                                    ("recipient", "0x" + "ee" * 20, "another deployment")):
            with self.subTest(field=field):
                stored = self.receipts[self.rows[0]["tx"]]["stored_receipt"]
                original = stored[field]
                stored[field] = value
                self.publish(error)
                stored[field] = original

    def test_current_provisional_state_rollback_is_rejected(self):
        self.entries[self.rows[0]["envelope_hash"]] = dict(self.entries[self.rows[0]["envelope_hash"]], bond_state="SLASHED")
        self.publish("current entry changed or disappeared")

    def test_projected_acceptance_cannot_hide_reopened_stored_receipt(self):
        self.receipts[self.rows[0]["tx"]]["stored_receipt"]["status"] = 9
        self.publish("accepted stored consensus")

    def test_successful_execution_cannot_be_replaced_by_idle_or_failed_execution(self):
        stored = self.receipts[self.rows[0]["tx"]]["stored_receipt"]
        for field in ("result", "txExecutionResult"):
            with self.subTest(field=field):
                stored[field] = 0
                self.publish("accepted stored consensus")
                stored[field] = 1

    def test_snapshot_bytes_and_trace_provenance_are_bound(self):
        original = copy.deepcopy(self.rows[0])
        for field, value, error in (("snapshot_excerpt", "tampered dummy bytes", "unreproducible record"),
                                    ("snapshot_provenance", {"trace_transaction_id": self.rows[1]["tx"]}, "another transaction"),
                                    ("snapshot_provenance", {"source": "getTransactionAllData.eqBlocksOutputs", "transaction_id": original["tx"], "eq_block_index": 1, "stored_block": {"number": "10"}}, "invalid stored equivalence")):
            with self.subTest(field=field, value=value):
                self.rows[0][field] = value
                self.publish(error)
                self.rows[0] = copy.deepcopy(original)

    def test_round_detail_cannot_override_actual_stored_votes(self):
        self.rows[0]["rounds_detail"] = {"support_a": True, "support_b": True, "conflict": -1, "fetched": False}
        self.publish("unreproducible record|round answers disagree")

    def test_current_unresolved_attempt_blocks_full_publication(self):
        candidate = self.add_candidate("old-timeout-reopened", "flooding")
        self.history.append(dict(self.manifest[-1], entry_class=candidate["class"], status="VALIDATORS_TIMEOUT", reason="Old capture retained"))
        self.publish("unresolved or unsubmitted")

    def test_unsubmitted_candidate_blocks_full_publication(self):
        self.add_candidate("unsubmitted", "honest", submitted=False)
        self.publish("live run is incomplete")

    def test_missing_honest_control_cannot_lower_twenty_judgement_floor(self):
        row = self.rows.pop(0)
        self.entries.pop(row["envelope_hash"])
        self.seed["entries"] = [candidate for candidate in self.seed["entries"] if candidate["id"] != row["id"]]
        self.manifest = [transaction for transaction in self.manifest if transaction["tx"] != row["tx"]]
        self.publish("honest control group incomplete")


class SubmissionRunnerTest(unittest.TestCase):
    def test_original_nine_independent_inputs_keep_progress_guard(self):
        seed = json.loads((ROOT / "corpus/live.json").read_text())
        cases = [candidate for candidate in seed["entries"] if candidate["class"] != "honest" and not candidate.get("supports")]
        self.assertEqual(len(cases), 9)
        for candidate in cases:
            with self.subTest(candidate=candidate["id"]), tempfile.TemporaryDirectory(prefix="hearsay-submission-runner-") as temporary:
                folder = Path(temporary)
                address, account, tx = "0x" + "aa" * 20, "0x" + "bb" * 20, "0x" + "11" * 32
                (folder / "live").mkdir()
                (folder / "seed.json").write_text(json.dumps({"space": seed["space"], "entries": [candidate]}))
                (folder / "bradbury.jsonl").write_text(json.dumps({"tx": tx, "address": address, "envelope_hash": "old", "consensus_max_rotations": 3}) + "\n")
                (folder / "live/unresolved.json").write_text(json.dumps([{"tx": tx}]))
                argv = ["run_live.py", "--address", address, "--account", account, "--seed", str(folder / "seed.json"), "--run-dir", str(folder), "--allow-known-unsettled-progress"]
                captured = []
                def process(command, **kwargs):
                    self.assertIn("genlayer_write.mjs", command[1])
                    captured.append(json.loads((folder / "live/request.json").read_text()))
                    return runner.subprocess.CompletedProcess(command, 1, "", "Intentional fixture stop; no SDK process started")
                with patch.object(sys, "argv", argv), patch.object(collector, "read_call", side_effect=lambda endpoint, addr, method, args, timeout: 20 if method == "entry_count" else dict(seed["space"], owner=account)), patch.object(runner, "prepare_progress_guard", return_value={"transactions": [tx], "scan_complete": True, "solvency_balanced": True}), patch.object(runner.subprocess, "run", side_effect=process):
                    with self.assertRaisesRegex(RuntimeError, "write failed"):
                        runner.main()
                self.assertEqual(len(captured), 1)
                self.assertEqual(captured[0]["args"][1], candidate["class"])
                self.assertEqual(captured[0]["progress_guard"]["transactions"], [tx])
                self.assertFalse(json.loads(captured[0]["args"][2]).get("supports"))

    def test_impossible_citation_is_not_sent_or_counted_as_judged(self):
        seed = json.loads((ROOT / "corpus/live.json").read_text())
        candidate = next(candidate for candidate in seed["entries"] if candidate["id"] == "laundering")
        with tempfile.TemporaryDirectory(prefix="hearsay-submission-citation-") as temporary:
            folder = Path(temporary)
            address, account = "0x" + "aa" * 20, "0x" + "bb" * 20
            (folder / "seed.json").write_text(json.dumps({"space": seed["space"], "entries": [candidate]}))
            argv = ["run_live.py", "--address", address, "--account", account, "--seed", str(folder / "seed.json"), "--run-dir", str(folder), "--allow-known-unsettled-progress"]
            with patch.object(sys, "argv", argv), patch.object(collector, "read_call", side_effect=lambda endpoint, addr, method, args, timeout: 20 if method == "entry_count" else dict(seed["space"], owner=account)), patch.object(runner.subprocess, "run") as process, redirect_stdout(io.StringIO()):
                self.assertEqual(runner.main(), 0)
                process.assert_not_called()
            refused = json.loads((folder / "live/refused.json").read_text())
            self.assertEqual(refused[0]["consensus_rounds_spent"], 0)
            self.assertFalse((folder / "bradbury.jsonl").exists())
            self.assertFalse((folder / "records.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
