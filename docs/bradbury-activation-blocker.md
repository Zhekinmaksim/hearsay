# Bradbury activation blocker

The pending queue cleared on **9 October**. At block **23904318**,
**04:45:30 UTC**, it was empty **31/31**, and Burberry had no application
judgement. Continuation then produced a verified Whitbread admission: the
frozen 50-attempt scan has **12 honest judgements**, below the required 20,
and no negative case has been submitted. The appended resumption section
preserves these observations alongside the earlier blocker history.

## Historical National Grid blocker: 11:17 UTC

This report preserves the blocker observed at **2026-10-08 11:17:56 UTC**. A later pinned read at block **23813319** (chain timestamp `1791472305`) found the pending queue empty: head and tail were both 23, with a zero head transaction hash. National Grid was then UNDETERMINED without application execution. Continuation resumed with Prudential; neither transition adds a judged control. The accepted queue still had an unresolved Vodafone appeal. The observations below are historical, not the current queue state.

At the report's original checkpoint, the campaign remained incomplete: **5 of the required 20 honest controls** had verified application judgements. At pinned block 23805969 (2026-10-08T11:17:56+00:00), an expired NATIONAL GRID PLC transaction still occupied pending head 22 of tail 23. The normal progress guard rejected another write. The negative phase had not started.

Contract: `0x2a5c1aA4Ae9e2292B737FE574aF44A2d8a5bB3F7`. Chain: Bradbury 4221, ConsensusMain VERSION 2.0.0. Contract source and SDK are unchanged; five initial validators and maxRotations 3 remain pinned. Earlier deployments are excluded.

Canonical blocker: `0xde4ce941e1f98c69ba2015e7ca4d420c028993c19e4b83371deed4ec2e573a9d`; stored PROPOSING (2), result IDLE (0), execution NOT_VOTED (0), no commitments or reveals. Its original validUntil `1791457126` passed before the pinned observation. The accepted queue head is `0x10c26378ce5d948caefca1343ebb0d058115552ebfbf20cde2f37018bac19e3c`. Seven supported recovery broadcasts changed the leader without releasing the pending queue or creating an application judgement. The last simulation of finalizeTransaction reverted; advanceStuckTransaction returned advanced=false. These observations establish an activation blocker; its underlying cause remains unresolved.

The [saved 11:22 checkpoint](../web/bradbury-prompt-checkpoint-20261008-1122.json), checked at 2026-10-08T11:22:16.305794+00:00, accounts for all 60 initial campaign candidates: 5 verified judgements, 6 finalized infrastructure outcomes, 10 unresolved outcomes and 39 unsubmitted candidates. The unresolved group includes three UNDETERMINED receipts and three stored validator timeouts that have not finalized. None is an application refusal. The extra 20 candidates in [the second reserve](../corpus/live-second-reserve.json) were preflight only and unsubmitted at that checkpoint.

All five snapshots matched canonical stored equivalence outputs or trace bytes by SHA-256 and reproduced the recorded votes. At that original snapshot, solvency was balanced: held, escrowed and pools were each 505000; credited was 0. All 39 public EVM hashes were mined, with no unresolved, foreign or unbound broadcast. Latest and pending nonce were both 668; the pinned account balance was `158589023187484014360` wei. No signer, runner or observer remained active at that stop.

## Outcomes at the original checkpoint

Company names come from the exact submitted envelopes. The outcome columns use the fresh canonical checkpoint; historical timeouts remain preserved separately.

| Company number | Submitted company name | Protocol transaction | Stored status | Outcome at checkpoint |
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

## Burberry blocker: 18:29 UTC

BURBERRY GROUP PLC, company number **03458224**, was submitted as an honest
active-status claim. Its protocol transaction is
`0x093f34a6b9b100dfd92d2dfddc655d0ef7c62ee153129596d44b42c4658978b6`.
At block **23823415**, hash
`0x6b9096d66236d49e55f87961efd5f83b78eb8a9333ac947b1d22c40d4cad529d`,
stored state was `PROPOSING / IDLE / NOT_VOTED`, with **0 commitments and
0 reveals**. It still occupied pending head **30** of tail **31**, so the
unchanged queue guard blocked the next write. Its original `validUntil`
`1791486502` is **19:08:22 UTC**; that lifetime had not expired at this read.

One supported `processIdleness` call from the original sender mined at block
**23822937**, **18:21:12 UTC**, EVM transaction
`0x4d1ff77a403311b3335d3f2f646eedf2accc05e556fcb89b5885cc4feac29c37`.
The recorded effect was a leader change from `a856…` to `2CD…`, with no
application judgement or queue release. Activation reset to `1791483671`
(**18:21:11 UTC**); its 420-second deadline, `1791484091` (**18:28:11 UTC**),
had passed again by the pinned observation. An earlier `finalizeTransaction`
simulation reverted. No repeated call that merely changed metadata, admin
operation, or replacement deployment is part of this update. The cause of
the stalled activation remains unresolved.

