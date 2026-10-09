# Frontend finalization blocker: 9 October 2026

The production wallet successfully created space 1. Its protocol transaction
[91b4a237…f2f02653](https://explorer-bradbury.genlayer.com/tx/0x91b4a237aff71bdd4b90ac3b097cd232479926f0accea4daf0879064f2f02653)
is Accepted, Majority agree, Finished with return, and matches the created
namespace. The user authorized the prepared TESCO claim only after this
creation becomes Finalized. No claim request has been initiated.

At block 23921642, 9 October 06:18:45 UTC, creation occupied finalization slot
37 and was not the queue head. The older owned
[Vodafone transaction](https://explorer-bradbury.genlayer.com/tx/0x10c26378ce5d948caefca1343ebb0d058115552ebfbf20cde2f37018bac19e3c)
remained APPEAL_REVEALING, with eleven commitments and ten reveals, at both
the Accepted and finalization heads, slot 10. An empty pending queue did not
release this separate finalization queue.

Verified Consensus 2.0.0 source requires both an elapsed acceptance window and
being the finalization head. The creation's last vote at 06:05:41 UTC plus
1800 seconds gives a timer floor of 06:35:41 UTC (11:35:41 Asia/Tashkent).
Its validUntil at 07:05:16 UTC is not automatic finalization. A fresh read at
block 23925410, 06:39:07 UTC, still showed Accepted after the timer floor.

At pinned block 23922963, hash
`0xf48024a0db18248957d4c6d424153f29012fb4f6d926f53ab1f079f89bd25177`,
06:25:53 UTC, both supported public Main methods, `finalizeTransaction` and
`processIdleness`, reverted in nonpersistent eth_call with the verified error
`InsufficientActiveValidators(34,33)`, selector `0xb5e5b936`. Sender and app
ownership matched the expected account and deployment. No useful recovery
was established, and no paid recovery transaction was sent.
`advanceStuckTransaction` was absent from the verified Main ABI and was not
called. No admin or direct-phase mutation was attempted.

This establishes the blocker at those blocks, not a permanent failure or an
estimated completion time. Validator availability and protocol state can
change. The wallet journal retains the public hashes, and the frontend keeps
tracking without duplicate sends. Its own Accepted attempts still block new
wallet writes until Finalized.

The user approved publishing this
[addendum to issue 426](https://github.com/genlayerlabs/genlayer-cli/issues/426#issuecomment-6075779424).
It describes this newer case separately from the older HSBC report. Local
proofs are in `runs/frontend-live-oct9/finalization-head-audit`, including the
known ABI, exact block, ownership, source binding, raw simulation results and
verified error decoding.

A fresh read at block **24013797**, **9 October 14:38:32 UTC**
(19:38:32 Asia/Tashkent), confirmed the same blocker. Space creation remains
Accepted / Majority agree / Finished with return at slot 37, with five of
five votes. Vodafone remains APPEAL_REVEALING at the Accepted and finalization
head, slot 10, with eleven commitments and ten reveals. The pending queue is
empty at 79/79. Both supported public Main calls still revert in nonpersistent
simulation with `InsufficientActiveValidators(34,33)`. Consensus version and
Main, Data and Queues implementation bindings are unchanged. No recovery or
frontend claim transaction was sent. Fresh evidence is saved in
`runs/frontend-live-oct9/fresh-finality/check-24013797.json`.

The next check, block **24026853**, **9 October 15:49:38 UTC**
(20:49:38 Asia/Tashkent), found the same creation status, finalization head,
votes and recovery error. The pending queue was empty at 91/91. No signature
or broadcast was made. The complete pinned read and both decoded simulations
are saved in `runs/frontend-live-oct9/fresh-finality/check-24026853.json`.
