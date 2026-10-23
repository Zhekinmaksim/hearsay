# Steward corrections — 23 October 2026

The steward's state-machine corrections are implemented and deployed on
Bradbury **Phase 1**. The final Intelligent Contract is
[`0xD0B85aB75f479d060A1680E220931c5001f7ba46`](https://explorer-bradbury.genlayer.com/address/0xD0B85aB75f479d060A1680E220931c5001f7ba46),
and its bound EVM vault is
[`0x81f29ce35b2624c3e04764cad423fc660ef4d3a7`](https://explorer-bradbury.genlayer.com/address/0x81f29ce35b2624c3e04764cad423fc660ef4d3a7).
Source bytes, native runtime and controller binding match the pinned artifacts.
The [final checkpoint](https://hearsay.run/steward-final-checkpoint.json)
records canonical status separately from application outcomes.

Earlier timeout attempts and the intermediate deployment's generated EVM-proxy
failure remain in [diagnostic evidence](https://hearsay.run/steward-diagnostics.json)
and the [timeout investigation](timeout-investigation.md).
The final adapter uses the pinned SDK's typed ABI and EthCall/EthSend host
interface with an explicit recipient and value. Exact adapter classes passed
both leader and validator runtime simulation before deployment. Five native EVM
tests verify failed recipient delivery and successful recovery. The live
challenge/rejudge checkpoint does not claim an IC-to-vault withdrawal.

The original contract `0x2a5c1aA4Ae9e2292B737FE574aF44A2d8a5bB3F7`, October 9
checkpoint and film remain historical. Their 20 honest controls and five
negative judgements are not results for the corrected version.

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

[Deployment metadata](../deployments/bradbury-steward-final.json) records both
addresses, deployment/binding transactions, source commit and source hashes.
The IC was deployed with the vault as its required constructor argument;
the vault deployer then bound its immutable controller to the IC. The actual
IC source bytes and compiled vault runtime match the pinned artifacts.

```sh
node scripts/verify_steward_deployment.mjs
python3 scripts/checkpoint_steward_http.py --run-dir runs/steward-final-oct23 \
  --deployment deployments/bradbury-steward-final.json \
  --receipts-dir web/steward-final-receipts --out web/steward-final-checkpoint.json
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

The final run preserves five initial source-pinned write records before any
lifecycle mutation: a wrong CPython header version, corrected admission of the
same claim, and a four-entry admitted dependency chain. A deliberately false
challenge tests rejection; it does not manufacture an upheld objection against
correct evidence. Expiry tests deep invalidation, including the descendant
whose stored flag remains ADMITTED while its effective status is TAINTED.
Direct rejudge of the root and all three descendants restores their independent
source support; two bounded calls consume the remaining stale queue slots.
The final checkpoint determines whether each operation is Accepted or Finalized.
No successful queued AI batch or second referee stage is claimed by this path.

| Live operation | Transaction |
| --- | --- |
| False challenge rejected | [Canonical challenge receipt](https://explorer-bradbury.genlayer.com/tx/0x13861334e540a06d6b7291e19669109228add120bcabc97a6c9b8eded370f4f3) |
| Root expiry invalidated all three descendants | [Expiry](https://explorer-bradbury.genlayer.com/tx/0x47a51c496d618146ed19b8675398c15f42e15814fd79aec53fdcb3daf5df9855) |
| Expired root independently readmitted | [Root rejudge](https://explorer-bradbury.genlayer.com/tx/0x2bcb3899ff83b6bbcff0ca7d5cfd9db3635f92ea5148925be0bab8346b14ba60) |
| Logically tainted / stored-admitted descendant readmitted | [Deep rejudge](https://explorer-bradbury.genlayer.com/tx/0xb9e814a0a03ed646a0ec7a0f4a0150fd7addc818bd8f1c1dc01c9d6c1f464f2f) |

The checkpoint links the remaining rejudgements, both bounded sweeps, full
canonical receipts, calldata-bound intents and initial source-pinned records.


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
`02df3ea8c9f4f8181681d3adaf46df785998af27fee4a968271de653beb3df7b`.
The codec preserves executable AST and exact prompt strings; five codec tests
exercise lossless decoding, Unicode, overlap and executable AST identity.
The IC source is pinned to commit `e1c90fe5c39a8c17ad89708054831f719ae5057b`.

## Reproduce the checks

Python 3.12 and make:

```sh
make lint test
make dry-run replay gate
```

`make test` reports 96 baseline assertions, 18 focused unittest cases and five
deployment-codec cases, seven source transport cases, three runner cases and
eight publication guards. The
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

Use [resubmit.txt](resubmit.txt), kept below 1,000 characters. The canonical
checkpoint and current deployment metadata are the source of completion claims.