The frozen full scan retains **29 honest attempts**, **7 verified entries**,
**22 attempts without matching application state**, and **0 scan errors**.
All seven pinned snapshots and recorded votes reproduce; BP and AstraZeneca
are Finalized, while the other five entries are Accepted and provisional.
Protocol failures and missing state are not application refusals. The original
60-candidate cohort remains unchanged: 50 honest candidates and ten negative
cases, including one construction-only citation refusal. The extra 30 controls
in the third reserve remain preflight evidence and are not active or judged.

After the recovery, all **48 public EVM hashes were mined**, with **0 unbound
broadcasts** and latest/pending nonce **677/677**. Held value, escrowed value
and pools were each **507000 wei**, with balanced accounting.

The [saved 18:35 checkpoint](../web/bradbury-prompt-checkpoint-20261008-1835.json), checked
at **2026-10-08 18:35:05 UTC**, covers the 60 declared candidates: **7 verified
judgements, 6 finalized infrastructure outcomes, 16 unresolved outcomes and
31 unsubmitted**. Its report matches the verified entries and solvency is
balanced. The [saved 17:31 checkpoint](../web/bradbury-prompt-checkpoint-20261008-1731.json)
preserves the earlier 26-attempt observation; the 11:22 archive remains intact.

Frozen local evidence under `runs/bradbury-prompt`:

- `current-queue-23823415.json` — pinned queue and canonical receipts.
- `entry-idleness-results.jsonl` — recovery result and before/after state.
- `resumed-honest-audit/after-burberry-idleness-reconcile.json` — public hashes
  and nonce reconciliation.
- `resumed-honest-audit/fresh-29-after-idleness-records.jsonl`, its
  `.issues.json` companion and `fresh-29-after-idleness-receipts/` — full scan
  and canonical receipt captures.
- `resumed-honest-audit/fresh-29-after-idleness-verified-records.jsonl` — the
  seven hash-verified, replayed records.

These paths identify frozen local proofs; the
[public checkpoint](../web/bradbury-prompt-checkpoint.json) carries its own
`checked_at` and incomplete coverage. No defence conclusion follows from the
recovery or from these seven controls.

## Burberry after original expiry: 19:11 UTC

At block **23825889**, hash
`0xbfd1ace6ba27a025fd7b43e84b5c8514d8d73c4eb86e721f1934565479411d02`,
chain timestamp `1791486706` (**2026-10-08 19:11:46 UTC**, **9 October
00:11:46 Asia/Tashkent**), the original `validUntil` `1791486502`
(**19:08:22 UTC**) had passed. The same Burberry transaction remained at
pending head **30** of tail **31**, `PROPOSING / IDLE / NOT_VOTED`, with
**0 commitments, 0 reveals and 13 validators**. No matching application
judgement existed. Expiry did not release the pending queue.

Fresh supported read-only simulations returned `advanced=false / status=2`
for `advanceStuckTransaction`; `finalizeTransaction` reverted with selector
`0x90cb8b61` at block **23825773**. The idleness operations could be simulated,
but no further recovery was signed after the single mined `4d1ff77…` call
recorded above. Its leader change remains the only observed effect; no
administrative action or redeployment was used.

The final frozen scan again contains **7 verified entries from 29 honest
attempts**, **22 missing application records** and **0 scan errors**. Full
60-candidate coverage remains **7 judged, 6 finalized infrastructure outcomes,
16 unresolved and 31 unsubmitted**; no negative case has been submitted.
All **48 public EVM hashes** are mined, latest/pending nonce is **677/677**,
unbound broadcasts are **0**, and the pinned account balance is
**158587664100632438110 wei**. Held, escrowed and pools remain **507000 wei**
with balanced accounting. No live writer, runner or observer remains after
bounded cleanup. Source, deployment, SDK and consensus settings are unchanged.

Post-expiry local proofs under `runs/bradbury-prompt` are
`current-queue-23825889.json` and, under `resumed-honest-audit/`,
`expired-burberry-29-verified-records.jsonl`,
`expired-burberry-29-records.jsonl`, its `.issues.json` companion,
`expired-burberry-29-receipts/`, `expired-burberry-journal-reconcile.json`,
`expired-burberry-summary.json` and `expired-burberry-report.md`.

The [8 October checkpoint](../web/bradbury-prompt-checkpoint-20261008-1917.json) has exact
`checked_at` `2026-10-08T19:17:41.483065+00:00` (**19:17:41 UTC**, **9 October
00:17:41 Asia/Tashkent**). Its full 60-candidate accounting remains **7 judged,
6 finalized infrastructure outcomes, 16 unresolved and 31 unsubmitted**, with
0 construction-only cases completed. Its report matches the verified entries
and solvency is balanced. The 18:35 and earlier checkpoint archives remain
preserved.

