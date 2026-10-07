# Hearsay

An admission layer in front of shared agent memory, on GenLayer.

An agent reads shared memory and acts on what it finds there. Write one
plausible falsehood into that memory and every decision taken downstream is
poisoned — more cheaply than any direct attack, because no contract has to be
broken, only a sentence written.

Hearsay judges a candidate entry on exactly two questions, and refuses to judge
a third:

- **support** — does the cited source, fetched by consensus at judging time, actually support the claim
- **consistency** — does the claim contradict something already admitted
- *not* whether the claim is true in general. That is an undecidable specification, and [Jastrow](https://github.com/Zhekinmaksim/jastrow) exists to demonstrate it.

## Verdicts

| verdict | meaning |
| --- | --- |
| `ADMITTED` | source supports the claim, nothing admitted contradicts it |
| `UNSOURCED` | source missing, unfetchable, or does not support the claim |
| `CONTRADICTED` | conflicts with an admitted entry, which is named |
| `INCONCLUSIVE` | unreadable rounds, disagreeing framings, or too few rounds |

`INCONCLUSIVE` does not admit. Fail closed, or the entire attack surface
collapses to making an entry unreadable.

## The revocation cascade

Poison propagates. Entry B leaned on A, C leaned on B. Revoke A and the other
two are standing on a falsehood while still counting as admitted.

So revocation propagates too. Every entry records what it leaned on. When one
is revoked, everything above it becomes `TAINTED` and has to be rejudged on its
own source. An entry with an independent source survives; an entry that only
ever stood on the revoked one dies with it.

The walk is breadth-first and bounded by a per-space depth. Past the bound,
entries go to a deferred queue rather than into the same transaction —
unwinding an unbounded graph in one call is the largest source of unexpected
cost in a design like this.

Cycles cannot be built: an entry may only cite entries that already exist, so
the graph is acyclic by construction. What that does not stop — entries
propping each other up with no external source — is stopped separately, by
requiring a fetchable source on every entry whether it cites anything or not.

## Why the source is fetched, not submitted

Suborn takes the evidence body inline and treats the URL as metadata. That is
right there, because the object under test is a document the attacker wrote.

Here the object under test is provenance, and an entry carrying its own
"source" proves nothing — the writer would attach a page saying what the claim
says. So the contract fetches, and pins what it fetched. Every downstream step
refers to that pin: a challenge is admissible only if the finding is visible in
it, and a rejudge compares against it. An unreproducible verdict cannot be
challenged.

## The gate

The gate is the product. The corpus is the evidence that the gate works.

```
python3 cli/gate.py gate   --entry e.json --corpus web/corpus.json
python3 cli/gate.py verify --receipt r.json
```

`gate` is what a writing agent calls before it writes. Exit codes are chosen so
that `set -e` does the obvious thing:

| code | meaning |
| --- | --- |
| 0 | `ADMITTED`, or the receipt reproduces |
| 1 | refused: `UNSOURCED`, `CONTRADICTED`, a flattened duplicate, or a receipt that does not reproduce |
| 2 | `INCONCLUSIVE`, or no verdict on record yet |
| 3 | the envelope is malformed and was never judged |

2 and 3 are separate on purpose. `INCONCLUSIVE` means consensus looked and could
not tell, which is a fact about the entry. 3 means nothing was ever asked. A
caller that collapses them will eventually treat "we could not read it" as "it
is fine".

Everything the gate can settle locally is settled locally, before the chain: a
malformed envelope and a claim that flattens onto one already in the space are
both refused without spending a bond.

`verify` recomputes a verdict from a receipt with no chain, no network and no
model. It checks three things, and each catches a different lie: the envelope
hash catches a row describing a different entry, the snapshot hash catches a
verdict re-attributed to another page, and the verdict itself catches a row
whose recorded answers do not produce the verdict printed beside them. The third
is the one that matters — it is the only line in a corpus that can be shown to
be false with nothing but the file in front of you.

Verdict assembly lives in one pure function, `decide`, implemented in both the
contract and the gate and run over the same vectors by the test suite. A
duplicate is only tolerable while something proves the two are the same
behaviour.

## What gets published

Two numbers per run:

- **false-rejection rate on honest entries with real sources**, first
- admission rate per attack class, second

That order is deliberate. An admission layer that cuts good-faith entries does
not survive production, however well it scores against attacks, and almost
nobody publishes how much good work they break. A class that has not reached the
space's round threshold is reported as `INCONCLUSIVE`, never as a defence that
held. A class prevented by the envelope rules is flagged and excluded from the
caught count.

## The page

`web/index.html` is the record: every entry offered to the space, kept whatever
the outcome, with the false-rejection rate on honest entries printed before any
score against attacks.

It opens on the gate doing its job rather than on a statistic. A real claim from
the record is set at headline size, the way evidence is set, and the ruling
arrives under it — one orchestrated moment on load, and after that the same
reveal only answers a click. Two controls step through the attempts and the
honest entries so the two sides can be read against each other, which is the
comparison the whole project turns on. A rate as the first thing on the page
would be a claim about the gate; this is the gate. The corpus is baked into the page rather than fetched, so it
reads from a saved file, from the repository, and from anywhere that will not
let a page call out.

Three things on the page do something no other corpus page can, because they
are the product rather than a picture of it.

**Revoke an entry** replays the cascade in the browser. Who leans on whom, and
whether an entry's own source carried its claim, are recorded facts from the
run; what re-executes is the contract's own walk — breadth-first, bounded at the
space's depth, then a rejudge of everything tainted with the dead premise
removed. Entries past the bound go to the deferred queue in front of you rather
than being unrolled in one transaction.

**Run the gate** is the half of `cli/gate.py` that needs no chain, live. Paste a
claim that already exists with different spacing and watch dedup flattening
catch it while judging would still see your bytes untouched. Paste one
containing the fence characters and watch them broken before fencing, under a
marker derived from the content it is fencing.

**Verify a receipt** takes a row, lets you forge its verdict, swap its page or
edit its claim, and catches each. The third of those is the thesis of the
project made clickable: the recorded rounds no longer produce the verdict
printed beside them, and that is provable with the file alone.

All of it runs on `web/lib.mjs`, which is a third implementation of code that
already exists twice in Python. `make parity` checks it against the Python over
the same vectors, including zero-width joiners, a right-to-left override and
characters outside the basic plane — the inputs where three implementations
drift apart without anyone noticing. SHA-256 is written out rather than taken
from `crypto.subtle`, which needs a secure context: a page meant to open from a
saved file cannot hash in one place and not the other.

An entry's verdict is its position, not its colour — admitted on one side of the
rule, refused on the other. The only colour on the page is reserved for the two
honesty marks: the warning that a scripted run measures the stand rather than
the defence, and the class that the envelope rules prevent rather than catch. A
page that colour-codes its own scores is selling them.

## Every vote, beside the verdict

The verdict on each entry is printed next to the votes it came from, never
instead of them: both support framings and the consistency round, as cast. An
unread round shows as unread and a round that never ran shows as not asked;
those are the fail-closed cases and the only place the page spends colour.

The idea is taken from how Awwwards publishes a site's score — the total sits
above a table of every juror's individual marks, and next to a link to the
weights that produced it. That is the honest shape for a consensus verdict, and
Hearsay is nothing but consensus verdicts. The same page also pins a section
index at the foot of the screen; the record has grown long enough to need one.
The rules of the space — round floor, cascade depth, admission lifetime — are
published beside the numbers they produced for the same reason.

Recording the votes was not cosmetic. The first version of the verifier rebuilt
the votes from the verdict and then confirmed the verdict followed from them: a
check that could never fail. With the votes stored by the contract and replayed
for real, one row did not reproduce on the first run — an unreachable source was
ruled in a branch of the contract that bypassed `decide`, so the claim that
every verdict comes out of one function was untrue for exactly that path.
`decide` now covers it, in all three implementations, and `make replay` re-derives
every corpus row from its votes on every build so that class of bug cannot come
back quietly.

Publishing the rules beside the numbers caught a second one. The page read the
cascade depth from the report, where it does not exist, so in the browser the
bound was `undefined`, every comparison against it was false, and the cascade
never deferred anything. The page test now fails on the word `undefined`
anywhere in the rendered text, and on a revocation from the root that does not
defer the entry four deep.

## The mark

A vertical rule is the gate. Two claims arrive from the left: the upper one is
carried by its source and crosses, the lower one is not and stops where it was
turned away. The gap is the only part that means anything, which is why it is
sized to survive a 16-pixel favicon.

There are two cuts. The display cut is drawn at the weight of the hairline rules
it sits among; at icon size that weight turns to mush and the gap closes, so the
icon cut is heavier with a shorter stopped bar. A mark legible at one size and a
smear at the other is not a mark.

`make assets` draws all of it, and generates `web/og.png` from the corpus rather
than from a design file. The claim on the share card is a real entry and the
ruling under it is the one the run produced, so after a live run the card tells
the truth about that run instead of the previous one. The mark and the favicon
are baked into `web/index.html` as inline SVG and a data URI: the page keeps its
icon when it is saved to a desktop as a single file.

`og:image` is the one thing that cannot be inlined, because a crawler fetches it
by URL. `make site` leaves it relative; pass `--base https://host` to
`build_site.py` for an absolute one.

## Standing in the ecosystem

Collective Memory was examined as an integration target and rejected. It is a
citizen-journalism platform: people upload photos and video, and events are
clustered by geography, time and semantic proximity, with confidence following
the number of independent sources. There is no agent-written entry and no source
field in the sense used here — the source is the footage. Corroboration as a
product is also already theirs, and rebuilding it on consensus would be a
demonstration rather than infrastructure.

What the ecosystem does have is an agent marketplace, a court for agent-to-agent
deals and an oracle, and none of them has an admission layer in front of shared
state. Write infrastructure everywhere, admissibility infrastructure nowhere.

## Layout

```
contracts/hearsay.py     the Intelligent Contract
cli/gate.py              the gate: admit, refuse, or reproduce a verdict
cli/entry.py             build, hash and check envelopes
spec/memory-entry.md     the hearsay/1 envelope
corpus/seed.json         the seed corpus, with the honest control group
scripts/dry_run.py       run offline into runs/offline, leaving published data intact
scripts/collect_receipts.py match Bradbury receipts and entry state by envelope hash
scripts/diagnose_missing.py explain missing state using the collector's chain reads
scripts/build_assets.py  draw the mark, the icons and the share card
scripts/replay_corpus.py re-derive every corpus row from its recorded votes
scripts/build_site.py    bake the corpus into a self-contained web/index.html
web/mark.svg             the mark, display cut
scripts/emit_vectors.py  write the vectors the JavaScript is checked against
web/template.html        the page, before its data and library are baked in
web/lib.mjs               hashing, flattening, verdict assembly and the cascade, in JS
test/parity.mjs          JavaScript against Python, over the same vectors
test/page.mjs            open the built page and drive every control on it
test/run_tests.py        offline end to end run, no network
test/stub/genlayer.py    local stub: scriptable model and fetcher
```

## Running it

```
make test        # offline end to end, no network
make dry-run     # run the seed corpus, write runs/offline/corpus.json and entries
make gate        # the gate against that corpus, all four exit codes
make assets      # mark, icons and the share card
make site        # bake the corpus, the mark and the icon into web/index.html
make replay      # every corpus row, re-derived from the votes it records
make parity      # the page's JavaScript against the Python, same vectors
make page        # drive every control on the built page (needs jsdom)
make receipts-test # offline checks for collection and diagnosis
make chain-test # stored consensus status and SDK projection stay distinct
make bridge-test # transaction journal survives a lost RPC reply, no network
```

Solvency is asserted after every action that touches value, not only at the end.

Dry runs now write only to `runs/offline/corpus.json` and
`runs/offline/entries/`. They leave `web/corpus.json` and the submitted example
envelopes intact. An explicit output pointing at a published live corpus is
refused. The archived offline corpus remains the reference for the 95 Python
checks, 18 replayed entries, 67 JavaScript checks and 50 page checks.

Before a Bradbury write, both collection and diagnosis must pass
`make receipts-test`. Keep a JSONL manifest with `tx`, `envelope_hash`, `file`
(the exact submitted envelope), and optional `entry_id`. Include
`method: "write_entry"`; deployment and `open_space` transactions can be kept
in the same manifest under their own method names.

After each entry, before sending the next:

```sh
python3 scripts/collect_receipts.py runs/bradbury.jsonl \
  --address "$CONTRACT" --entries runs/live/entries --out runs/records.jsonl
python3 scripts/diagnose_missing.py --address "$CONTRACT" \
  --manifest runs/bradbury.jsonl --records runs/records.jsonl \
  --out runs/diagnosis.json
```

The collector checkpoints authoritative RPC receipts and explorer enrichment
under `runs/receipts/`, checks
the submitted envelope against chain state, and replays its recorded votes.
Incomplete collection exits 2 and preserves existing records. The diagnosis
scans the actual chain entry count and can recover a record under a different
ID. A failed read or partial scan stays unresolved; an accepted receipt without
state does not establish why the entry is missing.

State reads use the installed SDK's machine JSON against Bradbury, independent
of the CLI's active network. Large integers retain their exact value, and
multiline claims are never reparsed as JavaScript display text.

Receipts take status, result, initial validator count and the latest stored
round from `getTransactionAllData` at a recorded EVM block. The SDK's timestamp
projection is retained separately; its legacy enum and repeated round lookup
must not override stored state. A finalized protocol timeout remains an
infrastructure outcome and is never turned into an admitted record.

`get_entry` exposes the snapshot hash. `scripts/enrich_snapshots.py` recovers
the exact pinned bytes from GenVM trace storage, matches their SHA-256 to that
hash, and verifies both the envelope and recorded votes. It writes a separate
`runs/verified-records.jsonl`; only fully verified receipts can be published.
It never substitutes a newly fetched page for the page judged on chain.

Vercel serves the committed `web/` directory using `vercel.json`. Its build does
not run a dry run or install application dependencies.

The live candidates are in `corpus/live.json`: independently fetched
company profiles from Companies House, followed by the attack candidates.
The stale-name candidate cites a verified Wayback capture of Shell's profile
from 23 January 2021 and records its live counterpart. These are candidate
expectations, not measured verdicts. The control group uses one registry, so
its results do not establish performance across arbitrary websites.

Bradbury deployment metadata is in `deployments/bradbury.json`. To build the
deployment source, run `python3 scripts/build_deploy.py`. It preserves the
executable AST and prompt strings, removes documentation and whitespace, and
uses a reversible string dictionary to fit the network's transaction gas cap.
Its source hash is included in the wrapper. No binary Python modules are
required in GenVM. Keep the JSON runner directive as the only initial comment;
additional contiguous comments are parsed as part of that JSON by validators.

The installed CLI 0.39.1 sends zero native value on writes. The thin
`scripts/genlayer_write.mjs` bridge uses its bundled SDK and the already unlocked
OS keychain account, verifies the expected public address, and fsyncs the
transaction ID into the manifest. It never exports the signing key. Values in
the live corpus are in wei; the small demonstration bonds are not an economic
security calibration.

The bridge also fsyncs the public EVM hash before broadcasting and records the
RPC acknowledgement separately. If sending fails, inspect the run's
`bradbury.jsonl.broadcasts.jsonl` and chain receipt before retrying. A missing
HTTP response does not establish that the transaction was never broadcast.

After deploying and confirming `open_space`, run:

```sh
python3 scripts/run_live.py --address "$CONTRACT" --account "$ACCOUNT"
```

The runner resumes from the same manifest, stops before the next write if
collection or diagnosis is unresolved, and checks solvency after every write.
Use `--limit 1` to perform the first write separately. It also refuses an
impossible dependency locally before spending a bond or asking consensus.
The published offline reference stays intact throughout the live run.

`ValidatorsTimeout` and `LeaderTimeout` are protocol outcomes, distinct from a
contract refusal. They are diagnosed and retained with receipts and recovery
actions. `--accept-diagnosed-timeouts` permits continuing only past timeouts
diagnosed and saved in `runs/live/infrastructure-failures.json`; ordinary missing
state still stops the run. Additional reviewed controls keep the completed
honest cohort at twenty without deleting infrastructure failures or counting
them as defence successes.

After the entire run is collected:

```sh
python3 scripts/enrich_snapshots.py
python3 scripts/publish_live.py --address "$CONTRACT"
make site page live-page
```

The publisher checks the chain count, solvency, honest cohort and every verdict,
then rereads each entry and its current RPC status to reject rolled-back state
or a reopened appeal
before writing `web/live-corpus.json` and a separate `web/live.html`. The live
page links each transaction, publishes every vote, filters by class, and replays
editable receipts locally. `make live-page` checks its controls independently
of the fifty checks for the offline stand. Accepted consensus state is labelled
as accepted; it is not presented as finalization.

The public `web/bradbury-checkpoint.json` is an explicitly incomplete snapshot
of the current run, with pinned source bytes, finalized receipts, diagnosed
infrastructure failures and the unresolved transaction. It is not the live
defence measurement. Resume `scripts/run_live.py` with the same manifest after
the pending consensus round resolves; it will not resend existing transactions.
The complete publisher still requires at least twenty judged honest controls
and coverage of every submitted candidate.

Use `--run-dir runs/bradbury-rescue` for a separate deployment. Its manifest,
entries, receipts, diagnosis and infrastructure outcomes are isolated from the
first run. A resume rejects a manifest belonging to another contract. Re-run
the whole cohort on the replacement contract; do not combine admissions from
different deployments into one control denominator. Enrich its records with
explicit `--records` and `--out` paths, then publish with those records,
`--run-dir` and the replacement's `--deployment` metadata.

`--max-rotations 0` keeps the network's five initial validators and disables
leader replacements. Record this operating parameter with the deployment;
a resume rejects a different limit. It leaves both source framings and the
contract's admission rule unchanged. This limits one source of validator-pool
exhaustion; appeals can still expand the committee and depend on network health.

The separate deployment in `deployments/bradbury-decisions.json` tests strict
equality of parsed model decisions. Each validator still answers both support
questions independently; the source-fetch comparison remains comparative.
The changed equivalence criteria and local compatibility evidence are documented
in [Consensus decision comparison](docs/consensus-decisions.md). Its run lives in
`runs/bradbury-decisions` and must complete the same publication checks; results
from the earlier deployments are excluded from its denominator.

To save an incomplete run, use an explicit checkpoint path:

```sh
python3 scripts/publish_checkpoint.py \
  --run-dir runs/bradbury-decisions \
  --records runs/bradbury-decisions/verified-records.jsonl \
  --deployment deployments/bradbury-decisions.json \
  --seed corpus/live.json --out web/bradbury-decisions-checkpoint.json
```

This verifies current chain state, pinned bytes and votes, preserves unresolved
transactions and infrastructure history, and always marks the result incomplete.
It does not bypass the full live publisher's coverage requirements.

`make dry-run` produces a real corpus file with real hashes, real snapshots and
a real verdict per entry. It does not produce a defence measurement, and its own
header says so: the judge in that run is a scripted stand-in that answers what
the seed file tells it to. Feeding it an attack and recording the refusal would
be recording the seed file. The numbers that count come from Bradbury, where the
answer is not ours to write.

The one thing the dry run settles honestly is what happens before any model is
asked. The citation-laundering row is refused at the write path by the ordering
rule, with zero consensus rounds spent, and is reported that way.

## Related

- [Jastrow](https://github.com/Zhekinmaksim/jastrow) — how often validators part company on one specification
- [Suborn](https://github.com/Zhekinmaksim/suborn) — whether a specification survives hostile evidence

The evidence envelope, the two-framing referee check and the fail-closed rule
come from Suborn. The fence defusing and the integer-thousandths reporting come
from Jastrow.
