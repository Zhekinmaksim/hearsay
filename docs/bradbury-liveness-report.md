# Bradbury consensus liveness report

Published reports: [Bradbury recovery #426](https://github.com/genlayerlabs/genlayer-cli/issues/426) and [SDK validator-count #231](https://github.com/genlayerlabs/genlayer-js/issues/231). Their submitted texts are preserved in [docs/issues](issues/README.md).

Observed at 2026-10-07T14:56:00+00:00. This report contains public chain data only.

Environment: GenLayer CLI 0.39.1, its bundled genlayer-js 1.1.8, Bradbury
RPC https://rpc-bradbury.genlayer.com, chain ID 4221. Consensus main:
`0x0112Bf6e83497965A5fdD6Dad1E447a6E004271D`, implementation
`0x0a2c393975da79505ed930efc55ae4aeb88b0d62`, VERSION `2.0.0`.

The same reviewed contract was deployed three times; deployment source SHA-256
`b8ed0663f5734e31dc5ea3a5a71bcb7ce96ccded8e3e502704ec7c7d524dc0e2`.
The readable source is in https://github.com/Zhekinmaksim/hearsay.
All writes are sequential. No pending transaction has been resubmitted.

## Observations

1. Contract `0x774237BD6e669bF1Af1b8F807ada3A0d4889987F`:
   transaction `0xc877675db83e49a59543280648b7bd7ac3739762bf00d920ee24baaaac4366b0`
   remained in APPEAL_REVEALING with 10 of 11 votes revealed beyond valid_until.
   Sender cancellation reverted with InvalidTransactionStatus (`0xf8062102`).
   Public finalization/idleness simulations reverted. Fifteen earlier entries
   finalized and their pinned snapshots and recorded votes reproduce.

2. Replacement `0x2390Ca5C7E369aD63ECbB4bF36509e7f7B7219B9`:
   transaction `0x1a976d68c60c44cd4af5e93b7de0c556cb7606d047d26b5f031d6c44af82b0ad`
   reached round 4, committee 23, COMMITTING. Both leaderIdleness and
   processIdleness estimates reverted with ValidatorSelectionFailed
   (`0x1f90236d`). Staking reported 34 active validators, 46 total, epoch 173.
   This suggests a selection/pool constraint; the exact cause is not established.
   Three earlier entries were admitted and two others timed out without state.

3. Replacement `0xD596971Da562647Cddd13Ec095a3431073682340` used
   maxRotations=0. Constructor and open_space were accepted. The first write
   `0x31a99972d4a097296c89d07606f2156e56937ccc9bbb29e5843f53c92367b584`
   has stored status FINALIZED with result TIMEOUT, round 3, committee
   13, commits 13, reveals
   13. Decoded EVM calldata confirms _maxRotations=0 and
   _numOfInitialValidators=5. SDK getTransaction currently reports
   numOfInitialValidators=0, inconsistent with
   that calldata. A zero rotation limit does not stop appeal expansion.

The first claim is independently supported by its real primary source:
https://find-and-update.company-information.service.gov.uk/company/00048839.
It states that Companies House lists BARCLAYS PLC, number 00048839, as Active.
Stored on-chain eqBlocksOutputs for Prudential, replacement Unilever and bounded
Barclays contain the correct nonempty registry text and both support outputs
`supported: true`. Prudential and Unilever also record no contradiction.
Timeouts dominate the failed rounds. Debug traces may replay execution, so they
do not establish the original execution cost or which external call timed out.
Missing application state is not counted as a contract refusal.

The installed SDK's getTransaction falls back from an absent
numOfInitialValidators to initialRotations (dist/index.js line 1299). Thus a
reported initial count of 0 or 3 can actually be the rotation limit. Original
addTransaction calldata confirms five initial validators. Its vote enum also
labels value 4 DETERMINISTIC_VIOLATION, whereas explorer enrichment identifies
that value as nondet_disagree; this label does not prove a deterministic bug.

## Parsed-decision experiment

With user authorization, deployment
`0xb8BAd484689a32357Caa6E0F427D31B29347fdB4` changes only the comparison of
parsed boolean/conflict decisions to `strict_eq`. Source-fetch comparison and
five initial validators remain unchanged. Source and packed deployment hashes
are recorded in `deployments/bradbury-decisions.json`; no earlier entries count
towards this experiment.

The first write, `0x119ceed3267d1304cf691a0d6c7cfb2efd53135ac647bfb990ee40d2ae3bdcff`,
was accepted with four agreements and one timeout. Its pinned source and
`yes/yes` support votes reproduce. Stored equivalence outputs contain typed
`true/true`, rather than the original JSON response strings.

The second write, `0xbfbeb7d712d834a94b8f00ccba3ae98f06466db39dee7ad9fcd3f8902e45b8c0`,
stored a correct source and `true/true/-1` decisions but entered an appeal after
initial timeout votes. A public `processIdleness` call succeeded in EVM at
`0x85a9257b3a11f1a749b0256d8f885d38e057768cedf41f592e443556eaa11dd6`;
the immediate stored status remained APPEAL_COMMITTING. Later the transaction
reached APPEAL_REVEALING, with ten of eleven votes revealed. This does not prove
that the recovery call caused the later transition or resolved the transaction.

Both initial-round debug traces returned successfully. Replay metrics reported
zero LLM/web calls, so they cannot measure original provider calls or latency.
The HSBC trace's storage-pickling warning is retained in the local audit; it
does not by itself establish a failed execution. Reduced comparison calls are
inferred from the code and pinned SDK, not measured speed. The experiment has
not completed the honest cohort or attack coverage.

## Current prompt cohort: 8 October 2026

The current separate deployment is
`0x2a5c1aA4Ae9e2292B737FE574aF44A2d8a5bB3F7`, readable source SHA-256
`d2670d4204d769ce14f26328d3f8a4a86c4b645f0a54c5149d5269804ce53296`.
It retains five initial validators, three leader rotations, two independent
support framings and strict equality of parsed decisions. Earlier deployments
are excluded from its denominator.

The [current incomplete checkpoint](https://hearsay-psi.vercel.app/bradbury-prompt-checkpoint.json)
contains three real `ADMITTED` controls: BP P.L.C. (00102498), ASTRAZENECA PLC
(02723534), and BT GROUP PLC (04190816). Their exact source bytes came from
stored equivalence outputs, match the contract's SHA-256, and reproduce the
recorded `yes / yes / none` votes. Of the 36 original candidates, three have
verified judgements, three have finalized infrastructure outcomes, five are
unresolved, and 25 remain unsubmitted. The three pending transactions are a
subset of those five unresolved outcomes. The campaign has not reached the
required 20 judged honest controls or started the attack phase.

NATWEST GROUP PLC's transaction
`0x8930d0ab292f6b3cf9ebbb3a6e4ba3b5f0a754838b18ae5fbcdcf752a9529922`
remained in stored `APPEAL_REVEALING`, with 11 commitments and 10 of 11 reveals,
after a bounded 1200-second wait. At block **23791154**, hash
`0x8cd8ec8682bb7394aa5888fe3220f1416123e9ab8e0d7f0f7ffb6fc190fb0d37`,
fresh `processIdleness` and `leaderIdleness` simulations from the original
sender both reverted with `execution reverted`. No recovery was signed or
broadcast. The missing reveal prevents durable completion. The earlier stop
before the next write was our conservative orchestration guard: a later queue
audit found the pending queue empty, allowing activation of independent writes.
Later accepted outputs can be replayed after an adverse appeal and remain
provisional until fresh reconciliation and finalization. A specific latency or
application cause is unproven.

An earlier reader wrongly applied the newer Consensus v0.6 status table to
deployed ConsensusMain 2.0.0. Stored code 13 is `LeaderTimeout`, and 14 is
`LeaderRevealing`. The [verified version evidence](bradbury-protocol-version.md)
and captured-node regression fixture support the correction. This display
error is separate from the current raw status-9 appeal and genuine finalized
protocol failures. Historical captures remain preserved. A timeout that later
recovered, such as BP, remains in history and is excluded from current failures.

## Open investigation questions

- What supported public recovery operation can release these exact transactions?
- Can an appeal/idle transition get stuck when it cannot select the next committee?
- How should SDK consumers obtain the actual initial validator count during appeal?

Original checkpoint: https://hearsay-psi.vercel.app/bradbury-checkpoint.json.
Raw RPC, explorer, VM trace and simulation captures remain in the local run
archives and can be supplied after reviewing them. No signing keys, credentials
or serialized signed transaction bytes are included in this report.