At that stop, the project remained **not ready**. Resumption required a fresh
actually empty pending queue and the same full signing guards. Neither expiry
nor a successful EVM recovery receipt substituted for that proof or for an
application judgement.

## 9 October queue release and continuation

At block **23904318**, timestamp `1791521130` (**2026-10-09 04:45:30 UTC**),
pending head and tail were both **31**, with a zero pending-head transaction.
Consensus VERSION `2.0.0`, bindings and implementations were unchanged.
Burberry was now `UNDETERMINED / IDLE / NOT_VOTED`, without matching
application state; it is not a judged control or a contract refusal. The fresh
29-attempt scan retained seven source- and vote-verified entries. All 48 public
hashes were mined, nonce remained 677, and the same signing guards permitted
continuation. The release is not attributed to the earlier recovery call.

**WHITBREAD PLC**, company **04120344**, was the thirtieth honest attempt,
protocol transaction
`0xa0037e22bcf7f3bf5f4f62959202d69ceb9f6a0fe7a7062b011e045f7ccd0785`.
At block **23905621**, timestamp `1791521547` (**04:52:27 UTC**), its
canonical receipt was Accepted with successful execution and five validator
votes. The matching entry 7 was `ADMITTED`; its `yes / yes / none` votes and
exact stored EQ source snapshot reproduce. Accepted state remains provisional.

The frozen full scan after that write has **30 honest attempts**, **8 verified
entries**, **22 missing application records** and **0 scan errors**. Every
source snapshot and recorded vote was freshly verified. At block **23905861**,
timestamp `1791521626` (**04:53:46 UTC**), the pending queue was empty
**32/32**. All **49 public EVM hashes** were mined, latest/pending nonce was
**678/678**, and held, escrowed and pools were each **508000 wei**, balanced.
Continuation remains in progress. The original full 60-candidate master cohort
is unchanged, and no negative case has been submitted.

Frozen proof paths under `runs/bradbury-prompt/oct9-resume-audit/` are
`fresh-29-verified-records.jsonl`, `fresh-30-verified-records.jsonl`, their
fresh raw records/issue companions/receipt captures, and
`before-next-30-reconcile.json`. BAT then produced entry 8 with verified
`yes / yes / none` votes and source bytes, bringing the frozen 31-attempt scan
to nine judgements, 22 absent records and zero scan errors. Its protocol hash
is `0x3f7c4996daa603e9559729fbf76727051fe058fa550425ec5386708665a2804d`;
proof uses `fresh-31-verified-records.jsonl`. The current checkpoint, checked
at `2026-10-09T05:19:03.085954+00:00`, accounts for the full 60 candidates:
9 judged, 6 finalized infrastructure, 16 unresolved and 29 unsubmitted.
The report matches and accounting is balanced at 509000 wei. The project still needs
20 genuine honest judgements and the original negative-case coverage; this
resumption does not complete that goal.

## SPIRAX continuation and 07:05 checkpoint

SPIRAX GROUP PLC (00596337) became the tenth verified honest control, entry 9,
ADMITTED with yes/yes/no-conflict votes. The fresh 39-attempt scan has ten
verified records and twenty-nine absent records, with zero scan errors.
The current full-60 checkpoint, checked at `2026-10-09T07:05:16.613866+00:00`,
contains ten judged, six finalized infrastructure, twenty-three unresolved and
twenty-one unsubmitted. Its report matches and global accounting is balanced
at 1010000 wei, including the separate frontend namespace. Older snapshots
remain preserved. Neither the negative phase nor the twenty-control target is
complete.

## SEVERN TRENT continuation and 07:53 checkpoint

The current full-60 snapshot at `2026-10-09T07:53:37.751049+00:00` contains
eleven current verified honest records after SEVERN TRENT, six finalized
infrastructure outcomes, twenty-eight unresolved and fifteen unsubmitted.
All eleven source/vote proofs reproduce; the full scan has zero errors and
global accounting is balanced at 1011000 wei. UNITED UTILITIES repeatedly
changed leaders and reached a leader timeout, without a judgement; pending
then emptied naturally at block23938529. No retry or paid recovery caused
that release. Earlier snapshots remain preserved.

## Full initial fifty and conditional reserve

The complete initial fifty milestone was verified at
`2026-10-09T08:54:38.385827+00:00`: twelve current judgements, six finalized
infrastructure outcomes, thirty-two unresolved and the ten original negative
cases unsubmitted. Its complete original-sixty snapshot and master remain
publicly archived. The conditional second twenty controls were appended to
both identical masters, preserving original fields/order, for active coverage
80 and SHA `dcd2e3be3029cd05b2f3c2a1ade735f938c4243c23b32f78c9ed2651e51995f9`.
The strict expanded snapshot at `2026-10-09T09:06:14.416021+00:00` has twelve
judged, six finalized infrastructure, thirty-two unresolved and thirty
unsubmitted, balanced at 1012000 wei. The third reserve remains inactive.
