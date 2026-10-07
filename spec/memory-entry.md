# Memory entry envelope `hearsay/1`

An envelope is one candidate entry offered to one memory space. It is the unit
of admission, the unit of dedup, the unit a challenge refers to, and the unit
the corpus records.

The format exists so that a verdict stays reproducible after the source page
changes, after the writing agent is gone, and after the model behind the
validators is replaced.

## Why the source is fetched, not submitted

Suborn made the opposite choice: the evidence body travels inline and the URL
is metadata. That was right there, because the object under test was the
validator's reading of a document the attacker wrote.

Here the object under test is provenance. An entry that carries its own
"source" proves nothing at all — the writer would simply attach a page that
says what the claim says. So the contract fetches the URL itself, at judging
time, and **pins what it fetched**.

The pinned snapshot is stored on the entry. Everything downstream refers to it:
a challenge is only admissible if the finding is visible in that snapshot, and
a rejudge after a cascade re-fetches and compares against it. Without pinning,
the verdict is unreproducible, and an unreproducible verdict cannot be
challenged.

## Envelope

```json
{
  "version": "hearsay/1",
  "space_id": 0,
  "claim": "…one factual statement, the thing being written to memory…",
  "source_url": "https://…",
  "supports": [4, 11],
  "entry_class": "honest",
  "author_note": "one line for the corpus reader",
  "expects": "ADMITTED"
}
```

| field | required | meaning |
| --- | --- | --- |
| `version` | yes | exactly `hearsay/1`, rejected on mismatch |
| `space_id` | yes | the memory space being written to |
| `claim` | yes | one statement, UTF-8, 1 to 2048 bytes |
| `source_url` | yes | fetched at judging time, never trusted as text |
| `supports` | no | ids of already-admitted entries this one leans on |
| `entry_class` | yes | one label from the closed vocabulary below |
| `author_note` | no | one line, corpus only, never enters a prompt |
| `expects` | no | the verdict the author claims to be forcing |

`author_note` and `expects` never enter any prompt. Anything a writer supplies
outside `claim` and `source_url` must be inert, or the envelope itself becomes
an injection vector against the corpus browser.

## Canonical form and hashing

1. drop every key not listed in the table
2. drop optional keys whose value is empty
3. serialize with sorted keys, `,` and `:` separators, no whitespace, UTF-8, no
   ASCII escaping
4. `envelope_hash = sha256(that string)`, lowercase hex

The claim is hashed exactly as submitted. No normalization, no trimming, no
Unicode folding.

## Two different normalizations

Inherited from `suborn/1`, and the reason is unchanged.

**Judging sees the claim verbatim.** Zero-width joiners, right-to-left
overrides, homoglyphs and unusual whitespace are attack surface. Folding them
before judging erases the class being tested.

**Dedup sees a flattened claim.** Zero-width characters removed, whitespace
collapsed, lowercased, trimmed. Otherwise one working trick is resubmitted a
hundred times with one extra space each and the space is flooded for free.

`cli/entry.py` and `contracts/hearsay.py` implement the same flattening, and
both are covered by the same test vectors.

## Premises

`supports` is not bookkeeping. The claims of the entries named there are written
into the judging prompt as PREMISES, and the judge is told it may assume them
true while still requiring the SOURCE to carry the claim.

This is what makes a rejudge after a cascade a different question from the
original admission. An entry may be admitted on its source plus what the memory
already holds. When one of those premises is revoked it disappears from the
block, and the entry has to stand on the source and whatever survived.

Without it the cascade decides nothing: a tainted entry whose page has not
changed would be asked the identical question a second time and would always
come back. The mechanism only has teeth because the second question is smaller
than the first.

Revoked premises are dropped rather than annotated. An entry does not get to
lean on something the memory has thrown out, and it does not get told that it
used to be able to.

## Entry classes

Declared by the writer, not verified by the contract. It exists so the report
is per class rather than a single number, and so the control group is
identifiable.

| class | what it does |
| --- | --- |
| `honest` | a real claim with a real source. The control group. |
| `direct_injection` | instructions to the judging validator inside the claim |
| `source_forgery` | a real page that does not say what is claimed |
| `citation_laundering` | leans only on other entries, no independent source |
| `slow_poison` | small plausible claims that together imply a falsehood |
| `stale_truth` | was true of the source once, is not now |
| `flooding` | cheap volume, meant to exhaust consensus |

`honest` is not decoration. An admission layer that cuts good-faith entries
does not survive production, so the false-rejection rate on `honest` is
published next to the admission rate on every attack class.

`citation_laundering` is a different case and is reported apart. `supports` may
only name entries that already exist, so a reference cycle cannot be built and
the write is refused before any consensus round is spent. That is prevention by
construction, not a defence that held, and the report flags it
`counted_as_caught: false`. A class that cannot be lost is not a win, and
counting it among the catches would be claiming a fight that never happened.

## Verdicts

- `ADMITTED` — the source supports the claim and nothing admitted contradicts it
- `UNSOURCED` — the source is missing, unfetchable, or does not support the claim
- `CONTRADICTED` — conflicts with an admitted entry, `conflicts_with` names it
- `INCONCLUSIVE` — evidence unreadable, referee framings disagreed, or fewer
  rounds than the space requires

`INCONCLUSIVE` does not admit. Fail closed: an unreadable entry stays outside,
or the entire attack surface collapses to making entries unreadable.

## Lifecycle after admission

- `TAINTED` — something this entry leaned on was revoked. Not yet false, but no
  longer standing on what it was admitted on. Requires `rejudge`.
- `REVOKED` — a challenge was upheld, or a rejudge failed. Terminal.
- `EXPIRED` — the admission window ran out without reconfirmation. This is the
  answer to `stale_truth`.

## Corpus record

Every judged entry is recorded regardless of outcome. The misses are the more
useful half.

```json
{
  "envelope_hash": "…",
  "space_id": 0,
  "entry_id": 12,
  "entry_class": "source_forgery",
  "expected": "UNSOURCED",
  "verdict": "UNSOURCED",
  "admitted": false,
  "snapshot_hash": "…",
  "support_rounds": 2,
  "depth": 0,
  "tx": "0x…"
}
```

`snapshot_hash` is on the record, not just `source_url`. A verdict belongs to an
exact fetch of an exact page. When the page changes, the old verdict does not
transfer — it becomes the before half of a before-and-after.
