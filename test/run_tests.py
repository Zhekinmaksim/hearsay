#!/usr/bin/env python3
"""Offline end to end run. No network, no Bradbury.

    python3 test/run_tests.py

Solvency is asserted after every action that touches value, not only at the
end. A contract that ends balanced after passing through an unbalanced state
has a window in it.
"""

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
import gate  # noqa: E402

OWNER = glmod.Address("0x" + "11" * 20)
WRITER = glmod.Address("0x" + "22" * 20)
WRITER2 = glmod.Address("0x" + "33" * 20)
CHALLENGER = glmod.Address("0x" + "44" * 20)

WRITE_BOND = 1_000
CHALLENGE_BOND = 2_000
POOL = 500_000

PAGES = {
    "https://example.org/a": "The registry lists ACME Corp as dissolved on 4 March.",
    "https://example.org/b": "Independent filing: ACME Corp assets were transferred in April.",
    "https://example.org/c": "A third page with its own account of the same filing.",
}

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    line = ("  ok   " if cond else "  FAIL ") + name
    if detail and not cond:
        line += "   <- " + str(detail)
    print(line)


def as_(addr, value=0):
    gl.message.sender_address = addr
    gl.message.value = value


def fresh(model, cascade_depth=3, admit_ttl=50, min_rounds=2):
    gl.nondet.handler = model
    gl.nondet.web.pages = dict(PAGES)
    gl.nondet.web.fetches = []
    gl.advanced.transfers = []
    c = hs.Hearsay()
    as_(OWNER, POOL)
    sid = c.open_space(
        name="test space",
        policy="sources: any https origin",
        admit_ttl=admit_ttl,
        cascade_depth=cascade_depth,
        min_rounds=min_rounds,
        write_bond=WRITE_BOND,
        challenge_bond=CHALLENGE_BOND,
    )
    return c, sid


def env(claim, source="https://example.org/a", supports=None, klass="honest", space=0):
    e = {
        "version": "hearsay/1",
        "space_id": space,
        "claim": claim,
        "source_url": source,
        "entry_class": klass,
    }
    if supports:
        e["supports"] = supports
    return e


def write(c, model, e, sender=WRITER):
    as_(sender, WRITE_BOND)
    return c.write_entry(e["space_id"], e["entry_class"], json.dumps(e))


def solvent(c):
    return c.solvency()["balanced"]


def expect_error(fn, fragment=""):
    try:
        fn()
    except Exception as exc:  # the stub raises the same UserError type
        return fragment in str(exc) if fragment else True
    return False


# --------------------------------------------------------------- verdicts


def test_admits_a_supported_claim():
    m = ScriptedModel()
    c, _ = fresh(m)
    eid = write(c, m, env("ACME Corp was dissolved in March."))
    e = c.get_entry(eid)
    check("supported claim is admitted", e["status"] == hs.ADMITTED, e["status"])
    check("both framings counted as rounds", e["rounds"] == 2, e["rounds"])
    check("snapshot pinned on the entry", len(e["snapshot_hash"]) == 64)
    check("source was actually fetched", len(gl.nondet.web.fetches) == 1)
    check("bond stays locked while admitted", e["bond_state"] == hs.LOCKED)
    check("solvent after admission", solvent(c))


def test_unreachable_source():
    m = ScriptedModel()
    c, _ = fresh(m)
    eid = write(c, m, env("A claim with nowhere to stand.", source="https://example.org/gone"))
    e = c.get_entry(eid)
    check("unreachable source is UNSOURCED", e["status"] == hs.UNSOURCED, e["status"])
    check("unreachable source forfeits the bond", e["bond_state"] == hs.SLASHED)
    check("solvent after a forfeited bond", solvent(c))


def test_source_does_not_support():
    m = ScriptedModel()
    m.support = False
    c, _ = fresh(m)
    eid = write(c, m, env("A claim the page never makes.", klass="source_forgery"))
    e = c.get_entry(eid)
    check("unsupported claim is UNSOURCED", e["status"] == hs.UNSOURCED, e["status"])


