#!/usr/bin/env python3
"""Publish exact live lifecycle evidence, distinguishing acceptance from finality."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

import collect_receipts as collector
from steward_live import Campaign

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "runs/steward-http-oct23"
PUBLIC = ROOT / "web/steward-http-receipts"
META = ROOT / "deployments/bradbury-steward-http.json"


def validate_lifecycle(history, initial, state, challenge):
    by_id = {event["id"]: event for event in history}
    records = {r["entry_id"]: r for r in initial}
    if set(records) != {0, 1, 2, 3, 4} or any(records[i].get("supports") != [i - 1] for i in (2, 3, 4)):
        raise ValueError("initial four-entry dependency chain missing")
    bad, root = records[0], records[1]
    if (bad["status"] != "UNSOURCED" or root["status"] != "ADMITTED"
            or bad["claim"] != root["claim"] or bad["author"] != root["author"]
            or bad["source_url"] == root["source_url"]):
        raise ValueError("same-claim correction not established")
    if challenge["entry_id"] != 1 or challenge["outcome"] != "REJECTED":
        raise ValueError("review challenge did not have its intended outcome")
    expired = by_id["expire-root"]["after"]
    if expired["entries"][1]["status"] != "EXPIRED":
        raise ValueError("root expiry missing")
    if not all(expired["entries"][i]["status"] == "TAINTED" for i in (2, 3, 4)):
        raise ValueError("a deep descendant remained trusted")
    if expired["entries"][4]["stored_status"] != "ADMITTED":
        raise ValueError("outside-walk trust invalidation was not demonstrated")
    if not any(event["transaction"]["method"] == "process_deferred" for event in history):
        raise ValueError("deferred processing was not executed")
    direct = by_id["direct-rejudge-deep"]
    if (direct["before"]["entries"][4]["status"] != "TAINTED"
            or direct["before"]["entries"][4]["stored_status"] != "ADMITTED"
            or direct["after"]["entries"][4]["status"] != "ADMITTED"):
        raise ValueError("direct rejudge of an unswept admitted descendant not demonstrated")
    if state["deferred"] or not all(state["entries"][i]["status"] == "ADMITTED" for i in (1, 2, 3, 4)):
        raise ValueError("deferred completion/readmission missing")
    if by_id["rejudge-root"]["after"]["entries"][1]["status"] != "ADMITTED":
        raise ValueError("root rejudge did not readmit")
    if not state["solvency"]["balanced"]:
        raise ValueError("solvency failed")
    return {"wrong_source": "UNSOURCED", "same_claim_correction": "ADMITTED",
            "challenge": "REJECTED", "expired_root": "EXPIRED", "immediately_untrusted_descendants": 3,
            "outside_walk_stored_status": "ADMITTED", "outside_walk_trust_status": "TAINTED",
            "direct_unswept_rejudge": "ADMITTED", "deferred_remaining": 0, "surviving_dependents": 3,
            "root_rejudge": "ADMITTED", "queue_completion_path": "Direct rejudge of three tainted descendants, then bounded consumption of stale queue slots"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=RUN)
    parser.add_argument("--deployment", type=Path, default=META)
    parser.add_argument("--receipts-dir", type=Path, default=PUBLIC)
    parser.add_argument("--out", type=Path, default=ROOT / "web/steward-http-checkpoint.json")
    args = parser.parse_args()
    run, public, metadata = args.run_dir, args.receipts_dir, args.deployment
    prefix = public.name
    meta = json.loads(metadata.read_text())
    verification = subprocess.run(["node", "scripts/verify_steward_deployment.mjs", str(metadata)],
                                  cwd=ROOT, capture_output=True, text=True, timeout=120, check=True)
    public.mkdir(exist_ok=True)
    collector.checkpoint(public / "deployment-verification.json", json.loads(verification.stdout))
    manifest = [json.loads(line) for line in (run / "transactions.jsonl").read_text().splitlines() if line.strip()]
    transactions = []
    for row, receipt, error in collector.lookup_receipts(manifest, "", meta["rpc"], 45, workers=3):
        if error or receipt.get("status_basis") != "getTransactionAllData":
            raise RuntimeError("canonical receipt unavailable; keep the previous checkpoint: " + row["id"])
        collector.checkpoint(public / (row["id"] + ".json"), receipt)
        executed = collector.has_application_execution(receipt)
        known_batch_timeout = row["id"] == "deferred-00" and collector.is_consensus_timeout(receipt)
        if not executed and not known_batch_timeout:
            raise RuntimeError("successful stored execution absent: " + row["id"])
        transactions.append({"id": row["id"], "method": row["method"], "tx": row["tx"],
                             "status": collector.status_of(receipt), "result": receipt["resultName"],
                             "execution": receipt["txExecutionResultName"], "stored_block": receipt["stored_block"],
                             "last_vote_timestamp": receipt["lastVoteTimestamp"],
                             "successful_application_execution": executed,
                             "receipt": prefix + "/" + row["id"] + ".json"})
    intents = subprocess.run(["node", "scripts/verify_steward_intents.mjs", str(run), str(public)],
                             cwd=ROOT, capture_output=True, text=True, timeout=60, check=True)
    collector.checkpoint(public / "reviewed-intents.json", json.loads(intents.stdout))
    initial = [json.loads(line) for line in (run / "initial-records.jsonl").read_text().splitlines() if line.strip()]
    for record in initial:
        if not record.get("snapshot_verified") or not collector.gate.run_verify(record)[1]["reproduces"]:
            raise ValueError("initial receipt does not reproduce")
    history = json.loads((run / "lifecycle.json").read_text())
    c = Campaign(run, contract=meta["address"])
    state, challenge = c.snapshot(), c.call("get_challenge", [0])
    assertions = validate_lifecycle(history, initial, state, challenge)
    state["read_basis"] = "sequential latest-nonfinal application views"
    collector.checkpoint(public / "application-state.json", state)
    collector.checkpoint(public / "challenge.json", challenge)
    collector.checkpoint(public / "lifecycle.json", history)
    shutil.copyfile(run / "initial-records.jsonl", public / "initial-records.jsonl")
    complete = all(t["status"] == "FINALIZED" for t in transactions)
    meta["deployment_status"] = transactions[0]["status"]
    meta["lifecycle_verification"] = "finalized" if complete else "accepted-provisional"
    collector.checkpoint(metadata, meta)
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "complete": complete, "deployment": meta,
              "deployment_verification": prefix + "/deployment-verification.json",
              "reviewed_intents": prefix + "/reviewed-intents.json",
              "initial_records": prefix + "/initial-records.jsonl",
              "lifecycle": prefix + "/lifecycle.json", "application_state": prefix + "/application-state.json",
              "transactions": transactions, "assertions": assertions, "entry_count": len(state["entries"]),
              "diagnostics": "steward-diagnostics.json",
              "solvency": state["solvency"], "limitations": [
                  "Challenge rejected in the first referee stage; a second stage and upheld-challenge revocation are not claimed.",
                  "Five initial write records are a lifecycle demonstration, not a twenty-control attack-resistance benchmark.",
                  "Initial write receipts are preserved separately from later rejudged state.",
                  "Live completion used direct rejudge followed by bounded stale-slot processing; no successful queued AI batch is claimed.",
                  "Payment recovery is covered by native EVM tests and real GenVM adapter simulation; this lifecycle checkpoint does not claim an IC-to-vault withdrawal.",
                  "RPC timings do not establish the private cause of other validators' timeouts."]}
    if (public / "browser-replay.json").exists():
        browser = json.loads((public / "browser-replay.json").read_text())
        if not collector.gate.run_verify(browser)[1]["reproduces"]:
            raise ValueError("browser-downloaded receipt does not reproduce")
        report["browser_replay"] = {"file": prefix + "/browser-replay.json",
                                    "scope": "Current rejudged entry and canonical finalized initial-write receipt; not the initial entry state"}
    collector.checkpoint(args.out, report)
    print(json.dumps({"complete": complete, "assertions": assertions,
                      "transactions": [{k: t[k] for k in ("id", "status")} for t in transactions]}, indent=2))


if __name__ == "__main__":
    main()
