# getTransaction reports initialRotations as numOfInitialValidators on Bradbury (0 instead of 5)

On Bradbury, `getTransaction()` reports the leader-rotation limit as the initial validator count. A transaction actually created with five validators and zero rotations is reported as having zero initial validators.

### Environment / observed result

CLI 0.39.1, bundled genlayer-js 1.1.8, Bradbury RPC https://rpc-bradbury.genlayer.com, chain ID 4221.

Transaction:
[`0xbfbeb7d712d834a94b8f00ccba3ae98f06466db39dee7ad9fcd3f8902e45b8c0`](https://explorer-bradbury.genlayer.com/tx/0xbfbeb7d712d834a94b8f00ccba3ae98f06466db39dee7ad9fcd3f8902e45b8c0).

At block **23734515** on 7 October 2026:

| Value | Observed |
| --- | --- |
| `getTransaction().numOfInitialValidators` | `"0"` |
| `getTransactionAllData()[0].numOfInitialValidators` | `5` |
| `getTransactionAllData()[0].initialRotations` | `0` |

The two parameters describe different things. Initial validators remain five while the appeal committee expands.

### Reproduction

Use `genlayer-js@1.1.8` and `viem` in a Node project; save this as `repro.mjs` and run `node repro.mjs`. It only reads an existing public transaction; no signing key is needed.

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

Expected: `sdkInitialValidators` equals `storedInitialValidators`, here `"5"`.
Observed: SDK `"0"`, stored `"5"`, rotations `"0"`.

### Source of the mismatch

The same fallback is present in current main at commit
[`1b7f50a3a3f2963ea857941b0fb386081dd5c326`](https://github.com/genlayerlabs/genlayer-js/commit/1b7f50a3a3f2963ea857941b0fb386081dd5c326).

[`src/transactions/decoders.ts:79–81`](https://github.com/genlayerlabs/genlayer-js/blob/1b7f50a3a3f2963ea857941b0fb386081dd5c326/src/transactions/decoders.ts#L79-L81):

```ts
const numOfInitialValidators =
  tx.numOfInitialValidators ?? (tx as any).initialRotations;
```

[`getTransaction`](https://github.com/genlayerlabs/genlayer-js/blob/1b7f50a3a3f2963ea857941b0fb386081dd5c326/src/transactions/actions.ts#L156-L179)
already fetches `getTransactionAllData`, but merges only `txExecutionResult` into the projected transaction before decoding it. The authoritative initial-validator field in the stored transaction is available in that existing response.

### Suggested fix / regression checks

Normalize the actual initial-validator field from the stored transaction already fetched by `getTransaction`. Do not substitute `initialRotations`; for ABIs without the count, expose an explicit unknown/error consistent with the API's compatibility policy.

Regression fixtures should distinguish:
- stored initial count 5, projected count absent, rotations 0 → initial count 5;
- stored initial count 5, projected count absent, rotations 3 → initial count 5.

This affects committee-size diagnostics and monitoring. The [separate stalled-appeal report](https://github.com/genlayerlabs/genlayer-cli/issues/426) does not establish that this decoder bug causes the chain to stall.

Related receipt compatibility work: #144, #148 and #220. I did not find a public issue describing this exact count/rotation substitution.
