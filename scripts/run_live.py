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


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", default="corpus/live.json")
    ap.add_argument("--address", required=True)
    ap.add_argument("--account", required=True, help="expected public account address")
    ap.add_argument("--space", type=int, default=0)
    ap.add_argument("--limit", type=int, default=None, help="maximum NEW writes in this invocation")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--wait", type=int, default=300)
    ap.add_argument("--accept-diagnosed-timeouts", action="store_true", help="continue past explicitly saved consensus timeouts; never count them as judged")
    args = ap.parse_args()
    root = collector.ROOT
    seed = json.loads(Path(args.seed).read_text())
    manifest = root / "runs/bradbury.jsonl"
    records = root / "runs/records.jsonl"
    folder = root / "runs/live/entries"
    folder.mkdir(parents=True, exist_ok=True)
    existing = {row["envelope_hash"]: row for row in collector.load_manifest(manifest)} if manifest.exists() else {}
    collected = {json.loads(line)["tx"] for line in records.read_text().splitlines() if line.strip()} if records.exists() else set()
    failures_path = root / "runs/live/infrastructure-failures.json"
    failures = json.loads(failures_path.read_text()) if failures_path.exists() and args.accept_diagnosed_timeouts else []
    known_failures = {failure["tx"] for failure in failures if failure["status"] in collector.TIMEOUTS}
    refused_path = root / "runs/live/refused.json"
    refused = json.loads(refused_path.read_text()) if refused_path.exists() else []
    prevented = {row["id"] for row in refused}
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
            }
            request_path = root / "runs/live/request.json"
            collector.checkpoint(request_path, request)
            result = subprocess.run(["node", str(root / "scripts/genlayer_write.mjs"), "--request", str(request_path), "--manifest", str(manifest)], capture_output=True, text=True)
            if result.returncode:
                collector.checkpoint(root / "runs/live/send-error.json", {"id": candidate["id"], "stdout": result.stdout, "stderr": result.stderr})
                raise RuntimeError("write failed; inspect runs/live/send-error.json before retrying")
            row = collector.load_manifest(manifest)[-1]
            existing[fingerprint] = row
            writes += 1
            print(candidate["id"], row["tx"], "submitted", flush=True)
        deadline = time.monotonic() + args.wait
        while True:
            try:
                receipt = collector.fetch_receipt(collector.EXPLORER, row["tx"], args.timeout)
            except Exception as exc:
                collector.checkpoint(root / "runs/receipts" / (row["tx"] + ".json"), {"lookup_error": str(exc)})
                if time.monotonic() >= deadline:
                    raise RuntimeError("receipt lookup unavailable; resume with the same manifest") from exc
                time.sleep(4)
                continue
            collector.checkpoint(root / "runs/receipts" / (row["tx"] + ".json"), {"receipt": receipt})
            if collector.status_of(receipt) in collector.TERMINAL:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("receipt still settling; resume later using the same manifest")
            time.sleep(4)
        collection = subprocess.run([sys.executable, str(root / "scripts/collect_receipts.py"), str(manifest), "--address", args.address, "--entries", str(folder), "--out", str(records)], capture_output=True, text=True)
        diagnosis_command = [sys.executable, str(root / "scripts/diagnose_missing.py"), "--address", args.address, "--manifest", str(manifest), "--records", str(records), "--out", str(root / "runs/diagnosis.json")]
        for tx in sorted(known_failures):
            diagnosis_command += ["--exclude-tx", tx]
        diagnosis = subprocess.run(diagnosis_command, capture_output=True, text=True)
        issues_path = Path(str(records) + ".issues.json")
        issues = json.loads(issues_path.read_text()) if issues_path.exists() else {"scan_errors": ["no collection report"], "transactions": []}
        unexplained = [issue for issue in issues["transactions"] if issue["tx"] not in known_failures]
        if (collection.returncode and (unexplained or issues["scan_errors"])) or diagnosis.returncode:
            print(collection.stdout + collection.stderr + diagnosis.stdout + diagnosis.stderr, flush=True)
            raise RuntimeError("collection or diagnosis unresolved; next write was not sent")
        solvency = collector.read_call("", args.address, "solvency", [], args.timeout)
        collector.checkpoint(root / "runs/live/solvency.json", solvency)
        if not solvency.get("balanced"):
            raise RuntimeError("solvency failed; next write was not sent")
        got = next(json.loads(line) for line in records.read_text().splitlines() if json.loads(line)["tx"] == row["tx"])
        print(candidate["id"], got["status"], "votes", got["votes"], "collected; solvency balanced", flush=True)
        collected.add(row["tx"])
    print("new writes:", writes, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
