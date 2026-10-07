#!/usr/bin/env python3
"""Envelope tool for `hearsay/1`.

Canonical form, hashing and dedup flattening. The contract implements the same
two functions; if they ever disagree, dedup silently breaks and one working
trick can be resubmitted with an extra space each time. Both sides are covered
by the vectors in test/vectors.json.

    python3 cli/entry.py build   --claim … --source … [--supports 1,2] [--class honest]
    python3 cli/entry.py hash    envelope.json
    python3 cli/entry.py check   envelope.json
"""

import argparse
import hashlib
import json
import sys

VERSION = "hearsay/1"

MAX_CLAIM = 2048
MAX_SUPPORTS = 8

CLASSES = (
    "honest",
    "direct_injection",
    "source_forgery",
    "citation_laundering",
    "slow_poison",
    "stale_truth",
    "flooding",
)

REQUIRED = ("version", "space_id", "claim", "source_url", "entry_class")
OPTIONAL = ("supports", "author_note", "expects")


def flatten(text):
    """Dedup normalization. Mirrors _flatten in contracts/hearsay.py."""
    out = []
    for ch in text:
        o = ord(ch)
        if o in (0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF):
            continue
        if ch.isspace():
            out.append(" ")
            continue
        out.append(ch.lower())
    flat = "".join(out)
    while "  " in flat:
        flat = flat.replace("  ", " ")
    return flat.strip()


def canonical(env):
    """1. drop unknown keys 2. drop empty optionals 3. sorted, tight, UTF-8."""
    kept = {}
    for k in REQUIRED:
        if k not in env:
            raise ValueError("missing required field: " + k)
        kept[k] = env[k]
    for k in OPTIONAL:
        v = env.get(k)
        if v is None:
            continue
        if isinstance(v, (str, list)) and len(v) == 0:
            continue
        kept[k] = v
    return json.dumps(kept, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def envelope_hash(env):
    return hashlib.sha256(canonical(env).encode("utf-8")).hexdigest()


def dedup_key(space_id, claim):
    return "%d:%s" % (
        int(space_id),
        hashlib.sha256(flatten(claim).encode("utf-8")).hexdigest(),
    )


def validate(env):
    problems = []
    if env.get("version") != VERSION:
        problems.append("version must be exactly " + VERSION)
    claim = env.get("claim", "")
    if not isinstance(claim, str) or len(claim) == 0:
        problems.append("claim is required")
    elif len(claim.encode("utf-8")) > MAX_CLAIM:
        problems.append("claim exceeds %d bytes" % MAX_CLAIM)
    url = env.get("source_url", "")
    if not isinstance(url, str) or len(url.strip()) == 0:
        problems.append("source_url is required")
    elif not url.startswith("http://") and not url.startswith("https://"):
        problems.append("source_url must be http or https")
    if env.get("entry_class") not in CLASSES:
        problems.append("entry_class must be one of: " + ", ".join(CLASSES))
    sup = env.get("supports", [])
    if not isinstance(sup, list):
        problems.append("supports must be a list")
    elif len(sup) > MAX_SUPPORTS:
        problems.append("supports exceeds %d entries" % MAX_SUPPORTS)
    elif len(set(sup)) != len(sup):
        problems.append("supports contains duplicates")
    return problems


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="entry")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--space", type=int, default=0)
    b.add_argument("--claim", required=True)
    b.add_argument("--source", required=True)
    b.add_argument("--supports", default="")
    b.add_argument("--class", dest="klass", default="honest")
    b.add_argument("--note", default="")
    b.add_argument("--expects", default="")
    b.add_argument("--out", default="-")

    h = sub.add_parser("hash")
    h.add_argument("path")

    c = sub.add_parser("check")
    c.add_argument("path")

    args = ap.parse_args(argv)

    if args.cmd == "build":
        env = {
            "version": VERSION,
            "space_id": args.space,
            "claim": args.claim,
            "source_url": args.source,
            "entry_class": args.klass,
        }
        sup = [int(x) for x in args.supports.split(",") if x.strip() != ""]
        if sup:
            env["supports"] = sup
        if args.note:
            env["author_note"] = args.note
        if args.expects:
            env["expects"] = args.expects
        problems = validate(env)
        if problems:
            for p in problems:
                print("error: " + p, file=sys.stderr)
            return 2
        text = json.dumps(env, indent=2, ensure_ascii=False) + "\n"
        if args.out == "-":
            sys.stdout.write(text)
        else:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(text)
        return 0

    if args.cmd == "hash":
        env = _load(args.path)
        print(envelope_hash(env))
        print(dedup_key(env.get("space_id", 0), env.get("claim", "")))
        return 0

    if args.cmd == "check":
        env = _load(args.path)
        problems = validate(env)
        for p in problems:
            print("error: " + p, file=sys.stderr)
        if problems:
            return 1
        print("ok  " + envelope_hash(env))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
