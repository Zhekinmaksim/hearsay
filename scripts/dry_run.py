#!/usr/bin/env python3
"""Run the seed corpus through the contract offline and publish the result.

    python3 scripts/dry_run.py

What this produces is a real corpus file with real envelope hashes, real dedup
keys, real snapshots and a real verdict per entry, which is what `cli/gate.py`
needs something to read. The plumbing it exercises is genuine: envelope
canonicalization, the write path, the support stage, the consistency window, the
cascade bookkeeping, the money.

What it does NOT produce is a defence measurement, and the output says so in its
own header. The judge here is `test/model.py`, a scripted stand-in that answers
whatever the seed row tells it to answer. Feeding it an attack and recording
that it refused would be recording the seed file, not the defence. The admission
rates in this file measure the harness. The numbers that count come from
Bradbury, where the answer is not ours to write.

The one thing the dry run does settle honestly is what happens before any model
is asked: the citation-laundering row is refused at the write path, by the
ordering rule, with no consensus round spent. That is prevention rather than
judgement, and it is reported as such.
"""

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "test", "stub"))
sys.path.insert(0, os.path.join(ROOT, "test"))
sys.path.insert(0, os.path.join(ROOT, "cli"))
sys.path.insert(0, os.path.join(ROOT, "contracts"))

import genlayer as glmod  # noqa: E402
from genlayer import gl  # noqa: E402
from model import ScriptedModel  # noqa: E402

import entry as envtool  # noqa: E402
import hearsay as hs  # noqa: E402

OWNER = glmod.Address("0x" + "11" * 20)
WRITER = glmod.Address("0x" + "22" * 20)

WRITE_BOND = 1_000
CHALLENGE_BOND = 2_000
POOL = 500_000

SEED = os.path.join(ROOT, "corpus", "seed.json")
OUT_CORPUS = os.path.join(ROOT, "runs", "offline", "corpus.json")
OUT_ENTRIES = os.path.join(ROOT, "runs", "offline", "entries")


def _as(addr, value=0):
    gl.message.sender_address = addr
    gl.message.value = value