def test_framings_disagree_is_inconclusive():
    m = ScriptedModel()
    m.support = (True, False)
    c, _ = fresh(m)
    eid = write(c, m, env("A claim the two framings read differently.", klass="direct_injection"))
    e = c.get_entry(eid)
    check("split framings are INCONCLUSIVE", e["status"] == hs.INCONCLUSIVE, e["status"])
    check("INCONCLUSIVE does not admit", e["admitted_at"] == 0)
    check("INCONCLUSIVE forfeits the bond", e["bond_state"] == hs.SLASHED)


def test_unreadable_round_is_inconclusive():
    m = ScriptedModel()
    m.support = (None, True)
    c, _ = fresh(m)
    eid = write(c, m, env("A claim one framing could not answer.", klass="direct_injection"))
    e = c.get_entry(eid)
    check("unreadable round is INCONCLUSIVE", e["status"] == hs.INCONCLUSIVE, e["status"])
    check("short rounds are recorded", e["rounds"] == 1, e["rounds"])


def test_unreadable_consistency_check_is_inconclusive():
    m = ScriptedModel()
    c, _ = fresh(m)
    write(c, m, env("First claim."))
    m.conflict = "unreadable"
    eid = write(c, m, env("Second claim."))
    e = c.get_entry(eid)
    check(
        "unreadable consistency check is INCONCLUSIVE",
        e["status"] == hs.INCONCLUSIVE,
        e["status"],
    )


def test_contradiction_names_the_entry():
    m = ScriptedModel()
    c, _ = fresh(m)
    first = write(c, m, env("ACME Corp was dissolved in March."))
    m.conflict = first
    eid = write(c, m, env("ACME Corp is trading normally.", klass="slow_poison"))
    e = c.get_entry(eid)
    check("conflicting claim is CONTRADICTED", e["status"] == hs.CONTRADICTED, e["status"])
    check("CONTRADICTED names what it conflicts with", e["conflicts_with"] == first)


def test_unnameable_conflict_is_inconclusive():
    m = ScriptedModel()
    c, _ = fresh(m)
    write(c, m, env("ACME Corp was dissolved in March."))
    m.conflict = 999
    eid = write(c, m, env("Another claim entirely.", klass="slow_poison"))
    e = c.get_entry(eid)
    check(
        "a conflict that names nothing real is INCONCLUSIVE",
        e["status"] == hs.INCONCLUSIVE,
        e["status"],
    )


# ------------------------------------------------------------------ dedup


def test_dedup_survives_whitespace_padding():
    m = ScriptedModel()
    c, _ = fresh(m)
    write(c, m, env("ACME Corp was dissolved in March."))
    padded = env("acme corp  was dissolved\u200b in   March.")
    check(
        "flattened resubmission is refused",
        expect_error(lambda: write(c, m, padded), "already recorded"),
    )


def test_cli_and_contract_flatten_identically():
    vectors = [
        "ACME Corp was dissolved in March.",
        "  ACME   Corp\twas\ndissolved in March.  ",
        "acme corp was dissolved\u200b in march.",
        "\ufeffMixed\u2060 Case With Zero Width",
    ]
    same = all(envtool.flatten(v) == hs._flatten(v) for v in vectors)
    check("cli and contract flatten identically", same)
    key_cli = envtool.dedup_key(0, vectors[0])
    key_contract = "%d:%s" % (0, hs._fingerprint(hs._flatten(vectors[0])))
    check("dedup keys agree", key_cli == key_contract)


def test_envelope_canonicalisation():
    e = env("A claim.", supports=[])
    e["author_note"] = ""
    h1 = envtool.envelope_hash(e)
    e2 = env("A claim.")
    e2["unknown_field"] = "ignored"
    h2 = envtool.envelope_hash(e2)
    check("empty optionals and unknown keys drop out", h1 == h2)


# --------------------------------------------------------------- supports


def test_cannot_lean_on_an_unadmitted_entry():
    m = ScriptedModel()
    m.support = False
    c, _ = fresh(m)
    bad = write(c, m, env("Unsupported.", klass="source_forgery"))
    m.support = True
    check(
        "supports must already be admitted",
        expect_error(
            lambda: write(c, m, env("Leaning on a rejection.", supports=[bad])),
            "not admitted",
        ),
    )


