#!/usr/bin/env python3
"""Read-only, dated deployment and live-run checkpoint; never fabricates verdicts."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

import collect_receipts as collector
from steward_live import Campaign

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "runs/steward-live-oct23"
PUBLIC = ROOT / "web/steward-receipts"


def main():
    meta = json.loads((ROOT / "deployments/bradbury-steward.json").read_text())
    verified = subprocess.run(["node", "scripts/verify_steward_deployment.mjs"], cwd=ROOT,
                              capture_output=True, text=True, timeout=120, check=True)
    verification = json.loads(verified.stdout)
    PUBLIC.mkdir(exist_ok=True)
    collector.checkpoint(PUBLIC / "deployment-verification.json", verification)
    transactions = []
    for folder, prefix in [(RUN, "registry"), (RUN / "immutable", "immutable")]:
        manifest = folder / "transactions.jsonl"
        for line in manifest.read_text().splitlines():
            row = json.loads(line)
            receipt = collector.lookup_receipt(collector.EXPLORER, meta["rpc"], row["tx"], 45)
            if receipt.get("status_basis") != "getTransactionAllData":
                raise RuntimeError("canonical stored receipt unavailable; keep the previous checkpoint")
            name = prefix + "-" + row["id"] + ".json"
            collector.checkpoint(PUBLIC / name, receipt)
            item = {"id": prefix + "/" + row["id"], "method": row["method"], "tx": row["tx"],
                    "status": collector.status_of(receipt), "result": receipt.get("resultName"),
                    "execution": receipt.get("txExecutionResultName"),
                    "stored_block": receipt["stored_block"], "receipt": "steward-receipts/" + name}
            if row.get("file"):
                item["envelope"] = json.loads((ROOT / row["file"]).read_text())
            transactions.append(item)
    c = Campaign(RUN)
    state = c.snapshot()
    # These are current reads, individually observed, not an atomic historical
    # state snapshot. Receipts above each contain their exact pinned block.
    state["read_basis"] = "sequential latest-nonfinal application views"
    collector.checkpoint(PUBLIC / "application-state.json", state)
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "complete": False,
              "deployment": meta, "deployment_verification": "steward-receipts/deployment-verification.json",
              "application_state": "steward-receipts/application-state.json",
              "entry_count": len(state["entries"]), "solvency": state["solvency"],
              "transactions": transactions,
              "limitations": ["Deployment and controller binding are verified separately from live AI execution.",
                              "No live challenge/rejudge or bridge payout is claimed by this checkpoint.",
                              "Historical October 9 controls and video belong to the previous contract.",
                              "A protocol timeout is not UNSOURCED, INCONCLUSIVE or an attack rejection."]}
    if (RUN / "wrong-source-idle-0.receipt.json").exists():
        for name in ("wrong-source-idle-0.receipt.json", "wrong-source.recovery-simulation.json"):
            shutil.copyfile(RUN / name, PUBLIC / name)
        report["recovery"] = {
            "process_idleness": {"tx": "0xc4c468cff5414bc95aabfc07383c488134fd84eed68636fffaa875b1d5e6d5fa",
                                 "receipt": "steward-receipts/wrong-source-idle-0.receipt.json", "application_progress": False},
            "simulation": "steward-receipts/wrong-source.recovery-simulation.json", "paid_appeal_sent": False}
    collector.checkpoint(ROOT / "web/steward-checkpoint.json", report)
    print(json.dumps({"checked_at": report["checked_at"], "entry_count": report["entry_count"],
                      "transactions": [{k: r[k] for k in ("id", "status", "result")} for r in transactions]}, indent=2))


if __name__ == "__main__":
    main()
