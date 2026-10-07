# Bradbury: APPEAL_REVEALING remains at 10/11 reveals past validUntil; recovery unclear

A public Bradbury transaction remains in stored `APPEAL_REVEALING` with 10 of 11 votes revealed after `validUntil`. It has no matching application entry, and I have not found a supported public recovery that settles it.

### Environment and current evidence

- RPC: https://rpc-bradbury.genlayer.com; chain ID 4221.
- CLI 0.39.1, bundled genlayer-js 1.1.8; Node 20.20.2.
- Consensus main: `0x0112Bf6e83497965A5fdD6Dad1E447a6E004271D`; observed implementation `0x0a2c393975da79505ed930efc55ae4aeb88b0d62`, VERSION 2.0.0.
- Contract: `0xb8BAd484689a32357Caa6E0F427D31B29347fdB4`.
- Transaction: [0xbfbeb7d712d834a94b8f00ccba3ae98f06466db39dee7ad9fcd3f8902e45b8c0](https://explorer-bradbury.genlayer.com/tx/0xbfbeb7d712d834a94b8f00ccba3ae98f06466db39dee7ad9fcd3f8902e45b8c0).
- Read-only confirmation on 7 October 2026 at block **23734515**, hash `0xc98d85ad906b2ccc4eb9b39e8d4bedd2239debad7d08e17e3f90a1c7b074623c`.
- Block timestamp **1791395584**, `validUntil` **1791394876**: 708 seconds past the transaction's validity timestamp.
- Stored status **9**, `APPEAL_REVEALING`; last stored round array index 3; 11 commits, 10 reveals; votes `[1,0,3,3,1,1,1,1,1,1,3]`.
- Five initial validators, initial rotations 0. Zero leader replacements did not prevent automatic appeal expansion.
- `entry_count()` is 1: the preceding Barclays entry is ADMITTED; the HSBC transaction above has not produced its entry.

These observations come from `getTransactionAllData` pinned to the block above. They are independent of any frontend status display. Expiry is reported as evidence; I am asking what terminal/recovery behavior the protocol intends after it.

### Reproduce by reading the existing transaction

Save as `repro.mjs` in a Node project with `genlayer-js@1.1.8` and `viem`, then run `node repro.mjs`. This requires no account or signing key.

```js
import { createClient } from "genlayer-js";
import { testnetBradbury } from "genlayer-js/chains";
import { createPublicClient, http } from "viem";

const rpc = "https://rpc-bradbury.genlayer.com";
const hash = "0xbfbeb7d712d834a94b8f00ccba3ae98f06466db39dee7ad9fcd3f8902e45b8c0";
const sdk = createClient({ chain: testnetBradbury, endpoint: rpc });
const evm = createPublicClient({
  chain: testnetBradbury, transport: http(rpc),
});
const block = await evm.getBlock();
const spec = testnetBradbury.consensusDataContract;
const [stored, rounds] = await evm.readContract({
  address: spec.address, abi: spec.abi,
  functionName: "getTransactionAllData",
  args: [hash], blockNumber: block.number,
});
const projected = await sdk.getTransaction({ hash });
console.log(JSON.stringify({
  block: block.number, timestamp: block.timestamp,
  storedStatus: stored.status,
  validUntil: stored.validUntil,
  initialRotations: stored.initialRotations,
  storedInitialValidators: stored.numOfInitialValidators,
  sdkInitialValidators: projected.numOfInitialValidators,
  lastRound: rounds.at(-1),
}, (_, value) => typeof value === "bigint" ? value.toString() : value, 2));
```

The live state can advance after this capture. The recorded status, block and timestamp above identify the observed failure.

### Recovery and contract execution evidence

A sender-authorized `processIdleness(tx)` call succeeded in EVM:
[`0x85a9257b3a11f1a749b0256d8f885d38e057768cedf41f592e443556eaa11dd6`](https://explorer-bradbury.genlayer.com/tx/0x85a9257b3a11f1a749b0256d8f885d38e057768cedf41f592e443556eaa11dd6).
Immediately afterward, stored status was still APPEAL_COMMITTING. It later reached APPEAL_REVEALING; I cannot attribute that later transition to this call. A later read-only `processIdleness` simulation in APPEAL_REVEALING reverted with a generic `execution reverted`, without a revert-data reason.

The leader's stored equivalence outputs contain the real registry page and typed support decisions `true/true`, plus no-conflict `-1`. The initial-round debug trace returned successfully. Trace metrics may be replayed/cached, so they do not establish original provider latency or which validator operation timed out.

A separate earlier deployment also remains at 10/11 appeal reveals:
`0xc877675db83e49a59543280648b7bd7ac3739762bf00d920ee24baaaac4366b0`.
On another earlier deployment, an expanded 23-validator committee remained COMMITTING and idleness simulation returned `ValidatorSelectionFailed`; those are separate observations, not proof of a shared root cause.

### Expected / requested behavior

Please identify the supported public operation that can settle or recover this transaction when a validator does not reveal. If remaining nonterminal after `validUntil` is intended, please document the applicable recovery/finality rules.

The stalled transaction blocks the project's sequential live campaign. I have not resubmitted it or counted absent application state as a contract refusal.

### Evidence and related reports

- [Reviewed source and deployment metadata](https://github.com/Zhekinmaksim/hearsay/blob/8f0a2d9c673e17e709efc472e71d1f3d19bc936e/deployments/bradbury-decisions.json).
- [Verified incomplete checkpoint](https://github.com/Zhekinmaksim/hearsay/blob/8f0a2d9c673e17e709efc472e71d1f3d19bc936e/web/bradbury-decisions-checkpoint.json).
- [Historical liveness report](https://github.com/Zhekinmaksim/hearsay/blob/8f0a2d9c673e17e709efc472e71d1f3d19bc936e/docs/bradbury-liveness-report.md).
- genlayerlabs/genlayer-studio#1721 concerns large-committee concurrency in Studio; applicability to this deployed Bradbury runtime is unverified.
- genlayerlabs/genlayer-studio#1769 concerns unanimous timeout handling; this capture has mixed votes.
- genlayerlabs/genlayer-studio#814 concerns recovery after a local simulator restart. This report reads stored public-chain state.

I filed this public-testnet symptom here alongside other Bradbury CLI reports; please transfer it if the network/consensus team tracks recovery elsewhere.

