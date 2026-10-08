# Bradbury activation blocker

The current campaign remains incomplete: **5 of the required 20 honest controls** have verified application judgements. At pinned block 23805969 (2026-10-08T11:17:56+00:00), an expired NATIONAL GRID PLC transaction still occupies pending head 22 of tail 23. The normal progress guard rejects another write. The negative phase has not started.

Contract: `0x2a5c1aA4Ae9e2292B737FE574aF44A2d8a5bB3F7`. Chain: Bradbury 4221, ConsensusMain VERSION 2.0.0. Contract source and SDK are unchanged; five initial validators and maxRotations 3 remain pinned. Earlier deployments are excluded.

Canonical blocker: `0xde4ce941e1f98c69ba2015e7ca4d420c028993c19e4b83371deed4ec2e573a9d`; stored PROPOSING (2), result IDLE (0), execution NOT_VOTED (0), no commitments or reveals. Its original validUntil `1791457126` passed before the pinned observation. The accepted queue head is `0x10c26378ce5d948caefca1343ebb0d058115552ebfbf20cde2f37018bac19e3c`. Seven supported recovery broadcasts changed the leader without releasing the pending queue or creating an application judgement. The last simulation of finalizeTransaction reverted; advanceStuckTransaction returned advanced=false. These observations establish an activation blocker; its underlying cause remains unresolved.

The [fresh checkpoint](../web/bradbury-prompt-checkpoint.json), checked at 2026-10-08T11:22:16.305794+00:00, accounts for all 60 initial campaign candidates: 5 verified judgements, 6 finalized infrastructure outcomes, 10 unresolved outcomes and 39 unsubmitted candidates. The unresolved group includes three UNDETERMINED receipts and three stored validator timeouts that have not finalized. None is an application refusal. The extra 20 candidates in [the second reserve](../corpus/live-second-reserve.json) remain preflight only and unsubmitted.

All five snapshots match canonical stored equivalence outputs or trace bytes by SHA-256 and reproduce the recorded votes. Solvency is balanced: held, escrowed and pools are each 505000; credited is 0. All 39 public EVM hashes are mined, with no unresolved, foreign or unbound broadcast. Latest and pending nonce are both 668; the pinned account balance is `158589023187484014360` wei. No signer, runner or observer remains active.

## Current outcomes

Company names come from the exact submitted envelopes. The outcome columns use the fresh canonical checkpoint; historical timeouts remain preserved separately.

