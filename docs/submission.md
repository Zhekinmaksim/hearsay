# Hearsay — GenLayer Portal project submission

Destination: **GenLayer Portal → Builder → Projects**. The form text supplied
by the user is the requirements source for this package. The Portal showed
**one weekly Project spot remaining**; final submission consumes that spot.

**Preparation status: not ready to submit.** The live app at `/app.html` is
implemented. Its SDK and page checks pass, and a real browser has read Bradbury,
connected the wallet, matched BP's finalized transaction to entry 0, downloaded
its verified receipt and reproduced the verdict with the CLI. **Space creation through the frontend wallet is now demonstrated live. A new
claim transaction and verdict remain pending.** That remaining check matters to the Portal's full-transaction-lifecycle quality bar.
The app is published on Vercel, and its CI checks passed. On 9 October the
pending queue cleared, allowing the same cohort to resume. The current
published checkpoint contains **10/20 verified honest controls** after 39
attempts, including the newly admitted SPIRAX record. The negative phase has not started.
The authorized frontend `open_space` was sent and accepted, with matching
space 1. It remains provisional. The subsequent TESCO claim is prepared and
authorized only after creation finalizes; no claim transaction has been sent.

The user requested on 9 October that Portal work stop until the project is
fully ready. The existing unsubmitted draft is historical preparation; no
further filling, upload or submission is authorized at this stage.

## Copy-ready Portal fields

**Project name**

```text
Hearsay
```

**Project logo — optional identity asset**

Upload [`web/favicon-180.png`](../web/favicon-180.png): PNG, **180 × 180 px**,
**786 bytes**. Its dimensions and file type were inspected. It meets the
supplied PNG/JPEG/WebP, 128–2048 px and ≤2 MB requirements. The 32 px favicon
does not meet the minimum size. The prepared PNG remains unuploaded. The
actual Portal DOM reports all mandatory fields complete without it; optional
upload approval remains pending.

**Primary tag and topic tags**

Selected in the unsubmitted Portal draft:

- Primary: **AI & Agents**.
- Topics: **Source Verification** and **Multi-Agent Coordination**.

The inspected topic choices were Autonomous Execution, Multi-Agent
Coordination, Model Evaluation, AI Policy Enforcement, Verifiable Inference,
and Source Verification. On **9 October**, the actual Portal DOM and
screenshots verified unsubmitted draft **1079417206**, logged in as
**Zhekin**, with **7/7 mandatory fields complete**. The project name,
151-character one-liner, 943-character description, nine how-to steps,
439-character expected outcome, public app website, exact contract link,
selected tags and Application date are entered. The required GitHub URL is
filled and one valid GitHub Repository item is attached through Add Evidence.
No authentication-wallet signature was made. No project was submitted and the
weekly slot was not consumed.

**One-liner — 151/180 characters**

```text
Source-backed admission for shared agent memory: GenLayer judges claims, records evidence and votes, and cascades revocation through dependent entries.
```

**Description — local draft within 1000 characters**

The text describes the implemented app and discloses its remaining live-write
and evaluation limits. Update those disclosures only after verified evidence
supersedes them. The field below is the updated local draft.
The earlier Portal draft still contains 7/20; it has not been changed under
the user's instruction to finish the project before returning to the form.

```text
Agents reuse shared memory, so one unsupported entry can become a premise for many later decisions. Hearsay puts a GenLayer Intelligent Contract in front of admission.

The contract fetches each claim's source, asks two independent support framings and checks consistency against recent admitted entries. It records ADMITTED, UNSOURCED, CONTRADICTED or INCONCLUSIVE with pinned evidence and votes. Unreadable or disagreeing rounds do not admit. Challenges revoke an entry and taint its dependents; a bounded cascade rejudges them without the revoked premise.

The app reads Bradbury, connects a wallet and supports separate memory spaces, claim submission and canonical transaction tracking. Verified receipts replay locally. The public checkpoint has 10/20 judged honest controls; the attack phase has not started. Space creation ran live; a new claim transaction remains pending. Offline fixtures verify the implementation, not attack resistance.
```

**Website — required**

