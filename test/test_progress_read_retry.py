"""The retry boundary is entirely read-only and keeps guard failures fatal."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_live as runner


class ProgressReadRetryTest(unittest.TestCase):
    def test_missing_pin_restarts_full_guard_and_records_full_error(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); manifest = root / "manifest.jsonl"; manifest.write_text("")
            args = argparse.Namespace()
            error = RuntimeError("Details: block `0x16db620` not found; full RPC details")
            proof = {"transactions": ["known"], "scan_complete": True}
            with patch.object(runner, "_prepare_progress_guard_once", side_effect=[error, proof]) as guard:
                self.assertEqual(runner.prepare_progress_guard(args, root, manifest), proof)
            self.assertEqual(guard.call_count, 2)
            audit = json.loads((root / "live/progress-guard-read-attempts.json").read_text())
            self.assertTrue(audit["read_only"])
            self.assertEqual(audit["attempts"][0]["error"], str(error))
            self.assertTrue(audit["attempts"][1]["success"])

    def test_missing_entry_pin_can_retry_but_changed_count_cannot(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); manifest = root / "manifest"; manifest.write_text("")
            errors = [{"entry_id": 3, "error": "block 0x1234 not found"}]
            for count, expected in ((4, 2), (5, 1)):
                error = runner.ProgressScanError(4, 3, errors, count)
                with patch.object(runner, "_prepare_progress_guard_once", side_effect=[error, None]) as guard:
                    if expected == 2: runner.prepare_progress_guard(argparse.Namespace(), root, manifest)
                    else:
                        with self.assertRaises(runner.ProgressScanError): runner.prepare_progress_guard(argparse.Namespace(), root, manifest)
                self.assertEqual(guard.call_count, expected)

    def test_only_matching_optional_quotes_around_an_exact_block_are_recognized(self):
        for value in ('block 123 not found', 'block "0x123" not found', "block '123' not found", 'block `0x123` not found'):
            self.assertTrue(runner._block_not_found(RuntimeError(value)), value)
        for value in ('block `0x123 not found', 'block whatever not found', 'block not found', 'unknown outcome'):
            self.assertFalse(runner._block_not_found(RuntimeError(value)), value)

    def test_unknown_outcome_insolvency_and_mixed_scan_errors_never_retry(self):
        failures = [RuntimeError("progress guard solvency failed"), RuntimeError("unknown outcome"),
                    runner.ProgressScanError(2, 0, [{"error": "block 0x1 not found"}, {"error": "no entry returned"}], 2)]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); manifest = root / "manifest"; manifest.write_text("")
            for error in failures:
                with patch.object(runner, "_prepare_progress_guard_once", side_effect=error) as guard:
                    with self.assertRaises(RuntimeError): runner.prepare_progress_guard(argparse.Namespace(), root, manifest)
                self.assertEqual(guard.call_count, 1)

    def test_missing_pin_attempts_are_bounded_to_three(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); manifest = root / "manifest"; manifest.write_text("")
            with patch.object(runner, "_prepare_progress_guard_once", side_effect=RuntimeError("block 0x1 not found")) as guard:
                with self.assertRaises(RuntimeError): runner.prepare_progress_guard(argparse.Namespace(), root, manifest)
            self.assertEqual(guard.call_count, 3)

    def test_changed_manifest_stops_before_second_read(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); manifest = root / "manifest"; manifest.write_text("")
            def first(*args):
                manifest.write_text("new transaction")
                raise RuntimeError("block 0x1 not found")
            with patch.object(runner, "_prepare_progress_guard_once", side_effect=first) as guard:
                with self.assertRaisesRegex(RuntimeError, "inputs changed"): runner.prepare_progress_guard(argparse.Namespace(), root, manifest)
            self.assertEqual(guard.call_count, 1)


if __name__ == "__main__": unittest.main()