| Company number | Submitted company name | Protocol transaction | Stored status | Current outcome |
| --- | --- | --- | --- | --- |
| 00048839 | BARCLAYS PLC | `0x82a9fa0b5e81d5da4ba72a3188562fcc60212c4ca45ca211fa075ac52ad20e68` | FINALIZED | NOT_EXECUTED |
| 00617987 | HSBC HOLDINGS PLC | `0xc66d7127bc788cfe8bc5cead04502f28718816b48967753773ee25bd13fdf066` | FINALIZED | TIMEOUT |
| 00102498 | BP P.L.C. | `0x45e19a6288faf1376f2a055c1da060734490f392ce25bd8f126987863406f9b0` | FINALIZED | VERIFIED JUDGEMENT |
| 04366849 | SHELL PLC | `0x99cace8e89b7b9e91bb5cf67ec84868b94e45df6ee21800b8963e72527589aab` | FINALIZED | TIMEOUT |
| 00445790 | TESCO PLC | `0xb449ab7e5af96fa47dd3cd7eb5133c84f712ade7500a6a114917267767ff5692` | FINALIZED | NOT_EXECUTED |
| 00041424 | UNILEVER PLC | `0x4c03ad5bb72838b747ab51f8d0f974785e3e3cf106d483cd2c0b84ff08e3f7a2` | FINALIZED | TIMEOUT |
| 03888792 | GSK PLC | `0xfae808a56c96380d2ee0e007c9a9537196ffced3086bb51a88969addaad1c414` | FINALIZED | TIMEOUT |
| 02723534 | ASTRAZENECA PLC | `0xb37860005e5a179eecbcb1d36ef123ceb761b369fc2b752d25a55837ade69663` | FINALIZED | VERIFIED JUDGEMENT |
| 01833679 | VODAFONE GROUP PUBLIC LIMITED COMPANY | `0x10c26378ce5d948caefca1343ebb0d058115552ebfbf20cde2f37018bac19e3c` | APPEAL_REVEALING | UNRESOLVED |
| 04190816 | BT GROUP PLC | `0x4edfcd50b27e1ba3c7e7912d759030f22fb5454d5671b330068e925f91282223` | ACCEPTED | VERIFIED JUDGEMENT |
| SC045551 | NATWEST GROUP PLC | `0x8930d0ab292f6b3cf9ebbb3a6e4ba3b5f0a754838b18ae5fbcdcf752a9529922` | APPEAL_REVEALING | UNRESOLVED |
| SC095000 | LLOYDS BANKING GROUP PLC | `0x9308f6adfd7b0042a88b93bb9d83cb144f8a63583b6daed6c64d805e6db1acbd` | ACCEPTED | VERIFIED JUDGEMENT |
| 00023307 | DIAGEO PLC | `0x958f228bc20833c6ba6475e772ca470913d1dfde323d85816013a6bd6a5c0d74` | VALIDATORS_TIMEOUT | UNRESOLVED |
| 06270876 | RECKITT BENCKISER GROUP PLC | `0x94ec35b0103548c2ff63d7a62a4f8d4284072e950b26a49aa2900783de89fd5c` | UNDETERMINED | UNRESOLVED |
| 01470151 | BAE SYSTEMS PLC | `0x97c7118a4f838b6a1c6e107fb75bb445c0dfc46fa351f76a87cec24d96200d4d` | UNDETERMINED | UNRESOLVED |
| 07524813 | ROLLS-ROYCE HOLDINGS PLC | `0x4a738e90999f5cfab24e43eea92651dc25ad26a83ac780164684b6413b6e1810` | VALIDATORS_TIMEOUT | UNRESOLVED |
| 02468686 | AVIVA PLC | `0xdb36c145ff3d845c837cc69e0dea56a6b822b685e457e5db51a688e1c72d5e9d` | VALIDATORS_TIMEOUT | UNRESOLVED |
| 01417162 | LEGAL & GENERAL GROUP PLC | `0x98f408559e94146fa92a3452eec2a1357def78f8997775cf41dece34e6789bba` | APPEAL_COMMITTING | UNRESOLVED |
| 04256886 | MARKS AND SPENCER GROUP P.L.C. | `0xa83fcb15a17ee1873e8af77d0435acc3480aee673397b74ee738115c2bbceee1` | ACCEPTED | VERIFIED JUDGEMENT |
| 00185647 | J SAINSBURY PLC | `0x3fb7b0de6712922513a03d5b306fb20714f0a7ab67ef0ec2340c7b7bd57096a9` | UNDETERMINED | UNRESOLVED |
| 04031152 | NATIONAL GRID PLC | `0xde4ce941e1f98c69ba2015e7ca4d420c028993c19e4b83371deed4ec2e573a9d` | PROPOSING | UNRESOLVED |

## National Grid recovery broadcasts

Every broadcast below mined successfully. The recorded immediate effect was a leader change; later natural transitions are not attributed to these calls.

| Operation | EVM transaction | Observed block after receipt |
| --- | --- | --- |
| processIdleness | `0x8957c708498d383188b75ed65ed4ffcff9187b6836b80ed9c5bc5c202871518b` | 23803068 |
| processIdleness | `0x21e586ae3ec279621522cda9db0a019c12043783d38b7b5e7c5ca4654b256e8d` | 23803515 |
| processIdleness | `0xa6bbbd4d9c76f703e2956313b7209533114e52c317331eda21ace73a7c817cdf` | 23804018 |
| processIdleness | `0x9f070d9b2a33017d02e4529cc82248a20c02f3712772acad9d264eff6ba0f541` | 23804561 |
| processIdleness | `0x0dee6117b8ea43ce51d4ba2cd4df45975cf1012c8c089fe176c825c01dd27da4` | 23805139 |
| leaderIdleness | `0xf670aeddf02ac05a3f3962deb8ecd257f841ae8e65fc7d1e7124b9996e93c0e4` | 23805433 |
| processIdleness | `0xcb48168799adba89dd97d3888c0f41b38075a958c97401d51478562e45e48087` | 23805729 |

The full original manifest, historical outcomes, refusals, receipts and all recovery results remain under `runs/bradbury-prompt`. Public audit paths are `expired-guard-audit/pinned-blocker.json`, `broadcast-reconciliation.json`, `result.json` and `checkpoint-summary.json`. Signing keys and serialized signed transaction bytes are excluded. Resume the same cohort only after fresh full scan, balanced solvency and the unchanged pinned queue guard permit progress. No new deployment or defence conclusion is part of this checkpoint.
