# Bradbury deployed protocol version

The campaign reads ConsensusMain `0x0112Bf6e83497965A5fdD6Dad1E447a6E004271D`
and ConsensusData `0x85D7bf947A512Fc640C75327A780c90847267697` on chain 4221.
These match the [official current chain preset](https://github.com/genlayerlabs/genlayer-js/blob/main/src/chains/testnetBradbury.ts)
and the installed SDK 1.1.8. No SDK upgrade or network deployment was made.

At block **23788085**, hash
`0x06cc9d1d9b9b15e1cc0e530c7fb8fdcd30f81d23e2f9bac46bfaf15a6bd58869`,
ConsensusMain `VERSION()` returned `2.0.0`. Its ERC1967 implementation slot
selected `0x0a2c393975da79505ed930efc55ae4aeb88b0d62`; ConsensusData selected
`0x7ee629530e70e2a3a772f8522d8835060abf0755`.
The chain explorer exposes verified source for
[ConsensusMain](https://explorer-api.testnet-chain.genlayer.com/api?module=contract&action=getsourcecode&address=0x0a2c393975da79505ed930efc55ae4aeb88b0d62)
and [ConsensusData](https://explorer-api.testnet-chain.genlayer.com/api?module=contract&action=getsourcecode&address=0x7ee629530e70e2a3a772f8522d8835060abf0755).
Both include `contracts/transactions/interfaces/ITransactions.sol` with this enum:

| Code | Stored status |
| --- | --- |
| 11 | ReadyToFinalize |
| 12 | ValidatorsTimeout |
| 13 | LeaderTimeout |
| 14 | LeaderRevealing |

The [SDK 1.1.8 source](https://github.com/genlayerlabs/genlayer-js/blob/v1.1.8/src/types/transactions.ts)
also maps codes 11–13 this way. Its released table omits 14; the verified
Solidity source and current SDK source include it. The deployed `ResultType`
is `Idle`, `MajorityAgree`, `MajorityDisagree`, `MajorityTimeout`,
`DeterministicViolation`, `NoMajority` (codes 0–5). Execution results are
`NotVoted`, `FinishedWithReturn`, `FinishedWithError`, `Timeout`,
`NondetDisagree` (codes 0–4).

For transaction
`0xc66d7127bc788cfe8bc5cead04502f28718816b48967753773ee25bd13fdf066`,
the pinned `getTransactionAllData` result stored status 13. Separately,
`gen_getTransactionStatus` returned `LeaderTimeout / 13`, and the raw
`gen_getTransactionReceipt` returned status 13. The node did not expose
`gen_getTransactionLifecycle`. This is evidence about the deployed version,
independent of the SDK's time-dependent `getTransactionData` projection.

The [Consensus v0.6 status documentation](https://docs.genlayer.com/understand-genlayer-protocol/core-concepts/transactions/transaction-statuses)
removes ReadyToFinalize and shifts the subsequent values. Applying that table
to this deployed 2.0.0 implementation incorrectly labels a stored leader
timeout as leader revealing. The earlier manual decoder made that error;
raw stored values and historical receipts remain preserved.

`scripts/read_chain.mjs` now reads `VERSION()` at the same block as each
stored receipt and refuses unverified versions. The regression fixture
`test/fixtures/bradbury-v2-node-receipt.json` preserves the actual node capture,
verified Solidity enum text, source provenance and pinned SDK mapping.
Tests derive expected names from that source text. ReadyToFinalize remains
nonterminal in the runner, and finalized results without execution cannot
count as application judgements.
