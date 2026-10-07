#!/usr/bin/env python3
"""Verify collected live records against state and build a separate public page."""
import argparse
from collections import Counter
import html
import json
from pathlib import Path

import collect_receipts as collector


def escape(value):
    return html.escape(str(value), quote=True)


def refresh_record(row, address):
    """Do not publish an admission rolled back by a later consensus round."""
    current = collector.read_entry("", address, row["entry_id"], 30)
    if not current:
        raise ValueError("entry disappeared before publication: " + row["id"])
    for key in ("envelope_hash", "snapshot_hash", "space_id", "claim", "source_url",
                "entry_class", "supports", "status", "votes", "rounds", "bond", "bond_state"):
        if current.get(key) != row.get(key):
            raise ValueError("chain state changed before publication: %s (%s)" % (row["id"], key))
    receipt = collector.lookup_receipt(collector.EXPLORER, "", row["tx"], 30)
    status = collector.status_of(receipt)
    if status not in {"FINALIZED", "ACCEPTED", "SUCCESS"}:
        raise ValueError("consensus no longer accepted: %s (%s)" % (row["id"], status))
    refreshed = dict(row, receipt_status=status)
    refreshed["consensus_checkpoint"] = {
        "status": status, "result": receipt.get("resultName"),
        "chain_timestamp": receipt.get("currentTimestamp"),
    }
    return refreshed