def test_depth_tracks_the_graph():
    m = ScriptedModel()
    c, _ = fresh(m)
    a = write(c, m, env("Root claim."))
    b = write(c, m, env("Second claim.", source="https://example.org/b", supports=[a]))
    d = write(c, m, env("Third claim.", source="https://example.org/c", supports=[b]))
    check("depth increments along the chain", c.get_entry(d)["depth"] == 2)
    check("dependents index is populated", c.get_entry(a)["dependents"] == [b])


# --------------------------------------------------------------- challenge


def test_challenge_upheld_revokes_and_pays():
    m = ScriptedModel()
    c, _ = fresh(m)
    a = write(c, m, env("Root claim."))
    m.defeats = True
    as_(CHALLENGER, CHALLENGE_BOND)
    cid = c.challenge(a, "The source names a different company.")
    check("solvent mid challenge", solvent(c))
    as_(CHALLENGER, 0)
    outcome = c.confirm_challenge(cid)
    check("two framings uphold the challenge", outcome == hs.UPHELD, outcome)
    check("challenged entry is revoked", c.get_entry(a)["status"] == hs.REVOKED)
    check(
        "challenger takes both bonds",
        c.balance_of(CHALLENGER.as_hex) == CHALLENGE_BOND + WRITE_BOND,
        c.balance_of(CHALLENGER.as_hex),
    )
    check("solvent after payout", solvent(c))
    as_(CHALLENGER, 0)
    moved = c.withdraw()
    check("withdraw moves the credited balance", moved == CHALLENGE_BOND + WRITE_BOND)
    check("solvent after withdraw", solvent(c))


def test_challenge_rejected_forfeits_the_bond():
    m = ScriptedModel()
    c, _ = fresh(m)
    a = write(c, m, env("Root claim."))
    m.defeats = False
    as_(CHALLENGER, CHALLENGE_BOND)
    c.challenge(a, "A finding that is not in the source.")
    check("entry survives a failed challenge", c.get_entry(a)["status"] == hs.ADMITTED)
    check("failed challenger is credited nothing", c.balance_of(CHALLENGER.as_hex) == 0)
    check("solvent after a failed challenge", solvent(c))


def test_second_framing_can_still_refuse():
    m = ScriptedModel()
    c, _ = fresh(m)
    a = write(c, m, env("Root claim."))
    m.defeats = (True, False)
    as_(CHALLENGER, CHALLENGE_BOND)
    cid = c.challenge(a, "Visible once, not on a second reading.")
    as_(CHALLENGER, 0)
    outcome = c.confirm_challenge(cid)
    check("second framing can refuse", outcome == hs.REJECTED, outcome)
    check("entry survives", c.get_entry(a)["status"] == hs.ADMITTED)


def test_unreadable_referee_fails_closed():
    m = ScriptedModel()
    c, _ = fresh(m)
    a = write(c, m, env("Root claim."))
    m.defeats = None
    as_(CHALLENGER, CHALLENGE_BOND)
    cid = c.challenge(a, "An objection the referee could not read.")
    check(
        "unreadable referee is not a win",
        c.get_challenge(cid)["outcome"] == hs.REJECTED,
    )
    check("entry survives an unreadable referee", c.get_entry(a)["status"] == hs.ADMITTED)


# ----------------------------------------------------------------- cascade


def build_chain(c, m):
    a = write(c, m, env("Root claim."))
    b = write(c, m, env("Second claim.", source="https://example.org/b", supports=[a]))
    d = write(c, m, env("Third claim.", source="https://example.org/c", supports=[b]))
    return a, b, d


