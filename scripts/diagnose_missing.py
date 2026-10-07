#!/usr/bin/env python3
"""Explain missing Hearsay entries before another Bradbury write is submitted.

Ported from Suborn's diagnosis v2. Uses the collector's explorer and CLI reads.
Receipt status alone never proves why contract state is absent. A complete
scan is required to establish absence; read failures remain UNRESOLVED.

    python3 scripts/diagnose_missing.py --address 0xCONTRACT \
        --manifest runs/bradbury.jsonl --out runs/diagnosis.json

By default scans entry_count() entries. --scan limits that scan; a partial scan
cannot establish absence. --from-json uses the collector's offline cache shape.
"""

import argparse
import json
from pathlib import Path

import collect_receipts as collector


def dig(obj, *names):
    found = []
    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in names and child not in (None, "", [], {}):
                    found.append((key, child))
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(obj)
    return found


def diagnose(row, receipt, index, complete):
    hit = index.get(row["envelope_hash"])
    status = collector.status_of(receipt)
    if hit:
        verdict = "RECOVERABLE"
        reason = "matching envelope found on chain as entry %d" % hit["entry_id"]
    elif status in collector.TIMEOUTS:
        verdict = "CONSENSUS TIMEOUT"
        reason = "protocol validation/execution timed out; this is not a contract rejection"
    elif status in collector.FAILED:
        verdict = "FAILED ON CHAIN"
        reason = "receipt records a failed transaction; inspect its errors and execution trace"
    elif not complete:
        verdict = "UNRESOLVED"
        reason = "entry scan incomplete; absence has not been established"
    elif status in collector.TERMINAL:
        verdict = "SETTLED WITHOUT MATCHING STATE"
        reason = "complete scan found no matching entry; receipt alone does not establish the cause"
    else:
        verdict = "UNRESOLVED"
        reason = "transaction is still settling or receipt could not be read"
    return {
        "tx": row["tx"], "file": row.get("file", ""),
        "envelope_hash": row["envelope_hash"], "status": status,
        "verdict": verdict, "reason": reason,
        "recovered_as": hit["entry_id"] if hit else None,
        "recovered_record": hit,
        "errors": dig(receipt, "error", "errorMessage", "message", "revert_reason", "err"),
        "receipt": receipt,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--address", default="")
    ap.add_argument("--manifest", default=str(collector.ROOT / "runs" / "bradbury.jsonl"))
    ap.add_argument("--records", default=str(collector.ROOT / "runs" / "records.jsonl"))
    ap.add_argument("--explorer", default=collector.EXPLORER)
    ap.add_argument("--endpoint", default="")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--scan", type=int, default=None)
    ap.add_argument("--tx", action="append", default=[])
    ap.add_argument("--exclude-tx", action="append", default=[], help="already diagnosed protocol failures; kept in the report")
    ap.add_argument("--from-json", default="")
    ap.add_argument("--out", default=str(collector.ROOT / "runs" / "diagnosis.json"))
    args = ap.parse_args()
    rows = collector.load_manifest(args.manifest)
    collected = set()
    if Path(args.records).exists():
        collected = {json.loads(line)["tx"] for line in Path(args.records).read_text().splitlines() if line.strip()}
    targets = [row for row in rows if row["tx"] in args.tx] if args.tx else [row for row in rows if row["tx"] not in collected]
    excluded = [row["tx"] for row in targets if row["tx"] in args.exclude_tx]
    targets = [row for row in targets if row["tx"] not in args.exclude_tx]
    if not targets:
        collector.checkpoint(args.out, {"scan_complete": None, "scan_skipped": "all remaining manifest transactions already collected", "excluded_txs": excluded, "scan_errors": [], "transactions": []})
        print("0 missing transactions; %s" % args.out)
        return 0
    cache = json.loads(Path(args.from_json).read_text()) if args.from_json else None
    if cache is None and not args.address:
        ap.error("--address is required for chain reads")
    scan_errors, index, complete = [], {}, False
    if cache is not None:
        index = {value["entry"]["envelope_hash"]: value["entry"] for value in cache.values() if value.get("entry")}
        # Cached fixtures establish presence, not chain-wide absence.
    else:
        try:
            total = int(collector.read_call(args.endpoint, args.address, "entry_count", [], args.timeout))
            limit = total if args.scan is None else min(total, max(0, args.scan))
            index, scan_errors = collector.scan_entries(args.endpoint, args.address, args.timeout, count=limit)
            complete = limit == total and not scan_errors
        except Exception as exc:
            scan_errors.append({"error": str(exc)})

    results = []
    for row in targets:
        lookup_error = ""
        try:
            receipt = cache.get(row["tx"], {}).get("receipt") if cache is not None else collector.fetch_receipt(args.explorer, row["tx"], args.timeout)
        except Exception as exc:
            receipt, lookup_error = None, str(exc)
        result = diagnose(row, receipt, index, complete)
        result["lookup_error"] = lookup_error
        results.append(result)
        # Persist after every lookup, including unsuccessful ones.
        collector.checkpoint(args.out, {"scan_complete": complete, "excluded_txs": excluded, "scan_errors": scan_errors, "transactions": results})
        print("%s %s: %s" % (row["tx"][:14], result["verdict"], result["reason"]))
    collector.checkpoint(args.out, {"scan_complete": complete, "excluded_txs": excluded, "scan_errors": scan_errors, "transactions": results})
    unresolved = sum(result["verdict"] == "UNRESOLVED" for result in results)
    print("%d transactions checked, %d unresolved; %s" % (len(results), unresolved, args.out))
    return 2 if unresolved or scan_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