def build_page(corpus):
    root = collector.ROOT
    template = (root / "web/live-template.html").read_text()
    library = "\n".join(line for line in (root / "web/lib.mjs").read_text().splitlines() if not line.startswith("export {"))
    rows = []
    for index, row in enumerate(corpus["entries"]):
        votes = row["votes"]
        rows.append('<tr data-class="%s"><td>%s<details><summary>Source and envelope</summary><p><a href="%s">%s</a></p><p class="hash">Envelope %s</p><p class="hash">Snapshot %s</p><p>%s</p></details></td><td class="status">%s<br><button data-replay="%d">Replay</button></td><td class="votes">%s / %s</td><td class="votes">%s</td><td><a href="%s/tx/%s">%s</a></td></tr>' % (
            escape(row["entry_class"]), escape(row["claim"]), escape(row["source_url"]), escape(row["source_url"]), escape(row["envelope_hash"]), escape(row["snapshot_hash"]), escape(row["note"]), escape(row["status"]), index, escape(votes["a"]), escape(votes["b"]), escape(votes["conflict"]), collector.EXPLORER, escape(row["tx"]), escape(row["receipt_status"])))
    classes = []
    for item in corpus["report"]["classes"]:
        classes.append('<tr><td>%s</td><td>%d</td><td>%d</td><td>%d/1000</td><td>%d</td></tr>' % (escape(item["class"]), item["attempts"], item["ever_admitted"], item["admission_rate_milli"], item["inconclusive"]))
    refused = ''.join('<p class="note"><strong>%s</strong> · %s · %s · 0 consensus rounds</p>' % (escape(row["id"]), escape(row["class"]), escape(row["reason"])) for row in corpus["refused_at_write"]) or '<p class="empty">None.</p>'
    infrastructure = ''.join('<p class="note flag"><strong>%s</strong> · %s · <a href="%s/tx/%s">Receipt</a><br>%s</p>' % (escape(row["id"]), escape(row["status"]), collector.EXPLORER, escape(row["tx"]), escape(row["reason"])) for row in corpus.get("infrastructure_failures", [])) or '<p class="empty">None.</p>'
    options = ''.join('<option value="%s">%s</option>' % (escape(item["class"]), escape(item["class"])) for item in corpus["report"]["classes"])
    report, policy = corpus["report"], corpus["policy"]
    replacements = {
        "DATE": "7 October 2026", "LEAD": "%d of %d judged honest entries were admitted. False rejections lead the record, followed by admission rates for each attack class." % (report["honest_admitted"], report["honest_attempts"]),
        "FALSE_RATE": "%d/1000" % report["false_rejection_milli"],
        "FALSE_COUNT": "%d of %d honest entries refused." % (report["honest_attempts"] - report["honest_admitted"], report["honest_attempts"]),
        "JUDGED": str(len(corpus["entries"])), "PREVENTED": str(len(corpus["refused_at_write"])),
        "HEALTH_WARNING": escape(corpus["health_warning"]),
        "RULES": escape("%s · support round floor %d · cascade depth %d · admission lifetime %d sequence units. %s" % (policy["name"], policy["min_rounds"], policy["cascade_depth"], policy["admit_ttl"], policy["policy"])),
        "CONTRACT_URL": collector.EXPLORER + "/address/" + corpus["contract_address"],
        "DEPLOY_TX_URL": collector.EXPLORER + "/tx/" + corpus["deployment_tx"],
        "CLASSES": ''.join(classes), "ROWS": ''.join(rows), "REFUSED": refused,
        "INFRASTRUCTURE": infrastructure,
        "OPTIONS": options, "BALANCED": str(corpus["solvency"]["balanced"]).lower(),
        "LIB": library, "DATA": json.dumps(corpus, ensure_ascii=False).replace("</", "<\\/"),
    }
    for key, value in replacements.items():
        template = template.replace("/*__" + key + "__*/", value)
    return template


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--address", required=True)
    ap.add_argument("--space", type=int, default=0)
    ap.add_argument("--seed", default="corpus/live.json")
    ap.add_argument("--records", default="runs/verified-records.jsonl")
    args = ap.parse_args()
    seed = json.loads(Path(args.seed).read_text())
    rows = [json.loads(line) for line in Path(args.records).read_text().splitlines() if line.strip()]
    refused_path = collector.ROOT / "runs/live/refused.json"
    refused = json.loads(refused_path.read_text()) if refused_path.exists() else []
    failures_path = collector.ROOT / "runs/live/infrastructure-failures.json"
    infrastructure_history = json.loads(failures_path.read_text()) if failures_path.exists() else []
    collected_hashes = {row["envelope_hash"] for row in rows}
    failures = [failure for failure in infrastructure_history if failure["envelope_hash"] not in collected_hashes]
    if len(rows) + len(refused) + len(failures) != len(seed["entries"]):
        raise ValueError("live run is incomplete; nothing published")
    if len({row["envelope_hash"] for row in rows}) != len(rows):
        raise ValueError("duplicate envelope hashes")
    expected = set()
    for candidate in seed["entries"]:
        envelope = {"version": "hearsay/1", "space_id": args.space, "claim": candidate["claim"], "source_url": candidate["source_url"], "entry_class": candidate["class"]}
        for key in ("supports", "author_note", "expects"):
            if candidate.get(key):
                envelope[key] = candidate[key]
        expected.add(collector.envtool.envelope_hash(envelope))
    if expected != {row["envelope_hash"] for row in rows + refused + failures}:
        raise ValueError("collected cohort differs from the submitted candidates")
    report = collector.read_call("", args.address, "report", [args.space], 30)
    policy = collector.read_call("", args.address, "get_space", [args.space], 30)
    solvency = collector.read_call("", args.address, "solvency", [], 30)
    if report["entries"] != len(rows) or not solvency["balanced"]:
        raise ValueError("collected records disagree with chain count or solvency")
    honest = [row for row in rows if row["entry_class"] == "honest"]
    if len(honest) < 20 or len(honest) != report["honest_attempts"]:
        raise ValueError("honest control group incomplete")
    if sum(row["status"] == "ADMITTED" for row in honest) != report["honest_admitted"]:
        raise ValueError("honest admissions disagree with chain report")
    counts = Counter(row["entry_class"] for row in rows)
    if counts != {item["class"]: item["attempts"] for item in report["classes"]}:
        raise ValueError("class counts disagree with chain report")
    for row in rows:
        if not row.get("snapshot_verified") or "snapshot_excerpt" not in row:
            raise ValueError("snapshot bytes have not been verified for " + row["id"])
        code, result = collector.gate.run_verify(dict(row, min_rounds=policy["min_rounds"]))
        if code:
            raise ValueError("unreproducible record: " + json.dumps(result))
    rows = [refresh_record(row, args.address) for row in rows]
    metadata = json.loads((collector.ROOT / "deployments/bradbury.json").read_text())
    if metadata["address"].lower() != args.address.lower():
        raise ValueError("deployment metadata target mismatch")
    corpus = {
        "run": "bradbury", "contract_address": args.address,
        "deployment_tx": metadata["deployment_tx"], "space_id": args.space,
        "health_warning": "Verdicts were collected from consensus state. Accepted receipts remain provisional until finalization. Pinned source bytes were recovered from GenVM traces and hash-checked against contract state. All controls use one registry.",
        "policy": policy, "entries": rows, "refused_at_write": refused,
        "infrastructure_failures": failures,
        "infrastructure_history": infrastructure_history,
        "report": report, "solvency": solvency,
    }
    collector.checkpoint(collector.ROOT / "web/live-corpus.json", corpus)
    collector.atomic_write(collector.ROOT / "web/live.html", build_page(corpus))
    print("published %d real records, %d prevented, %d honest; false rejection %d/1000" % (len(rows), len(refused), len(honest), report["false_rejection_milli"]))


if __name__ == "__main__":
    raise SystemExit(main())