def test_cascade_taints_dependents():
    m = ScriptedModel()
    c, _ = fresh(m, cascade_depth=3)
    a, b, d = build_chain(c, m)
    m.defeats = True
    as_(CHALLENGER, CHALLENGE_BOND)
    cid = c.challenge(a, "The source says otherwise.")
    as_(CHALLENGER, 0)
    c.confirm_challenge(cid)
    check("revoked root", c.get_entry(a)["status"] == hs.REVOKED)
    check("direct dependent tainted", c.get_entry(b)["status"] == hs.TAINTED)
    check("second level tainted", c.get_entry(d)["status"] == hs.TAINTED)
    check("nothing deferred within the bound", c.deferred_queue() == [])
    check("solvent after cascade", solvent(c))


def test_cascade_respects_the_depth_bound():
    m = ScriptedModel()
    c, _ = fresh(m, cascade_depth=1)
    a, b, d = build_chain(c, m)
    m.defeats = True
    as_(CHALLENGER, CHALLENGE_BOND)
    cid = c.challenge(a, "The source says otherwise.")
    as_(CHALLENGER, 0)
    c.confirm_challenge(cid)
    check("first level still tainted", c.get_entry(b)["status"] == hs.TAINTED)
    check("second level untouched", c.get_entry(d)["status"] == hs.ADMITTED)
    check("second level deferred instead", c.deferred_queue() == [d], c.deferred_queue())


def test_entry_with_its_own_source_survives_rejudge():
    m = ScriptedModel()
    c, _ = fresh(m, cascade_depth=3)
    a, b, _d = build_chain(c, m)
    m.defeats = True
    as_(CHALLENGER, CHALLENGE_BOND)
    cid = c.challenge(a, "The source says otherwise.")
    as_(CHALLENGER, 0)
    c.confirm_challenge(cid)
    as_(WRITER2, 0)
    status = c.rejudge(b)
    check("an independently sourced entry survives", status == hs.ADMITTED, status)
    check("it no longer leans on the revoked entry", c.get_entry(b)["supports"] == [])
    check("its depth collapses to the root", c.get_entry(b)["depth"] == 0)


def test_entry_without_its_own_support_dies():
    m = ScriptedModel()
    c, _ = fresh(m, cascade_depth=3)
    a, b, _d = build_chain(c, m)
    m.defeats = True
    as_(CHALLENGER, CHALLENGE_BOND)
    cid = c.challenge(a, "The source says otherwise.")
    as_(CHALLENGER, 0)
    c.confirm_challenge(cid)
    m.support = False
    as_(WRITER2, 0)
    status = c.rejudge(b)
    check("an entry that cannot restand is revoked", status == hs.REVOKED, status)


# ------------------------------------------------------------------ expiry


def test_expiry_returns_the_bond_and_taints_children():
    m = ScriptedModel()
    c, _ = fresh(m, cascade_depth=3, admit_ttl=1)
    a = write(c, m, env("Root claim."))
    b = write(c, m, env("Second claim.", source="https://example.org/b", supports=[a]))
    as_(WRITER2, 0)
    status = c.expire(a)
    check("elapsed window expires the entry", status == hs.EXPIRED, status)
    check("bond returns to the author", c.balance_of(WRITER.as_hex) == WRITE_BOND)
    check("children of an expired entry are tainted", c.get_entry(b)["status"] == hs.TAINTED)
    check("solvent after expiry", solvent(c))


def test_expiry_refuses_inside_the_window():
    m = ScriptedModel()
    c, _ = fresh(m, admit_ttl=1000)
    a = write(c, m, env("Root claim."))
    as_(WRITER2, 0)
    check(
        "expiry refuses inside the window",
        expect_error(lambda: c.expire(a), "window has"),
    )


# ------------------------------------------------------------------ report


def test_report_publishes_false_rejection():
    m = ScriptedModel()
    c, _ = fresh(m)
    write(c, m, env("Honest one."))
    write(c, m, env("Honest two.", source="https://example.org/b"))
    m.support = False
    write(c, m, env("Honest three but rejected.", source="https://example.org/c"))
    write(c, m, env("A forged source.", klass="source_forgery"))
    m.support = True
    r = c.report(0)
    check("honest attempts counted", r["honest_attempts"] == 3, r["honest_attempts"])
    check("honest admissions counted", r["honest_admitted"] == 2, r["honest_admitted"])
    check(
        "false rejection published in thousandths",
        r["false_rejection_milli"] == 333,
        r["false_rejection_milli"],
    )
    forgery = [x for x in r["classes"] if x["class"] == "source_forgery"][0]
    check("attack class admits nothing", forgery["ever_admitted"] == 0)


