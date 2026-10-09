#!/usr/bin/env python3
"""Inline the corpus into the page and write web/index.html.

    python3 scripts/build_site.py

The data is baked in rather than fetched at load. A page that fetches its own
corpus is one failed request away from showing nothing, and the thing being
published here is a record: it should be readable from a saved file, from a
repository, and from anywhere that will not let a page call out.

Reads only the published corpus. Dry runs write to runs/offline separately.
"""

import copy
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, "web", "corpus.json")
TEMPLATE = os.path.join(ROOT, "web", "template.html")
OUT = os.path.join(ROOT, "web", "index.html")

MARKER = "/*__CORPUS__*/ null"
MARK = os.path.join(ROOT, "web", "mark.svg")
FAVICON = os.path.join(ROOT, "web", "favicon.svg")
LIB_MARKER = "/*__LIB__*/"
LIB = os.path.join(ROOT, "web", "lib.mjs")
SEED = os.path.join(ROOT, "corpus", "seed.json")


def enrich_offline_snapshots(corpus, seed=None):
    """Copy the scripted corpus and attach only its exact hash-pinned pages.

    Match dry_run.py's source dictionary, including the last fixture for a URL.
    The published golden corpus is never changed. Live evidence is not enriched
    from fictional fixtures.
    """
    enriched = copy.deepcopy(corpus)
    if enriched.get("run") != "offline-scripted":
        return enriched
    if seed is None:
        with open(SEED, encoding="utf-8") as fh:
            seed = json.load(fh)
    pages = {row["source_url"]: row["page"] for row in seed["entries"]
             if row.get("page") is not None}
    by_id = {row["id"]: row for row in seed["entries"]}
    for row in enriched["entries"]:
        page = pages.get(row["source_url"], "")
        if not isinstance(page, str):
            raise ValueError("scripted source text must be a string")
        digest = hashlib.sha256(page.encode("utf-8")).hexdigest()
        if digest != row.get("snapshot_hash"):
            raise ValueError("scripted source does not match snapshot pin for %s" % row.get("id"))
        if "snapshot_excerpt" in row and row["snapshot_excerpt"] != page:
            raise ValueError("existing scripted excerpt differs from pinned fixture")
        row["snapshot_excerpt"] = page
        # The archived golden rows omit inert author notes. Recover the full
        # receipt envelope only when its canonical hash proves every field.
        envelope = {"version": "hearsay/1", "space_id": enriched["space_id"],
                    "claim": row["claim"], "source_url": row["source_url"],
                    "entry_class": row["entry_class"]}
        for key, value in [("supports", row.get("supports")),
                           ("expects", row.get("expects")),
                           ("author_note", by_id.get(row.get("id"), {}).get("note"))]:
            if value:
                envelope[key] = value
        canonical = json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != row.get("envelope_hash"):
            raise ValueError("scripted envelope does not match recorded pin")
        row["envelope"] = envelope
    return enriched


