#!/usr/bin/env python3
"""Collect Bradbury receipts and match entries by envelope hash, never by order.

Ported from Suborn. Chain reads are shared with diagnose_missing.py. A manifest
is JSONL with tx, envelope_hash and file (the exact submitted envelope); entry_id
is optional. Run this after EACH write before sending the next one.

    python3 scripts/collect_receipts.py runs/bradbury.jsonl \
        --address 0xCONTRACT --out runs/records.jsonl

--from-json accepts {tx: {receipt: {...}, entry: {...}}} for offline checks.
Raw receipts are checkpointed even when no entry state can be recovered.
Nothing here submits a transaction or publishes a corpus.
"""

import argparse
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
import entry as envtool  # noqa: E402
import gate  # noqa: E402

EXPLORER = "https://explorer-bradbury.genlayer.com"
FAILED = {"ERROR", "CANCELED", "CANCELLED", "REVERTED", "FAILED"}
TIMEOUTS = {"VALIDATORS_TIMEOUT", "LEADER_TIMEOUT"}
TERMINAL = FAILED | TIMEOUTS | {"FINALIZED", "ACCEPTED", "UNDETERMINED", "SUCCESS"}
STORED_STATUSES = (
    "UNINITIALIZED", "PENDING", "PROPOSING", "COMMITTING", "REVEALING",
    "ACCEPTED", "UNDETERMINED", "FINALIZED", "CANCELED", "APPEAL_REVEALING",
    "APPEAL_COMMITTING", "READY_TO_FINALIZE", "VALIDATORS_TIMEOUT", "LEADER_TIMEOUT", "LEADER_REVEALING",
)


