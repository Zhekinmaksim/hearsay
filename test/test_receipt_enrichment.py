"""Offline checks for optional explorer enrichment in canonical receipt reads."""
from argparse import Namespace
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import collect_receipts as collector
import run_live as runner

TX = "0x" + "ab" * 32
ADDRESS = "0x" + "12" * 20
ACCOUNT = "0x" + "34" * 20
RECEIPT = {
    "txId": TX, "recipient": ADDRESS, "sender": ACCOUNT,
    "status_basis": "getTransactionAllData", "consensus_version": "2.0.0",
    "stored_block": {"number": "23792080", "hash": "0x" + "56" * 32, "timestamp": "1791441300"},
    "stored_receipt": {"id": TX, "status": 9, "result": 0, "txExecutionResult": 1,
                       "recipient": ADDRESS, "sender": ACCOUNT, "numOfInitialValidators": "5", "initialRotations": "3"},
    "stored_rounds": [{"votesCommitted": "11", "votesRevealed": "10"}],
    "projected_receipt": {"statusName": "ACCEPTED"},
}


class OptionalEnrichmentTests(unittest.TestCase):
    def response(self, receipt=RECEIPT):
        return subprocess.CompletedProcess([], 0, json.dumps(receipt), "")

    def test_empty_explorer_keeps_full_fresh_canonical_bridge_read(self):
        with patch.object(collector.subprocess, "run", return_value=self.response()) as rpc, patch.object(collector, "fetch_receipt") as explorer:
            received = collector.lookup_receipt("", "https://rpc.invalid", TX, 30)
        self.assertEqual(received, RECEIPT)
        self.assertEqual(collector.status_of(received), "APPEAL_REVEALING")
        explorer.assert_not_called()
        rpc.assert_called_once_with(["node", str(ROOT / "scripts/read_chain.mjs"), TX, "https://rpc.invalid"], capture_output=True, text=True, timeout=30)

    def test_default_enrichment_still_collects_optional_evidence(self):
        with patch.object(collector.subprocess, "run", return_value=self.response()), patch.object(collector, "fetch_receipt", return_value={"status": "accepted"}) as explorer:
            received = collector.lookup_receipt(collector.EXPLORER, "", TX, 30)
        explorer.assert_called_once_with(collector.EXPLORER, TX, 30)
        self.assertEqual(received["explorer_receipt"], {"status": "accepted"})
        self.assertEqual(collector.status_of(received), "APPEAL_REVEALING")

    def test_default_explorer_failure_cannot_change_stored_outcome(self):
        with patch.object(collector.subprocess, "run", return_value=self.response()), patch.object(collector, "fetch_receipt", side_effect=TimeoutError("optional explorer timed out")):
            received = collector.lookup_receipt(collector.EXPLORER, "", TX, 30)
        self.assertIn("timed out", received["explorer_lookup_error"])
        self.assertEqual(received["stored_receipt"], RECEIPT["stored_receipt"])

    def test_no_explorer_does_not_bypass_canonical_basis_or_version_checks(self):
        invalid = [dict(RECEIPT, status_basis="projected"), dict(RECEIPT, stored_receipt=None),
                   dict(RECEIPT, consensus_version=None), dict(RECEIPT, consensus_version="0.6.0")]
        for receipt in invalid:
            with self.subTest(receipt=receipt), patch.object(collector.subprocess, "run", return_value=self.response(receipt)), patch.object(collector, "fetch_receipt") as explorer:
                with self.assertRaises(RuntimeError):
                    collector.lookup_receipt("", "", TX, 30)
                explorer.assert_not_called()

    def test_canonical_read_error_still_stops(self):
        with patch.object(collector.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "canonical RPC unavailable")), patch.object(collector, "fetch_receipt") as explorer:
            with self.assertRaisesRegex(RuntimeError, "canonical RPC unavailable"):
                collector.lookup_receipt("", "", TX, 30)
            explorer.assert_not_called()

    def test_guard_freshly_reads_every_missing_receipt_without_enrichment(self):
        with tempfile.TemporaryDirectory(prefix="hearsay-enrichment-guard-") as folder:
            folder = Path(folder)
            rows = []
            for name, tx in [("present", "0x" + "01" * 32), ("missing-one", TX), ("missing-two", "0x" + "cd" * 32)]:
                envelope = {"version": "hearsay/1", "space_id": 0, "entry_class": "honest",
                            "claim": name, "source_url": "https://example.org/" + name}
                file = folder / (name + ".json")
                file.write_text(json.dumps(envelope))
                rows.append({"tx": tx, "method": "write_entry", "envelope_hash": collector.envtool.envelope_hash(envelope), "file": str(file)})
            manifest = folder / "manifest.jsonl"
            manifest.write_text("".join(json.dumps(row) + "\n" for row in rows))
            index = {rows[0]["envelope_hash"]: {"entry_id": 0, "envelope_hash": rows[0]["envelope_hash"]}}
            reads = []
            def call(endpoint, address, method, args, timeout):
                reads.append(method)
                self.assertEqual((endpoint, address, timeout), ("", ADDRESS, 30))
                if method == "entry_count":
                    return 1
                self.assertEqual(method, "solvency")
                return {"balanced": True}
            def receipt(explorer, endpoint, tx, timeout):
                self.assertEqual((endpoint, timeout), ("", 30))
                observed = copy.deepcopy(RECEIPT)
                observed["txId"] = observed["stored_receipt"]["id"] = tx
                return observed
            proof = {"consensus_version": "2.0.0", "stored_block": RECEIPT["stored_block"],
                     "pending_head": "13", "pending_tail": "13", "pending_head_tx": "0x" + "00" * 32,
                     "provisional": True, "finalization_guaranteed": False}
            with patch.object(collector, "read_call", side_effect=call), patch.object(collector, "scan_entries", return_value=(index, [])) as scan, patch.object(collector, "lookup_receipt", side_effect=receipt) as lookup, patch.object(runner.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, json.dumps(proof), "")) as queue:
                result = runner.prepare_progress_guard(Namespace(address=ADDRESS, account=ACCOUNT, timeout=30), folder, manifest)
            self.assertEqual(reads, ["entry_count", "entry_count", "solvency"])
            scan.assert_called_once_with("", ADDRESS, 30, count=1, workers=1)
            self.assertEqual(lookup.call_args_list, [unittest.mock.call("", "", row["tx"], 30) for row in rows[1:]])
            command = queue.call_args.args[0]
            self.assertEqual(command[:5], ["node", str(ROOT / "scripts/read_chain.mjs"), "--progress-guard", ADDRESS, ACCOUNT])
            self.assertEqual(json.loads(command[5]), [row["tx"] for row in rows[1:]])
            self.assertEqual(result["transactions"], [row["tx"] for row in rows[1:]])
            saved = json.loads((folder / "live/progress-guard.json").read_text())
            self.assertTrue(saved["scan_complete"])
            self.assertEqual(saved["entry_count"], 1)
            self.assertEqual(saved["solvency"], {"balanced": True})
            self.assertEqual([row["receipt"]["stored_receipt"]["id"] for row in json.loads((folder / "live/unresolved.json").read_text())], result["transactions"])

    def test_real_collector_cli_empty_explorer_flag_skips_only_enrichment(self):
        # Exercise the saved argparse -> main -> lookup_receipt path. A fake
        # Node bridge returns canonical data; sitecustomize denies all HTTPS.
        # Neither CLI invocation can contact a network or load an SDK account.
        for skip in (False, True):
            with self.subTest(skip=skip), tempfile.TemporaryDirectory(prefix="hearsay-enrichment-cli-") as folder:
                folder = Path(folder)
                (folder / "receipt.json").write_text(json.dumps(RECEIPT))
                (folder / "manifest.jsonl").write_text(json.dumps({"tx": TX, "envelope_hash": "ab" * 32}) + "\n")
                node = folder / "node"
                node.write_text("#!" + sys.executable + "\nimport json,sys,os\nfrom pathlib import Path\n"
                    "if sys.argv[2:4] == ['--call', '" + ADDRESS + "']:\n"
                    " assert sys.argv[4]=='entry_count'\n print('0')\n"
                    "else:\n assert sys.argv[2]=='" + TX + "'\n print(Path(os.environ['GUARD_ENRICHMENT_RECEIPT']).read_text())\n")
                node.chmod(0o700)
                (folder / "sitecustomize.py").write_text("import urllib.request\ndef denied(*args,**kwargs):\n raise RuntimeError('offline explorer attempt recorded')\nurllib.request.urlopen=denied\n")
                env = dict(os.environ, PATH=str(folder) + os.pathsep + os.environ["PATH"], PYTHONPATH=str(folder),
                           PYTHONDONTWRITEBYTECODE="1", GUARD_ENRICHMENT_RECEIPT=str(folder / "receipt.json"))
                args = [sys.executable, str(ROOT / "scripts/collect_receipts.py"), str(folder / "manifest.jsonl"),
                        "--address", ADDRESS, "--out", str(folder / "records.jsonl"), "--raw-dir", str(folder / "raw")]
                if skip:
                    args += ["--explorer", ""]
                result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                raw = json.loads((folder / "raw" / (TX + ".json")).read_text())
                self.assertEqual(raw["receipt"]["stored_receipt"], RECEIPT["stored_receipt"])
                self.assertEqual(raw["receipt"]["stored_block"], RECEIPT["stored_block"])
                self.assertEqual(raw["error"], "still settling: APPEAL_REVEALING")
                self.assertFalse((folder / "records.jsonl").exists())
                if skip:
                    self.assertNotIn("explorer_lookup_error", raw["receipt"])
                    self.assertNotIn("explorer_receipt", raw["receipt"])
                else:
                    self.assertEqual(raw["receipt"]["explorer_lookup_error"], "offline explorer attempt recorded")


if __name__ == "__main__":
    unittest.main()
