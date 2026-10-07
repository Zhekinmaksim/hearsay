#!/usr/bin/env python3
"""Inline the corpus into the page and write web/index.html.

    python3 scripts/build_site.py

The data is baked in rather than fetched at load. A page that fetches its own
corpus is one failed request away from showing nothing, and the thing being
published here is a record: it should be readable from a saved file, from a
repository, and from anywhere that will not let a page call out.

Reads only the published corpus. Dry runs write to runs/offline separately.
"""

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


def main():
    if not os.path.exists(CORPUS):
        print("no published corpus at %s" % CORPUS, file=sys.stderr)
        return 2

    corpus = json.load(open(CORPUS, encoding="utf-8"))
    template = open(TEMPLATE, encoding="utf-8").read()
    if os.path.exists(os.path.join(ROOT, "web", "live.html")):
        template = template.replace(
            "</header>",
            '</header>\n  <p class="whereabouts"><a href="live.html">Live Bradbury record — sources, votes and receipts</a> · offline stand below</p>',
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
             "defuse", "fence", "decide", "localGate", "cascade"]
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
