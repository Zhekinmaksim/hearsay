#!/usr/bin/env python3
"""Replay every row of the published corpus from its own recorded votes.

    python3 scripts/replay_corpus.py [web/corpus.json]

Each row carries the votes as they were cast. This recomputes every verdict
from those votes with the same `decide` the gate uses and fails on the first
row that does not reproduce.

It exists because the first version of the page checked receipts against
themselves: it reconstructed the votes from the verdict and then confirmed the
verdict followed from them, which can never fail. The moment the votes were
recorded and replayed for real, one row did not reproduce — an unreachable
source was ruled in a branch of the contract that bypassed `decide`. This script
is what stops that class of bug from coming back quietly.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "cli"))

import gate  # noqa: E402


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "web", "corpus.json")
    corpus = json.load(open(path, encoding="utf-8"))
    min_rounds = corpus["policy"]["min_rounds"]

    failures = []
    for row in corpus["entries"]:
        receipt = {
            "votes": row["votes"],
            "status": row["status"],
            "rounds": row["rounds"],
            "min_rounds": min_rounds,
            "envelope": {
                "version": "hearsay/1",
                "space_id": corpus["space_id"],
                "claim": row["claim"],
                "source_url": row["source_url"],
                "entry_class": row["entry_class"],
            },
        }
        code, payload = gate.run_verify(receipt)
        if code != 0:
            failures.append((row["entry_id"], row.get("id", ""), payload.get("failures")))

    total = len(corpus["entries"])
    print("replayed %d rows from their recorded votes: %d reproduce, %d do not"
          % (total, total - len(failures), len(failures)))
    for eid, name, why in failures:
        print("  entry %s %s" % (eid, name))
        for line in why or []:
            print("    " + line)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
