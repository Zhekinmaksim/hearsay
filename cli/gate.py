#!/usr/bin/env python3
"""The admission gate. This is the thing you put in front of your own storage.

Two commands, and the difference between them is the project.

    gate     decide whether one entry may be written, and exit accordingly
    verify   recompute a verdict from a receipt, offline, and say whether it
             reproduces

`gate` is what a writing agent calls. `verify` is what a reader calls when it
does not want to take the chain's word for it. A verdict nobody can recompute is
a verdict nobody can contest, and a corpus of uncontestable verdicts is a
press release.

    python3 cli/gate.py gate   --entry e.json --corpus web/corpus.json
    python3 cli/gate.py gate   --entry e.json --corpus web/corpus.json --strict
    python3 cli/gate.py verify --receipt r.json

Exit codes, chosen so `set -e` does the obvious thing:

    0   ADMITTED, or the receipt reproduces
    1   refused: UNSOURCED, CONTRADICTED, or the receipt does not reproduce
    2   INCONCLUSIVE, or no verdict is on record yet
    3   the entry is malformed and was never judged

2 and 3 are separate on purpose. INCONCLUSIVE means consensus looked and could
not tell, which is a fact about the entry. 3 means nothing was ever asked. A
caller that treats them the same will eventually treat "we could not read it"
as "it is fine".
"""

import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "contracts"))

from entry import canonical, dedup_key, envelope_hash, flatten, validate  # noqa: E402

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_INCONCLUSIVE = 2
EXIT_MALFORMED = 3

ADMITTED = "ADMITTED"
UNSOURCED = "UNSOURCED"
CONTRADICTED = "CONTRADICTED"
INCONCLUSIVE = "INCONCLUSIVE"

_EXIT_FOR = {
    ADMITTED: EXIT_OK,
    UNSOURCED: EXIT_REFUSED,
    CONTRADICTED: EXIT_REFUSED,
    INCONCLUSIVE: EXIT_INCONCLUSIVE,
}


def decide(a, b, rounds, min_rounds, conflict, fetched=True):
    """Verdict assembly, mirroring `decide` in contracts/hearsay.py.

    Duplicated rather than imported at runtime, because the contract file
    carries a GenLayer dependency header and importing it drags the runtime in.
    test/run_tests.py runs both over the same vectors; if they ever disagree the
    parity test fails loudly, which is the only acceptable way for a duplicate
    to exist.
    """
    if not fetched:
        return (UNSOURCED, "source unreachable or empty", 0)
    if rounds < min_rounds:
        return (INCONCLUSIVE, "fewer readable rounds than the space requires", 0)
    if a is None or b is None or a != b:
        return (INCONCLUSIVE, "referee framings disagreed or were unreadable", 0)
    if a is False:
        return (UNSOURCED, "source does not support the claim", 0)
    if conflict is None:
        return (INCONCLUSIVE, "consistency check unreadable", 0)
    if conflict >= 0:
        return (CONTRADICTED, "conflicts with entry %d" % conflict, conflict)
    return (ADMITTED, "", 0)


_VOTE = {"yes": True, "no": False, "unread": None, "unasked": None, "": None}


def _from_votes(votes):
    conflict_raw = votes.get("conflict", "")
    if conflict_raw in ("", "none"):
        conflict = -1
    elif conflict_raw in ("unread",):
        conflict = None
    elif conflict_raw == "unasked":
        conflict = -1
    else:
        conflict = int(conflict_raw)
    return {
        "fetched": votes.get("a") != "unasked",
        "support_a": _VOTE.get(votes.get("a", ""), None),
        "support_b": _VOTE.get(votes.get("b", ""), None),
        "conflict": conflict,
    }


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _rows(corpus):
    """Accept either a bare list of rows or the published corpus object."""
    if isinstance(corpus, list):
        return corpus
    return corpus.get("entries", corpus.get("rows", []))


# ------------------------------------------------------------------- gate


