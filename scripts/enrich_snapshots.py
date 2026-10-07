#!/usr/bin/env python3
"""Recover pinned source bytes from GenVM traces and verify complete receipts."""
import argparse
import json
from pathlib import Path
import subprocess

import collect_receipts as collector


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--records", default="runs/records.jsonl")
    ap.add_argument("--out", default="runs/verified-records.jsonl")
    args = ap.parse_args()
    path = Path(args.records)
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    for row in records:
        if row.get("snapshot_verified"):
            code, _ = collector.gate.run_verify(row)
            if code:
                raise ValueError("previously verified receipt no longer reproduces")
            continue
        result = subprocess.run(["node", str(collector.ROOT / "scripts/read_chain.mjs"), row["tx"], "--snapshot", row["snapshot_hash"]], capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise RuntimeError("snapshot recovery failed for %s: %s" % (row["id"], result.stderr[-800:]))
        snapshot = json.loads(result.stdout)
        row["snapshot_excerpt"] = snapshot.pop("snapshot_excerpt")
        row["snapshot_verified"] = True
        row["snapshot_provenance"] = snapshot
        code, verification = collector.gate.run_verify(row)
        if code:
            raise ValueError("complete receipt does not reproduce: " + json.dumps(verification))
        collector.atomic_write(args.out, "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
        print(row["id"], "snapshot and votes verified", flush=True)
    collector.atomic_write(args.out, "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
    print("%d full receipts verified" % len(records))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
