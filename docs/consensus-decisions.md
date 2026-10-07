# Consensus decision comparison

On 2026-10-07, the user authorized applying the consensus-cost draft and
testing it in a separate Bradbury experiment. This changes how validators
compare decisions. It does not establish a fix for historical timeouts or
`ValidatorSelectionFailed`, or provide a liveness guarantee.

Only `_ask_bool` and `_check_contradiction` change. Each node still executes
the original judging prompt independently, then parses its answer inside the
nondeterministic function. `gl.eq_principle.strict_eq` compares the derived
boolean or conflict ID instead of asking an additional comparison model.
`_ask_bool` also serves challenge rounds; its existing private `principle`
argument remains in the signature but is unused.

The comparative source fetch, both support framings, `decide`, minimum-round
policy, five initial validators, bounds, storage, money, cascade, and public
ABI retain their existing behavior under this scoped change.

The local mapping from a fixed answer to a decision is preserved, including
the existing `int(...)` coercion for conflict IDs. The complete consensus
relation changes:

- Differing malformed answers and catchable model errors can agree on `None`.
  `None` remains unreadable and cannot produce admission. Whether the network
  can record that outcome can differ from the original error comparison.
- `conflicts: false` becomes `-1` regardless of an unused, missing, or malformed
  `entry_id`. The original comparison prompt also asked that `entry_id` match.
  For example, no-conflict answers carrying `-1` and `99` now agree.
- Matching normalized decisions agree directly; differing decisions disagree
  without another LLM judgment. Model disagreement, uncatchable VM errors,
  appeals, and validator-selection failures remain possible.

Logical LLM calls inferred from the successful source path are:

| Path | Leader, before → after | Validator, before → after |
| --- | --- | --- |
| Both support rounds | 2 → 2 | 5 → 3 |
| Support and consistency | 3 → 3 | 7 → 4 |

Validator counts include the retained source-fetch comparison. Provider retries,
committee retries, appeals, sandbox overhead, and later cascade work are excluded.
These counts establish neither measured latency savings nor the cause of past
timeouts.

Both isolated baseline and candidate runs passed the original **95 checks**.
Each dry run judged **18 entries**, refused **one** before consensus, rejected
**zero of nine honest entries**, and replayed **18/18** recorded verdicts.
The generated corpus and all 19 envelopes were byte-identical. Differential
parsing matched type and value on 32 boolean and 453 contradiction fixtures;
an AST audit found no changes outside the two methods. These are scripted
plumbing checks, not live defence measurements. Local evidence is retained in
`runs/consensus-cost/verification.json` and `proof-notes.txt`.

Readable source SHA-256 is
`ec1866990a75b05b5a1f9e4d406dfd342cd13779c21f559d233f5676bab08d87`;
the experiment's packed source is
`af67bf5014bab3909d11ea668fa67606a8e161aae069e728720e94db9ded2e41`.
The prior readable baseline was
`bd3140aab5f2c83e8067c6684f64b543cdedbdc90ec789e0997e1c1c7e9f7acb`.

The packed file passed `genvm-linter` 0.11.0 with three lint checks and
16 public methods: eight views and eight writes. Direct import of its wrapper
succeeded; its decoded executable AST matches the readable source with
documentation removed, its embedded source hash matches, and its public schema
equals the baseline schema. Leading runner JSON preserves the exact
`py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6`
dependency, resolving cached release `v0.2.11` and
`py-lib-genlayer-std:11rhn002yfajawsz7fai6mykznbxkxs6l91iskj5cm82c92qhy3v`
without upgrade notes.

With `genvm-linter==0.11.0` installed, run from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 genvm-lint check runs/deploy/hearsay.py --json
```

The linter uses mocked WASI for import and schema reflection. These checks do
not execute the full GenVM leader/validator protocol or prove that the new
decisions converge on Bradbury. The separate live experiment is identified in
`deployments/bradbury-decisions.json`; its evidence remains separate from these
local compatibility checks and earlier deployments.