def render_page():
    """Render in memory. Only main() writes the generated index."""
    if not os.path.exists(CORPUS):
        print("no published corpus at %s" % CORPUS, file=sys.stderr)
        return 2

    corpus = enrich_offline_snapshots(json.load(open(CORPUS, encoding="utf-8")))
    template = open(TEMPLATE, encoding="utf-8").read()
    if os.path.exists(os.path.join(ROOT, "web", "app.html")):
        template = template.replace(
            "</header>",
            '<p class="whereabouts"><a href="app.html">Open the live Bradbury app</a></p></header>',
            1,
        )
    if os.path.exists(os.path.join(ROOT, "web", "live.html")):
        template = template.replace(
            "</header>",
            '</header>\n  <p class="whereabouts"><a href="live.html">Live Bradbury record — sources, votes and receipts</a> · offline stand below</p>',
            1,
        )
    elif os.path.exists(os.path.join(ROOT, "web", "bradbury-prompt-checkpoint.json")):
        checkpoint = json.load(open(os.path.join(ROOT, "web", "bradbury-prompt-checkpoint.json"), encoding="utf-8"))
        if checkpoint.get("complete") is not False:
            raise ValueError("prompt checkpoint must be explicitly incomplete")
        honest = int(checkpoint["coverage"]["honest_judged"])
        required = int(checkpoint["required_honest_judgements"])
        template = template.replace(
            "</header>",
            '</header>\n  <p class="whereabouts">Bradbury campaign incomplete: %d/%d verified honest controls. <a href="bradbury-prompt-checkpoint.json">Current verified checkpoint</a> · offline stand below</p>' % (honest, required),
            1,
        )
    elif os.path.exists(os.path.join(ROOT, "web", "bradbury-decisions-checkpoint.json")):
        template = template.replace(
            "</header>",
            '</header>\n  <p class="whereabouts">Bradbury experiment incomplete: pending protocol consensus. <a href="bradbury-decisions-checkpoint.json">Current verified checkpoint</a> · <a href="bradbury-checkpoint.json">Earlier deployment</a> · offline stand below</p>',
            1,
        )
    elif os.path.exists(os.path.join(ROOT, "web", "bradbury-checkpoint.json")):
        template = template.replace(
            "</header>",
            '</header>\n  <p class="whereabouts">Bradbury run incomplete: pending protocol consensus. <a href="bradbury-checkpoint.json">Verified checkpoint</a> · offline stand below</p>',
            1,
        )
    if MARKER not in template or LIB_MARKER not in template:
        print("template is missing a marker", file=sys.stderr)
        return 2

    # web/lib.mjs is a module so test/parity.mjs can import it and check it
    # against the Python side. Inlined into the page the export line is dead
    # weight, so it comes off here rather than being kept in two versions.
    lib = open(LIB, encoding="utf-8").read()
    lib = "\n".join(l for l in lib.splitlines() if not l.startswith("export {"))
    names = ["sha256", "flatten", "dedupKey", "canonical", "envelopeHash",
             "defuse", "fence", "decide", "localGate", "cascade",
             "fnv1a64", "fingerprintMatches"]
    lib += "\nconst HS = { " + ", ".join(names) + " };\n"

    # `</script>` inside a string literal would close the host script tag early,
    # which is the one way inlining JSON into HTML goes wrong.
    blob = json.dumps(corpus, ensure_ascii=False).replace("</", "<\\/")
    # Everything the page needs is carried inside it. A record that goes blank
    # when a sibling file is missing is not a record, and the icon has to
    # survive being saved to a desktop as one file.
    import base64

    mark = open(MARK, encoding="utf-8").read()
    mark = mark[mark.index("<svg"):].strip()
    favicon = open(FAVICON, "rb").read()
    favicon_uri = "data:image/svg+xml;base64," + base64.b64encode(favicon).decode()

    apple = os.path.join(ROOT, "web", "favicon-180.png")
    if os.path.exists(apple):
        apple_uri = "data:image/png;base64," + base64.b64encode(open(apple, "rb").read()).decode()
    else:
        apple_uri = favicon_uri

    # og:image is the one thing that cannot be inlined: a crawler fetches it by
    # URL. Relative works on most, absolute works on all, so pass --base when
    # the deploy host is known.
    base = ""
    for i, arg in enumerate(sys.argv):
        if arg == "--base" and i + 1 < len(sys.argv):
            base = sys.argv[i + 1].rstrip("/") + "/"
    og = base + "og.png"

    page = (template
            .replace(LIB_MARKER, lib)
            .replace("/*__MARK__*/", mark)
            .replace("/*__FAVICON__*/", favicon_uri)
            .replace("/*__APPLETOUCH__*/", apple_uri)
            .replace("/*__OGIMAGE__*/", og)
            .replace(MARKER, blob))

    return page, corpus, og, base


def main():
    rendered = render_page()
    if isinstance(rendered, int):
        return rendered
    page, corpus, og, base = rendered
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(page)

    size = os.path.getsize(OUT)
    print("wrote %s  (%.1f kB, self-contained)" % (os.path.relpath(OUT, ROOT), size / 1024))
    print("     %d judged entries, %d turned away at the write path"
          % (len(corpus["entries"]), len(corpus.get("refused_at_write", []))))
    print("     og:image points at %s%s" % (og, "" if base else "  (relative; pass --base https://host to make it absolute)"))
    if corpus.get("run") == "offline-scripted":
        print()
        print("     the page carries the harness warning, because this corpus is")
        print("     a scripted dry run and its rates measure the stand, not the defence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
