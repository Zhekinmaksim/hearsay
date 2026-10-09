# Hearsay film

A 60-second Remotion explainer, 1920 × 1080 at 30 fps, using the site's
Newsreader and Archivo fonts and the supplied soundtrack. `hearsay.run` is the
owner's planned domain. The working demo is https://hearsay-psi.vercel.app/app.html.

```sh
npm ci --ignore-scripts
npm run sync
npx tsc --noEmit
npm run studio
npm run sheet
npm run render
# Review the export, copy the MP4 and evidence.json to ../web/demo/, then:
npm run check
```

Set `CHROME_PATH` to an installed browser executable to render without a browser
download. On macOS:

```sh
CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npm run sheet
CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npm run render
```

The output is `out/hearsay.mp4`; `sheet/` contains 24 review frames. Rendering
runs in a separate headless profile and does not connect to a wallet. Node and
npm dependencies are required only for the optional film, not the Python
contract tests or offline dry run.

The site serves the reviewed export at `../web/demo/hearsay.mp4`, with an input
and checkpoint manifest in `../web/demo/evidence.json`. After rendering a new
export, copy both `out/hearsay.mp4` and `out/evidence.json` there, then run
`npm run check`. The check rejects changed inputs or a stale published export.

The first part shows **offline scripted examples with fictional sources**.
Claims and votes come from the existing offline corpus. `sync` adds exact
source text from the seed only after checking its SHA-256 against each recorded
pin. The cascade is computed by the same `cascade()` used on the page. It
illustrates tested application behaviour; it is not a live attack result.

The numbers scene first shows the harness's nine honest controls and eighteen
replayed verdicts. It then shows the **dated published Bradbury checkpoint**,
including its honest-control target and incomplete status. `sync` verifies each
live snapshot and replays each receipt through the Python gate before copying
only checkpoint metadata into the film. It never overwrites `web/corpus.json`.
Accepted receipts are provisional; unresolved attempts are not contract refusals.

After publishing a new verified checkpoint, run `sync`, `sheet` and `render`
again, review and replace the public export, then run `check`. Do not remove the incomplete-evaluation disclosure until the full
cohort has been reconciled and the negative phase completed. A new frontend
wallet transaction is a separate live acceptance check.

`src/beats.json` retains the supplied picture/music timing. The supplied track
has a 92.25 BPM body and a slower outro; `scripts/cut_track.py` preserves the
original cut constants. No new audio alignment measurements are claimed here.
The project owner confirmed the right to use `public/track.wav` in the public
demo on 9 October 2026. This confirmation does not grant a general license to
redistribute the soundtrack. Font licenses are documented in `../web/fonts/README.md`.

The code follows the repository's MIT license. Remotion's own license applies
to its packages; the soundtrack and fonts have their separate terms.
