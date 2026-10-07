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
        response = type("Result", (), {"returncode": 0, "stdout": json.dumps({"status": 12, "statusName": "VALIDATORS_TIMEOUT", "resultName": "TIMEOUT"}), "stderr": ""})()
        with patch.object(collector.subprocess, "run", return_value=response), patch.object(collector, "fetch_receipt", return_value={"status": "accepted"}):
            receipt = collector.lookup_receipt(collector.EXPLORER, "", self.tx, 1)
        self.assertEqual(collector.status_of(receipt), "VALIDATORS_TIMEOUT")
        self.assertEqual(receipt["explorer_receipt"]["status"], "accepted")

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