def test_report_marks_honest_class_as_control():
    m = ScriptedModel()
    c, _ = fresh(m)
    write(c, m, env("Honest one."))
    r = c.report(0)
    honest = [x for x in r["classes"] if x["class"] == "honest"][0]
    check("honest is not scored as a defence", honest["settled"] is False)


# -------------------------------------------------------------------- main


def test_premise_carries_the_entry_and_its_removal_kills_it():
    """The cascade only means something if a rejudge is a different question.

    Here the second entry is admitted while the first is standing, and refused
    once the first is gone, on a page that never changed. Without premises in
    the judging prompt both answers would be identical and the cascade would be
    decoration.
    """
    m = ScriptedModel()
    c, _sid = fresh(m)

    base = write(c, m, env("The registry lists ACME as dissolved on 4 March."))
    check("the premise is admitted", c.get_entry(base)["status"] == hs.ADMITTED)

    m.needs_premise = True
    leaner = write(
        c,
        m,
        env(
            "ACME's April asset transfer was made by a dissolved company.",
            source="https://example.org/b",
            supports=[base],
        ),
    )
    e = c.get_entry(leaner)
    check("a claim standing on a live premise is admitted", e["status"] == hs.ADMITTED, e)
    check("and the premise reached the judge", any("PREMISES" in p for p in m.seen))

    _revoke_premise(c, m, base)

    check("the dependent is tainted", c.get_entry(leaner)["status"] == hs.TAINTED,
          c.get_entry(leaner)["status"])
    as_(WRITER)
    outcome = c.rejudge(leaner)
    check("and dies on rejudge with the premise gone", outcome == hs.REVOKED, outcome)
    check("solvent after the cascade", solvent(c))


def _revoke_premise(c, m, eid):
    """Revoke through the front door: an upheld challenge, not a test hook."""
    m.defeats = True
    as_(CHALLENGER, CHALLENGE_BOND)
    cid = c.challenge(eid, "the registry page does not carry this")
    as_(CHALLENGER, 0)
    c.confirm_challenge(cid)
    m.defeats = False


def test_every_vote_is_recorded_as_cast():
    """Without the individual votes a receipt can only be checked against
    itself. These are what make `verify` a check rather than a tautology."""
    m = ScriptedModel()
    c, _sid = fresh(m)

    clean = write(c, m, env("ACME Corp was dissolved on 4 March."))
    v = c.get_entry(clean)["votes"]
    check("an admitted entry records two yes votes", v["a"] == "yes" and v["b"] == "yes", v)
    check("and no conflict", v["conflict"] == "none", v)

    m.support = (True, None)
    split = write(c, m, env("ACME Corp filed something.", source="https://example.org/b"))
    v = c.get_entry(split)["votes"]
    check("a split vote is kept split", v["a"] == "yes" and v["b"] == "unread", v)
    check("an unread round is not stored as a no", v["b"] != "no", v)
    check("and the consistency round was never reached", v["conflict"] == "", v)

    m.support = False
    refused = write(c, m, env("ACME Corp is still trading.", source="https://example.org/c"))
    v = c.get_entry(refused)["votes"]
    check("a refusal records two no votes", v["a"] == "no" and v["b"] == "no", v)

    m.support = True
    gone = write(c, m, env("ACME has a licence.", source="https://example.org/missing"))
    v = c.get_entry(gone)["votes"]
    check("an unreachable source was never asked", v["a"] == "unasked", v)
    check("which is not the same as unread", v["a"] != "unread", v)


# --------------------------------------------------------------- the gate

