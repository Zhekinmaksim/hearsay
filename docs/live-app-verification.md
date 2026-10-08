# Live app verification

The app is served at `/app.html`. Its source is `web/app.mjs` and
`web/app-core.mjs`; the checked-in browser bundle pins GenLayer SDK 1.1.8.
It uses public Bradbury RPC reads and an injected wallet for writes. No private
key or signing service is deployed.

On 8 October 2026, the local browser read ConsensusMain VERSION 2.0.0 and
verified contract bindings and proxy implementations at block 23815375.
Solvency was balanced and space 0 contained five application records.
Wallet connection and switching to chain 4221 displayed the expected public
account. Space 0 remained unavailable for writes in the UI.

Tracking protocol transaction
`0x45e19a6288faf1376f2a055c1da060734490f392ce25bd8f126987863406f9b0`
recovered the canonical `write_entry` envelope and matched BP entry 0. Its
receipt was Finalized, Majority agree, Finished with return. The app showed
ADMITTED, two readable support rounds, votes yes/yes/none, and snapshot SHA-256
`100c06830b6454b4b5bac2b83fb36f9e91b1e592fe89359184fa88a922566a4f`.

The browser's **Download replayable receipt** produced a flat receipt with
1,670 original snapshot characters. Running `python3 cli/gate.py verify
--receipt <download>` returned exit 0 and `reproduces: true`. Reloading resumed
the public transaction without a wallet send. The raw **Download current
receipt** is a separate audit wrapper, not a CLI replay row.

The actual Chrome page was inspected at 360 × 800 and 1280 × 900. Its document
widths were 345 and 1265 pixels respectively, with no horizontal overflow.
An unrelated installed wallet extension logged an injection conflict; the
tested app reads, connection and network switch completed successfully.

`make app-test` passed 43 SDK/wallet and 18 DOM checks. They cover actual bundled
SDK encoding, space creation, rejected requests, lost replies, insufficient
funds, failed estimates, changed wallet/network, reload, replay rollback,
canonical calldata binding and benchmark isolation. These fixtures perform
zero real sends and do not count as live campaign judgements.

A new wallet transaction initiated by this frontend has not yet completed on
Bradbury. The existing public transaction verifies the read, proof and replay
path; it does not establish that remaining write-path milestone. The live
benchmark still needs at least twenty current judged honest controls and the
original negative-input phase before its complete report can be published.
