"""Offline failure and recovery checks for the live evidence pipeline."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import collect_receipts as collector
import diagnose_missing as diagnosis
import publish_live as publisher
import run_live as runner


class ReceiptsTest(unittest.TestCase):
    def setUp(self):
        self.env = json.loads((ROOT / "examples/entries/01-honest-dissolution.json").read_text())
        self.entry = json.loads((ROOT / "web/corpus.json").read_text())["entries"][0]
        self.entry["space_id"] = self.env["space_id"]
        self.tx = "0x" + "ab" * 32
        self.row = {"tx": self.tx, "envelope_hash": collector.envtool.envelope_hash(self.env), "file": str(ROOT / "examples/entries/01-honest-dissolution.json")}
        self.receipt = {"status": "FINALIZED"}

    def test_cli_literals_preserve_strings(self):
        parsed = collector.extract_json("Result:\n{entry_id: 7, votes: {a: 'yes', b: 'yes'}, pool: 9007199254740993n, open: true, note: 'true false null 12n'}\n✔ done")
        self.assertEqual(parsed["pool"], 9007199254740993)
        self.assertTrue(parsed["open"])
        self.assertEqual(parsed["note"], "true false null 12n")

    def test_resume_cannot_mix_deployments(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "manifest.jsonl"
            path.write_text(json.dumps(dict(self.row, address="0x" + "12" * 20)) + "\n")
            runner.validate_manifest_target(path, "0x" + "12" * 20)
            with self.assertRaisesRegex(ValueError, "different contract"):
                runner.validate_manifest_target(path, "0x" + "34" * 20)
            with self.assertRaisesRegex(ValueError, "different protocol"):
                runner.validate_manifest_target(path, "0x" + "12" * 20, 0)

    def test_malformed_cli_is_a_read_error(self):
        with self.assertRaises(RuntimeError):
            collector.extract_json("Result:\nnot an object\n✔ done")

    def test_machine_reads_preserve_money_and_literal_strings(self):
        value = collector.decode_chain_json(json.dumps({"pool": {"$bigint": "9007199254740993123"}, "claim": "first\n{true: false}, null 12n"}))
        self.assertEqual(value["pool"], 9007199254740993123)
        self.assertEqual(value["claim"], "first\n{true: false}, null 12n")

    def test_explorer_indexing_lag_stays_pending(self):
        error = urllib.error.HTTPError("url", 404, "Not Found", {}, None)
        with patch.object(collector, "fetch_json", side_effect=error):
            self.assertIsNone(collector.fetch_receipt(collector.EXPLORER, self.tx, 1))
        error = urllib.error.HTTPError("url", 503, "Unavailable", {}, None)
        with patch.object(collector, "fetch_json", side_effect=error):
            with self.assertRaises(urllib.error.HTTPError):
                collector.fetch_receipt(collector.EXPLORER, self.tx, 1)

    def test_scan_recovers_after_empty_slot(self):
        def reader(endpoint, address, entry_id, timeout):
            return None if entry_id == 0 else {"entry_id": entry_id, "envelope_hash": "hash"}
        index, errors = collector.scan_entries("", "", 1, count=2, reader=reader)
        self.assertEqual(index["hash"]["entry_id"], 1)
        self.assertEqual(errors[0]["entry_id"], 0)

    def test_scan_failure_does_not_hide_later_entry(self):
        def reader(endpoint, address, entry_id, timeout):
            if entry_id == 0:
                raise RuntimeError("RPC unavailable")
            return {"entry_id": entry_id, "envelope_hash": "hash"}
        index, errors = collector.scan_entries("", "", 1, count=2, reader=reader)
        self.assertIn("hash", index)
        self.assertIn("RPC", errors[0]["error"])

    def test_incremental_scan_recovers_new_shifted_id(self):
        reads = []
        def reader(endpoint, address, entry_id, timeout):
            reads.append(entry_id)
            return {"entry_id": entry_id, "envelope_hash": str(entry_id)}
        index, errors = collector.scan_entries("", "", 1, count=5, reader=reader, start=3)
        self.assertEqual(reads, [3, 4])
        self.assertEqual(index["4"]["entry_id"], 4)
        self.assertEqual(errors, [])

    def test_record_reproduces_actual_votes(self):
        record = collector.assemble_record(self.row, self.entry, self.env, 2, self.receipt)
        self.assertEqual(record["status"], "ADMITTED")
        self.assertFalse(record["snapshot_verified"])
        self.assertEqual(record["votes"], self.entry["votes"])

    def test_publication_refuses_rolled_back_state(self):
        record = collector.assemble_record(self.row, self.entry, self.env, 2, self.receipt)
        with patch.object(collector, "read_entry", return_value=None):
            with self.assertRaisesRegex(ValueError, "disappeared"):
                publisher.refresh_record(record, "address")
        changed = dict(self.entry, snapshot_hash="00" * 32)
        with patch.object(collector, "read_entry", return_value=changed):
            with self.assertRaisesRegex(ValueError, "state changed"):
                publisher.refresh_record(record, "address")

    def test_publication_refuses_a_reopened_appeal(self):
        record = collector.assemble_record(self.row, self.entry, self.env, 2, self.receipt)
        with patch.object(collector, "read_entry", return_value=self.entry), patch.object(collector, "lookup_receipt", return_value={"statusName": "APPEAL_REVEALING"}):
            with self.assertRaisesRegex(ValueError, "no longer accepted"):
                publisher.refresh_record(record, "address")

    def test_publication_refreshes_finalization(self):
        record = collector.assemble_record(self.row, self.entry, self.env, 2, {"status": "ACCEPTED"})
        with patch.object(collector, "read_entry", return_value=self.entry), patch.object(collector, "lookup_receipt", return_value={"statusName": "FINALIZED", "currentTimestamp": "123", "recipient": "address"}):
            refreshed = publisher.refresh_record(record, "address")
        self.assertEqual(refreshed["receipt_status"], "FINALIZED")
        self.assertEqual(refreshed["consensus_checkpoint"]["chain_timestamp"], "123")
        self.assertEqual(record["receipt_status"], "ACCEPTED")

    def test_publication_cannot_borrow_another_contracts_receipt(self):
        record = collector.assemble_record(self.row, self.entry, self.env, 2, self.receipt)
        with patch.object(collector, "read_entry", return_value=self.entry), patch.object(collector, "lookup_receipt", return_value={"statusName": "FINALIZED", "recipient": "other"}):
            with self.assertRaisesRegex(ValueError, "another contract"):
                publisher.refresh_record(record, "address")

    def test_wrong_slot_is_rejected(self):
        other = dict(self.entry, envelope_hash="00" * 32)
        with self.assertRaisesRegex(ValueError, "hashes disagree"):
            collector.assemble_record(self.row, other, self.env, 2, self.receipt)

    def test_forged_verdict_is_rejected(self):
        other = dict(self.entry, status="UNSOURCED")
        with self.assertRaisesRegex(ValueError, "does not reproduce"):
            collector.assemble_record(self.row, other, self.env, 2, self.receipt)

    def test_modified_claim_is_rejected(self):
        other = dict(self.entry, claim="some other claim")
        with self.assertRaisesRegex(ValueError, "disagree on claim"):
            collector.assemble_record(self.row, other, self.env, 2, self.receipt)

    def test_recorded_round_count_is_checked(self):
        other = dict(self.entry, rounds=0)
        with self.assertRaisesRegex(ValueError, "does not reproduce"):
            collector.assemble_record(self.row, other, self.env, 2, self.receipt)

    def test_diagnosis_recovers_shifted_id(self):
        shifted = dict(self.entry, entry_id=12)
        result = diagnosis.diagnose(self.row, self.receipt, {self.row["envelope_hash"]: shifted}, False)
        self.assertEqual(result["verdict"], "RECOVERABLE")
        self.assertEqual(result["recovered_as"], 12)

    def test_partial_scan_does_not_prove_absence(self):
        result = diagnosis.diagnose(self.row, self.receipt, {}, False)
        self.assertEqual(result["verdict"], "UNRESOLVED")

    def test_complete_scan_does_not_invent_cause(self):
        result = diagnosis.diagnose(self.row, self.receipt, {}, True)
        self.assertEqual(result["verdict"], "SETTLED WITHOUT MATCHING STATE")
        self.assertIn("does not establish the cause", result["reason"])

    def test_failed_receipt_is_not_pending(self):
        result = diagnosis.diagnose(self.row, {"status": "REVERTED", "error": "boom"}, {}, False)
        self.assertEqual(result["verdict"], "FAILED ON CHAIN")
        self.assertEqual(result["errors"], [("error", "boom")])

    def test_protocol_timeout_is_not_a_contract_rejection(self):
        for status in ("ValidatorsTimeout", "validators_timeout", "LeaderTimeout"):
            result = diagnosis.diagnose(self.row, {"status": status}, {}, True)
            self.assertEqual(result["verdict"], "CONSENSUS TIMEOUT")
            self.assertIn("not a contract rejection", result["reason"])

    def test_rpc_receipt_overrides_stale_explorer(self):
        response = type("Result", (), {"returncode": 0, "stdout": json.dumps({"status_basis": "getTransactionAllData", "consensus_version": "2.0.0", "stored_receipt": {"status": 12}, "status": 12, "statusName": "VALIDATORS_TIMEOUT", "resultName": "MAJORITY_TIMEOUT"}), "stderr": ""})()
        with patch.object(collector.subprocess, "run", return_value=response), patch.object(collector, "fetch_receipt", return_value={"status": "accepted"}):
            receipt = collector.lookup_receipt(collector.EXPLORER, "", self.tx, 1)
        self.assertEqual(collector.status_of(receipt), "VALIDATORS_TIMEOUT")
        self.assertEqual(receipt["explorer_receipt"]["status"], "accepted")

    def test_stored_pending_state_overrides_projected_terminal_labels(self):
        for projected in ("ACCEPTED", "FINALIZED", "VALIDATORS_TIMEOUT", "LEADER_TIMEOUT"):
            receipt = {"statusName": projected, "stored_receipt": {"status": 3}, "projected_receipt": {"statusName": projected}}
            self.assertEqual(collector.status_of(receipt), "COMMITTING")
            result = diagnosis.diagnose(self.row, receipt, {}, True)
            self.assertEqual(result["verdict"], "UNRESOLVED")

    def test_stored_leader_reveal_is_not_a_timeout(self):
        receipt = {"statusName": "LEADER_TIMEOUT", "stored_receipt": {"status": 14}}
        self.assertEqual(collector.status_of(receipt), "LEADER_REVEALING")
        self.assertNotIn(collector.status_of(receipt), collector.TERMINAL)
        self.assertFalse(collector.is_consensus_timeout(receipt))

    def test_actual_captured_node_timeout_agrees_with_verified_legacy_enum(self):
        fixture = json.loads((ROOT / "test/fixtures/bradbury-v2-node-receipt.json").read_text())
        receipt = {"consensus_version": fixture["consensus_version"], "stored_receipt": fixture["stored_transaction"]}
        self.assertEqual(fixture["node_status"], {"status": "LeaderTimeout", "statusCode": 13})
        self.assertEqual(collector.status_of(receipt), "LEADER_TIMEOUT")
        self.assertTrue(collector.is_consensus_timeout(receipt))
        self.assertIn('"13": TransactionStatus.LEADER_TIMEOUT', fixture["pinned_sdk_status_mapping"])
        self.assertEqual(diagnosis.diagnose(self.row, receipt, {}, True)["verdict"], "CONSENSUS TIMEOUT")

    def test_ready_to_finalize_without_a_judgement_stays_unresolved(self):
        receipt = {"consensus_version": "2.0.0", "stored_receipt": {"status": 11, "result": 0, "txExecutionResult": 0}}
        self.assertEqual(collector.status_of(receipt), "READY_TO_FINALIZE")
        self.assertNotIn(collector.status_of(receipt), collector.TERMINAL)
        self.assertFalse(collector.is_consensus_timeout(receipt))
        self.assertIsNone(collector.finalized_infrastructure_outcome(receipt))
        self.assertEqual(diagnosis.diagnose(self.row, receipt, {}, True)["verdict"], "UNRESOLVED")

    def test_live_lookup_refuses_missing_or_unverified_protocol_version(self):
        for version in (None, "0.6.0"):
            payload = {"status_basis": "getTransactionAllData", "stored_receipt": {"status": 7}, "consensus_version": version}
            response = subprocess.CompletedProcess([], 0, json.dumps(payload), "")
            with patch.object(collector.subprocess, "run", return_value=response):
                with self.assertRaisesRegex(RuntimeError, "verified consensus version"):
                    collector.lookup_receipt(collector.EXPLORER, "", self.tx, 1)
        self.assertEqual(collector.status_of({"consensus_version": "0.6.0", "stored_receipt": {"status": 7}}), "PENDING")

    def test_finalized_stored_timeout_is_not_a_judged_refusal(self):
        receipt = {"statusName": "FINALIZED", "stored_receipt": {"status": 7, "result": 3}}
        self.assertEqual(collector.status_of(receipt), "FINALIZED")
        self.assertTrue(collector.is_consensus_timeout(receipt))
        result = diagnosis.diagnose(self.row, receipt, {}, True)
        self.assertEqual(result["verdict"], "CONSENSUS TIMEOUT")
        self.assertIn("not a contract rejection", result["reason"])

    def test_past_or_projected_timeout_cannot_fail_a_current_round(self):
        receipt = {"statusName": "VALIDATORS_TIMEOUT", "resultName": "TIMEOUT", "lastRound": {"result": 3}, "stored_receipt": {"status": 3, "result": 0}}
        self.assertFalse(collector.is_consensus_timeout(receipt))
        receipt["stored_receipt"] = {"status": 7, "result": 1}
        self.assertFalse(collector.is_consensus_timeout(receipt))

    def test_publication_refuses_finalized_stored_timeout(self):
        record = collector.assemble_record(self.row, self.entry, self.env, 2, self.receipt)
        receipt = {"statusName": "FINALIZED", "recipient": "address", "stored_receipt": {"status": 7, "result": 3}}
        with patch.object(collector, "read_entry", return_value=self.entry), patch.object(collector, "lookup_receipt", return_value=receipt):
            with self.assertRaisesRegex(ValueError, "no longer accepted"):
                publisher.refresh_record(record, "address")

    def test_unknown_stored_status_cannot_fall_back_to_projection(self):
        for stored in ({}, {"status": 99}, {"status": "invalid"}, None):
            receipt = {"statusName": "FINALIZED", "stored_receipt": stored}
            self.assertEqual(collector.status_of(receipt), "PENDING")

    def test_live_lookup_requires_stored_status_evidence(self):
        response = type("Result", (), {"returncode": 0, "stdout": json.dumps({"statusName": "FINALIZED"}), "stderr": ""})()
        with patch.object(collector.subprocess, "run", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "lacks stored"):
                collector.lookup_receipt(collector.EXPLORER, "", self.tx, 1)

    def test_resume_skips_diagnosed_finalized_timeout_without_resending(self):
        with tempfile.TemporaryDirectory(prefix="hearsay-resume-") as folder:
            folder = Path(folder)
            (folder / "live").mkdir()
            address, account = "0x" + "12" * 20, "0x" + "34" * 20
            candidate = {"id": "retained-timeout", "class": self.env["entry_class"], "claim": self.env["claim"], "source_url": self.env["source_url"]}
            for key in ("supports", "author_note", "expects"):
                if self.env.get(key):
                    candidate[key] = self.env[key]
            policy = {"min_rounds": 2, "write_bond": 1000, "challenge_bond": 2000, "cascade_depth": 3, "admit_ttl": 50}
            seed = folder / "seed.json"
            seed.write_text(json.dumps({"entries": [candidate], "space": policy}))
            (folder / "bradbury.jsonl").write_text(json.dumps(dict(self.row, address=address, consensus_max_rotations=0)) + "\n")
            (folder / "live/infrastructure-failures.json").write_text(json.dumps([{"tx": self.tx, "status": "FINALIZED", "consensus_outcome": "TIMEOUT"}]))
            argv = ["run_live.py", "--run-dir", str(folder), "--seed", str(seed), "--address", address, "--account", account, "--max-rotations", "0", "--accept-diagnosed-timeouts"]
            with patch.object(sys, "argv", argv), patch.object(collector, "read_call", return_value=dict(policy, owner=account)), patch.object(collector, "lookup_receipt") as lookup, patch.object(runner.subprocess, "run") as send:
                self.assertEqual(runner.main(), 0)
            lookup.assert_not_called()
            send.assert_not_called()

    def test_publication_refuses_stale_projected_acceptance(self):
        record = collector.assemble_record(self.row, self.entry, self.env, 2, self.receipt)
        receipt = {"statusName": "ACCEPTED", "recipient": "address", "stored_receipt": {"status": 10}}
        with patch.object(collector, "read_entry", return_value=self.entry), patch.object(collector, "lookup_receipt", return_value=receipt):
            with self.assertRaisesRegex(ValueError, "no longer accepted"):
                publisher.refresh_record(record, "address")

    def test_publication_refuses_reopened_infrastructure_timeout(self):
        failure = dict(self.row, id="timed-out", status="VALIDATORS_TIMEOUT")
        receipt = {"statusName": "VALIDATORS_TIMEOUT", "recipient": "address", "stored_receipt": {"status": 9, "result": 0}}
        with patch.object(collector, "lookup_receipt", return_value=receipt):
            with self.assertRaisesRegex(ValueError, "still settling"):
                publisher.refresh_failure(failure, "address", {})

    def test_publication_verifies_final_timeout_absence(self):
        failure = dict(self.row, id="timed-out", status="VALIDATORS_TIMEOUT")
        receipt = {"recipient": "address", "stored_receipt": {"status": 7, "result": 3}}
        with patch.object(collector, "lookup_receipt", return_value=receipt):
            verified = publisher.refresh_failure(failure, "address", {})
            self.assertEqual(verified["status"], "FINALIZED")
            self.assertEqual(verified["consensus_outcome"], "TIMEOUT")
            with self.assertRaisesRegex(ValueError, "now has application state"):
                publisher.refresh_failure(failure, "address", {self.row["envelope_hash"]: self.entry})

    def test_finalized_no_execution_requires_explicit_stored_fields_and_complete_scan(self):
        receipt = {"stored_receipt": {"status": 7, "result": 0, "txExecutionResult": 0}}
        self.assertEqual(collector.finalized_infrastructure_outcome(receipt), "NOT_EXECUTED")
        self.assertEqual(diagnosis.diagnose(self.row, receipt, {}, True)["verdict"], "FINALIZED WITHOUT EXECUTION")
        self.assertEqual(diagnosis.diagnose(self.row, receipt, {}, False)["verdict"], "UNRESOLVED")
        self.assertIsNone(collector.finalized_infrastructure_outcome({"stored_receipt": {"status": 7}}))
        self.assertIsNone(collector.finalized_infrastructure_outcome({"stored_receipt": {"status": 13, "result": 0, "txExecutionResult": 0}}))
        self.assertIsNone(collector.finalized_infrastructure_outcome({"statusName": "FINALIZED", "result": 0, "txExecutionResult": 0}))

    def test_no_execution_outcome_cannot_publish_a_judged_record(self):
        record = collector.assemble_record(self.row, self.entry, self.env, 2, self.receipt)
        receipt = {"recipient": "address", "stored_receipt": {"status": 7, "result": 0, "txExecutionResult": 0}}
        with patch.object(collector, "read_entry", return_value=self.entry), patch.object(collector, "lookup_receipt", return_value=receipt):
            with self.assertRaisesRegex(ValueError, "no longer accepted"):
                publisher.refresh_record(record, "address")

    def test_runner_retains_complete_final_no_execution_without_counting_a_record(self):
        with tempfile.TemporaryDirectory(prefix="hearsay-no-execution-") as folder:
            folder = Path(folder)
            address, account = "0x" + "12" * 20, "0x" + "34" * 20
            policy = {"min_rounds": 2, "write_bond": 1000, "challenge_bond": 2000, "cascade_depth": 3, "admit_ttl": 50}
            candidate = {"id": "unexecuted", "class": self.env["entry_class"], "claim": self.env["claim"], "source_url": self.env["source_url"]}
            for key in ("supports", "author_note", "expects"):
                if self.env.get(key):
                    candidate[key] = self.env[key]
            seed = folder / "seed.json"
            seed.write_text(json.dumps({"entries": [candidate], "space": policy}))
            (folder / "bradbury.jsonl").write_text(json.dumps(dict(self.row, address=address)) + "\n")
            receipt = {"stored_receipt": {"status": 7, "result": 0, "txExecutionResult": 0}}
            def subprocess_result(command, **kwargs):
                if "collect_receipts.py" in command[1]:
                    collector.checkpoint(folder / "records.jsonl.issues.json", {"scan_errors": [], "transactions": [{"tx": self.tx}]})
                    return subprocess.CompletedProcess(command, 2, "", "")
                if "diagnose_missing.py" in command[1]:
                    collector.checkpoint(folder / "diagnosis.json", {"scan_complete": True, "transactions": [{"tx": self.tx, "status": "FINALIZED", "verdict": "FINALIZED WITHOUT EXECUTION", "reason": "no execution", "receipt": receipt}]})
                    return subprocess.CompletedProcess(command, 0, "", "")
                self.fail("unexpected submission")
            argv = ["run_live.py", "--run-dir", str(folder), "--seed", str(seed), "--address", address, "--account", account, "--accept-diagnosed-no-execution"]
            with patch.object(sys, "argv", argv), patch.object(collector, "lookup_receipt", return_value=receipt), patch.object(collector, "read_call", side_effect=lambda endpoint, addr, method, args, timeout: {"balanced": True} if method == "solvency" else dict(policy, owner=account)), patch.object(runner.subprocess, "run", side_effect=subprocess_result):
                self.assertEqual(runner.main(), 0)
            failures = json.loads((folder / "live/infrastructure-failures.json").read_text())
            self.assertEqual(failures[0]["consensus_outcome"], "NOT_EXECUTED")
            self.assertFalse((folder / "records.jsonl").exists())

    def test_reopened_timeout_waits_for_same_tx_and_keeps_original_deadline(self):
        fixture = json.loads((ROOT / "test/fixtures/bradbury-v2-node-receipt.json").read_text())
        timeout_receipt = {"consensus_version": fixture["consensus_version"], "stored_receipt": fixture["stored_transaction"]}
        reopened = {"consensus_version": "2.0.0", "stored_receipt": {"status": 10, "result": 0, "txExecutionResult": 0}}
        settled = {"consensus_version": "2.0.0", "stored_receipt": {"status": 7, "result": 1, "txExecutionResult": 1}}
        for mode in ("settled", "deadline", "lookup_failure", "scan_error"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix="hearsay-reopened-") as folder:
                folder = Path(folder)
                address, account = "0x" + "12" * 20, "0x" + "34" * 20
                policy = {"min_rounds": 2, "write_bond": 1000, "challenge_bond": 2000, "cascade_depth": 3, "admit_ttl": 50}
                candidate = {"id": "reopened", "class": self.env["entry_class"], "claim": self.env["claim"], "source_url": self.env["source_url"]}
                for key in ("supports", "author_note", "expects"):
                    if self.env.get(key):
                        candidate[key] = self.env[key]
                seed = folder / "seed.json"
                seed.write_text(json.dumps({"entries": [candidate], "space": policy}))
                (folder / "bradbury.jsonl").write_text(json.dumps(dict(self.row, address=address)) + "\n")
                clock, collections, phase = [0], [], ["timeout"]
                def lookup(*args):
                    if phase[0] == "timeout":
                        return timeout_receipt
                    if mode == "lookup_failure":
                        raise RuntimeError("fresh receipt unavailable")
                    return settled if mode == "settled" and clock[0] >= 40 else reopened
                def subprocess_result(command, **kwargs):
                    if "collect_receipts.py" in command[1]:
                        collections.append(clock[0])
                        if len(collections) == 1:
                            phase[0] = "reopened"
                            collector.checkpoint(folder / "records.jsonl.issues.json", {"scan_errors": ["entry scan failed"] if mode == "scan_error" else [], "transactions": [{"tx": self.tx}]})
                            return subprocess.CompletedProcess(command, 2, "", "")
                        self.assertIs(lookup(), settled, "recollection must wait for settled state")
                        record = collector.assemble_record(self.row, self.entry, self.env, 2, settled)
                        collector.atomic_write(folder / "records.jsonl", json.dumps(record) + "\n")
                        collector.checkpoint(folder / "records.jsonl.issues.json", {"scan_errors": [], "transactions": []})
                        return subprocess.CompletedProcess(command, 0, "", "")
                    if "diagnose_missing.py" in command[1]:
                        unresolved = len(collections) == 1
                        collector.checkpoint(folder / "diagnosis.json", {"scan_complete": mode != "scan_error", "scan_errors": ["entry scan failed"] if mode == "scan_error" else [], "transactions": [{"tx": self.tx, "verdict": "UNRESOLVED", "receipt": reopened}] if unresolved else []})
                        return subprocess.CompletedProcess(command, 2 if unresolved else 0, "", "")
                    self.fail("unexpected submission; manifested tx must never be resent")
                wait = "35" if mode == "deadline" else "100"
                argv = ["run_live.py", "--run-dir", str(folder), "--seed", str(seed), "--address", address, "--account", account, "--wait", wait]
                with patch.object(sys, "argv", argv), patch.object(collector, "lookup_receipt", side_effect=lookup), patch.object(collector, "read_call", side_effect=lambda endpoint, addr, method, args, timeout: {"balanced": True} if method == "solvency" else dict(policy, owner=account)), patch.object(runner.subprocess, "run", side_effect=subprocess_result), patch.object(runner.time, "monotonic", side_effect=lambda: clock[0]), patch.object(runner.time, "sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)):
                    if mode == "settled":
                        self.assertEqual(runner.main(), 0)
                        self.assertEqual(collections, [32, 40])
                        self.assertEqual(json.loads((folder / "records.jsonl").read_text())["tx"], self.tx)
                    else:
                        expected_error = {"deadline": "still settling", "lookup_failure": "fresh receipt unavailable", "scan_error": "collection or diagnosis unresolved"}[mode]
                        with self.assertRaisesRegex(RuntimeError, expected_error):
                            runner.main()
                        self.assertEqual(collections, [32])
                        self.assertLess(clock[0], 40)
                        self.assertFalse((folder / "records.jsonl").exists())

    def test_opt_in_reopening_deadline_retains_unresolved_without_resending(self):
        with tempfile.TemporaryDirectory(prefix="hearsay-opt-reopen-") as folder:
            folder = Path(folder)
            address, account = "0x" + "12" * 20, "0x" + "34" * 20
            policy = {"min_rounds": 2, "write_bond": 1000, "challenge_bond": 2000, "cascade_depth": 3, "admit_ttl": 50}
            candidate = {"id": "one", "class": self.env["entry_class"], "claim": self.env["claim"], "source_url": self.env["source_url"]}
            for key in ("supports", "author_note", "expects"):
                if self.env.get(key):
                    candidate[key] = self.env[key]
            seed = folder / "seed.json"
            seed.write_text(json.dumps({"space": policy, "entries": [candidate]}))
            clock, sent, phase = [0], [], ["timeout"]
            timeout_receipt = {"stored_receipt": {"status": 13}}
            reopened = {"stored_receipt": {"status": 10}}
            def process(command, **kwargs):
                if "genlayer_write.mjs" in command[1]:
                    sent.append(command)
                    collector.atomic_write(folder / "bradbury.jsonl", json.dumps(dict(self.row, address=address)) + "\n")
                    return subprocess.CompletedProcess(command, 0, "", "")
                if "collect_receipts.py" in command[1]:
                    phase[0] = "reopened"
                    collector.checkpoint(folder / "records.jsonl.issues.json", {"scan_errors": [], "transactions": [{"tx": self.tx}]})
                    return subprocess.CompletedProcess(command, 2, "", "")
                if "diagnose_missing.py" in command[1]:
                    collector.checkpoint(folder / "diagnosis.json", {"scan_errors": [], "transactions": [{"tx": self.tx, "verdict": "UNRESOLVED"}]})
                    return subprocess.CompletedProcess(command, 2, "", "")
                self.fail("unexpected command")
            def guard(args, run_dir, manifest, required_tx):
                self.assertEqual(required_tx, self.tx)
                self.assertEqual(clock[0], 36, "original deadline must expire without extension")
                collector.checkpoint(run_dir / "live/unresolved.json", [{"tx": self.tx, "consensus_outcome": "UNRESOLVED"}])
                return {"transactions": [self.tx]}
            argv = ["run_live.py", "--run-dir", str(folder), "--seed", str(seed), "--address", address, "--account", account, "--wait", "35", "--allow-known-unsettled-progress"]
            with patch.object(sys, "argv", argv), patch.object(collector, "read_call", side_effect=lambda endpoint, addr, method, args, timeout: 0 if method == "entry_count" else dict(policy, owner=account)), patch.object(collector, "lookup_receipt", side_effect=lambda *args: timeout_receipt if phase[0] == "timeout" else reopened), patch.object(runner.subprocess, "run", side_effect=process), patch.object(runner, "prepare_progress_guard", side_effect=guard), patch.object(runner.time, "monotonic", side_effect=lambda: clock[0]), patch.object(runner.time, "sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)):
                self.assertEqual(runner.main(), 0)
            self.assertEqual(len(sent), 1)
            self.assertFalse((folder / "records.jsonl").exists())
            self.assertFalse((folder / "live/infrastructure-failures.json").exists())
            self.assertEqual(json.loads((folder / "live/unresolved.json").read_text())[0]["consensus_outcome"], "UNRESOLVED")

    def test_opt_in_retains_unresolved_and_only_sends_guarded_unique_candidate(self):
        for mode in ("allow", "scan_error", "insolvent", "unknown", "queue_rewind"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix="hearsay-progress-") as folder:
                folder = Path(folder)
                address, account = "0x" + "12" * 20, "0x" + "34" * 20
                policy = {"min_rounds": 2, "write_bond": 1000, "challenge_bond": 2000, "cascade_depth": 3, "admit_ttl": 50}
                candidates = [{"id": "old", "class": self.env["entry_class"], "claim": self.env["claim"], "source_url": self.env["source_url"]},
                              {"id": "next", "class": "honest", "claim": "The next independent source supports another claim.", "source_url": "https://example.org/next"}]
                for key in ("supports", "author_note", "expects"):
                    if self.env.get(key):
                        candidates[0][key] = self.env[key]
                seed = folder / "seed.json"
                seed.write_text(json.dumps({"space": policy, "entries": candidates}))
                old = dict(self.row, address=address, id="old", sender=account)
                (folder / "bradbury.jsonl").write_text(json.dumps(old) + "\n")
                new_tx, submitted, accepted = "0x" + "cd" * 32, [], [False]
                unsettled = {"consensus_version": "2.0.0", "stored_receipt": {"status": 99 if mode == "unknown" else 9}}
                settled = {"consensus_version": "2.0.0", "stored_receipt": {"status": 7, "result": 1, "txExecutionResult": 1}}
                new_env = {"version": "hearsay/1", "space_id": 0, "entry_class": "honest", "claim": candidates[1]["claim"], "source_url": candidates[1]["source_url"]}
                new_hash = collector.envtool.envelope_hash(new_env)
                new_entry = dict(self.entry, claim=new_env["claim"], source_url=new_env["source_url"], envelope_hash=new_hash)
                def read_call(endpoint, addr, method, args, timeout):
                    if method == "entry_count":
                        return int(accepted[0])
                    if method == "solvency":
                        return {"balanced": mode != "insolvent"}
                    return dict(policy, owner=account)
                def scan(*args, **kwargs):
                    return ({new_hash: new_entry} if accepted[0] else {}, [{"error": "scan unavailable"}] if mode == "scan_error" else [])
                def process(command, **kwargs):
                    if "read_chain.mjs" in command[1]:
                        self.assertIn("--progress-guard", command)
                        self.assertEqual(json.loads(command[-1]), [self.tx])
                        return subprocess.CompletedProcess(command, 1 if mode == "queue_rewind" else 0, json.dumps({"consensus_version": "2.0.0", "stored_block": {"number": "10"}, "provisional": True}), "pending queue rewound" if mode == "queue_rewind" else "")
                    if "genlayer_write.mjs" in command[1]:
                        request = json.loads((folder / "live/request.json").read_text())
                        self.assertEqual(request["id"], "next")
                        self.assertEqual(request["progress_guard"]["transactions"], [self.tx])
                        self.assertNotEqual(request["envelope_hash"], old["envelope_hash"])
                        submitted.append(request)
                        new_row = dict(request, tx=new_tx, sender=account)
                        with (folder / "bradbury.jsonl").open("a") as stream:
                            stream.write(json.dumps(new_row) + "\n")
                        accepted[0] = True
                        return subprocess.CompletedProcess(command, 0, "", "")
                    if "collect_receipts.py" in command[1]:
                        new_row = collector.load_manifest(folder / "bradbury.jsonl")[-1]
                        record = collector.assemble_record(new_row, new_entry, new_env, 2, settled)
                        collector.atomic_write(folder / "records.jsonl", json.dumps(record) + "\n")
                        collector.checkpoint(folder / "records.jsonl.issues.json", {"scan_errors": [], "transactions": [{"tx": self.tx, "error": "still unresolved"}]})
                        return subprocess.CompletedProcess(command, 2, "", "")
                    if "diagnose_missing.py" in command[1]:
                        self.assertIn("--exclude-tx", command)
                        self.assertIn(self.tx, command)
                        collector.checkpoint(folder / "diagnosis.json", {"scan_errors": [], "transactions": []})
                        return subprocess.CompletedProcess(command, 0, "", "")
                    self.fail("unexpected command")
                argv = ["run_live.py", "--run-dir", str(folder), "--seed", str(seed), "--address", address, "--account", account, "--allow-known-unsettled-progress", "--limit", "1"]
                with patch.object(sys, "argv", argv), patch.object(collector, "read_call", side_effect=read_call), patch.object(collector, "scan_entries", side_effect=scan), patch.object(collector, "lookup_receipt", side_effect=lambda explorer, endpoint, tx, timeout: unsettled if tx == self.tx else settled), patch.object(runner.subprocess, "run", side_effect=process):
                    if mode == "allow":
                        self.assertEqual(runner.main(), 0)
                        self.assertEqual(len(submitted), 1)
                        retained = json.loads((folder / "live/unresolved.json").read_text())
                        self.assertEqual(retained[0]["tx"], self.tx)
                        self.assertEqual(retained[0]["consensus_outcome"], "UNRESOLVED")
                        self.assertEqual(json.loads((folder / "records.jsonl").read_text())["tx"], new_tx)
                        self.assertFalse((folder / "live/infrastructure-failures.json").exists())
                    else:
                        with self.assertRaises(RuntimeError):
                            runner.main()
                        self.assertEqual(submitted, [])
                        self.assertEqual(len(collector.load_manifest(folder / "bradbury.jsonl")), 1)

    def test_cli_checkpoints_missing_state_and_preserves_records(self):
        with tempfile.TemporaryDirectory(prefix="hearsay-receipts-") as folder:
            folder = Path(folder)
            manifest, cache, out = folder / "manifest.jsonl", folder / "cache.json", folder / "records.jsonl"
            manifest.write_text(json.dumps(self.row) + "\n")
            cache.write_text(json.dumps({self.tx: {"receipt": self.receipt, "entry": self.entry}}))
            command = [sys.executable, str(ROOT / "scripts/collect_receipts.py"), str(manifest), "--from-json", str(cache), "--min-rounds", "2", "--out", str(out), "--raw-dir", str(folder / "raw")]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            before = out.read_bytes()
            missing = copy.deepcopy(self.row)
            missing["tx"] = "0x" + "cd" * 32
            manifest.write_text(json.dumps(self.row) + "\n" + json.dumps(missing) + "\n")
            cache.write_text(json.dumps({missing["tx"]: {"receipt": self.receipt}}))
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(second.returncode, 2)
            self.assertEqual(out.read_bytes(), before)
            raw = json.loads((folder / "raw" / (missing["tx"] + ".json")).read_text())
            self.assertEqual(raw["receipt"]["status"], "FINALIZED")
            self.assertIn("diagnose_missing", raw["error"])
            diagnosed = subprocess.run([sys.executable, str(ROOT / "scripts/diagnose_missing.py"), "--manifest", str(manifest), "--records", str(out), "--from-json", str(cache), "--out", str(folder / "diagnosis.json")], capture_output=True, text=True)
            self.assertEqual(diagnosed.returncode, 2, diagnosed.stdout + diagnosed.stderr)
            self.assertEqual(json.loads((folder / "diagnosis.json").read_text())["transactions"][0]["verdict"], "UNRESOLVED")


if __name__ == "__main__":
    unittest.main()