# Every combination that reaches the verdict assembly, including the ones the
# contract can only produce by accident. The point of a shared pure function is
# that the awkward cases are cheap to enumerate, so they are enumerated.
DECIDE_VECTORS = [
    (True, True, 2, 2, -1),
    (True, True, 2, 2, 7),
    (True, True, 2, 2, None),
    (False, False, 2, 2, -1),
    (True, False, 2, 2, -1),
    (False, True, 2, 2, -1),
    (None, True, 1, 2, -1),
    (None, None, 0, 1, -1),
    (True, None, 1, 2, -1),
    (True, True, 1, 2, -1),
    (True, True, 0, 0, -1),
    (False, False, 2, 2, 3),
    (None, None, 0, 2, -1, False),
    (True, True, 2, 2, -1, False),
]


def test_decide_is_identical_in_contract_and_gate():
    """The gate duplicates `decide` rather than importing the contract, because
    the contract file drags the runtime in. A duplicate is only acceptable while
    something proves the two are the same string of behaviour."""
    mismatches = []
    for v in DECIDE_VECTORS:
        if hs.decide(*v) != gate.decide(*v):
            mismatches.append((v, hs.decide(*v), gate.decide(*v)))
    check("contract and gate agree on every vector", not mismatches, mismatches)
    check(
        "an unreadable round never reads as a clean negative",
        hs.decide(None, False, 1, 1, -1)[0] == "INCONCLUSIVE",
    )
    check(
        "the round floor is checked before the answers",
        hs.decide(True, True, 1, 2, -1)[0] == "INCONCLUSIVE",
    )


def _corpus_row(c, eid):
    e = c.get_entry(eid)
    return {
        "entry_id": eid,
        "envelope_hash": e["envelope_hash"],
        "dedup_key": envtool.dedup_key(e["space_id"], e["claim"]),
        "status": e["status"],
        "note": e["note"],
        "snapshot_hash": e["snapshot_hash"],
    }


def test_gate_exit_codes():
    model = ScriptedModel()
    c, _sid = fresh(model)

    admitted = env("ACME Corp was dissolved on 4 March.")
    aid = write(c, model, admitted)

    model.support = False
    refused = env("ACME Corp is still trading.", source="https://example.org/b", klass="source_forgery")
    rid = write(c, model, refused)

    corpus = [_corpus_row(c, aid), _corpus_row(c, rid)]

    code, payload = gate.run_gate(admitted, corpus)
    check("an admitted entry exits 0", code == 0, payload)
    check("and reports the verdict", payload["verdict"] == "ADMITTED", payload)

    code, payload = gate.run_gate(refused, corpus)
    check("a refused entry exits 1", code == 1, payload)

    unknown = env("Nothing has ever been said about this.", source="https://example.org/c")
    code, payload = gate.run_gate(unknown, corpus)
    check("an unjudged entry exits 2, not 0", code == 2, payload)

    broken = dict(admitted)
    broken["version"] = "hearsay/0"
    code, payload = gate.run_gate(broken, corpus)
    check("a malformed envelope exits 3, not 2", code == 3, payload)
    check("and never reaches a verdict", payload["verdict"] is None, payload)


def test_gate_refuses_a_flattened_duplicate():
    """The contract raises on this. The gate should refuse locally rather than
    send a caller to spend a bond on a certain failure."""
    model = ScriptedModel()
    c, _sid = fresh(model)
    first = env("ACME Corp was dissolved on 4 March.")
    fid = write(c, model, first)
    corpus = [_corpus_row(c, fid)]

    twin = env("  ACME   Corp\twas dissolved on 4 MARCH.  ", source="https://example.org/c")
    code, payload = gate.run_gate(twin, corpus)
    check("a whitespace twin is refused before the chain", code == 1, payload)
    check("and the reason names the original", "duplicate" in payload["reason"], payload)


def test_gate_strict_refuses_an_unjudged_entry():
    model = ScriptedModel()
    c, _sid = fresh(model)
    unknown = env("Never submitted anywhere.", source="https://example.org/c")
    code, payload = gate.run_gate(unknown, [], strict=True)
    check("--strict turns no record into a refusal", code == 1, payload)
    code, payload = gate.run_gate(unknown, [])
    check("without it the same entry is inconclusive", code == 2, payload)