def run_gate(env, corpus, strict=False):
    """Local checks first, then the recorded verdict.

    Order matters. Everything the gate can settle without the chain is settled
    without the chain: a caller should not spend a bond to be told its envelope
    was malformed, and a duplicate claim should not reach consensus at all. Only
    what genuinely needs judgement is looked up.

    Returns (exit_code, payload).
    """
    problems = validate(env)
    if problems:
        return (
            EXIT_MALFORMED,
            {"verdict": None, "reason": "malformed envelope", "problems": problems},
        )

    ehash = envelope_hash(env)
    key = dedup_key(env.get("space_id", 0), env.get("claim", ""))
    rows = _rows(corpus)

    for row in rows:
        if row.get("envelope_hash") == ehash:
            verdict = row.get("status") or row.get("verdict")
            return (
                _EXIT_FOR.get(verdict, EXIT_INCONCLUSIVE),
                {
                    "verdict": verdict,
                    "entry_id": row.get("entry_id"),
                    "note": row.get("note", ""),
                    "snapshot_hash": row.get("snapshot_hash", ""),
                    "source": "corpus",
                },
            )

    # A different envelope that flattens to the same claim in the same space.
    # The contract would raise on this, so the gate refuses rather than sending
    # a caller to certain failure.
    for row in rows:
        if row.get("dedup_key") == key:
            return (
                EXIT_REFUSED,
                {
                    "verdict": None,
                    "reason": "duplicate of entry %s after dedup flattening"
                    % row.get("entry_id"),
                    "source": "corpus",
                },
            )

    if strict:
        # `--strict` is for callers that must never write on an unjudged entry:
        # no record means no, rather than maybe.
        return (
            EXIT_REFUSED,
            {"verdict": None, "reason": "no verdict on record and --strict is set"},
        )
    return (
        EXIT_INCONCLUSIVE,
        {
            "verdict": None,
            "reason": "no verdict on record yet; submit the entry first",
            "envelope_hash": ehash,
        },
    )


# ----------------------------------------------------------------- verify


def run_verify(receipt):
    """Recompute a verdict from a receipt without a chain, a network or a model.

    Three things are checked, and each catches a different lie:

      the envelope hash, which catches a row describing a different entry
      the snapshot hash, which catches a verdict re-attributed to another page
      the verdict itself, which catches a row whose recorded answers do not
      actually produce the verdict beside them

    The third is the one that matters. Everything else in the corpus is a claim
    about what happened; this is the only line that can be shown to be false
    with nothing but the file in front of you.
    """
    failures = []
    env = receipt.get("envelope")
    if env is None:
        return (EXIT_MALFORMED, {"reason": "receipt carries no envelope"})

    recomputed = envelope_hash(env)
    if receipt.get("envelope_hash") not in (None, recomputed):
        failures.append(
            "envelope_hash does not match the envelope: recorded %s, recomputed %s"
            % (receipt.get("envelope_hash"), recomputed)
        )

    excerpt = receipt.get("snapshot_excerpt")
    if excerpt is not None:
        snap = _sha(excerpt)
        if receipt.get("snapshot_hash") not in (None, snap):
            failures.append(
                "snapshot_hash does not match the pinned excerpt: recorded %s, recomputed %s"
                % (receipt.get("snapshot_hash"), snap)
            )

    rounds_in = receipt.get("rounds_detail")
    if rounds_in is None and receipt.get("votes"):
        # A corpus row is a receipt. Its votes are stored as cast — "yes",
        # "no", "unread", "unasked" — and are translated here, never inferred
        # from the verdict sitting beside them.
        rounds_in = _from_votes(receipt["votes"])
    if rounds_in is None:
        failures.append("receipt carries no round answers, so the verdict cannot be recomputed")
        return (EXIT_REFUSED, {"reproduces": False, "failures": failures})

    a = rounds_in.get("support_a")
    b = rounds_in.get("support_b")
    readable = sum(1 for v in (a, b) if v is not None)
    verdict, note, conflict = decide(
        a,
        b,
        readable,
        int(receipt.get("min_rounds", 1)),
        rounds_in.get("conflict", -1),
        rounds_in.get("fetched", True),
    )

    recorded = receipt.get("status") or receipt.get("verdict")
    if recorded is not None and recorded != verdict:
        failures.append(
            "verdict does not follow from the recorded rounds: recorded %s, recomputed %s"
            % (recorded, verdict)
        )
    recorded_rounds = receipt.get("rounds")
    if recorded_rounds is not None and int(recorded_rounds) != readable:
        failures.append(
            "round count does not match the recorded answers: recorded %s, recomputed %d"
            % (recorded_rounds, readable)
        )

    payload = {
        "reproduces": not failures,
        "recomputed_verdict": verdict,
        "note": note,
        "conflicts_with": conflict,
        "readable_rounds": readable,
        "envelope_hash": recomputed,
    }
    if failures:
        payload["failures"] = failures
        return (EXIT_REFUSED, payload)
    return (EXIT_OK, payload)


# -------------------------------------------------------------------- main


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gate")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gate", help="decide whether one entry may be written")
    g.add_argument("--entry", required=True)
    g.add_argument("--corpus", required=True)
    g.add_argument("--strict", action="store_true")
    g.add_argument("--quiet", action="store_true")

    v = sub.add_parser("verify", help="recompute a verdict from a receipt, offline")
    v.add_argument("--receipt", required=True)
    v.add_argument("--quiet", action="store_true")

    args = ap.parse_args(argv)

    if args.cmd == "gate":
        code, payload = run_gate(_load(args.entry), _load(args.corpus), args.strict)
    else:
        code, payload = run_verify(_load(args.receipt))

    if not args.quiet:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
