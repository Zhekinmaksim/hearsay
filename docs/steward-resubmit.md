# Steward corrections — 23 October 2026

These changes address the request on the Hearsay submission dated 21 October.
They change the source and the offline browser harness. **A corrected on-chain
deployment has not been made.** The previous Bradbury contract at
`0x2a5c1aA4Ae9e2292B737FE574aF44A2d8a5bB3F7`, the 9 October checkpoint, and
the existing video retain their original meaning and limitations. None is a
live verification of these fixes. The public site is https://hearsay.run/.

## Failed-claim correction

`write_entry` keeps every failed entry and forfeited bond in history, but
reserves global claim deduplication only after admission. A corrected attempt
creates a new entry, attaches a fresh write bond, fetches source bytes again,
and performs the same two support framings and consistency check.

The allowance is three attempts **per author per normalized claim**, not three
attempts shared by all users. An attacker cannot consume another author's
allowance. The same author's identical URL/source bytes/support ids are
rejected as unchanged evidence. New authors still pay a bond and consensus
costs; this is bounded per author, not Sybil resistance. Once admitted, a claim
cannot be admitted again by changing whitespace, author or URL.

The CLI and browser gate use the latest matching receipt. A changed source for
a failed claim receives exit 2 until a new judgement exists. `--retry-failed`
requests another judgement of an unchanged envelope, never exit 0 based on the
old failure. Strict mode continues to refuse absent judgement. Supplying a
corpus is an offline check of that corpus, not proof of current chain state.

## Dependency invalidation and deferred completion

Revocation and expiry share the same invalidation path. Entries pin the
judgement revisions of their supports. Public entry status, premise selection,
support validation and the contradiction window check the entire ancestry,
failing closed on a non-admitted support or changed revision. Thus a descendant
outside the physical storage walk is immediately exposed as `TAINTED` and
cannot be used as a trusted premise. `stored_status` is exposed separately for
audit; it is not the trust decision. `get_space().admitted` counts trusted
entries rather than unswept storage flags.

An ancestor's later recovery does not silently restore a descendant: its pinned
revision is stale until that descendant is rejudged. Stale dependency edges
are removed when a survivor drops its invalid premises.

`process_deferred(limit)` is permissionless and consumes 1–16 queue slots per
call, including stale slots. It runs the actual source fetch and judgement,
retains survivors, revokes failures and propagates further work. Direct
`rejudge` also accepts logically tainted entries outside the stored walk.
Active queue entries are deduplicated. The per-space depth limit remains, with
a 32-node expansion budget, maximum fanout 32 and maximum verified ancestry
256 entries; larger ancestry is refused before judging. The bounded expansion
may enqueue its remaining frontier; it does not walk the whole graph in one
transaction. Source/consensus failures during rejudgement cannot admit.

The browser's scripted cascade now marks deferred descendants untrusted and
has a **Process deferred batch** control. This is a reproduction of recorded
fixture facts, not a live challenge or validator execution.

## Failed-payment recovery

`withdraw()` now returns a **withdrawal id**, reserves the balance in a durable
`PENDING` record and emits funding to `HearsayPayoutVault`, rather than directly
emitting GEN to the beneficiary. `solvency().withdrawing` includes this pending
liability. Moving from available to pending does not erase the claim or assert
that value has been delivered.

The Solidity vault accepts deposits only from its controller, records an
immutable withdrawal-id/beneficiary/amount receipt and credits a pull balance
without calling beneficiary code. `reconcile_withdrawal(id)` verifies that
receipt through an EVM view before marking the IC record `FUNDED`. Funded means
the vault received custody, not that the beneficiary's chosen recipient was
paid. Receipt records survive successful claims.

The beneficiary calls `claim(recipient)` directly on the vault. A failing
recipient reverts the entire EVM transaction, preserving the vault balance and
the enforceable credit. The beneficiary can select a working recipient and
claim again. Reentrancy and duplicate withdrawal deposits cannot double-pay.
There is no administrator withdrawal path.

An absent vault receipt alone is **not** proof that an emitted message failed.
`retry_withdrawal(id)` is restricted to the beneficiary, reconciles first, and
requires actual IC balance covering *all* pool, available-credit and pending
liabilities before emitting again. Value still reserved by the bridge cannot
be replaced using somebody else's pool. A late duplicate deposit reverts
atomically in the vault. If bridge-held value is neither delivered nor returned,
the claim stays pending; this mechanism does not manufacture a protocol refund
or bypass a stalled network. A deployment without EVM support or a bound vault
fails closed and leaves available credits untouched.

