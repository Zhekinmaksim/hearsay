#!/usr/bin/env python3
"""Draw the mark, the icons and the share card.

    python3 scripts/build_assets.py

The share card is generated from web/corpus.json rather than drawn by hand, so
it is a still of the page rather than a picture of it: the claim on the card is
a real entry from the record and the ruling under it is the one the run
produced. Re-run after a live run and the card tells the truth about that run
instead of the previous one.

Rasterising needs cairosvg and the two project faces installed system-wide. If
either is missing the SVG sources are still written and only the PNG step is
skipped, because the page itself only needs the SVG.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
CORPUS = os.path.join(WEB, "corpus.json")

INK = "#15181d"
PAPER = "#f2f3f1"
SOFT = "#585f6b"
FAINT = "#8d94a0"
FLAG = "#7c4a2d"

# Plain family names with generic fallbacks. If the faces are not installed the
# renderer falls back silently rather than failing, so build_assets prints what
# it matched and the card is worth a glance before it ships.
SERIF = "Newsreader, Georgia, serif"
SANS = "Archivo, Helvetica, sans-serif"

# The glyph, as geometry rather than as a file read, so every asset below draws
# the same one and they cannot drift apart.
#
# Two cuts, not one. The display cut is drawn at the weight of the hairline
# rules it sits among. At 16 pixels that weight turns to mush and the gap — the
# only part that carries meaning — closes up, so the icon cut is heavier, the
# stopped bar is shorter, and the upright is pulled in. A mark that is legible
# at one size and a smear at the other is not a mark.
DISPLAY = ('<path d="M6 23 H58"/><path d="M6 43 H29"/><path d="M39 8 V56"/>', 6)
ICON = ('<path d="M5 21 H59"/><path d="M5 45 H26"/><path d="M41 9 V55"/>', 11)


def gate(colour, cut=DISPLAY, transform="", width=None):
    paths, w = cut
    g = (f'<g fill="none" stroke="{colour}" stroke-width="{width or w}" '
         f'stroke-linecap="butt">{paths}</g>')
    return f'<g transform="{transform}">{g}</g>' if transform else g


def esc(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace('"', "&quot;"))


def wrap(text, limit):
    """Greedy wrap by character count. Crude, but the card has one headline and
    a fixed face, so measuring properly would buy nothing."""
    words, lines, current = text.split(), [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if len(candidate) > limit and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def write(path, content):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


# ----------------------------------------------------------------- assets


def favicon_svg():
    """Explicit colours, not currentColor: a favicon is rendered outside the
    page and inherits nothing. The dark-scheme rule is inside the SVG because
    that is the only place a favicon can carry one."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <title>Hearsay</title>
  <style>
    .g {{ stroke: {INK}; }}
    @media (prefers-color-scheme: dark) {{ .g {{ stroke: #e8eae6; }} }}
  </style>
  <g class="g" fill="none" stroke-width="{ICON[1]}" stroke-linecap="butt">{ICON[0]}</g>
</svg>
"""


def logo_svg():
    """Mark plus wordmark. The upright of the gate and the stem of the H sit on
    the same vertical, so the lockup reads as one object rather than two."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 72" width="420" height="72" role="img" aria-label="Hearsay">
  <title>Hearsay</title>
  {gate("currentColor", DISPLAY, "translate(4 4) scale(0.78)")}
  <text x="76" y="48" font-family="{SERIF}" font-size="44" font-weight="400"
        letter-spacing="-0.8" fill="currentColor">Hearsay</text>
  <text x="78" y="66" font-family="{SANS}" font-size="12.5" fill="{SOFT}"
        letter-spacing="0.2">admissibility for shared agent memory</text>
</svg>
"""


def og_svg(corpus):
    report = corpus["report"]
    entries = corpus["entries"]

    # The same entry the page opens on: an injection, because it is the attack a
    # reader recognises as an attack without being told.
    shown = next((e for e in entries if e["entry_class"] == "direct_injection"), None)
    shown = shown or next((e for e in entries if e["status"] != "ADMITTED"), entries[0])

    verdict = {
        "ADMITTED": "Admitted.",
        "UNSOURCED": "Refused as unsourced.",
        "CONTRADICTED": "Refused as contradicted.",
        "INCONCLUSIVE": "Not admitted: inconclusive.",
    }.get(shown["status"], "Refused.")

    note = shown["note"] or "The page was fetched at judging time and does not establish this."
    note = note[0].upper() + note[1:]
    lines = wrap(shown["claim"], 38)[:4]
    body = ""
    for i, line in enumerate(lines):
        body += (f'<text x="104" y="{232 + i * 62}" font-family="{SERIF}" font-size="52" '
                 f'font-weight="300" letter-spacing="-1" fill="{INK}">{esc(line)}</text>')

    rule_bottom = 232 + len(lines) * 62 - 48
    refused_honest = report["honest_attempts"] - report["honest_admitted"]
    rate = (f'{report["honest_attempts"]} honest entries offered, '
            f'{refused_honest} refused')

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630">
  <rect width="1200" height="630" fill="{PAPER}"/>
  {gate(INK, DISPLAY, "translate(72 56) scale(0.62)")}
  <text x="128" y="96" font-family="{SERIF}" font-size="34" fill="{INK}" letter-spacing="-0.5">Hearsay</text>
  <text x="1128" y="96" text-anchor="end" font-family="{SANS}" font-size="17" fill="{FAINT}">memory space {esc(corpus['policy']['name'])}</text>

  <text x="72" y="168" font-family="{SANS}" font-size="19" fill="{SOFT}">Something offered this to the shared memory.</text>
  <rect x="72" y="188" width="3" height="{rule_bottom - 188 + 24}" fill="{INK}"/>
  {body}

  <text x="104" y="{rule_bottom + 94}" font-family="{SERIF}" font-size="36" fill="{INK}" letter-spacing="-0.6">{esc(verdict)}</text>
  <text x="104" y="{rule_bottom + 134}" font-family="{SANS}" font-size="19" fill="{SOFT}">{esc(note)}</text>

  <rect x="72" y="546" width="1056" height="1" fill="#c9cdc6"/>
  <text x="72" y="586" font-family="{SANS}" font-size="18" fill="{INK}">{esc(rate)}</text>
  <text x="1128" y="586" text-anchor="end" font-family="{SANS}" font-size="18" fill="{FLAG}">the number printed first</text>
</svg>
"""


def main():
    made = [
        write(os.path.join(WEB, "favicon.svg"), favicon_svg()),
        write(os.path.join(WEB, "logo.svg"), logo_svg()),
    ]

    if not os.path.exists(CORPUS):
        print("no corpus — run scripts/dry_run.py first", file=sys.stderr)
        return 2
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    made.append(write(os.path.join(WEB, "og.svg"), og_svg(corpus)))

    for path in made:
        print("wrote %s" % os.path.relpath(path, ROOT))

    try:
        import subprocess
        for family in ("Newsreader", "Archivo"):
            got = subprocess.run(["fc-match", family], capture_output=True, text=True).stdout
            mark = "ok" if family.lower() in got.lower() else "MISSING, falling back"
            print("     face %-12s %s" % (family, mark))
    except Exception:
        pass

    try:
        import cairosvg
    except ImportError:
        print()
        print("cairosvg not installed — PNGs skipped (pip install cairosvg)")
        return 0

    raster = [
        ("og.svg", "og.png", 1200, 630),
        ("favicon.svg", "favicon-32.png", 32, 32),
        ("favicon.svg", "favicon-180.png", 180, 180),
    ]
    for src, dst, w, h in raster:
        cairosvg.svg2png(
            url=os.path.join(WEB, src),
            write_to=os.path.join(WEB, dst),
            output_width=w,
            output_height=h,
            background_color=PAPER if dst.startswith("og") else None,
        )
        size = os.path.getsize(os.path.join(WEB, dst))
        print("wrote web/%s  (%d\u00d7%d, %.1f kB)" % (dst, w, h, size / 1024))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