def fetch_json(url, timeout):
    request = urllib.request.Request(url, headers={"accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_receipt(explorer, tx, timeout):
    if not re.fullmatch(r"0x[0-9a-fA-F]{64}", tx):
        raise ValueError("invalid transaction hash")
    try:
        return fetch_json(explorer.rstrip("/") + "/api/v1/transactions/" + tx, timeout)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            # The explorer indexes asynchronously after the SDK returns a tx.
            return None
        raise


def replace_js_atoms(source):
    """Translate CLI literals without touching words inside quoted strings."""
    out, index, quote, escaped = [], 0, "", False
    while index < len(source):
        char = source[index]
        if quote:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            out.append(char)
            index += 1
            continue
        match = re.match(r"\b(?:true|false|null)\b|\b\d+n\b", source[index:])
        if match:
            word = match.group()
            out.append({"true": "True", "false": "False", "null": "None"}.get(word, word[:-1]))
            index += len(word)
        else:
            out.append(char)
            index += 1
    return "".join(out)


def extract_json(text):
    markers = list(re.finditer(r"(?m)^Result:\s*$", text))
    payload = text[markers[-1].end():] if markers else text
    payload = re.split(r"\n\s*[✔✖]", payload, maxsplit=1)[0].strip()
    if not payload:
        raise RuntimeError("genlayer call returned no result")
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        quoted = re.sub(r"([,{]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', payload)
        try:
            return ast.literal_eval(replace_js_atoms(quoted))
        except (SyntaxError, ValueError) as exc:
            raise RuntimeError("could not parse genlayer call output") from exc


def read_call(endpoint, address, method, args, timeout):
    command = ["node", str(ROOT / "scripts/read_chain.mjs"), "--call", address, method, json.dumps(args)]
    if endpoint:
        command.append(endpoint)
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        message = (result.stdout + result.stderr).strip()
        if method == "get_entry" and "unknown entry" in message.lower():
            return None
        raise RuntimeError(message or "genlayer call failed")
    return decode_chain_json(result.stdout)


def decode_chain_json(source):
    def bigint(value):
        if set(value) == {"$bigint"}:
            return int(value["$bigint"])
        return value
    return json.loads(source, object_hook=bigint)


def read_entry(endpoint, address, entry_id, timeout):
    return read_call(endpoint, address, "get_entry", [entry_id], timeout)


def lookup_receipt(explorer, endpoint, tx, timeout):
    """Stored consensus state gates settlement; projected/explorer views are evidence."""
    command = ["node", str(ROOT / "scripts/read_chain.mjs"), tx]
    if endpoint:
        command.append(endpoint)
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "RPC receipt lookup failed")
    receipt = json.loads(result.stdout)
    if receipt.get("status_basis") != "getTransactionAllData" or not isinstance(receipt.get("stored_receipt"), dict):
        raise RuntimeError("RPC receipt lacks stored consensus status")
    if receipt.get("consensus_version") != "2.0.0":
        raise RuntimeError("RPC receipt lacks verified consensus version 2.0.0")
    if not explorer:
        return receipt
    try:
        receipt["explorer_receipt"] = fetch_receipt(explorer, tx, timeout)
    except Exception as exc:
        receipt["explorer_lookup_error"] = str(exc)
    return receipt


def status_of(receipt):
    if not isinstance(receipt, dict):
        return "PENDING"
    stored = receipt.get("stored_receipt")
    if "stored_receipt" in receipt:
        # Numeric stored state wins over SDK labels and time-based projection.
        # Unknown or missing state cannot authorize another write/publication.
        if not isinstance(stored, dict):
            return "PENDING"
        if receipt.get("consensus_version", "2.0.0") != "2.0.0":
            return "PENDING"
        try:
            code = int(stored["status"])
        except (KeyError, TypeError, ValueError):
            return "PENDING"
        return STORED_STATUSES[code] if 0 <= code < len(STORED_STATUSES) else "PENDING"
    for key in ("statusName", "status_name", "consensus_status", "status"):
        if receipt.get(key):
            value = str(receipt[key]).upper()
            return {"VALIDATORSTIMEOUT": "VALIDATORS_TIMEOUT", "LEADERTIMEOUT": "LEADER_TIMEOUT", "APPEALCOMMITTING": "APPEAL_COMMITTING", "APPEALREVEALING": "APPEAL_REVEALING"}.get(value.replace("_", ""), value)
    return "PENDING"


def is_consensus_timeout(receipt):
    """A finalized timeout remains a timeout; a projected old round proves none."""
    status = status_of(receipt)
    if status in TIMEOUTS:
        return True
    stored = receipt.get("stored_receipt") if isinstance(receipt, dict) else None
    return status == "FINALIZED" and isinstance(stored, dict) and stored.get("result") in (3, "3")


def finalized_infrastructure_outcome(receipt):
    """Classify explicit stored terminal outcomes, never unexplained missing state."""
    stored = receipt.get("stored_receipt") if isinstance(receipt, dict) else None
    if status_of(receipt) != "FINALIZED" or not isinstance(stored, dict):
        return None
    if is_consensus_timeout(receipt):
        return "TIMEOUT"
    if stored.get("result") in (0, "0") and stored.get("txExecutionResult") in (0, "0"):
        return "NOT_EXECUTED"
    return None


def has_application_execution(receipt):
    """Successful stored consensus and execution, independent of old labels."""
    stored = receipt.get("stored_receipt") if isinstance(receipt, dict) else None
    return (isinstance(stored, dict) and receipt.get("consensus_version") == "2.0.0"
            and status_of(receipt) in {"ACCEPTED", "FINALIZED"}
            and stored.get("result") in (1, "1") and stored.get("txExecutionResult") in (1, "1"))


def load_manifest(path):
    rows = []
    with open(path, encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not row.get("tx"):
                raise ValueError("manifest line %d has no tx" % number)
            if not re.fullmatch(r"0x[0-9a-fA-F]{64}", row["tx"]):
                raise ValueError("manifest line %d has invalid tx" % number)
            if row.get("method", "write_entry") == "write_entry":
                if not row.get("envelope_hash"):
                    raise ValueError("write manifest line %d has no envelope_hash" % number)
                rows.append(row)
    return rows


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = stream.name
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def checkpoint(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def scan_entries(endpoint, address, timeout, count=None, reader=read_entry, start=0):
    """Use the chain's count, including entries missed in the manifest."""
    if count is None:
        count = int(read_call(endpoint, address, "entry_count", [], timeout))
    index, errors = {}, []
    for entry_id in range(start, count):
        try:
            got = reader(endpoint, address, entry_id, timeout)
            if not isinstance(got, dict) or not got.get("envelope_hash"):
                errors.append({"entry_id": entry_id, "error": "no entry returned"})
            else:
                index[got["envelope_hash"]] = got
        except Exception as exc:
            errors.append({"entry_id": entry_id, "error": str(exc)})
    return index, errors


def find_envelope(row, folder):
    candidates = [Path(row["file"])] if row.get("file") else []
    candidates += sorted(Path(folder).glob("*.json"))
    for path in candidates:
        if not path.is_file():
            continue
        env = json.loads(path.read_text(encoding="utf-8"))
        if envtool.envelope_hash(env) == row["envelope_hash"]:
            return env
    raise ValueError("no submitted envelope matches " + row["envelope_hash"])


def assemble_record(row, judged, env, min_rounds, receipt):
    if finalized_infrastructure_outcome(receipt):
        raise ValueError("finalized infrastructure outcome cannot authorize a judged record")
    if "stored_receipt" in receipt and not has_application_execution(receipt):
        raise ValueError("stored consensus has no successful application execution")
    fingerprint = envtool.envelope_hash(env)
    if fingerprint != row["envelope_hash"] or fingerprint != judged.get("envelope_hash"):
        raise ValueError("manifest, envelope and chain hashes disagree")
    for key in ("space_id", "claim", "source_url", "entry_class"):
        if judged.get(key) != env.get(key):
            raise ValueError("chain and envelope disagree on " + key)
    if judged.get("supports", []) != env.get("supports", []):
        raise ValueError("chain and envelope disagree on supports")
    # A later rejudge changes votes and state. Collect immediately after writes;
    # preserve the original records when collecting again after a cascade.
    code, verification = gate.run_verify({
        "envelope": env, "envelope_hash": fingerprint,
        "votes": judged.get("votes"), "rounds": judged.get("rounds"),
        "status": judged.get("status"), "min_rounds": min_rounds,
    })
    if code:
        raise ValueError("entry verdict does not reproduce: " + json.dumps(verification))
    record = dict(judged)
    record.update({
        "id": row.get("id", Path(row.get("file", "entry")).stem),
        "tx": row["tx"], "receipt_status": status_of(receipt),
        "envelope": env, "expects": env.get("expects", ""),
        "dedup_key": envtool.dedup_key(env["space_id"], env["claim"]),
        "min_rounds": min_rounds,
        "as_expected": env.get("expects", "") in ("", judged["status"]),
        # get_entry exposes the snapshot hash, but not its bytes. Do not claim
        # that a snapshot was independently reproduced when it was not.
        "snapshot_verified": False,
    })
    return record


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("manifest")
    ap.add_argument("--address", default="")
    ap.add_argument("--endpoint", default="")
    ap.add_argument("--explorer", default=EXPLORER)
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--wait", type=int, default=0)
    ap.add_argument("--from-json", default="")
    ap.add_argument("--entries", default=str(ROOT / "examples" / "entries"))
    ap.add_argument("--min-rounds", type=int, default=None, help="required for offline fixtures")
    ap.add_argument("--out", required=True)
    ap.add_argument("--raw-dir", default=str(ROOT / "runs" / "receipts"))
    args = ap.parse_args()
    rows = load_manifest(args.manifest)
    cache = json.loads(Path(args.from_json).read_text()) if args.from_json else None
    if cache is None and not args.address:
        ap.error("--address is required for chain reads")
    if cache is not None and args.min_rounds is None:
        ap.error("--min-rounds is required with --from-json")

    existing = {}
    if Path(args.out).exists():
        for line in Path(args.out).read_text().splitlines():
            if line.strip():
                record = json.loads(line)
                existing[record["tx"]] = record
    problems, index, scan_errors = [], {}, []
    if cache is None:
        try:
            known_ids = {int(record["entry_id"]) for record in existing.values()}
            start = 0
            while start in known_ids:
                start += 1
            index, scan_errors = scan_entries(args.endpoint, args.address, args.timeout, start=start)
        except Exception as exc:
            scan_errors.append({"error": str(exc)})
    policy_cache = {}
    for row in rows:
        tx = row["tx"]
        if tx in existing:
            if existing[tx]["envelope_hash"] != row["envelope_hash"]:
                raise ValueError("manifest changed hash for already collected tx " + tx)
            continue
        raw = {}
        try:
            if cache is not None:
                raw = cache.get(tx, {})
                receipt, judged = raw.get("receipt"), raw.get("entry")
            else:
                deadline = time.monotonic() + args.wait
                while True:
                    receipt = lookup_receipt(args.explorer, args.endpoint, tx, args.timeout)
                    raw["receipt"] = receipt
                    checkpoint(Path(args.raw_dir) / (tx + ".json"), raw)
                    if status_of(receipt) in TERMINAL or time.monotonic() >= deadline:
                        break
                    time.sleep(min(4, max(0, deadline - time.monotonic())))
                judged = index.get(row["envelope_hash"])
                # It may have landed after the initial scan.
                if judged is None and row.get("entry_id") is not None:
                    candidate = read_entry(args.endpoint, args.address, int(row["entry_id"]), args.timeout)
                    if candidate and candidate.get("envelope_hash") == row["envelope_hash"]:
                        judged = candidate
            raw["entry"] = judged
            checkpoint(Path(args.raw_dir) / (tx + ".json"), raw)
            if status_of(receipt) not in TERMINAL:
                raise ValueError("still settling: " + status_of(receipt))
            if status_of(receipt) in FAILED:
                raise ValueError("failed transaction: " + status_of(receipt))
            if is_consensus_timeout(receipt):
                raise ValueError("consensus timeout: " + status_of(receipt))
            if not judged:
                raise ValueError("terminal receipt without matching entry; run diagnose_missing.py")
            if cache is None:
                sid = judged["space_id"]
                if sid not in policy_cache:
                    policy_cache[sid] = read_call(args.endpoint, args.address, "get_space", [sid], args.timeout)
                minimum = policy_cache[sid]["min_rounds"]
            else:
                minimum = args.min_rounds
            existing[tx] = assemble_record(row, judged, find_envelope(row, args.entries), minimum, receipt)
        except Exception as exc:
            raw["error"] = str(exc)
            checkpoint(Path(args.raw_dir) / (tx + ".json"), raw)
            problems.append({"tx": tx, "error": str(exc)})

    checkpoint(args.out + ".issues.json", {"transactions": problems, "scan_errors": scan_errors})
    if existing:
        atomic_write(args.out, "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in existing.values()))
    print("%d records, %d unresolved, %d scan errors" % (len(existing), len(problems), len(scan_errors)))
    for problem in problems:
        print("  %s %s" % (problem["tx"][:14], problem["error"]))
    return 2 if problems or scan_errors or not existing else 0


if __name__ == "__main__":
    raise SystemExit(main())
