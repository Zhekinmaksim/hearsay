#!/usr/bin/env python3
"""Write a verified, explicitly incomplete checkpoint to an explicit output path.

Reads chain state only. Does not submit transactions or generate a website.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re

import collect_receipts as collector
import publish_live as publisher


def candidate_envelope(candidate, space):
    envelope = {"version": "hearsay/1", "space_id": space, "claim": candidate["claim"],
                "source_url": candidate["source_url"], "entry_class": candidate["class"]}
    for key in ("supports", "author_note", "expects"):
        if candidate.get(key):
            envelope[key] = candidate[key]
    problems = collector.envtool.validate(envelope)
    if problems:
        raise ValueError("invalid seed envelope: " + "; ".join(problems))
    return envelope


def canonical_receipt(receipt, transaction, address):
    if not isinstance(receipt, dict):
        raise ValueError("receipt lacks canonical stored consensus evidence")
    stored = receipt.get("stored_receipt") if isinstance(receipt, dict) else None
    if receipt.get("status_basis") != "getTransactionAllData" or not isinstance(stored, dict):
        raise ValueError("receipt lacks canonical stored consensus evidence")
    if receipt.get("consensus_version") != "2.0.0":
        raise ValueError("receipt lacks verified consensus version 2.0.0")
    status = stored.get("status")
    if isinstance(status, bool) or not isinstance(status, int) or not 0 <= status < len(collector.STORED_STATUSES):
        raise ValueError("invalid stored consensus status")
    if (stored.get("id") or "").lower() != transaction["tx"].lower():
        raise ValueError("stored receipt transaction ID mismatch")
    if (stored.get("recipient") or "").lower() != address.lower():
        raise ValueError("receipt belongs to another deployment")
    if transaction.get("sender") and (stored.get("sender") or "").lower() != transaction["sender"].lower():
        raise ValueError("stored receipt sender mismatch")
    return collector.status_of(receipt)


def receipt_summary(receipt):
    result = publisher.public_infrastructure({"receipt": receipt})["receipt_summary"]
    result.update(status=collector.status_of(receipt), status_basis="getTransactionAllData",
                  consensus_version=receipt.get("consensus_version"), stored_status_code=receipt["stored_receipt"]["status"],
                  stored_block=receipt.get("stored_block"), initial_validators=receipt.get("numOfInitialValidators"),
                  round_array_index=receipt.get("numOfRounds"),
                  projected_status=(receipt.get("projected_receipt") or {}).get("statusName"))
    return result


def build_checkpoint(seed, metadata, manifest, rows, history, refused, *, space=0, endpoint="", timeout=30):
    address = metadata.get("address", "")
    if not re.fullmatch(r"0x[0-9a-fA-F]{40}", address) or metadata.get("chain_id") != 4221:
        raise ValueError("invalid Bradbury deployment metadata")
    candidates = {}
    for candidate in seed["entries"]:
        envelope = candidate_envelope(candidate, space)
        fingerprint = collector.envtool.envelope_hash(envelope)
        if fingerprint in candidates or any(item["id"] == candidate["id"] for item in candidates.values()):
            raise ValueError("duplicate seed candidate")
        candidates[fingerprint] = dict(candidate, envelope=envelope)
    transactions, submitted = {}, set()
    for transaction in manifest:
        if transaction.get("address", "").lower() != address.lower():
            raise ValueError("manifest belongs to another deployment")
        rotations = (metadata.get("protocol") or {}).get("max_rotations")
        if rotations is not None and transaction.get("consensus_max_rotations", 3) != rotations:
            raise ValueError("manifest rotation limit differs from deployment metadata")
        fingerprint = transaction["envelope_hash"]
        if fingerprint not in candidates or transaction.get("id", candidates[fingerprint]["id"]) != candidates[fingerprint]["id"]:
            raise ValueError("manifest differs from seed")
        if transaction["tx"] in transactions or fingerprint in submitted:
            raise ValueError("duplicate submitted transaction or candidate")
        transactions[transaction["tx"]] = transaction
        submitted.add(fingerprint)
    recorded = {}
    for row in rows:
        if row["tx"] not in transactions or row["tx"] in recorded:
            raise ValueError("record is duplicated or absent from this deployment manifest")
        if row["envelope_hash"] != transactions[row["tx"]]["envelope_hash"]:
            raise ValueError("record and manifest envelope hashes differ")
        if row.get("envelope") != candidates[row["envelope_hash"]]["envelope"]:
            raise ValueError("record envelope differs from seed")
        recorded[row["tx"]] = row
    for failure in history:
        transaction = transactions.get(failure.get("tx"))
        if not transaction or failure.get("envelope_hash") != transaction["envelope_hash"]:
            raise ValueError("infrastructure history belongs to another cohort")
    prevented = set()
    for item in refused:
        fingerprint = item.get("envelope_hash")
        if fingerprint not in candidates or fingerprint in submitted or fingerprint in prevented or item.get("id") != candidates[fingerprint]["id"]:
            raise ValueError("refused candidate differs from cohort")
        prevented.add(fingerprint)

    policy = collector.read_call(endpoint, address, "get_space", [space], timeout)
    for key in ("min_rounds", "write_bond", "challenge_bond", "cascade_depth", "admit_ttl"):
        if policy[key] != seed["space"][key]:
            raise ValueError("space policy differs from seed: " + key)
    count = int(collector.read_call(endpoint, address, "entry_count", [], timeout))
    index, errors = collector.scan_entries(endpoint, address, timeout, count=count)
    if errors or len(index) != count:
        raise ValueError("entry scan incomplete; absence cannot be established")
    receipts = {}
    verified, failures, unresolved = [], [], []
    for transaction in manifest:
        try:
            receipt = collector.lookup_receipt(collector.EXPLORER, endpoint, transaction["tx"], timeout)
            status = canonical_receipt(receipt, transaction, address)
            protocol = metadata.get("protocol") or {}
            for field, expected in (("numOfInitialValidators", protocol.get("initial_validators")), ("initialRotations", protocol.get("max_rotations"))):
                if expected is not None and str(receipt["stored_receipt"].get(field)) != str(expected):
                    raise ValueError("stored protocol parameters differ from deployment metadata")
        except RuntimeError as error:
            if transaction["tx"] in recorded:
                raise
            unresolved.append({"id": candidates[transaction["envelope_hash"]]["id"], "tx": transaction["tx"],
                               "envelope_hash": transaction["envelope_hash"], "status": "UNKNOWN", "diagnosis": "UNRESOLVED", "reason": str(error)})
            continue
        receipts[transaction["tx"]] = receipt
        fingerprint = transaction["envelope_hash"]
        candidate = candidates[fingerprint]
        current = index.get(fingerprint)
        if transaction["tx"] in recorded:
            row = recorded[transaction["tx"]]
            if not current or any(row.get(key) != value for key, value in current.items()):
                raise ValueError("current entry changed or disappeared: " + row["id"])
            if not row.get("snapshot_verified") or not isinstance(row.get("snapshot_excerpt"), str):
                raise ValueError("snapshot bytes unverified: " + row["id"])
            provenance = row.get("snapshot_provenance") or {}
            provenance_tx = provenance.get("trace_transaction_id")
            if provenance.get("source") == "getTransactionAllData.eqBlocksOutputs":
                provenance_tx = provenance.get("transaction_id")
                if provenance.get("eq_block_index") != 0 or not provenance.get("stored_block"):
                    raise ValueError("invalid stored equivalence snapshot provenance")
            if row["snapshot_excerpt"] and provenance_tx != row["tx"]:
                raise ValueError("snapshot trace belongs to another transaction")
            verification = dict(row, min_rounds=policy["min_rounds"])
            code, result = collector.gate.run_verify(verification)
            if code:
                raise ValueError("snapshot or votes do not reproduce: " + json.dumps(result))
            if verification.get("rounds_detail") is not None:
                vote_answers = collector.gate._from_votes(verification["votes"])
                details = verification["rounds_detail"]
                if not isinstance(details, dict) or any(type(details.get(key, default)) != type(vote_answers.get(key, default)) or details.get(key, default) != vote_answers.get(key, default)
                        for key, default in (("support_a", None), ("support_b", None), ("conflict", -1), ("fetched", True))):
                    raise ValueError("round answers disagree with stored votes")
            if not collector.has_application_execution(receipt):
                raise ValueError("record no longer has accepted stored consensus")
            # Reuse the live publisher's fresh current-entry/receipt guards.
            refreshed = publisher.refresh_record(row, address)
            refreshed["receipt_status"] = status
            refreshed["consensus_checkpoint"] = receipt_summary(receipt)
            verified.append(refreshed)
            continue
        item = {"id": candidate["id"], "tx": transaction["tx"], "envelope_hash": fingerprint,
                "entry_class": candidate["class"], "status": status, "receipt_summary": receipt_summary(receipt)}
        outcome = collector.finalized_infrastructure_outcome(receipt)
        if outcome and current is None:
            item.update(consensus_outcome=outcome, diagnosis="CONSENSUS TIMEOUT" if outcome == "TIMEOUT" else "FINALIZED WITHOUT EXECUTION",
                        reason="Finalized protocol outcome %s; complete entry scan found no matching state. This is not a contract rejection." % outcome)
            failures.append(item)
        else:
            reason = "matching entry awaits verified snapshot record" if current else "no matching entry; stored consensus has not established a final timeout"
            item.update(diagnosis="UNRESOLVED", reason=reason, matching_entry_id=current.get("entry_id") if current else None)
            unresolved.append(item)
    for item in refused:
        supports = candidates[item["envelope_hash"]]["envelope"].get("supports", [])
        by_id = {entry["entry_id"]: entry for entry in index.values()}
        if not any(dep not in by_id or by_id[dep]["space_id"] != space or by_id[dep]["status"] != "ADMITTED" for dep in supports):
            raise ValueError("write refusal cannot be reproduced from support constraints")
    report = collector.read_call(endpoint, address, "report", [space], timeout)
    solvency = collector.read_call(endpoint, address, "solvency", [], timeout)
    if not solvency.get("balanced") or count != int(collector.read_call(endpoint, address, "entry_count", [], timeout)):
        raise ValueError("solvency failed or run advanced during checkpoint; regenerate")
    current_space = [entry for entry in index.values() if entry["space_id"] == space]
    counts = Counter(entry["entry_class"] for entry in current_space)
    if report["entries"] != len(current_space) or counts != {item["class"]: item["attempts"] for item in report["classes"]}:
        raise ValueError("chain report disagrees with complete entry scan")
    history_public = [publisher.public_infrastructure(item) for item in history]
    known_history = {item["tx"] for item in history_public}
    history_public += [dict(item, captured_by_checkpoint=True) for item in failures if item["tx"] not in known_history]
    unsubmitted = [{"id": candidate["id"], "class": candidate["class"], "envelope_hash": fingerprint}
                   for fingerprint, candidate in candidates.items() if fingerprint not in submitted | prevented]
    honest = sum(row["entry_class"] == "honest" for row in verified)
    return {
        "run": "bradbury-checkpoint", "complete": False, "defence_conclusion": None,
        "required_honest_judgements": 20, "contract_address": address,
        "deployment_tx": metadata["deployment_tx"], "space_id": space,
        "source_sha256": metadata.get("source_sha256"), "deployment_source_sha256": metadata.get("deployment_source_sha256"),
        "consensus_policy": metadata.get("consensus_policy"), "experiment": metadata.get("experiment", False),
        "protocol": metadata.get("protocol"), "policy": policy,
        "consensus_version": "2.0.0",
        "decoder_correction": "Earlier captures used the newer Consensus v0.6 enum and could label stored code 13 as LeaderRevealing. The deployed 2.0.0 implementation uses code 13 for LeaderTimeout. This checkpoint uses its verified Solidity enum; original captures remain preserved. Current unresolved appeals and finalized protocol failures are separate from that display error.",
        "health_warning": "Incomplete checkpoint. Verified observations only; no defence conclusion. Accepted receipts remain provisional. A full report requires complete candidate coverage and at least 20 judged honest controls.",
        "coverage": {"candidates": len(candidates), "judged": len(verified), "honest_judged": honest,
                     "infrastructure_failures": len(failures), "unresolved": len(unresolved), "prevented": len(refused), "unsubmitted": len(unsubmitted)},
        "entries": verified, "refused_at_write": refused, "infrastructure_failures": failures,
        "infrastructure_history": history_public, "unresolved": unresolved,
        "pending": [item for item in unresolved if item.get("status") not in collector.TERMINAL],
        "unsubmitted_candidates": unsubmitted, "report": report,
        "report_scope": "current on-chain space; may include entries awaiting snapshot verification",
        "report_matches_verified_entries": report["entries"] == len(verified), "solvency": solvency,
        "previous_runs": [dict(prior, included_in_report=False) for prior in metadata.get("previous_deployments", [])],
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("run-dir", "records", "deployment", "seed", "out"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--space", type=int, default=0)
    parser.add_argument("--endpoint", default="")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    inputs = [run_dir / "bradbury.jsonl", Path(args.records), Path(args.seed), Path(args.deployment)]
    if Path(args.out).resolve() in {path.resolve() for path in inputs}:
        raise ValueError("output must not overwrite checkpoint inputs")
    captured = {path: path.read_bytes() for path in inputs}
    manifest = collector.load_manifest(run_dir / "bradbury.jsonl")
    rows = [json.loads(line) for line in Path(args.records).read_text().splitlines() if line.strip()]
    def optional(name):
        path = run_dir / "live" / name
        return json.loads(path.read_text()) if path.exists() else []
    checkpoint = build_checkpoint(json.loads(Path(args.seed).read_text()), json.loads(Path(args.deployment).read_text()),
                                  manifest, rows, optional("infrastructure-failures.json"), optional("refused.json"),
                                  space=args.space, endpoint=args.endpoint, timeout=args.timeout)
    if any(path.read_bytes() != content for path, content in captured.items()):
        raise ValueError("checkpoint inputs changed during verification; regenerate")
    collector.checkpoint(args.out, checkpoint)
    print("incomplete checkpoint: %d verified, %d unresolved, %d finalized infrastructure outcomes" %
          (len(checkpoint["entries"]), len(checkpoint["unresolved"]), len(checkpoint["infrastructure_failures"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