def _receipt(c, eid, envelope, min_rounds=2, a=True, b=True, conflict=-1):
    e = c.get_entry(eid)
    return {
        "envelope": envelope,
        "envelope_hash": e["envelope_hash"],
        "snapshot_excerpt": c.entries[eid].snapshot,
        "snapshot_hash": e["snapshot_hash"],
        "status": e["status"],
        "rounds": e["rounds"],
        "min_rounds": min_rounds,
        "rounds_detail": {"support_a": a, "support_b": b, "conflict": conflict},
    }


def test_verify_reproduces_a_sound_receipt():
    model = ScriptedModel()
    c, _sid = fresh(model)
    e = env("ACME Corp was dissolved on 4 March.")
    eid = write(c, model, e)

    code, payload = gate.run_verify(_receipt(c, eid, e))
    check("a sound receipt reproduces offline", code == 0, payload)
    check("and lands on the recorded verdict", payload["recomputed_verdict"] == "ADMITTED", payload)


def test_verify_catches_a_forged_verdict():
    """The one line in a corpus that can be shown to be false with nothing but
    the file in front of you."""
    model = ScriptedModel()
    c, _sid = fresh(model)
    model.support = False
    e = env("ACME Corp is still trading.", source="https://example.org/b", klass="source_forgery")
    eid = write(c, model, e)

    receipt = _receipt(c, eid, e, a=False, b=False)
    receipt["status"] = "ADMITTED"          # the lie
    code, payload = gate.run_verify(receipt)
    check("a verdict that does not follow is caught", code == 1, payload)
    check(
        "and the failure names both verdicts",
        any("recorded ADMITTED" in f for f in payload["failures"]),
        payload,
    )


def test_verify_catches_a_reattributed_snapshot():
    model = ScriptedModel()
    c, _sid = fresh(model)
    e = env("ACME Corp was dissolved on 4 March.")
    eid = write(c, model, e)

    receipt = _receipt(c, eid, e)
    receipt["snapshot_excerpt"] = "A different page entirely."
    code, payload = gate.run_verify(receipt)
    check("a verdict moved onto another page is caught", code == 1, payload)
    check(
        "and the failure names the snapshot",
        any("snapshot_hash" in f for f in payload["failures"]),
        payload,
    )


TESTS = [
    test_admits_a_supported_claim,
    test_unreachable_source,
    test_source_does_not_support,
    test_framings_disagree_is_inconclusive,
    test_unreadable_round_is_inconclusive,
    test_unreadable_consistency_check_is_inconclusive,
    test_contradiction_names_the_entry,
    test_unnameable_conflict_is_inconclusive,
    test_dedup_survives_whitespace_padding,
    test_cli_and_contract_flatten_identically,
    test_envelope_canonicalisation,
    test_cannot_lean_on_an_unadmitted_entry,
    test_depth_tracks_the_graph,
    test_challenge_upheld_revokes_and_pays,
    test_challenge_rejected_forfeits_the_bond,
    test_second_framing_can_still_refuse,
    test_unreadable_referee_fails_closed,
    test_cascade_taints_dependents,
    test_cascade_respects_the_depth_bound,
    test_entry_with_its_own_source_survives_rejudge,
    test_entry_without_its_own_support_dies,
    test_expiry_returns_the_bond_and_taints_children,
    test_expiry_refuses_inside_the_window,
    test_report_publishes_false_rejection,
    test_report_marks_honest_class_as_control,
    test_premise_carries_the_entry_and_its_removal_kills_it,
    test_every_vote_is_recorded_as_cast,
    test_decide_is_identical_in_contract_and_gate,
    test_gate_exit_codes,
    test_gate_refuses_a_flattened_duplicate,
    test_gate_strict_refuses_an_unjudged_entry,
    test_verify_reproduces_a_sound_receipt,
    test_verify_catches_a_forged_verdict,
    test_verify_catches_a_reattributed_snapshot,
]


def main():
    for t in TESTS:
        print(t.__name__)
        t()
    print()
    print("%d passed, %d failed" % (len(PASS), len(FAIL)))
    if FAIL:
        for name in FAIL:
            print("  failed: " + name)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
