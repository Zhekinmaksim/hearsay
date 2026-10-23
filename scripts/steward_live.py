#!/usr/bin/env python3
"""Resumable, sequential live correction/lifecycle run on explicit Phase 1.

Does not publish, alter fixtures, change consensus criteria or resend a saved
intent. Every next write needs successful stored consensus and matched state.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request

import collect_receipts as collector

ROOT = Path(__file__).resolve().parent.parent
ACCOUNT = "0x771388495f34d21c5574fefc04cd1d5811e00ada"
CONTRACT = "0xC51157f16406AD13527E1DBEa455374531Dd0396"
GENESIS = "0xef97917ce9bd9fa7d12ad6a8d81ea26c80ac1d727acc37cbb9799ae199788dc5"
RPC = "https://rpc-bradbury.genlayer.com"
TESCO = "https://find-and-update.company-information.service.gov.uk/company/00445790"
SAINSBURY = "https://find-and-update.company-information.service.gov.uk/company/00185647"


class Campaign:
    def __init__(self, folder, space_id=0):
        self.folder = folder
        self.space_id = space_id
        self.manifest = folder / "transactions.jsonl"
        self.events = folder / "lifecycle.json"
        self.history = json.loads(self.events.read_text()) if self.events.exists() else []

    def rpc(self, method, params):
        req = urllib.request.Request(RPC, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(), headers={"Content-Type": "application/json", "User-Agent": "Hearsay-deployment-preflight"})
        with urllib.request.urlopen(req, timeout=20) as response:
            result = json.load(response)
        if "error" in result:
            raise RuntimeError(result["error"])
        return result["result"]

    def call(self, method, args=None):
        return collector.read_call(RPC, CONTRACT, method, args or [], 45)

    def save(self, name, value):
        collector.checkpoint(self.folder / name, value)

    def rows(self):
        return [json.loads(line) for line in self.manifest.read_text().splitlines() if line.strip()]

    def send(self, identity, method, args, value=0, envelope=None):
        previous = next((row for row in self.rows() if row.get("id") == identity), None)
        if previous:
            return previous
        if any(row["id"] == identity for row in self.history):
            raise RuntimeError("missing manifest for an already recorded operation")
        if self.rpc("eth_getBlockByNumber", ["0x0", False])["hash"] != GENESIS:
            raise RuntimeError("wrong network genesis")
        pending = self.rpc("eth_getTransactionCount", [ACCOUNT, "pending"])
        if pending != self.rpc("eth_getTransactionCount", [ACCOUNT, "latest"]):
            raise RuntimeError("previous account transaction remains pending")
        request = {"id": identity, "method": method, "address": CONTRACT,
                   "expected_account": ACCOUNT, "expected_nonce": int(pending, 16),
                   "expected_genesis": GENESIS, "max_fee_wei": "50000000000000000",
                   "args": args, "value": str(value), "consensus_max_rotations": 3}
        if envelope:
            entry_path = self.folder / (identity + ".entry.json")
            self.save(entry_path.name, envelope)
            request.update(envelope_hash=collector.envtool.envelope_hash(envelope), file=str(entry_path))
        request_path = self.folder / (identity + ".request.json")
        self.save(request_path.name, request)
        output = subprocess.run(["node", "scripts/genlayer_write.mjs", "--request", str(request_path), "--manifest", str(self.manifest)], cwd=ROOT, capture_output=True, text=True, timeout=120)
        (self.folder / (identity + ".send.log")).write_text(output.stdout + output.stderr)
        if output.returncode:
            raise RuntimeError(identity + " send stopped; reconcile its public broadcast journal")
        row = next(row for row in self.rows() if row.get("id") == identity)
        print(identity, row["tx"], "submitted once", flush=True)
        return row

    def wait(self, row):
        deadline, last = time.monotonic() + 1200, None
        while True:
            receipt = collector.lookup_receipt(collector.EXPLORER, RPC, row["tx"], 45)
            self.save(row["id"] + ".receipt.json", receipt)
            status = collector.status_of(receipt)
            if status != last:
                print(row["id"], status, flush=True)
                last = status
            if collector.has_application_execution(receipt):
                return receipt
            if status in collector.FAILED | collector.TIMEOUTS | {"FINALIZED", "UNDETERMINED"}:
                raise RuntimeError(row["id"] + " did not establish successful application execution: " + status)
            if time.monotonic() >= deadline:
                raise RuntimeError(row["id"] + " still settling; resume this same manifest")
            time.sleep(12)

    def snapshot(self):
        return {"checked_at": datetime.now(timezone.utc).isoformat(),
                "space": self.call("get_space", [self.space_id]), "solvency": self.call("solvency"),
                "deferred": self.call("deferred_queue"),
                "entries": [self.call("get_entry", [i]) for i in range(self.call("entry_count"))]}

    def record(self, identity, row, receipt, before, after):
        event = {"id": identity, "transaction": row, "receipt": receipt, "before": before, "after": after}
        self.history = [item for item in self.history if item["id"] != identity] + [event]
        self.save(self.events.name, self.history)
        return after

    def step(self, identity, method, args, value=0):
        previous = next((item for item in self.history if item["id"] == identity), None)
        if previous:
            self.wait(previous["transaction"])
            return previous["after"]
        before = self.snapshot()
        row = self.send(identity, method, args, value)
        receipt = self.wait(row)
        after = self.snapshot()
        return self.record(identity, row, receipt, before, after)

    def entry(self, identity, claim, url, supports=None, entry_class="honest"):
        envelope = {"version": "hearsay/1", "space_id": self.space_id, "entry_class": entry_class, "claim": claim, "source_url": url}
        if supports:
            envelope["supports"] = supports
        row = self.send(identity, "write_entry", [self.space_id, entry_class, json.dumps(envelope, sort_keys=True, separators=(",", ":"))], 1000, envelope)
        self.wait(row)
        saved = self.folder / (identity + ".record.json")
        if saved.exists():
            record = json.loads(saved.read_text())
            if record.get("tx") != row["tx"] or record.get("envelope_hash") != collector.envtool.envelope_hash(envelope):
                raise RuntimeError("saved initial record differs from the reviewed intent")
            # Lifecycle calls change entry state. Never recollect the new state
            # and attribute it to the initial write's transaction.
            return record
        if self.history:
            raise RuntimeError("initial record absent after lifecycle mutations; recover the original evidence first")
        command = [sys.executable, "scripts/collect_receipts.py", str(self.manifest), "--address", CONTRACT,
                   "--endpoint", RPC, "--out", str(self.folder / "records.jsonl"), "--raw-dir", str(self.folder / "receipts"), "--wait", "0"]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=180)
        (self.folder / (identity + ".collection.log")).write_text(result.stdout + result.stderr)
        records = [json.loads(line) for line in (self.folder / "records.jsonl").read_text().splitlines() if line.strip()]
        matches = [record for record in records if record.get("tx") == row["tx"]]
        if len(matches) != 1:
            subprocess.run([sys.executable, "scripts/diagnose_missing.py", "--address", CONTRACT,
                            "--manifest", str(self.manifest), "--records", str(self.folder / "records.jsonl"),
                            "--out", str(self.folder / (identity + ".diagnosis.json"))], cwd=ROOT, timeout=180, check=True)
            raise RuntimeError(identity + " missing matched entry; no next write")
        verified_path = self.folder / "verified-records.jsonl"
        enriched = subprocess.run([sys.executable, "scripts/enrich_snapshots.py", "--records", str(self.folder / "records.jsonl"), "--out", str(verified_path)], cwd=ROOT, capture_output=True, text=True, timeout=300)
        (self.folder / (identity + ".enrichment.log")).write_text(enriched.stdout + enriched.stderr)
        if enriched.returncode:
            raise RuntimeError(identity + " source recovery stopped; no next write")
        record = next(json.loads(line) for line in verified_path.read_text().splitlines()
                      if json.loads(line).get("tx") == row["tx"])
        if not record.get("snapshot_verified"):
            raise RuntimeError(identity + " source pin not verified; enrich before continuing")
        print(identity, "entry", record["entry_id"], record["status"], record.get("votes"), flush=True)
        self.save(identity + ".record.json", record)
        return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", default="runs/steward-live-oct23")
    parser.add_argument("--space", type=int, default=0)
    parser.add_argument("--profile", choices=("registry", "immutable"), default="registry")
    args = parser.parse_args()
    c = Campaign(Path(args.run_dir), args.space)
    opening = next(row for row in c.rows() if row.get("id") == "review-open-space")
    c.wait(opening)
    if args.profile == "immutable":
        source_a = "https://raw.githubusercontent.com/python/cpython/v3.12.0/README.rst"
        source_b = "https://raw.githubusercontent.com/nodejs/node/v20.0.0/README.md"
        claim = "The CPython v3.12.0 README identifies the Python version as 3.12.0."
        combination = "The CPython README identifies Python version 3.12.0, and the Node.js v20.0.0 README describes Node.js as an open-source cross-platform JavaScript runtime."
        independent = "The Node.js v20.0.0 README describes Node.js as an open-source cross-platform JavaScript runtime environment."
        second_claim = "The Node.js v20.0.0 README says that the project uses an open governance model."
        third_claim = "The Node.js v20.0.0 README says that the OpenJS Foundation provides support for the project."
        ground = "The pinned CPython README says that this is Python version 2.7 rather than Python version 3.12.0."
    else:
        source_a, source_b = SAINSBURY, TESCO
        claim = "Companies House lists J SAINSBURY PLC (company number 00185647) as an active public limited company."
        combination = "Both J SAINSBURY PLC and TESCO PLC are listed as active public limited companies by Companies House."
        independent = "Companies House lists TESCO PLC as an active public limited company."
        second_claim = "Companies House records 27 November 1947 as the incorporation date of TESCO PLC."
        third_claim = "Companies House gives AL7 1GA as the registered office postcode of TESCO PLC."
        ground = "The cited snapshot lists J SAINSBURY PLC as Dissolved rather than Active."
    bad = c.entry("wrong-source", claim, source_b, entry_class="source_forgery")
    if bad["status"] not in ("UNSOURCED", "INCONCLUSIVE"):
        raise RuntimeError("wrong source unexpectedly admitted or contradicted; inspect evidence")
    root = c.entry("corrected-source", claim, source_a)
    if root["status"] != "ADMITTED":
        raise RuntimeError("corrected authoritative claim not admitted")
    a = root["entry_id"]
    dependent = c.entry("dependent-combination", combination, source_b, [a])
    if dependent["status"] != "ADMITTED":
        dependent = c.entry("dependent-independent", independent, source_b, [a])
    if dependent["status"] != "ADMITTED":
        raise RuntimeError("first dependent not admitted")
    second = c.entry("dependent-incorporation", second_claim, source_b, [dependent["entry_id"]])
    if second["status"] != "ADMITTED":
        raise RuntimeError("second dependent not admitted")
    third = c.entry("dependent-number", third_claim, source_b, [second["entry_id"]])
    if third["status"] != "ADMITTED":
        raise RuntimeError("third dependent not admitted")
    shutil.copyfile(c.folder / "verified-records.jsonl", c.folder / "initial-records.jsonl")
    c.save("before-lifecycle.json", c.snapshot())
    # Deliberately invalid objection: this tests rejection, not a manufactured
    # successful challenge against a correctly sourced claim.
    challenged = c.step("challenge", "challenge", [a, ground], 2000)
    cid = len([row for row in c.rows() if row.get("method") == "challenge"]) - 1
    challenge = c.call("get_challenge", [cid])
    if challenge["entry_id"] != a or challenge["challenger"].lower() != ACCOUNT.lower() or challenge["ground"] != ground:
        raise RuntimeError("challenge id does not match this campaign; reconcile before confirming")
    c.save("challenge-outcome.json", challenge)
    if challenge["outcome"] == "PENDING":
        c.step("confirm-challenge", "confirm_challenge", [cid])
        challenge = c.call("get_challenge", [cid])
        c.save("challenge-outcome.json", challenge)
    if challenge["outcome"] != "REJECTED":
        raise RuntimeError("unexpected challenge success; inspect before proceeding")
    expired = c.step("expire-root", "expire", [a])
    if expired["entries"][a]["status"] != "EXPIRED":
        raise RuntimeError("expiry not reflected")
    for row in (dependent, second, third):
        if expired["entries"][row["entry_id"]]["status"] != "TAINTED":
            raise RuntimeError("deep dependent remained trusted")
    for i in range(12):
        if not c.call("deferred_queue"):
            break
        c.step("deferred-%02d" % i, "process_deferred", [1])
    if c.call("deferred_queue"):
        raise RuntimeError("deferred queue did not complete within the planned bound")
    rejudged = c.step("rejudge-root", "rejudge", [a])
    if rejudged["entries"][a]["status"] != "ADMITTED":
        raise RuntimeError("root rejudgement did not readmit the authoritative claim")
    c.save("after-lifecycle.json", c.snapshot())
    print("LIVE LIFECYCLE EXECUTED; receipts remain provisional until canonical finalization", flush=True)


if __name__ == "__main__":
    main()