The distinction follows the documented asynchronous
[GenLayer value-transfer model](https://docs.genlayer.com/developers/intelligent-contracts/features/value-transfers)
and [external-message finalization](https://docs.genlayer.com/developers/intelligent-contracts/features/messages).
EVM vault interaction requires a network with real EVM support; it cannot be
claimed verified by Studio's simulated transfer support.

## Deployment and review path

1. Deploy `contracts/HearsayPayoutVault.sol` on the same supported chain as the
   new Intelligent Contract. Keep its deployed address, transaction and bytecode.
2. Deploy corrected `contracts/hearsay.py` with constructor argument
   `payout_vault` set to that vault address. This is a new storage schema,
   not an in-place patch to the historical contract.
3. From the vault deployer's account, call `bindController(newICAddress)` once.
   Verify `controller()` equals the IC address and that both contracts match
   these sources. The IC verifies the controller on every funding/recovery path.
4. Record **new** deployment addresses and source hashes separately. Do not
   replace the old checkpoint with old receipts relabelled as corrected results.
5. Use a separate review space for a live write, challenge, both referee stages,
   deferred batches, survivor/failure rejudgements and withdrawal reconciliation.
   Retain parent/child and EVM claim receipts. This step has not been run for
   this correction and must not be marked complete in a resubmit.

## Reproduce the checks

Python 3.12 and make:

```sh
make lint test
make dry-run replay gate
```

`make test` reports 96 baseline assertions and 18 focused unittest cases. The
original 95-assertion count changes because the withdrawal regression now also
asserts that an unconfigured vault preserves the beneficiary's credit. The
focused cases cover corrected claims, author-specific limits, fresh bytes and
unreadable rounds, normalized admitted duplicates, deep revocation and expiry,
deferred completion for survivors and failures, stale revisions, diamonds,
removed edges, fanout/round/batch limits, pending delivery, reserve protection,
late duplicates, receipt reconciliation and invalid controller/receipt data.

Node.js, with jsdom installed for page controls:

```sh
make parity gate-parity
node test/page.mjs
make film-check
```

These cover 67 existing parity checks, five additional retry parity cases and
deep cascade regressions, 17 gate cases, 65 page assertions and the unchanged
video's source/hash binding. The historical corpus still reproduces 18/18
verdicts. Its bytes, live checkpoints and video were not regenerated.

For native EVM execution, install Foundry 1.5.1 and solc 0.8.30:

```sh
forge test --offline --use "$(command -v solc)" -vv
```

Five Solidity tests exercise failed delivery followed by redirect, duplicate
funding, a foreign sender/rebinding attempt, reentrancy and independent
beneficiary balances. They run on a local EVM, not a stub or public testnet.
CI installs the pinned Foundry toolchain and runs `make payout-test`.

## Suggested resubmit response

Thank you for the detailed review. I corrected the three state-machine issues
and the support-round configuration:

1. Failed admission no longer permanently occupies a claim's global key.
   Corrected submissions create a new audited entry, attach a fresh bond and
   undergo fresh source retrieval and both support assessments. Attempts are
   limited per author, so a malicious first writer cannot exhaust another
   participant's correction allowance. Admitted-claim deduplication remains.
2. Revocation and expiry now invalidate the full dependency chain for trust
   decisions immediately, including descendants outside the storage walk.
   Support revision pins prevent silent readmission after an ancestor recovers.
   Permissionless bounded deferred processing rejudges queued entries to
   completion. The browser demo also exposes a deferred-batch control.
3. Withdrawals remain persistent pending claims until a verified EVM vault
   receipt proves funding. Beneficiaries pull from the vault; a failed outgoing
   payment atomically preserves their credit and can be retried to another
   recipient. Recovery checks reserves, rejects mismatched receipts and cannot
   double-pay a withdrawal id.
4. `min_rounds` is restricted to 1–2, matching the two implemented support rounds.

Validation includes 18 focused Python regression cases, five native EVM payout
tests, the baseline suite, browser/CLI parity, all 65 page checks and 18/18
archived verdict replays. The report contains exact reproduction commands:
https://github.com/Zhekinmaksim/hearsay/blob/main/docs/steward-resubmit.md

These are source and local-execution corrections. The old Bradbury contract,
dated checkpoint and video are historical and do not contain these fixes. A
new deployment and a live challenge/rejudgement run are still pending; I am
not presenting the old address as a corrected deployment.
