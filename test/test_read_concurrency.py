"""Bounded fresh reads preserve order, errors and fail-closed write guards."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import collect_receipts as collector
import run_live as runner


class ReadConcurrencyTest(unittest.TestCase):
    def test_bounded_out_of_order_reads_are_consumed_in_input_order(self):
        barrier = threading.Barrier(4)
        lock = threading.Lock()
        calls, active, peak = [], 0, 0
        release_first = threading.Event()
        def read(number):
            nonlocal active, peak
            with lock:
                active += 1; peak = max(peak, active); calls.append(number)
            if number < 4:
                barrier.wait(timeout=2)
                if number == 0:
                    self.assertTrue(release_first.wait(2))
                elif number == 3:
                    release_first.set()
            with lock:
                active -= 1
            return number * 2
        result = list(collector.ordered_reads(range(13), read, workers=4))
        self.assertEqual(result, [(i, i * 2, None) for i in range(13)])
        self.assertEqual(Counter(calls), Counter(range(13)))
        self.assertEqual(peak, 4)

    def test_prefetch_window_does_not_launch_whole_manifest(self):
        calls = []; lock = threading.Lock()
        def read(number):
            with lock: calls.append(number)
            return number
        results = collector.ordered_reads(range(100), read, workers=4)
        self.assertEqual(next(results), (0, 0, None))
        results.close()
        self.assertEqual(sorted(calls), [0, 1, 2, 3])

    def test_row_error_keeps_full_coverage_and_never_retries(self):
        error = RuntimeError("complete RPC failure details")
        calls = []
        def read(number):
            calls.append(number)
            if number == 2: raise error
            return number
        result = list(collector.ordered_reads(range(8), read, workers=4))
        self.assertEqual([r[0] for r in result], list(range(8)))
        self.assertIs(result[2][2], error)
        self.assertIsNone(result[2][1])
        self.assertEqual(Counter(calls), Counter(range(8)))
        self.assertEqual(result[-1], (7, 7, None))

    def test_scan_preserves_injected_reader_and_ordered_errors(self):
        def reader(endpoint, address, entry_id, timeout):
            if entry_id == 3: raise RuntimeError("scan error verbatim")
            if entry_id == 5: return None
            return {"entry_id": entry_id, "envelope_hash": str(entry_id)}
        index, errors = collector.scan_entries("rpc", "app", 1, count=7, start=2, reader=reader, workers=4)
        self.assertEqual(list(index), ["2", "4", "6"])
        self.assertEqual(errors, [{"entry_id": 3, "error": "scan error verbatim"}, {"entry_id": 5, "error": "no entry returned"}])

    def test_receipt_helper_preserves_arguments_canonical_values_and_failures(self):
        rows = [{"tx": str(i)} for i in range(7)]
        error = RuntimeError("block `0x123` not found")
        def lookup(explorer, endpoint, tx, timeout):
            self.assertEqual((explorer, endpoint, timeout), ("explorer", "rpc", 30))
            if tx == "3": raise error
            return {"stored_block": {"number": tx}, "status_basis": "getTransactionAllData"}
        with patch.object(collector, "lookup_receipt", side_effect=lookup) as mocked:
            result = list(collector.lookup_receipts(rows, "explorer", "rpc", 30, workers=4))
        self.assertEqual([row for row, _, _ in result], rows)
        self.assertEqual(mocked.call_count, 7)
        self.assertIs(result[3][2], error)
        self.assertEqual(result[-1][1]["stored_block"], {"number": "6"})

    def test_runner_lookup_error_stops_before_queue_or_financial_child(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); manifest = root / "bradbury.jsonl"
            manifest.write_text(json.dumps({"tx": "0x" + "12" * 32, "envelope_hash": "missing"}) + "\n")
            args = argparse.Namespace(address="app", account="account", timeout=1, read_workers=4)
            error = RuntimeError("ordinary RPC failure; do not retry")
            def call(endpoint, address, method, values, timeout):
                return {"balanced": True} if method == "solvency" else 0
            with patch.object(collector, "read_call", side_effect=call), patch.object(collector, "lookup_receipt", side_effect=error) as lookup, patch.object(runner.subprocess, "run") as child:
                with self.assertRaisesRegex(RuntimeError, "ordinary RPC failure"):
                    runner.prepare_progress_guard(args, root, manifest)
            self.assertEqual(lookup.call_count, 1)
            child.assert_not_called()
            audit = json.loads((root / "live/progress-guard-read-attempts.json").read_text())
            self.assertEqual(len(audit["attempts"]), 1)
            self.assertFalse(audit["attempts"][0]["retry_missing_pin"])

    def test_bad_worker_counts_rejected_and_serial_stays_serial(self):
        for workers in [0, 5, -1, True, 1.5]:
            with self.subTest(workers=workers), self.assertRaises(ValueError):
                list(collector.ordered_reads([], lambda item: item, workers))
        thread = threading.get_ident()
        self.assertEqual(list(collector.ordered_reads([1, 2], lambda _: threading.get_ident(), 1)), [(1, thread, None), (2, thread, None)])

    def test_collector_parallel_errors_keep_raw_evidence_and_manifest_order(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); manifest = root / "manifest.jsonl"; out = root / "records.jsonl"
            rows = [{"tx": "0x" + ("%064x" % i), "envelope_hash": str(i)} for i in range(1, 7)]
            manifest.write_text("".join(json.dumps(row) + "\n" for row in rows))
            def lookup(explorer, endpoint, tx, timeout):
                if tx == rows[2]["tx"]:
                    raise RuntimeError("full canonical RPC failure")
                return {"status": "ACCEPTED", "preserved_raw": tx}
            argv = ["collect_receipts.py", str(manifest), "--address", "app", "--workers", "4", "--out", str(out), "--raw-dir", str(root / "raw")]
            with patch.object(sys, "argv", argv), patch.object(collector, "scan_entries", return_value=({}, [])), patch.object(collector, "lookup_receipt", side_effect=lookup) as lookups:
                self.assertEqual(collector.main(), 2)
            self.assertEqual(lookups.call_count, len(rows))
            issues = json.loads(Path(str(out) + ".issues.json").read_text())
            self.assertEqual([item["tx"] for item in issues["transactions"]], [row["tx"] for row in rows])
            self.assertEqual(issues["transactions"][2]["error"], "full canonical RPC failure")
            self.assertFalse(out.exists())
            for row in rows:
                raw = json.loads((root / "raw" / (row["tx"] + ".json")).read_text())
                if row is rows[2]:
                    self.assertEqual(raw["error"], "full canonical RPC failure")
                else:
                    self.assertEqual(raw["receipt"]["preserved_raw"], row["tx"])

    def test_waiting_and_offline_modes_reject_parallel_flag(self):
        for extra in [["--wait", "1"], ["--from-json", "unused"]]:
            args = ["collect_receipts.py", "unused", "--out", "unused", "--workers", "4"] + extra
            with patch.object(sys, "argv", args), self.assertRaises(SystemExit) as raised:
                collector.main()
            self.assertEqual(raised.exception.code, 2)

if __name__ == "__main__":
    unittest.main()
