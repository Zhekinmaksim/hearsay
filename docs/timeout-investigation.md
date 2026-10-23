# Live timeout investigation — 23 October 2026

The original four AI writes on `0xC51157f16406AD13527E1DBEa455374531Dd0396`
finalized with `MAJORITY_TIMEOUT` and no entry. A fifth registry attempt was
kept separately. Submission gas succeeded; increasing EVM gas is not a verified
way to increase GenVM execution time on this Phase 1 deployment.

## Confirmed client defect

The live runner stopped as soon as a stored receipt said `LEADER_TIMEOUT` or
`VALIDATORS_TIMEOUT`. Those phases can still change: the protocol can rotate
leaders or expand a round. Stopping tracking did not cancel the transaction,
but prevented the runner from observing a later successful outcome and
continuing the planned lifecycle.

The runner now follows the same saved protocol ID through these phases. It
never resends that intent. A finalized timeout remains infrastructure failure,
not an application verdict. Three regressions cover application-error fail-fast, leader replacement followed
by acceptance and a finalized timeout that must not count as success.

The live corrected-source transaction
`0xfffe3a00e45cc02116df5c55fbb77ec9936832e8ad005d1877d6be1c2e57eed7`
traversed timeout/expanded-round phases and eventually obtained successful
stored consensus and an actual `ADMITTED` entry. This was the intermediate HTTP-source deployment, not the final payout-adapter release. Its manifest is retained under `runs/steward-http-oct23`; [public diagnostic receipts](https://hearsay.run/steward-diagnostics.json) preserve every outcome.

## Separate leader and validator measurements

The old RPC returns `eqOutputs` and accepts `leader_results`, as documented by
the [official v0.5.9 API snapshot](https://github.com/genlayerlabs/genlayer-docs/blob/a98151a7929b83bbda01870b19aa92c4b54c3c5b/pages/api-references/genlayer-node/gen/gen_call.mdx).
The current documentation's `leader_public_data` format is for a different node
version. The investigation used public `gen_call` simulation, without signing
or changing chain state, to execute both roles separately.

On the tested RPC, the unchanged Companies House write took about 8.8 seconds
as leader and 19.5 seconds as validator. Both completed successfully. The
validator's metrics recorded roughly 14.9 seconds in web rendering and 4.8
seconds in three model calls. This does not reveal other operators' private
provider configuration, retry queues or execution deadlines.

A separate one-prompt diagnostic contract obtained four agreeing votes from
five initial validators. This demonstrated that AI consensus was possible;
it did not establish that a longer Hearsay execution would meet every node's
deadline. This diagnostic deployment is not used as Hearsay lifecycle evidence.

## Narrow source transport optimization

For `https://raw.githubusercontent.com/` only, Hearsay now obtains a fresh HTTP
response on every validator, requires status 200, `text/plain` and valid UTF-8,
and uses strict equality of the bounded source text. It does not accept
writer-supplied evidence or reuse a leader's source without independent fetch.
All other origins retain browser-rendered comparative source verification.
Both support prompts, contradiction decisions, challenge criteria and minimum
support rounds remain unchanged. Five initial validators and three maximum
rotations remain in each submitted intent. Exact text agreement is stricter
than semantic agreement; changing bytes can cause a refusal to agree.

A CPython source-file probe using the actual Hearsay fetch/support functions
completed in about 4.1 seconds as leader and 3.5 seconds as validator, with two
model calls per role. Its HTTP operation took about 0.26/0.05 seconds.
A same-file probe with the former rendered/comparative path measured about
10.2/5.0 seconds and two/three model calls. These are individual observations,
not latency percentiles: provider time varied, and the former render itself
was already fast for this raw file. The measured difference cannot all be
attributed to HTTP transport. The earlier 14.9-second browser measurement was
for a different site and is not a controlled same-source comparison.

Seven transport regressions cover origin lookalikes, status/MIME failures,
invalid UTF-8, bounds, failed equality, network errors and the continued
requirement for both support assessments. The source is pinned to commit
`1f07fc5` in [deployment metadata](../deployments/bradbury-steward-http.json).

## Deferred processing and remaining network limits

The new contract completed wrong-source refusal, corrected admission, four
linked admitted entries, a rejected challenge and root expiry. The deepest
entry's stored flag was still `ADMITTED` while its public trust status was
already `TAINTED`.

The first queued AI batch encountered a protocol timeout. A public protocol
appeal reverted in simulation with both zero and 1,000 wei; no paid appeal was
sent. The failed attempt remains in the manifest and checkpoint. A pinned
queue read established that it was no longer at the pending head before
separate direct rejudgements were initiated. Recovery uses the contract's
public `rejudge` path, including the logically tainted/still-stored-admitted
case, followed by bounded consumption of the remaining stale queue slots.

This is a live lifecycle demonstration, not a claim that every validator is
healthy, that browser-source liveness is solved generally, or that a queued
source-rejudging batch succeeded. The focused local tests cover queued AI
survivor/failure processing; live evidence distinguishes it from stale-slot
completion. Accepted receipts remain provisional until canonical finalization.
The dated checkpoint is the authority for completion and exact transaction IDs.

## Pinned SDK payout adapter correction

A real withdrawal on the intermediate HTTP deployment reached successful
consensus but `FINISHED_WITH_ERROR` before changing credit. The generated EVM
interface rejected non-positional-only parameters. Inspecting the pinned
GenVM v0.2.11 SDK also found incompatible view-parent and send-value handling.
That deployment is retained as diagnostic history and is not the final release.

The final source uses the same SDK's typed ABI encoder/decoder with its
EthCall/EthSend host interface, explicitly binding the recipient and native
value. The exact two adapter classes were extracted from the contract and
executed in both leader and validator `gen_call` roles: controller and deposit
receipt reads succeeded, and both generated identical `deposit(42, beneficiary)`
calldata with exactly 1,000 wei. These simulations do not deliver funds.
A fresh IC and vault are required because the previous controller binding is
immutable. Final live results are published separately at
https://hearsay.run/steward-final-checkpoint.json.
