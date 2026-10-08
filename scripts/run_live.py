#!/usr/bin/env python3
"""Submit a live corpus sequentially, checkpoint and diagnose before each next write.

Requires a deployed contract and a confirmed open_space. Existing manifest
transactions are never sent again. Stop on any unresolved state or insolvency.
This writes only under runs/, never the published or offline corpus.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import collect_receipts as collector


def validate_manifest_target(path, address, max_rotations=3):
    """A resume must never borrow transactions from another deployment."""
    if path.exists():
        for row in collector.load_manifest(path):
            if row.get("address", "").lower() != address.lower():
                raise ValueError("manifest belongs to a different contract")
            if row.get("consensus_max_rotations", 3) != max_rotations:
                raise ValueError("manifest uses a different protocol rotation limit")


def wait_for_settlement(row, args, run_dir, deadline):
    """Wait on the same transaction; reopening never extends its deadline."""
    timeout_since = None
    while True:
        try:
            receipt = collector.lookup_receipt(collector.EXPLORER, "", row["tx"], args.timeout)
        except Exception as exc:
            collector.checkpoint(run_dir / "receipts" / (row["tx"] + ".json"), {"lookup_error": str(exc)})
            if time.monotonic() >= deadline:
                raise RuntimeError("receipt lookup unavailable; resume with the same manifest") from exc
            time.sleep(4)
            continue
        collector.checkpoint(run_dir / "receipts" / (row["tx"] + ".json"), {"receipt": receipt})
        status = collector.status_of(receipt)
        if collector.is_consensus_timeout(receipt):
            # Stored timeouts can reopen when a funded rotation starts.
            if timeout_since is None:
                timeout_since = time.monotonic()
            if time.monotonic() - timeout_since >= 30:
                return receipt
        else:
            timeout_since = None
            if status in collector.TERMINAL:
                return receipt
        if time.monotonic() >= deadline:
            raise RuntimeError("receipt still settling; resume later using the same manifest")
        time.sleep(4)


def prepare_progress_guard(args, run_dir, manifest, required_tx=None):
    """Preserve known unsettled outcomes; never infer judgement from absence."""
    count = int(collector.read_call("", args.address, "entry_count", [], args.timeout))
    index, errors = collector.scan_entries("", args.address, args.timeout, count=count)
    if errors or len(index) != count or int(collector.read_call("", args.address, "entry_count", [], args.timeout)) != count:
        raise RuntimeError("progress guard entry scan incomplete or changed; no next write")
    solvency = collector.read_call("", args.address, "solvency", [], args.timeout)
    if solvency.get("balanced") is not True:
        raise RuntimeError("progress guard solvency failed; no next write")
    unresolved = []
    allowed = {"PROPOSING", "COMMITTING", "REVEALING", "UNDETERMINED", "APPEAL_REVEALING", "APPEAL_COMMITTING", "LEADER_REVEALING"} | collector.TIMEOUTS
    for row in collector.load_manifest(manifest):
        if row["envelope_hash"] in index:
            continue
        receipt = collector.lookup_receipt(collector.EXPLORER, "", row["tx"], args.timeout)
        if collector.finalized_infrastructure_outcome(receipt):
            continue
        status = collector.status_of(receipt)
        if status not in allowed or receipt.get("consensus_version") != "2.0.0":
            raise RuntimeError("progress guard unknown or changed outcome; recollect before writing")
        envelope = collector.find_envelope(row, run_dir / "live/entries")
        unresolved.append(dict(row, entry_class=envelope["entry_class"], status=status, consensus_outcome="UNRESOLVED", receipt=receipt,
                               reason="Complete scan found no matching state; retained unresolved while empty pending queue permits independent provisional progress."))
    if required_tx and required_tx not in {row["tx"] for row in unresolved}:
        raise RuntimeError("blocked transaction changed; recollect before writing")
    if not unresolved:
        collector.checkpoint(run_dir / "live/unresolved.json", [])
        return None
    command = ["node", str(collector.ROOT / "scripts/read_chain.mjs"), "--progress-guard", args.address, args.account, json.dumps([row["tx"] for row in unresolved])]
    result = subprocess.run(command, capture_output=True, text=True, timeout=args.timeout)
    if result.returncode:
        raise RuntimeError("progress guard rejected: " + result.stderr[-1000:])
    proof = json.loads(result.stdout)
    collector.checkpoint(run_dir / "live/unresolved.json", unresolved)
    collector.checkpoint(run_dir / "live/progress-guard.json", dict(proof, scan_complete=True, entry_count=count, solvency=solvency))
    return {"transactions": [row["tx"] for row in unresolved], "scan_complete": True, "solvency_balanced": True,
            "scan_block_observation": proof["stored_block"], "provisional": True}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", default="corpus/live.json")
    ap.add_argument("--address", required=True)
    ap.add_argument("--account", required=True, help="expected public account address")
    ap.add_argument("--space", type=int, default=0)
    ap.add_argument("--run-dir", default="runs", help="isolated manifest, entries, receipts and diagnostics for this deployment")
    ap.add_argument("--max-rotations", type=int, default=3, help="leader replacements; initial validator count remains the network default")
    ap.add_argument("--limit", type=int, default=None, help="maximum NEW writes in this invocation")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--wait", type=int, default=300)
    ap.add_argument("--accept-diagnosed-timeouts", action="store_true", help="retain diagnosed consensus timeouts separately and continue; never count them as judged")
    ap.add_argument("--accept-diagnosed-no-execution", action="store_true", help="continue only past stored FINALIZED/IDLE/NOT_VOTED with complete absence diagnosis; never count as judged")
    ap.add_argument("--allow-known-unsettled-progress", action="store_true", help="opt in to independent writes with no supports only after complete absence scan, solvency and fresh empty pending queue; retain unresolved and provisional outcomes")
    args = ap.parse_args()
    root = collector.ROOT
    run_dir = Path(args.run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    seed = json.loads(Path(args.seed).read_text())
    manifest = run_dir / "bradbury.jsonl"
    if args.max_rotations < 0:
        raise ValueError("negative rotation limit")
    validate_manifest_target(manifest, args.address, args.max_rotations)
    records = run_dir / "records.jsonl"
    folder = run_dir / "live/entries"
    folder.mkdir(parents=True, exist_ok=True)
    existing = {row["envelope_hash"]: row for row in collector.load_manifest(manifest)} if manifest.exists() else {}
    collected = {json.loads(line)["tx"] for line in records.read_text().splitlines() if line.strip()} if records.exists() else set()
    failures_path = run_dir / "live/infrastructure-failures.json"
    failures = json.loads(failures_path.read_text()) if failures_path.exists() and (args.accept_diagnosed_timeouts or args.accept_diagnosed_no_execution) else []
    known_failures = {failure["tx"] for failure in failures if
        (args.accept_diagnosed_timeouts and (failure["status"] in collector.TIMEOUTS or failure.get("consensus_outcome") == "TIMEOUT")) or
        (args.accept_diagnosed_no_execution and failure.get("consensus_outcome") == "NOT_EXECUTED")}
    refused_path = run_dir / "live/refused.json"
    refused = json.loads(refused_path.read_text()) if refused_path.exists() else []
    prevented = {row["id"] for row in refused}
    unresolved_path = run_dir / "live/unresolved.json"
    retained = json.loads(unresolved_path.read_text()) if unresolved_path.exists() and args.allow_known_unsettled_progress else []
    retained_txs = {row["tx"] for row in retained}
    space = collector.read_call("", args.address, "get_space", [args.space], args.timeout)
    if space["owner"].lower() != args.account.lower():
        raise ValueError("space owner differs from expected account")
    for key in ("min_rounds", "write_bond", "challenge_bond", "cascade_depth", "admit_ttl"):
        if space[key] != seed["space"][key]:
            raise ValueError("live policy differs from seed on " + key)
    writes = 0
    for candidate in seed["entries"]:
        if candidate["id"] in prevented:
            continue
        env = {
            "version": "hearsay/1", "space_id": args.space,
            "claim": candidate["claim"], "source_url": candidate["source_url"],
            "entry_class": candidate["class"],
        }
        for key in ("supports", "author_note", "expects"):
            if candidate.get(key):
                env[key] = candidate[key]
        problems = collector.envtool.validate(env)
        if problems:
            raise ValueError(candidate["id"] + ": " + "; ".join(problems))
        fingerprint = collector.envtool.envelope_hash(env)
        path = folder / (candidate["id"] + ".json")
        collector.checkpoint(path, env)
        if fingerprint in existing:
            row = existing[fingerprint]
            if row["tx"] in collected or row["tx"] in known_failures:
                continue
            if args.allow_known_unsettled_progress:
                proof = prepare_progress_guard(args, run_dir, manifest, row["tx"])
                retained_txs.update(proof["transactions"])
                continue
        else:
            if args.limit is not None and writes >= args.limit:
                break
            count = int(collector.read_call("", args.address, "entry_count", [], args.timeout))
            bad_support = ""
            for entry_id in env.get("supports", []):
                if not isinstance(entry_id, int) or entry_id < 0 or entry_id >= count:
                    bad_support = "supports names an entry that does not exist"
                    break
                premise = collector.read_entry("", args.address, entry_id, args.timeout)
                if premise["space_id"] != args.space or premise["status"] != "ADMITTED":
                    bad_support = "support is not admitted in this space"
                    break
            if bad_support:
                refused.append({"id": candidate["id"], "class": candidate["class"], "refused_at": "write", "reason": bad_support, "envelope_hash": fingerprint, "consensus_rounds_spent": 0})
                collector.checkpoint(refused_path, refused)
                print(candidate["id"], "prevented before consensus", flush=True)
                continue
            request = {
                "address": args.address, "expected_account": args.account,
                "method": "write_entry", "value": str(space["write_bond"]),
                "args": [args.space, env["entry_class"], json.dumps(env, ensure_ascii=False)],
                "envelope_hash": fingerprint, "file": str(path), "id": candidate["id"],
                "consensus_max_rotations": args.max_rotations,
            }
            if args.allow_known_unsettled_progress and retained_txs:
                if env["entry_class"] not in collector.envtool.CLASSES or env.get("supports"):
                    raise RuntimeError("unsettled progress permits known independent input classes with no supports only")
                progress_guard = prepare_progress_guard(args, run_dir, manifest)
                if progress_guard:
                    request["progress_guard"] = progress_guard
                    retained_txs.update(progress_guard["transactions"])
            request_path = run_dir / "live/request.json"
            collector.checkpoint(request_path, request)
            result = subprocess.run(["node", str(root / "scripts/genlayer_write.mjs"), "--request", str(request_path), "--manifest", str(manifest)], capture_output=True, text=True)
            if result.returncode:
                collector.checkpoint(run_dir / "live/send-error.json", {"id": candidate["id"], "stdout": result.stdout, "stderr": result.stderr})
                raise RuntimeError("write failed; inspect the run's live/send-error.json before retrying")
            row = collector.load_manifest(manifest)[-1]
            existing[fingerprint] = row
            writes += 1
            print(candidate["id"], row["tx"], "submitted", flush=True)
        deadline = time.monotonic() + args.wait
        try:
            wait_for_settlement(row, args, run_dir, deadline)
        except RuntimeError:
            if not args.allow_known_unsettled_progress:
                raise
            prepare_progress_guard(args, run_dir, manifest, row["tx"])
            retained_txs.add(row["tx"])
            print(candidate["id"], "retained UNRESOLVED; guarded independent progress only", flush=True)
            continue
        while True:
            collection = subprocess.run([sys.executable, str(root / "scripts/collect_receipts.py"), str(manifest), "--address", args.address, "--entries", str(folder), "--out", str(records), "--raw-dir", str(run_dir / "receipts")], capture_output=True, text=True)
            diagnosis_command = [sys.executable, str(root / "scripts/diagnose_missing.py"), "--address", args.address, "--manifest", str(manifest), "--records", str(records), "--out", str(run_dir / "diagnosis.json")]
            for tx in sorted(known_failures | retained_txs):
                diagnosis_command += ["--exclude-tx", tx]
            diagnosis = subprocess.run(diagnosis_command, capture_output=True, text=True)
            issues_path = Path(str(records) + ".issues.json")
            issues = json.loads(issues_path.read_text()) if issues_path.exists() else {"scan_errors": ["no collection report"], "transactions": []}
            unexplained = [issue for issue in issues["transactions"] if issue["tx"] not in known_failures | retained_txs]
            if (args.accept_diagnosed_timeouts or args.accept_diagnosed_no_execution) and unexplained and not issues["scan_errors"]:
                diagnosis_data = json.loads((run_dir / "diagnosis.json").read_text())
                findings = diagnosis_data["transactions"]
                finding = next((item for item in findings if item["tx"] == row["tx"]), None)
                outcome = None
                if finding and args.accept_diagnosed_timeouts and finding["verdict"] == "CONSENSUS TIMEOUT":
                    outcome = "TIMEOUT"
                if finding and args.accept_diagnosed_no_execution and diagnosis_data.get("scan_complete") and finding["verdict"] == "FINALIZED WITHOUT EXECUTION":
                    outcome = collector.finalized_infrastructure_outcome(finding["receipt"])
                if outcome and all(issue["tx"] == row["tx"] for issue in unexplained):
                    failures.append({"id": candidate["id"], "tx": row["tx"], "envelope_hash": fingerprint, "entry_class": env["entry_class"], "status": finding["status"], "consensus_outcome": outcome, "reason": finding["reason"], "receipt": finding["receipt"]})
                    collector.checkpoint(failures_path, failures)
                    known_failures.add(row["tx"])
                    solvency = collector.read_call("", args.address, "solvency", [], args.timeout)
                    collector.checkpoint(run_dir / "live/solvency.json", solvency)
                    if not solvency.get("balanced"):
                        raise RuntimeError("solvency failed after infrastructure outcome; next write was not sent")
                    print(candidate["id"], finding["status"], "no judged state; retained as infrastructure outcome", flush=True)
                    break
            if (collection.returncode and (unexplained or issues["scan_errors"])) or diagnosis.returncode:
                # A real stored timeout can reopen between polling and the
                # collector's fresh read. Recollect only after this same tx
                # settles again, within the original bounded wait.
                if collection.returncode == 2 and diagnosis.returncode == 2 and unexplained and not issues["scan_errors"] and all(issue["tx"] == row["tx"] for issue in unexplained):
                    diagnosis_data = json.loads((run_dir / "diagnosis.json").read_text())
                    finding = next((item for item in diagnosis_data["transactions"] if item["tx"] == row["tx"]), None)
                    if finding and finding["verdict"] == "UNRESOLVED" and not diagnosis_data.get("scan_errors"):
                        fresh = collector.lookup_receipt(collector.EXPLORER, "", row["tx"], args.timeout)
                        status = collector.status_of(fresh)
                        if status in collector.STORED_STATUSES and status not in collector.TERMINAL:
                            print(candidate["id"], status, "reopened during collection; waiting on the same transaction", flush=True)
                            try:
                                wait_for_settlement(row, args, run_dir, deadline)
                            except RuntimeError:
                                if not args.allow_known_unsettled_progress:
                                    raise
                                proof = prepare_progress_guard(args, run_dir, manifest, row["tx"])
                                retained_txs.update(proof["transactions"])
                                print(candidate["id"], "retained UNRESOLVED after reopening; guarded independent progress only", flush=True)
                                break
                            continue
                print(collection.stdout + collection.stderr + diagnosis.stdout + diagnosis.stderr, flush=True)
                raise RuntimeError("collection or diagnosis unresolved; next write was not sent")
            solvency = collector.read_call("", args.address, "solvency", [], args.timeout)
            collector.checkpoint(run_dir / "live/solvency.json", solvency)
            if not solvency.get("balanced"):
                raise RuntimeError("solvency failed; next write was not sent")
            got = next(json.loads(line) for line in records.read_text().splitlines() if json.loads(line)["tx"] == row["tx"])
            print(candidate["id"], got["status"], "votes", got["votes"], "collected; solvency balanced", flush=True)
            collected.add(row["tx"])
            break
    print("new writes:", writes, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