Prepared value:
[https://hearsay-psi.vercel.app/app.html](https://hearsay-psi.vercel.app/app.html).
The production app's public reads and BP replay download were verified. The
root homepage remains the supplementary offline evidence
stand.

**GitHub — required evidence**

Add [https://github.com/Zhekinmaksim/hearsay](https://github.com/Zhekinmaksim/hearsay)
through **Add Evidence**. Confirm the submitted repository includes the live
frontend, contract, accurate documentation and reproducible checks.

**Contract explorer link — optional**

```text
https://explorer-bradbury.genlayer.com/address/0x2a5c1aA4Ae9e2292B737FE574aF44A2d8a5bB3F7
```

This is the exact current Bradbury deployment. Earlier deployments do not
contribute to its live cohort.

**Demo URL — optional**

Leave blank until a direct YouTube or X demo URL exists. No such URL is supplied
in this package. The required website field remains separate.

**How-to steps**

These steps match the implemented controls. The BP read and replay flow was
verified in the browser; creation and submission are implemented and tested
offline, with a new real wallet transaction still outstanding. The same BP
flow and downloaded receipt were also verified on the public production app.

| Optional heading | Instruction |
| --- | --- |
| Open the live app | Open https://hearsay-psi.vercel.app/app.html. Public reads need no wallet. Confirm Bradbury, chain ID 4221, and contract 0x2a5c1aA4Ae9e2292B737FE574aF44A2d8a5bB3F7. |
| Inspect a finalized judgement | Under Transaction activity, paste 0x45e19a6288faf1376f2a055c1da060734490f392ce25bd8f126987863406f9b0 and click Resume receipt. Its canonical Finalized receipt matches BP entry 0: ADMITTED, support votes yes/yes, consistency none, and SHA-verified original source bytes. |
| Reproduce the verdict | Click Download replayable receipt. From the repository, run python3 cli/gate.py verify --receipt ~/Downloads/hearsay-entry-0-replay.json. The expected result is reproduces: true and exit 0. Download current receipt is the separate canonical audit wrapper. |
| Connect a wallet | Click Connect wallet. If needed, click Switch to Bradbury. The wallet approves each transaction and pays testnet network fees. |
| Create your memory space | Expand Create a space for your wallet. Review the name, policy and optional initial pool, which defaults to 500000 wei. Click Create space in wallet and approve. Wait for the created space to load; its ID must be nonzero. Space 0 is the read-only benchmark in this app. |
| Prepare a sourced claim | Click Use the Companies House example. It states that TESCO PLC (00445790) is an active public limited company incorporated on 27 November 1947 and cites https://find-and-update.company-information.service.gov.uk/company/00445790. Check the source before submitting; validators fetch it again. |
| Submit the entry | Review the 1000 wei write bond and gas fee. Click Submit claim in wallet and approve the write_entry transaction. |
| Follow consensus | Open Transaction activity. Follow the saved EVM and protocol hashes and canonical status. Reloading resumes reads; Resume receipt tracks a saved hash, and Check receipt now refreshes it. Pending or appealed transactions remain unresolved. |
| Read and save the result | After successful execution, inspect the matching entry's verdict, votes and source hash. Only ADMITTED passes the gate; Accepted state remains provisional. Download current receipt saves the audit wrapper. Download verified snapshot requires hash-matching stored bytes; Download replayable receipt additionally requires the recorded verdict to reproduce. |

**Expected verification outcome — owner/steward field, 439/500 characters**

Use this field when the Portal exposes it for the owner or steward role.

```text
Resume the BP transaction in the live app. Its canonical Finalized receipt matches entry 0: ADMITTED, yes/yes/none votes and verified original source bytes. Download replayable receipt and run cli/gate.py verify on it; the verdict reproduces. A wallet can create a separate memory space and submit the Companies House example. Pending, appeal, timeout and failed execution remain distinct from application refusal; Accepted is provisional.
```

The new-space flow uses a default initial pool of **500000 wei** and a **1000
wei** bond for the subsequent write; both transactions also cost network fees.
The space's configured challenge bond is **2000 wei**. The reviewer can change
the initial pool. Review-space writes do not contribute to space 0's benchmark
cohort.

**Download current receipt** exports a canonical audit wrapper.
**Download replayable receipt** exports the flat CLI input only after the
canonical receipt, exact entry match, stored snapshot hash and recorded votes
verify. The real browser-downloaded BP receipt reproduced `ADMITTED` with
`yes / yes / none` votes and **1670 characters** of exact source text. This
proves receipt integrity and verdict assembly; it does not rerun the model or
count as a newly submitted frontend transaction.

## Project description

Shared memory lets agents reuse each other's findings. It also lets a writer
insert an unsupported claim that later agents treat as a premise. Hearsay puts
a source and consistency check before admission, records refusals as well as
admissions, and retains the evidence used for each decision.

Each candidate uses the [`hearsay/1` envelope](../spec/memory-entry.md): a
claim, source URL, memory space, and optional dependencies on admitted entries.
The contract fetches the source itself rather than accepting a writer's inline
evidence. Two support framings must agree and meet the space's readable-round
floor. Supported claims are checked against up to 16 recent admitted entries.
The verdict is `ADMITTED`, `UNSOURCED`, `CONTRADICTED`, or `INCONCLUSIVE`;
`INCONCLUSIVE` does not admit. This is a source-admissibility rule, not a
general truth oracle: a supported historical claim can be admitted.

Admitted entries can be challenged against their pinned source. A successful
two-stage challenge revokes the entry and taints its dependents. The bounded
breadth-first cascade rejudges them without revoked premises; work past the
space's depth limit goes into a deferred queue. Write and challenge bonds,
credited withdrawals, and solvency are part of the contract state machine.

## How GenLayer is used

The decision runs inside [`contracts/hearsay.py`](../contracts/hearsay.py).
GenLayer validators render the URL with `gl.nondet.web.render` and answer the
support and consistency prompts with `gl.nondet.exec_prompt`. Source fetching
uses comparative equivalence. In the current isolated experiment,
`gl.eq_principle.strict_eq` compares parsed boolean support decisions and
conflicting entry IDs. Validators still judge both support framings
independently. [The comparison policy and compatibility evidence](consensus-decisions.md)
describe this experiment; improved network liveness has not been established.

The contract stores the source snapshot hash and recorded application votes.
Collection recovers the exact source bytes from stored equivalence outputs or
hash-matching GenVM trace storage. A freshly downloaded replacement page is
never substituted for the evidence judged on chain.

The architecture is small enough to inspect:

| Component | Responsibility |
| --- | --- |
| [`contracts/hearsay.py`](../contracts/hearsay.py) | Fetch, judge, store votes, handle bonds, challenges and cascade |
| [`cli/entry.py`](../cli/entry.py), [`cli/gate.py`](../cli/gate.py) | Validate and hash envelopes, reject duplicates, return recorded verdicts, replay receipts |
| [`scripts/collect_receipts.py`](../scripts/collect_receipts.py), [`scripts/enrich_snapshots.py`](../scripts/enrich_snapshots.py) | Reconcile canonical protocol receipts with application state and pinned source bytes |
| [`web/app.html`](../web/app.html), [`web/app.mjs`](../web/app.mjs), [`web/app-core.mjs`](../web/app-core.mjs) | Live wallet controls, reviewer spaces, canonical receipts, matched entries and verified receipt downloads; new real frontend write still unproven |
| [`web/lib.mjs`](../web/lib.mjs), [`web/index.html`](../web/index.html) | Local gate, receipt replay and cascade demonstration, with Python/JavaScript parity checks |

The CLI gate checks a corpus; it does not request a new model decision. An
unjudged entry returns exit 2 until submitted and collected. Callers can use
`--strict` to refuse entries without a recorded verdict. Exit 0 permits an
admitted entry, 1 refuses it, 2 reports an inconclusive or absent verdict, and 3
reports malformed input. Receipt replay checks hashes and verdict assembly
from recorded votes; it does not repeat the semantic model judgement.

## Public links and deployment identity

| Item | Link |
| --- | --- |
| Source repository | [Zhekinmaksim/hearsay](https://github.com/Zhekinmaksim/hearsay) |
| Live app | [app.html](https://hearsay-psi.vercel.app/app.html) |
| Interactive offline demo | [hearsay-psi.vercel.app](https://hearsay-psi.vercel.app/) |
| Incomplete current-cohort checkpoint | [bradbury-prompt-checkpoint.json](https://hearsay-psi.vercel.app/bradbury-prompt-checkpoint.json) |
| Current contract | [0x2a5c1aA4Ae9e2292B737FE574aF44A2d8a5bB3F7](https://explorer-bradbury.genlayer.com/address/0x2a5c1aA4Ae9e2292B737FE574aF44A2d8a5bB3F7) |
| Deployment transaction | [0x7767c789…6267f3c](https://explorer-bradbury.genlayer.com/tx/0x7767c7897d9439503377111501bc020b6a159a092c3e7bd2f5a0bb5116267f3c) |
| Deployment metadata | [deployments/bradbury-prompt.json](../deployments/bradbury-prompt.json) |
| CI evidence, including the live app and submission guards | [GitHub Actions run 37890921250](https://github.com/Zhekinmaksim/hearsay/actions/runs/37890921250) |

Network: Bradbury testnet, chain ID **4221**. Current protocol parameters are
five initial validators and `maxRotations=3`. The deployed ConsensusMain is
VERSION `2.0.0`; [verified version evidence](bradbury-protocol-version.md)
documents its status decoder. The current contract is an isolated experiment;
earlier deployments remain separate and do not contribute to its denominator.

Readable contract SHA-256:
`d2670d4204d769ce14f26328d3f8a4a86c4b645f0a54c5149d5269804ce53296`.
Packed deployment source SHA-256:
`2125f18b442bface1d2538563ff9d4fb40bb6e3f690ff8b42a3d5916ffece97c`.
The linked green source-check CI run verifies commit `9818be0`, including the
live frontend and submission guards. Those implementations remain unchanged;
later documentation commits do not change this evidence. Its additional
fallback controls are preflight data, not active submissions or measured
judgements.

## Reproduce the local evidence

Use Python 3.12, Node.js 22 and `make`, as in
[repository CI](../.github/workflows/check.yml). The core Python checks use the
local GenLayer stub. Install the JavaScript test dependencies once; then the
commands below use local data and perform no chain writes, RPC reads or model
calls.

```sh
git clone https://github.com/Zhekinmaksim/hearsay.git
cd hearsay
npm install --no-save jsdom genlayer-js@1.1.8
make lint test receipts-test checkpoint-test chain-test bridge-test queue-test
make submission-test submission-signing-test app-test
make dry-run replay parity gate-parity
node test/page.mjs
make gate
```

`make dry-run` writes to `runs/offline/corpus.json` and
`runs/offline/entries/`, preserving the published corpus and example envelopes.
`node test/page.mjs` drives the committed page. The archived offline corpus is
[`web/corpus.json`](../web/corpus.json), SHA-256
`02ac47d18234ca9665ec5a64114491bde980ecac5676ce2fc691c78f8f32171e`.

The existing verified results are:

| Check | Result |
| --- | --- |
| Contract, envelope, money and cascade checks | 95 passed |
| Scripted offline run | 18 judged rows; 1 write prevented before consensus |
| Honest scripted fixtures | 0 refused out of 9; not a measured live false-rejection rate |
| Recorded verdict replay | 18/18 reproduce |
| Python/JavaScript parity | 67 checks passed |
| Interactive offline page | 50 checks passed |
| Receipt collection and diagnosis | 46 tests passed |
| Optional explorer enrichment boundary | 7 tests passed |
| Checkpoint accounting | 8 tests passed |
| Actual SDK queue guard | 37 checks passed |
| Broadcast journal | 13 checks passed |
| Live app SDK and wallet paths | 43 checks passed using the browser bundle; zero real sends |
| Live app DOM controls | 22 checks passed; zero real sends |
| Submission publication accounting | 16 tests passed |
| Submission signing guard | 40 checks passed with actual SDK, dummy accounts and fake RPC |
| Gate examples | Exit codes 0, 1, 2 and 2; malformed-input parity also covers exit 3 |

The offline model follows scripted fixture answers. These results verify the
state machine, accounting and replay plumbing; they do not measure resistance
to live attacks. The ordering rule's pre-consensus prevention is reported
separately from application judgement.

Separately, the initial real-browser check verified ConsensusMain `2.0.0`,
live accounting and five records, connected the wallet on chain 4221, and read BP's canonical
`Finalized / Majority agree / Finished with return` receipt. The matching
entry 0 was `ADMITTED`; **Download replayable receipt** produced a file that
the Python CLI verified with exit 0. No new wallet transaction was sent in that
browser session. This verifies the live read and replay path, while the new
frontend write remains a gap.

The complete local `make all` run passed the reference checks. Subsequent
connection and continuation fixes pass **65 app checks** and **56 publication
and signing checks**, alongside the existing receipt checks. Real browser
layouts were checked at **360 × 800** and **1280 × 900** without horizontal overflow.
Local PNG regeneration was skipped because the Cairo/font dependencies were
unavailable; the existing verified logo and image assets were preserved.

To rebuild the page and assets, use `make site page`. PNG generation additionally
uses CairoSVG and the repository's Newsreader and Archivo fonts; the committed
page can be opened directly without rebuilding. Full CI installs these asset
dependencies before running its build checks.

## Offline stand walkthrough

This supplements the live-app instructions above. It verifies local controls
and makes no live transaction.

1. Open the [demo](https://hearsay-psi.vercel.app/). Read the incomplete Bradbury
   notice and the scripted-run warning. Use **Show an honest entry** and
   **Show another attempt** to compare recorded claims and their votes.
2. In **Run the gate**, keep the preloaded whitespace variant. It is refused as
   a duplicate before consensus. Remove `https://` from the source to see exit
   3. Enter a fresh claim containing `>>>` to see exit 2 and the defused fence.
3. In **Verify a receipt**, start with **Reproduces.** Toggle **Forge the
   verdict**, **Swap the page**, **Edit the claim**, or **Flip one vote**. Each
   mutation changes the result to **Does not reproduce.** Toggle it back to
   restore the row.
4. In **Revoke an entry**, choose entry 0 and click **Revoke and cascade**.
   Follow the tainted dependents, the surviving independent source, and the
   entry deferred beyond depth 3. This replays recorded facts locally.
5. Open the [Bradbury checkpoint](https://hearsay-psi.vercel.app/bradbury-prompt-checkpoint.json).
   Inspect `complete: false`, `checked_at`, `coverage`, and one entry's
   `snapshot_provenance`, `votes`, and `consensus_checkpoint`. Its `tx` can be
   inspected at the [Bradbury explorer](https://explorer-bradbury.genlayer.com).

No wallet is needed for this walkthrough. A CLI reviewer can extract any row
from the downloaded checkpoint or offline corpus and replay it locally:

```sh
python3 - <<'PY'
import json
from pathlib import Path
row = json.loads(Path("web/bradbury-prompt-checkpoint.json").read_text())["entries"][0]
Path("/tmp/hearsay-review-receipt.json").write_text(json.dumps(row))
PY
python3 cli/gate.py verify --receipt /tmp/hearsay-review-receipt.json
```

The expected result is a reproduced verdict and exit 0.

## Live evidence and remaining submission work

The [current checkpoint](https://hearsay-psi.vercel.app/bradbury-prompt-checkpoint.json)
was checked at **2026-10-09 07:05:16 UTC** (**12:05:16 Asia/Tashkent**), exact
`2026-10-09T07:05:16.613866+00:00`. It accounts for all 60 candidates:
**10 verified honest judgements, 6 finalized infrastructure outcomes,
23 unresolved, 21 unsubmitted and 0 construction-only cases completed**.
The report matches the verified entries; held, escrowed and pools are each
**1010000 wei**, balanced, including the separate frontend-created namespace.
It remains incomplete, with no defence conclusion.

The [saved 05:19 checkpoint](../web/bradbury-prompt-checkpoint-20261009-0519.json)
preserves the earlier 31-attempt state with nine verified entries, six finalized
infrastructure outcomes, sixteen unresolved and twenty-nine unsubmitted.

The [saved 19:17 checkpoint](../web/bradbury-prompt-checkpoint-20261008-1917.json)
was checked at **2026-10-08 19:17:41 UTC** (**9 October 00:17:41 Asia/Tashkent**),
exact `checked_at` `2026-10-08T19:17:41.483065+00:00`. It accounts for all
60 candidates: **7 verified judgements, 6 finalized infrastructure outcomes,
16 unresolved outcomes and 31 unsubmitted**, with **0 construction-only cases
completed**. The report matches the seven verified entries and solvency is
balanced. This is an incomplete checkpoint, with no defence conclusion.

The [saved 18:35 checkpoint](../web/bradbury-prompt-checkpoint-20261008-1835.json)
was checked at **2026-10-08 18:35:05 UTC**. It covers all 60 declared candidates:
**7 verified judgements, 6 finalized infrastructure outcomes, 16 unresolved
outcomes and 31 unsubmitted**. Its report matches the verified entries and
its solvency is balanced. The [saved 17:31 checkpoint](../web/bradbury-prompt-checkpoint-20261008-1731.json)
preserves the earlier 26-attempt state: 7 verified, 6 finalized infrastructure,
13 unresolved and 34 unsubmitted.

The dated 8 October frozen scan retained **29 honest attempts**, **7 verified entries**,
**22 attempts without matching application state**, and **0 scan errors**.
The exact submitted names are BP P.L.C., ASTRAZENECA PLC, BT GROUP PLC,
LLOYDS BANKING GROUP PLC, MARKS AND SPENCER GROUP P.L.C., CENTRICA PLC, and
BTC PIPELINE HOLDING COMPANY LIMITED. All seven pinned snapshots and recorded
votes reproduce. BP and AstraZeneca are Finalized; the remaining five are
Accepted and provisional. Accepted state can be replayed after an adverse
appeal, so publication requires fresh reconciliation.

At **18:29:05 UTC**, block **23823415**, BURBERRY GROUP PLC (03458224),
transaction
`0x093f34a6b9b100dfd92d2dfddc655d0ef7c62ee153129596d44b42c4658978b6`,
remained `PROPOSING / IDLE / NOT_VOTED`, with no commitments or reveals,
occupying pending head **30** of tail **31**. One supported owned
`processIdleness` call mined at block **23822937** (**18:21:12 UTC**), EVM hash
`0x4d1ff77a403311b3335d3f2f646eedf2accc05e556fcb89b5885cc4feac29c37`.
It changed the leader without releasing the queue or creating a judgement.
The reset activation deadline (**18:28:11 UTC**) passed again before the
pinned observation; original transaction `validUntil` remained **19:08:22 UTC**.
An earlier finalization simulation reverted. No liveness improvement is
established by that recovery.

The final pinned read at block **23825889**, **2026-10-08 19:11:46 UTC**
(**9 October 00:11:46 Asia/Tashkent**), occurred after original `validUntil`
`1791486502` (**19:08:22 UTC**). Burberry still occupied pending **30/31**,
`PROPOSING / IDLE / NOT_VOTED`, with **0 commitments, 0 reveals and 13
validators**, and no application judgement. Fresh supported read-only
`advanceStuckTransaction` returned `advanced=false / status=2`;
`finalizeTransaction` reverted with `0x90cb8b61` at block **23825773**.
No further recovery signature followed the single leader-changing call.
Expiry did not release the queue.

The reconciliation found **48 mined public EVM hashes**, **0 unbound
broadcasts** and latest/pending nonce **677/677**. Held, escrowed and pools
were each **507000 wei**, with balanced accounting. Frozen local proof paths
are under `runs/bradbury-prompt`: `current-queue-23823415.json`,
`entry-idleness-results.jsonl`, and
`resumed-honest-audit/after-burberry-idleness-reconcile.json`. The full scan,
receipt captures and seven verified records use the
`resumed-honest-audit/fresh-29-after-idleness-` prefix. The
[activation report](bradbury-activation-blocker.md) preserves the exact timers
and all dated blocker observations.

Post-expiry proofs use `current-queue-23825889.json` and the
`resumed-honest-audit/expired-burberry-29-` prefix for records, issues,
receipts and the seven verified entries. The same directory contains
`expired-burberry-journal-reconcile.json`, `expired-burberry-summary.json`
and `expired-burberry-report.md`. They retain **7 verified, 6 finalized
infrastructure, 16 unresolved and 31 unsubmitted** in the original full
60-candidate cohort, with **0 negative cases submitted**. The pinned account
balance was **158587664100632438110 wei**, with **48 mined public hashes**,
nonce **677/677**, **0 unbound broadcasts** and balanced **507000 wei** held,
escrowed and pooled. No active writer, runner or observer remains after cleanup.

The exact planned cohort is public at
[`corpus/bradbury-prompt-campaign.json`](../corpus/bradbury-prompt-campaign.json):
50 honest candidates and the original ten negative cases. Its SHA-256 is
`6970d7ec5437f47f3705e9318143a4c37a33f29beecb31603c2b52d366820487`.
The original [11:22 checkpoint](../web/bradbury-prompt-checkpoint-20261008-1122.json)
remains preserved. Burberry's queue blockage is now dated history: the pending
queue cleared on 9 October without creating a Burberry judgement. Unresolved
appeals, protocol timeouts and no-execution outcomes remain infrastructure
history, never counted as application refusals.
The [liveness report](bradbury-liveness-report.md) includes the published
upstream issues.

The [third fallback reserve](../corpus/live-third-reserve.json) contains 30
additional preflight controls, SHA-256
`8e9d091f8d819e635716a381e24b9474096ff4898770b72a9bb8ff870e76860b`.
It is unsubmitted and inactive. It does not alter the current 60-candidate
cohort or add any judged controls.

The [negative-input preflight](live-negative-preflight.md) verifies the real
URLs and authentic archive, and defines the limits of each declared class.
Its checks are preflight only; no negative application verdict is implied.

The live control group uses Companies House company profiles. It does not
establish performance across arbitrary websites. Demonstration bonds are not
an economic-security calibration. Full live attack resistance, measured
latency savings, and a reliable protocol recovery method remain unproven.

## 9 October continuation

At block **23904318**, **2026-10-09 04:45:30 UTC**, the pending queue was
empty, head/tail **31/31**. Consensus VERSION `2.0.0`, bindings and
implementations were unchanged. Burberry was `UNDETERMINED / IDLE /
NOT_VOTED`, without an application judgement. The fresh full 29-attempt scan
retained all seven verified controls. No causal link between the overnight
release and the earlier recovery is established.

The thirtieth honest attempt was **WHITBREAD PLC**, company **04120344**,
transaction
`0xa0037e22bcf7f3bf5f4f62959202d69ceb9f6a0fe7a7062b011e045f7ccd0785`.
At block **23905621**, **04:52:27 UTC**, it was Accepted with successful
execution and five votes. The matching entry 7 is `ADMITTED`, with
`yes / yes / none` recorded application votes. Its exact stored EQ snapshot
matches the source hash and its verdict reproduces. Accepted remains
provisional.

The frozen full 30-attempt scan has **8 verified entries**, **22 missing
application records** and **0 scan errors**. All eight source snapshots and
recorded votes are freshly verified. At block **23905861**, **04:53:46 UTC**,
the pending queue was empty **32/32**, all **49 public EVM hashes were mined**,
latest/pending nonce was **678/678**, and held, escrowed and pools were each
**508000 wei**, balanced. These are dated observations; continuation is still
in progress. No negative case has been submitted, and the original
50-honest/10-negative master cohort remains unchanged.

Frozen local proofs are under `runs/bradbury-prompt/oct9-resume-audit/`:
`fresh-29-verified-records.jsonl`, `fresh-30-verified-records.jsonl` and their
fresh raw records, issues and receipt captures, plus `before-next-30-reconcile.json`.

The browser already had permission for wallet
`0x771388495F34d21C5574FeFc04cd1D5811E00aDa`; Bradbury 4221 and funding were
confirmed. Space **Hearsay reviewer · 9 October 2026**, with a **500000 wei**
pool, is prepared. Automatic approval review initially rejected **Create space
in wallet** before any click or send because the exact paid transaction had
not yet been approved. The user then **explicitly authorized initiation** for
the specified network, contract, name and pool; the final wallet signature
remains pending.

The wallet briefly switched accounts and disconnected. The browser later
restored the authorized funded account
`0x771388495F34d21C5574FeFc04cd1D5811E00aDa` on Bradbury 4221. No request was
initiated; the campaign signer must hold before the paid request proceeds. Browser automation is available again after the earlier
extension update requirement. No browser send or transaction-journal entry
occurred. The earlier authentication-identity and Rabby reputational-alert gaps
are no longer current.

## Pre-submission checklist

The supplied Portal quality bar requires a real trust problem, live or
authoritative data, full source with accurate documentation, a frontend that
calls the contract and handles its transaction lifecycle, and useful behaviour
beyond boilerplate. Hearsay's source-admission and dependent-revocation rules
address the trust problem; its pinned Companies House evidence is authoritative
registry data. Its frontend now makes genuine public contract reads and exports
a verified live receipt. Demonstrating a new frontend claim transaction and matching verdict
remains the product gap; the app is already published.

Form preparation:

- [x] Project name: Hearsay.
- [x] Logo: valid 180 × 180 px PNG, 786 bytes.
- [x] One-liner within 180 characters.
- [x] Description within 1000 characters, with incomplete-evaluation disclosure.
- [x] Expected verification outcome within 500 characters, prepared for the
  owner/steward field.
- [x] Exact optional Bradbury contract explorer link prepared.
- [x] Primary **AI & Agents**, topics **Source Verification** and
  **Multi-Agent Coordination**, selected in the unsubmitted Portal draft.
- [x] Set the required website to the verified public live app and confirm its
  how-to instructions match the route, controls and outputs.
- [x] Add the GitHub Repository item through Add Evidence in the unsubmitted
  draft.
- [x] Confirm the required GitHub URL and attached GitHub Repository evidence
  are selected and valid in the actual Portal DOM.
- [x] Enter the prepared description, nine how-to steps, expected outcome and
  verified public website.
- [ ] Optionally upload the valid prepared logo; upload approval is pending.
  Its absence does not block the verified 7/7 mandatory-field completion.
- [x] Verify Portal draft identity as Zhekin without an authentication-wallet
  signature.
- [x] Enter the 439-character expected-outcome field for the submitting role.

The [local Remotion film](../film/README.md) now distinguishes fictional
offline examples from the dated live checkpoint. `hearsay.run` is the owner's
planned domain; the working site remains on Vercel until it is connected.
The optional YouTube/X demo field can remain blank. No direct video or post URL
has been supplied. The optional contract link is ready to paste.

Live app acceptance:

- [x] Receive explicit authorization to initiate the exact prepared paid
  `open_space` request, with Bradbury, contract, name and 500000 wei pool pinned.
- [x] Restore the authorized funded `0x771…0aDa` wallet on Bradbury 4221.
- [x] Restore browser automation after the extension update requirement.
- [x] Initiate the authorized space request after a safe signer hold; its
  public wallet transaction is mined and its canonical creation is Accepted.
- [x] Connect the wallet and verify Bradbury chain ID 4221 and the exact current
  contract in the real browser. Offline tests cover wallet rejection and
  wrong-network state.
- [x] Create and load the reviewer's own nonzero memory space (space 1, Accepted
  and provisional; finalization still pending). Disclose the
  optional 500000 wei initial pool, 1000 wei write bond, 2000 wei challenge
  bond and additional network fees; keep benchmark space 0 read-only here.
- [ ] Submit a real `write_entry` transaction with the 1000 wei bond from the
  frontend, using a fresh supported claim that passes envelope and duplicate
  checks.
- [x] Display canonical protocol status and the matching application entry for
  the existing finalized BP transaction. Offline tests cover wallet/broadcast
  states, pending, appeal, timeout, failed execution and RPC errors. A
  successful EVM receipt alone is not an application verdict.
- [x] Display BP's verdict, recorded votes and source hash; recover exact pinned
  bytes and download a replayable receipt. Verify the actual browser download
  through `cli/gate.py verify` with exit 0.
- [x] Verify reload/resume and error paths offline without duplicate sends.
- [ ] Demonstrate the newly submitted wallet transaction through the same
  canonical receipt and application-verdict lifecycle, retaining unresolved
  protocol outcomes honestly.
- [x] Publish the app and verify production public reads, canonical BP entry
  matching, snapshot recovery and the downloaded receipt's Python replay.

The project's own live evaluation target remains separate from the Portal's
supplied form requirements:

- [ ] Reach at least **20 genuinely judged honest controls** on this same
  contract and source version, retaining every infrastructure outcome and
  original attempt. At the cited public checkpoint, at least 13 more judged
  controls remain.
- [ ] Complete the **original ten negative cases** in
  [`corpus/live.json`](../corpus/live.json): nine independent cases submitted
  for genuine judgement, plus the citation-laundering case with `supports:
  [999999]`, refused by construction with zero consensus rounds. Retain that
  prevention separately from judged outcomes. No extra case is required by
  this target. The live negative phase has not started.
- [ ] Reconcile current application state, canonical receipts, source bytes,
  recorded votes and solvency; account for all campaign candidates. Run the
  full live publisher only when its cohort and coverage checks pass, then
  verify the resulting live page and update the public evidence and field copy.

Final Portal action:

- [ ] Review the completed form against the published app and evidence, then
  submit it through Builder → Projects. This consumes the remaining weekly
  Project spot. This package has not created or submitted a Portal project.

## Frontend space creation: 9 October

The [wallet EVM transaction](https://explorer-bradbury.genlayer.com/tx/0x985528494b4e78767ee3bf74f38bafd18bb40d3455c679fd9987673c03bff620)
and [GenLayer protocol receipt](https://explorer-bradbury.genlayer.com/tx/0x91b4a237aff71bdd4b90ac3b097cd232479926f0accea4daf0879064f2f02653)
are distinct public identifiers. The app loaded matching space 1 with the
authorized owner, policy and 500000 wei pool. Canonical Accepted / Majority
agree / Finished with return establishes provisional creation, not finality
or a claim judgement. The user has separately authorized the prepared TESCO
claim after creation finalizes. The sole campaign signer reconciled this
UI transaction separately and resumed the original space 0 cohort.

The [frontend finalization audit](frontend-finalization-blocker.md) explains
why the prepared next claim still waits after the creation's acceptance
window. Public owned-head recovery simulations reverted with
`InsufficientActiveValidators(34,33)`; no paid recovery was attempted.
The user-approved [issue addendum](https://github.com/genlayerlabs/genlayer-cli/issues/426#issuecomment-6075779424)
is published. This is an external protocol-state dependency, not a completed
claim or a submission-ready result.

## Tenth verified control: SPIRAX

SPIRAX GROUP PLC, company 00596337, produced matching ADMITTED entry 9 with
`yes / yes / none` votes. Its protocol ID is
`0x6851760318ede68c82621b9773a27aff73bd2ac679f3e56fee99bd2497a4acb7`.
The exact stored source hashes to
`3ae1851174adc4a2b6b6afe6c35abd205f16910ca845376f2b1f9a849c4e46e3`.
The full fresh 39-attempt scan has ten verified records, twenty-nine missing
application records and zero scan errors. All ten source/vote replays pass.
Local proof is `runs/bradbury-prompt/oct9-resume-audit/fresh-39-verified-records.jsonl`.
