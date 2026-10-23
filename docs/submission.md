# Hearsay — corrected project submission

Website: https://hearsay.run/app.html

Repository: https://github.com/Zhekinmaksim/hearsay

The source corrections requested by the steward are deployed on **Bradbury
Phase 1**, chain ID 4221. This is a new IC and a separate EVM vault, not an
upgrade to the historical contract. Source bytes, vault runtime and the one-time controller binding were verified
from RPC; the final checkpoint records canonical finalization separately.
The [review response](steward-resubmit.md) describes each correction and tests.

The live review uses fresh pinned CPython release files. Its canonical proof is
[the final checkpoint](https://hearsay.run/steward-final-checkpoint.json).
Previous timeout and payout-adapter diagnostics remain separately visible in
[diagnostic receipts](https://hearsay.run/steward-diagnostics.json).

## Contract links to use

Corrected Intelligent Contract:

https://explorer-bradbury.genlayer.com/address/0xD0B85aB75f479d060A1680E220931c5001f7ba46

Payout vault:

https://explorer-bradbury.genlayer.com/address/0x81f29ce35b2624c3e04764cad423fc660ef4d3a7

Deployment transaction:

https://explorer-bradbury.genlayer.com/tx/0x54379576848362be645869046b7ca85125d792f5731a85c8e33040f59eeaefd1

[Deployment metadata](../deployments/bradbury-steward-final.json) pins the source
commit, both source hashes, reversible deployment codec, native EVM receipts,
network genesis and exact RPC. Run `node scripts/verify_steward_deployment.mjs`
for a public read-only source/runtime/controller verification. It requires
the existing GenLayer CLI with its bundled SDK; it never accesses a keychain.

Chain ID alone does not identify this network. Phase 1 RPC is
`https://rpc-bradbury.genlayer.com`; genesis is
`0xef97917ce9bd9fa7d12ad6a8d81ea26c80ac1d727acc37cbb9799ae199788dc5`.
The reset Phase 2 chain also uses 4221 and does not contain this deployment.
Do not change the RPC while keeping these addresses or evidence claims.

## Portal fields

Project name: **Hearsay**. Choose the available AI/agents primary tag and
precise topics matching shared agent memory and source verification.

One-liner (under 180 characters):

```text
A source-verified admission layer for shared agent memory, with challengeable claims, pinned evidence and dependency-aware revalidation on GenLayer.
```

Description (under 1,000 characters):

```text
Hearsay prevents unsupported claims from becoming trusted premises in shared agent memory. A GenLayer Intelligent Contract retrieves each cited source, evaluates support in two framings, checks recent admitted claims for contradictions and records evidence and votes. Challenges, expiry and dependency revisions make invalid descendants untrusted; bounded deferred processing revalidates them. Failed claims can be corrected without erasing their history. Withdrawals remain enforceable pending claims until verified funding reaches a pull-payment EVM vault. The frontend submits real payable calls and tracks canonical consensus receipts. The corrected contracts are deployed on Bradbury Phase 1. Live evidence records source correction, a rejected challenge and dependency revalidation; canonical receipts distinguish provisional Accepted from Finalized. October 9 evidence is historical. The repository includes focused state-machine, native EVM, frontend and receipt-replay tests.
```

Demo URL: use a direct YouTube/X link only if the user supplies one. The local
video at https://hearsay.run/demo/hearsay.mp4 is archival original-contract
material, not corrected-version live verification. Logo and social links
remain the user's fields.

## Exact review path

| Heading | Instruction |
| --- | --- |
| Verify deployment | Open https://hearsay.run/app.html. Confirm Phase 1, chain 4221 and corrected address 0xD0B85aB75f479d060A1680E220931c5001f7ba46. Public reads need no wallet. |
| Inspect canonical proof | Open https://hearsay.run/steward-final-checkpoint.json and its deployment-verification and transaction receipt links. Inspect the canonical status and application execution of every operation; diagnostic failures are retained separately. |
| Inspect current memory | Read space 0 and solvency in the app. Inspect entries 0–4, challenge 0 and the empty deferred queue; the CPython release chain is separate from the historical BP record. |
| Reproduce corrections | Clone the repository; run make lint test, make parity gate-parity app-test bridge-test, node test/page.mjs and make payout-test with the documented toolchains. See docs/steward-resubmit.md. |
| Optional network write | Only if Phase 1 consensus is operational: connect a funded Phase 1 wallet, create a separate space, wait for Finalized, then submit a primary-source claim. Each call costs testnet fees and the disclosed funding/bond. Accepted remains provisional; a timeout is not an application verdict. |

Expected verification outcome (under 500 characters):

```text
Public reads show the corrected Phase 1 IC, bound vault and five CPython-source entries. The proof links exact canonical receipts and initial votes separately from later state: failed-source correction, challenge rejection, deep trust invalidation, direct rejudge and bounded queue completion. Source/runtime hashes match the repository. Historical controls and video belong to the original contract.
```

## Evidence to attach

- Repository: https://github.com/Zhekinmaksim/hearsay
- Corrections and response: https://github.com/Zhekinmaksim/hearsay/blob/main/docs/steward-resubmit.md
- New deployment metadata: https://github.com/Zhekinmaksim/hearsay/blob/main/deployments/bradbury-steward-final.json
- Dated canonical proof: https://hearsay.run/steward-final-checkpoint.json
- Historical infrastructure issue: https://github.com/genlayerlabs/genlayer-cli/issues/426

Issue #426 documents the earlier infrastructure blocker. It is background,
not proof that these new state-machine corrections ran live. Diagnostic failures are preserved separately; no new issue/comment was posted.

The [historical submission package](submission-oct21.md) preserves earlier
controls, browser runs and transaction references. Its 20 honest controls and
five UNSOURCED negative judgements belong to contract
`0x2a5c1aA4Ae9e2292B737FE574aF44A2d8a5bB3F7` and are not reused as results for
the corrected deployment.
