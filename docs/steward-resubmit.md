# Steward corrections — 23 October 2026

The steward's state-machine corrections are implemented, tested and deployed
on Bradbury **Phase 1**. The new Intelligent Contract is
[`0xC51157f16406AD13527E1DBEa455374531Dd0396`](https://explorer-bradbury.genlayer.com/address/0xC51157f16406AD13527E1DBEa455374531Dd0396),
and its bound EVM vault is
[`0x40bf182ae03c2cca0123be64ac43d25da5adb7d7`](https://explorer-bradbury.genlayer.com/address/0x40bf182ae03c2cca0123be64ac43d25da5adb7d7).
Deployment is finalized. Source bytes, native vault runtime and controller
binding were checked against the chain. The frontend uses the corrected IC.

**Live lifecycle verification is incomplete.** Four new AI writes reached
finalized `MAJORITY_TIMEOUT` outcomes and created no entries. Thus there is no
standing entry on which to demonstrate challenge/rejudge. Live bridge funding
and payout are also unverified. The [dated checkpoint](https://hearsay.run/steward-checkpoint.json)
links all canonical receipts; a protocol timeout is not an application refusal.

The old contract `0x2a5c1aA4Ae9e2292B737FE574aF44A2d8a5bB3F7`, October 9
checkpoint and film remain historical. Their 20 honest controls and five
negative judgements are not results for this corrected version.

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

## Deployment and live verification

[Deployment metadata](../deployments/bradbury-steward.json) records both
addresses, deployment/binding transactions, source commit and source hashes.
The IC was deployed with the vault as its required constructor argument;
the vault deployer then bound its immutable controller to the IC. The actual
IC source bytes and compiled vault runtime match the pinned artifacts.

```sh
node scripts/verify_steward_deployment.mjs
python3 scripts/checkpoint_steward.py
```

These commands only read public chain data. The checkpoint preserves the
canonical consensus status, result, execution result and validator rounds
separately, with pinned block numbers for each receipt. Application views are
sequential latest-nonfinal reads, not a single historical state snapshot.

The Phase 1 genesis is
`0xef97917ce9bd9fa7d12ad6a8d81ea26c80ac1d727acc37cbb9799ae199788dc5`;
RPC `https://rpc-bradbury.genlayer.com`, chain 4221. Both frontend public reads
and wallet sends check genesis as well as protocol bindings. The reset Phase 2
chain uses the same ID and cannot be substituted while keeping these addresses.

Live operations, as verified at **10:12 UTC on October 23**:

| Operation | Canonical outcome | Application effect |
| --- | --- | --- |
| Deploy corrected IC | Finalized / majority agree / finished with return | Corrected schema and source verified |
| Open registry review space 0 | Finalized / majority agree | Pool 500,000 wei; TTL 1; cascade depth 1; two support rounds |
| Wrong Companies House source | Finalized / majority timeout | No entry; not UNSOURCED |
| Honest Companies House control | Finalized / majority timeout | No entry |
| Honest control after parent finalization | Finalized / majority timeout | No entry; accepted-parent state is not sufficient to explain the earlier failures |
| Open immutable-source review space 1 | Finalized / majority agree | Separate pool 500,000 wei |
| Wrong immutable Node.js README for CPython claim | Finalized / majority timeout | Source returned by leader, but no successful validator quorum or committed entry |

All four writes used five initial validators and three maximum rotations.
Expanded rounds also failed to establish successful consensus. `processIdleness`
on the first failed write succeeded as a native transaction but emitted no
progress events and did not change its application outcome. An appeal reverted
in read-only simulation; no paid appeal was sent. The final state has zero
entries and balanced pool accounting, so no meaningful challenge, rejudge or
withdrawal can be initiated yet. No claim about the root cause of validator
timeouts is made from these receipts alone.

The sequential, resumable live runner is `scripts/steward_live.py`. It writes
a public intent and hash journal before broadcast, resumes saved transaction
IDs and requires successful consensus, matched state and recovered source
bytes before the next write. It preserves the initial write record separately
from later lifecycle state. It must not be rerun as a new campaign to hide
failed attempts or treated as proof that the planned challenge ran.

To reproduce the deployed source package without overwriting another run:

```sh
python3 scripts/build_deploy.py --codec lzss --out runs/reproduce-steward/hearsay.py
```

Its SHA-256 is
`2a0cc73ea3ce7d8cc4db8fadd57fe08838641eb2530be488d22238c3804abdb8`.
The codec preserves executable AST and exact prompt strings; five codec tests
exercise lossless decoding, Unicode, overlap and executable AST identity.
The IC source is pinned to commit `c61c2d767af1ccdf4c667e19a984af2cf1706afe`.

## Reproduce the checks

Python 3.12 and make:

```sh
make lint test
make dry-run replay gate
```

`make test` reports 96 baseline assertions, 18 focused unittest cases and five
deployment-codec cases. The
original 95-assertion count changes because the withdrawal regression now also
asserts that an unconfigured vault preserves the beneficiary's credit. The
focused cases cover corrected claims, author-specific limits, fresh bytes and
unreadable rounds, normalized admitted duplicates, deep revocation and expiry,
deferred completion for survivors and failures, stale revisions, diamonds,
removed edges, fanout/round/batch limits, pending delivery, reserve protection,
late duplicates, receipt reconciliation and invalid controller/receipt data.

Node.js, with jsdom installed for page controls:

```sh
make parity gate-parity app-test bridge-test
node test/page.mjs
make film-check
```

These cover 67 existing parity checks, five additional retry parity cases and
deep cascade regressions, 17 gate cases, 65 page assertions and the unchanged
video's source/hash binding. The app adds 48 wallet/core and 30 DOM checks;
the broadcast journal has 15 checks. The historical corpus still reproduces 18/18
verdicts. Its bytes, live checkpoints and video were not regenerated.

For native EVM execution, install Foundry 1.5.1 and solc 0.8.30:

```sh
forge test --offline --use "$(command -v solc)" -vv
```

Five Solidity tests exercise failed delivery followed by redirect, duplicate
funding, a foreign sender/rebinding attempt, reentrancy and independent
beneficiary balances. They run on a local EVM, not a stub or public testnet.
CI installs the pinned Foundry toolchain and runs `make payout-test`.

## Final resubmit response

Thank you for the detailed review. The requested corrections are implemented
and deployed on Bradbury Phase 1:

Intelligent Contract:
https://explorer-bradbury.genlayer.com/address/0xC51157f16406AD13527E1DBEa455374531Dd0396

EVM payout vault:
https://explorer-bradbury.genlayer.com/address/0x40bf182ae03c2cca0123be64ac43d25da5adb7d7

1. Failed admission no longer permanently occupies the global claim key.
   Correction creates a new audited entry with a fresh bond, source retrieval
   and both support assessments. Attempts are bounded per author; another
   participant cannot consume the legitimate author's correction allowance.
   Admitted claims remain deduplicated, and unchanged evidence from the same
   author is refused.
2. Revocation and expiry immediately invalidate dependency chains for trust
   decisions, including descendants outside the storage walk. Support-revision
   pins prevent silent recovery when an ancestor is readmitted. Permissionless
   bounded deferred processing rejudges queued entries to completion.
3. Withdrawals remain durable pending claims until a verified EVM vault receipt
   proves funding. Beneficiaries pull their vault credit to a chosen recipient;
   failed delivery reverts atomically, preserving the enforceable credit for a
   later attempt. Recovery checks reserves and immutable receipt data, and a
   withdrawal ID cannot be funded twice.
4. `min_rounds` is restricted to 1–2, matching the implemented support rounds.

Validation passes: 96 baseline assertions, 18 focused regression cases, five
native EVM payout tests, five lossless deployment-codec tests, 67 original JS
parity checks plus retry/cascade regressions, 17 gate parity checks, 48 wallet/core
checks, 30 app DOM checks, 65 harness-page checks and 18/18 archived replays.
The deployed IC source, native vault runtime and one-time controller binding
were verified from public RPC. The frontend points to the corrected deployment.

Live verification limitation: deployment and both review-space creations are
Finalized with successful consensus. Four AI-write attempts, including honest
controls and immutable authoritative sources, instead finalized with
MAJORITY_TIMEOUT and created no entries. Therefore the corrected-version live
challenge/rejudge and IC-to-vault payout are not claimed as completed. These
protocol failures are not counted as application refusals. The previous
contract's checkpoint and video remain explicitly historical.

Correction details and reproduction commands:
https://github.com/Zhekinmaksim/hearsay/blob/main/docs/steward-resubmit.md

Dated canonical receipts and deployment proof:
https://hearsay.run/steward-checkpoint.json

Updated application:
https://hearsay.run/app.html