def _script(model, spec):
    """Reset the scripted judge, then apply one seed row's instructions."""
    model.support = True
    model.conflict = None
    model.defeats = False
    model.needs_premise = False
    for key, value in (spec or {}).items():
        if key == "support" and isinstance(value, list):
            value = tuple(value)
        setattr(model, key, value)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=OUT_CORPUS)
    ap.add_argument("--entries-out", default=OUT_ENTRIES)
    args = ap.parse_args()
    out_corpus, out_entries = os.path.abspath(args.out), os.path.abspath(args.entries_out)
    published = os.path.join(ROOT, "web", "corpus.json")
    if os.path.realpath(out_corpus) == os.path.realpath(published):
        if os.path.exists(published) and json.load(open(published, encoding="utf-8")).get("run") != "offline-scripted":
            ap.error("refusing to overwrite a live corpus with scripted data")
    if os.path.realpath(out_entries) == os.path.realpath(os.path.join(ROOT, "examples", "entries")):
        ap.error("use a separate entries output; examples/entries must not be overwritten")
    seed = json.load(open(SEED, encoding="utf-8"))
    policy = seed["space"]

    model = ScriptedModel()
    gl.nondet.handler = model
    gl.nondet.web.pages = {
        row["source_url"]: row["page"]
        for row in seed["entries"]
        if row.get("page")
    }
    gl.nondet.web.fetches = []
    gl.advanced.transfers = []

    c = hs.Hearsay()
    _as(OWNER, POOL)
    space_id = c.open_space(
        name=policy["name"],
        policy=policy["policy"],
        admit_ttl=policy["admit_ttl"],
        cascade_depth=policy["cascade_depth"],
        min_rounds=policy["min_rounds"],
        write_bond=WRITE_BOND,
        challenge_bond=CHALLENGE_BOND,
    )

    os.makedirs(out_entries, exist_ok=True)
    for stale in os.listdir(out_entries):
        if stale.endswith(".json"):
            os.remove(os.path.join(out_entries, stale))

    ids = {}
    rows = []
    refused = []

    for row in seed["entries"]:
        supports = []
        unresolved = False
        for name in row.get("supports", []):
            if name not in ids:
                unresolved = True
                break
            supports.append(ids[name])

        env = {
            "version": hs.VERSION,
            "space_id": space_id,
            "claim": row["claim"],
            "source_url": row["source_url"],
            "entry_class": row["class"],
        }
        if supports:
            env["supports"] = supports
        if row.get("expects"):
            env["expects"] = row["expects"]
        if row.get("note"):
            env["author_note"] = row["note"]

        path = os.path.join(out_entries, row["id"] + ".json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(env, indent=2, ensure_ascii=False) + "\n")

        if unresolved:
            # The ordering rule, doing its work before any model is asked.
            refused.append(
                {
                    "id": row["id"],
                    "class": row["class"],
                    "refused_at": "write",
                    "reason": "supports names an entry that does not exist",
                    "envelope_hash": envtool.envelope_hash(env),
                    "consensus_rounds_spent": 0,
                }
            )
            continue

        _script(model, row.get("script"))
        _as(WRITER, WRITE_BOND)
        try:
            eid = c.write_entry(space_id, row["class"], json.dumps(env))
        except Exception as exc:
            refused.append(
                {
                    "id": row["id"],
                    "class": row["class"],
                    "refused_at": "write",
                    "reason": str(exc),
                    "envelope_hash": envtool.envelope_hash(env),
                    "consensus_rounds_spent": 0,
                }
            )
            continue

        ids[row["id"]] = eid
        got = c.get_entry(eid)
        rows.append(
            {
                "entry_id": eid,
                "id": row["id"],
                "entry_class": row["class"],
                "expects": row.get("expects", ""),
                "claim": got["claim"],
                "source_url": got["source_url"],
                "envelope_hash": got["envelope_hash"],
                "dedup_key": envtool.dedup_key(space_id, got["claim"]),
                "snapshot_hash": got["snapshot_hash"],
                "supports": got["supports"],
                "status": got["status"],
                "note": got["note"],
                "rounds": got["rounds"],
                "votes": got["votes"],
                "conflicts_with": got["conflicts_with"],
                "as_expected": row.get("expects", "") in ("", got["status"]),
                # Whether the entry's own source carried the claim without help.
                # Recorded from the run, not guessed, so the cascade replay on
                # the page is a replay of what happened rather than a model of
                # what might.
                "stands_alone": not bool((row.get("script") or {}).get("needs_premise")),
            }
        )

    report = c.report(space_id)
    solvency = c.solvency()

    corpus = {
        "run": "offline-scripted",
        "health_warning": (
            "The judge in this run is a scripted stand-in that answers what the "
            "seed file tells it to. These admission rates measure the harness, "
            "not the defence. The numbers that count come from Bradbury."
        ),
        "space_id": space_id,
        "policy": policy,
        "entries": rows,
        "refused_at_write": refused,
        "report": report,
        "solvency": solvency,
    }
    os.makedirs(os.path.dirname(out_corpus), exist_ok=True)
    with open(out_corpus, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(corpus, indent=2, ensure_ascii=False) + "\n")

    print("wrote %s" % os.path.relpath(out_corpus, ROOT))
    print("     %d envelopes in %s" % (len(rows) + len(refused), os.path.relpath(out_entries, ROOT)))
    print()
    print("judged            %d" % len(rows))
    print("refused at write  %d  (no consensus round spent)" % len(refused))
    for r in refused:
        print("                  %-18s %s" % (r["class"], r["id"]))
    print()
    mismatched = [r for r in rows if not r["as_expected"]]
    print("landed where the seed said  %d of %d" % (len(rows) - len(mismatched), len(rows)))
    for r in mismatched:
        print("  %-28s expected %-14s got %s" % (r["id"], r["expects"], r["status"]))
    print()
    print("balanced          %s" % solvency["balanced"])
    print("deferred queue    %d" % report["deferred"])
    print()
    print("per class (harness, not defence):")
    for row in report["classes"]:
        flag = "  prevented by construction" if row.get("prevented_by_construction") else ""
        print(
            "  %-20s attempts %2d  admitted %2d  rate %4d/1000%s"
            % (row["class"], row["attempts"], row["ever_admitted"], row["admission_rate_milli"], flag)
        )
    print()
    print(
        "false rejection on honest entries  %d/1000  (%d of %d refused)"
        % (
            report["false_rejection_milli"],
            report["honest_attempts"] - report["honest_admitted"],
            report["honest_attempts"],
        )
    )
    return 0 if not mismatched else 1


if __name__ == "__main__":
    raise SystemExit(main())
