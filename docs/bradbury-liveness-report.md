# Bradbury consensus liveness report

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
   has status VALIDATORS_TIMEOUT, round 3, committee
   13, commits 13, reveals
   13. Decoded EVM calldata confirms _maxRotations=0 and
   _numOfInitialValidators=5. SDK getTransaction currently reports
   numOfInitialValidators=0, inconsistent with
   that calldata. A zero rotation limit does not stop appeal expansion.

The first claim is independently supported by its real primary source:
https://find-and-update.company-information.service.gov.uk/company/00048839.
It states that Companies House lists BARCLAYS PLC, number 00048839, as Active.
The leader trace of the replacement's initial write returned result_code=0,
without stderr. Missing application state is not counted as a contract refusal.

## Questions for maintainers

- What supported public recovery operation can release these exact transactions?
- Can an appeal/idle transition get stuck when it cannot select the next committee?
- How should SDK consumers obtain the actual initial validator count during appeal?

Original checkpoint: https://hearsay-psi.vercel.app/bradbury-checkpoint.json.
Raw RPC, explorer, VM trace and simulation captures remain in the local run
archives and can be supplied after reviewing them. No signing keys, credentials
or serialized signed transaction bytes are included in this report.
