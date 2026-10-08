import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { readFileSync, realpathSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { accountWithProgressGuard, readQueueProgress, VERIFIED_BINDINGS } from "../scripts/queue_progress.mjs";

// Independent literals from the deployed VERSION 2.0.0 queue audit at block
// 23792080, rather than copies read from the guard's expected-value table.
const bindings = {
  main: "0x0112bf6e83497965a5fdd6dad1e447a6e004271d", mainImplementation: "0x0a2c393975da79505ed930efc55ae4aeb88b0d62",
  data: "0x85d7bf947a512fc640c75327a780c90847267697", dataImplementation: "0x7ee629530e70e2a3a772f8522d8835060abf0755",
  manager: "0x8ace036c8c3c5d603db546b031302fcf149648e8", queues: "0x56a05a9bb7b261ad720020a08b9fd5a13177b949",
  queueImplementation: "0x7559ebdbc6f59e5dd2a048a1a1539ac14bf93db0",
};
assert.deepEqual(VERIFIED_BINDINGS, bindings);
const implementationSlot = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc";
const zeroHash = "0x" + "00".repeat(32);
const recipient = "0x2a5c1aA4Ae9e2292B737FE574aF44A2d8a5bB3F7";
const expectedAccount = "0x771388495F34d21C5574FeFc04cd1D5811E00aDa";
const unresolvedTx = "0x8930d0ab292f6b3cf9ebbb3a6e4ba3b5f0a754838b18ae5fbcdcf752a9529922";
const acceptedHead = "0xb449ab7e5af96fa47dd3cd7eb5133c84f712ade7500a6a114917267767ff5692";
const block = { number: 23792080n, timestamp: 1791441300n, hash: "0x" + "56".repeat(32) };

// Match test/broadcast.mjs: use the CI dependency or the installed CLI's SDK,
// and fail if the supposedly pinned actual signing path changes versions.
let sdkEntry;
try { sdkEntry = createRequire(import.meta.url).resolve("genlayer-js"); }
catch {
  const cliEntry = realpathSync(execFileSync("which", ["genlayer"], { encoding: "utf8" }).trim());
  sdkEntry = join(resolve(dirname(cliEntry), ".."), "node_modules/genlayer-js/dist/index.js");
}
const sdkRoot = resolve(dirname(sdkEntry), "..");
assert.equal(JSON.parse(readFileSync(join(sdkRoot, "package.json"), "utf8")).version, "1.1.8");
const sdk = await import(pathToFileURL(sdkEntry));
const chains = await import(pathToFileURL(join(sdkRoot, "dist/chains/index.js")));
const viemEntry = createRequire(pathToFileURL(join(sdkRoot, "package.json"))).resolve("viem");
const viem = await import(pathToFileURL(viemEntry));

function queueFixture(change = {}) {
  const state = {
    version: "2.0.0", manager: bindings.manager, queues: bindings.queues,
    head: 13n, tail: 13n, headTx: zeroHash, acceptedHead,
    queueType: 2, atPendingHead: false,
    transaction: { id: unresolvedTx, recipient, sender: expectedAccount,
      status: 9, numOfInitialValidators: 5n, initialRotations: 3n, ...change.transaction },
    implementations: {
      [bindings.main]: bindings.mainImplementation,
      [bindings.data]: bindings.dataImplementation,
      [bindings.queues]: bindings.queueImplementation,
      ...change.implementations,
    },
    ...change,
  };
  // Preserve merged transaction/implementation fields when only a field is changed.
  state.transaction = { id: unresolvedTx, recipient, sender: expectedAccount,
    status: 9, numOfInitialValidators: 5n, initialRotations: 3n, ...change.transaction };
  state.implementations = { [bindings.main]: bindings.mainImplementation,
    [bindings.data]: bindings.dataImplementation, [bindings.queues]: bindings.queueImplementation,
    ...change.implementations };
  const chain = { ...chains.testnetBradbury,
    consensusMainContract: { ...chains.testnetBradbury.consensusMainContract,
      address: change.mainAddress || chains.testnetBradbury.consensusMainContract.address },
    consensusDataContract: { ...chains.testnetBradbury.consensusDataContract,
      address: change.dataAddress || chains.testnetBradbury.consensusDataContract.address } };
  const calls = [];
  let blockReads = 0;
  const client = {
    getBlock: async () => { blockReads++; return block; },
    readContract: async request => {
      calls.push({ kind: "view", ...request });
      assert.equal(request.blockNumber, block.number, "every view must share the freshly selected block");
      // The actual pinned SDK ABI must encode every view used by the guard.
      viem.encodeFunctionData({ abi: request.abi, functionName: request.functionName, args: request.args });
      const name = request.functionName;
      const address = request.address.toLowerCase();
      if (["VERSION", "addressManager"].includes(name)) assert.equal(address, bindings.main);
      else if (name === "getAddress") {
        assert.equal(address, bindings.manager);
        assert.deepEqual(request.args, ["Queues"]);
      } else if (name === "getTransactionAllData") {
        assert.equal(address, bindings.data);
        assert.deepEqual(request.args, [unresolvedTx]);
      } else {
        assert.equal(address, bindings.queues);
        assert.equal(request.args[0], recipient);
        if (["getTxQueueType", "isAtPendingQueueHead"].includes(name)) assert.equal(request.args[1], unresolvedTx);
      }
      if (state.failView === name) throw new Error("fixture view unavailable");
      const results = {
        VERSION: state.version, addressManager: state.manager, getAddress: state.queues,
        getPendingHead: state.head, getPendingTail: state.tail, getPendingHeadTxId: state.headTx,
        getAcceptedHeadTxId: state.acceptedHead, getTxQueueType: state.queueType,
        isAtPendingQueueHead: state.atPendingHead, getTransactionAllData: [state.transaction, []],
      };
      assert(Object.hasOwn(results, name), "unexpected queue guard view " + name);
      return results[name];
    },
    getStorageAt: async request => {
      calls.push({ kind: "storage", ...request });
      assert.equal(request.blockNumber, block.number, "implementation reads must share the view block");
      assert.equal(request.slot, implementationSlot);
      const implementation = state.implementations[request.address.toLowerCase()];
      assert(implementation, "unexpected proxy address");
      return "0x" + "00".repeat(12) + implementation.slice(2);
    },
  };
  return { client, chain, calls, get blockReads() { return blockReads; }, state };
}

let passes = 0;
// In-process imports once passed while the as-main CLI exited 13 because its
// dynamic queue helper import formed an unresolved top-level-await cycle.
// Exercise that exact startup path without loading SDK accounts or networking.
const probe = spawnSync(process.execPath, [fileURLToPath(new URL("../scripts/read_chain.mjs", import.meta.url)), "--probe-progress-import"], {
  encoding: "utf8", timeout: 5000,
});
assert.ifError(probe.error);
assert.equal(probe.signal, null, "the CLI import probe must finish within its bounded timeout");
assert.equal(probe.status, 0, "the as-main CLI must start successfully, not exit 13 on a top-level-await import cycle");
assert.equal(probe.stdout.trim(), "queue progress imports ready");
assert.equal(probe.stderr, "");
passes++;

const valid = queueFixture();
const proof = await readQueueProgress(valid.client, valid.chain, recipient, expectedAccount, [unresolvedTx]);
assert.equal(valid.blockReads, 1);
assert.equal(valid.calls.filter(call => call.kind === "storage").length, 3);
assert.deepEqual(proof.stored_block, { number: String(block.number), hash: block.hash, timestamp: String(block.timestamp) });
assert.equal(proof.pending_head, "13");
assert.equal(proof.pending_tail, "13");
assert.equal(proof.accepted_head_tx, acceptedHead);
assert.equal(proof.provisional, true);
assert.equal(proof.finalization_guaranteed, false);
assert.deepEqual(proof.transactions, [{ tx: unresolvedTx, status_code: 9, queue_type: 2, at_pending_head: false }]);
passes++;

const rejectedFixtures = [
  ["protocol version", { version: "0.6.0" }, /unverified consensus/],
  ["main binding", { mainAddress: "0x" + "11".repeat(20) }, /unknown consensus binding/],
  ["data binding", { dataAddress: "0x" + "11".repeat(20) }, /unknown consensus binding/],
  ["address manager", { manager: "0x" + "11".repeat(20) }, /unknown AddressManager/],
  ["queue binding", { queues: "0x" + "11".repeat(20) }, /unknown Queues/],
  ...[bindings.main, bindings.data, bindings.queues].map(address => ["proxy implementation " + address,
    { implementations: { [address]: "0x" + "11".repeat(20) } }, /unknown proxy implementation/]),
  ["new pending write", { tail: 14n }, /pending queue is not empty/],
  ["replayed pending head", { head: 12n }, /pending queue is not empty/],
  ["pending head hash", { headTx: unresolvedTx }, /pending queue is not empty/],
  ["changed transaction id", { transaction: { id: zeroHash } }, /transaction ID changed/],
  ["foreign recipient", { transaction: { recipient: "0x" + "11".repeat(20) } }, /foreign transaction/],
  ["foreign sender", { transaction: { sender: "0x" + "11".repeat(20) } }, /foreign transaction/],
  ...[5, 6, 7, 11, 99].map(status => ["settled or unknown status " + status, { transaction: { status } }, /settled or has an unknown state/]),
  ["validator count", { transaction: { numOfInitialValidators: 0n } }, /consensus settings changed/],
  ["rotation limit", { transaction: { initialRotations: 0n } }, /consensus settings changed/],
  ...[0, 1, 99].map(queueType => ["invalid queue type " + queueType, { queueType }, /still in the pending queue/]),
  ["pending transaction flag", { atPendingHead: true }, /still in the pending queue/],
  ["read failure", { failView: "getPendingHead" }, /view unavailable/],
];
for (const [name, change, pattern] of rejectedFixtures) {
  const fixture = queueFixture(change);
  await assert.rejects(readQueueProgress(fixture.client, fixture.chain, recipient, expectedAccount, [unresolvedTx]), pattern, name);
  passes++;
}
for (const transactions of [[], [unresolvedTx, unresolvedTx], ["not a transaction hash"]]) {
  const fixture = queueFixture();
  await assert.rejects(readQueueProgress(fixture.client, fixture.chain, recipient, expectedAccount, transactions), /invalid unresolved transaction list/);
  assert.equal(fixture.blockReads, 0, "malformed guard targets stop before RPC reads");
  passes++;
}

async function sdkScenario(setup = {}) {
  const chain = { ...chains.testnetBradbury, rpcUrls: { default: { http: ["http://hearsay.invalid/rpc"] } } };
  const signingAccount = sdk.createAccount(); // Dummy ephemeral key remains in RAM.
  const protocolId = "0x" + "34".repeat(32);
  const events = [];
  const fixture = queueFixture({ ...setup.queue, transaction: { sender: signingAccount.address, ...setup.queue?.transaction } });
  let signCount = 0, rawCount = 0, guardCount = 0, solvencyReads = 0, finalClientHookCalls = 0;
  let rawHash, client;
  const originalAccount = { ...signingAccount, signTransaction: async parameters => {
    events.push("sign"); signCount++;
    assert.equal(events.at(-2), "guard passed", "the asynchronous guard must finish before signing");
    return signingAccount.signTransaction(parameters);
  } };
  const account = accountWithProgressGuard(originalAccount, async () => {
    guardCount++; events.push("guard started");
    const solvency = await client.readContract({ address: recipient, functionName: "solvency", args: [] });
    if (solvency.balanced !== true) throw new Error("fresh solvency guard: balance is not verified");
    await readQueueProgress(fixture.client, fixture.chain, recipient, signingAccount.address, [unresolvedTx]);
    await Promise.resolve();
    events.push("guard passed");
  });
  const reply = (body, value) => Response.json({ jsonrpc: "2.0", id: body.id, ...value });
  const mockFetch = async (url, init) => {
    assert.equal(url, chain.rpcUrls.default.http[0], "all SDK traffic must terminate at the fake RPC");
    const body = JSON.parse(init.body);
    switch (body.method) {
      case "eth_getTransactionCount": return reply(body, { result: "0x270" });
      case "eth_estimateGas": return reply(body, { result: "0x186a0" });
      case "eth_gasPrice": return reply(body, { result: "0x1" });
      case "gen_call": {
        solvencyReads++; events.push("fresh solvency");
        assert.equal(body.params[0].type, "read");
        assert.equal(body.params[0].to, recipient);
        const data = viem.fromRlp(body.params[0].data, "hex")[0];
        const call = sdk.abi.calldata.decode(new Uint8Array(Buffer.from(data.slice(2), "hex")));
        assert.equal(call instanceof Map ? call.get("method") : call.method, "solvency");
        const result = sdk.abi.calldata.encode({ balanced: setup.balanced ?? true });
        return reply(body, { result: { status: { code: 0 }, data: Buffer.from(result).toString("hex") } });
      }
      case "eth_sendRawTransaction": {
        rawCount++; events.push("send");
        assert.equal(signCount, 1);
        assert.equal(events.at(-2), "sign");
        const signed = body.params[0];
        rawHash = viem.keccak256(signed);
        const transaction = viem.parseTransaction(signed);
        const submission = viem.decodeFunctionData({ abi: chain.consensusMainContract.abi, data: transaction.data });
        assert.equal(submission.functionName, "addTransaction");
        assert.equal(submission.args[1].toLowerCase(), recipient.toLowerCase());
        assert.equal(submission.args[2], 5n);
        assert.equal(submission.args[3], 3n);
        assert.equal(transaction.value, 1000n);
        return reply(body, { result: rawHash });
      }
      case "eth_blockNumber": return reply(body, { result: "0x100" });
      case "eth_getTransactionReceipt": return reply(body, { result: {
        transactionHash: rawHash, transactionIndex: "0x0", blockHash: block.hash, blockNumber: "0x100",
        from: account.address, to: chain.consensusMainContract.address, contractAddress: null,
        cumulativeGasUsed: "0x186a0", gasUsed: "0x186a0", effectiveGasPrice: "0x1", status: "0x1", type: "0x0",
        logsBloom: "0x" + "00".repeat(256), logs: [{
          address: chain.consensusMainContract.address, blockHash: block.hash, blockNumber: "0x100", transactionHash: rawHash,
          transactionIndex: "0x0", logIndex: "0x0", removed: false, data: "0x",
          topics: viem.encodeEventTopics({ abi: chain.consensusMainContract.abi, eventName: "NewTransaction",
            args: { txId: protocolId, recipient, activator: account.address } }),
        }],
      } });
      default: throw new Error("Unexpected fake RPC method " + body.method);
    }
  };
  client = sdk.createClient({ chain, account }); // Wrap before the SDK captures intermediate clients.
  client.sendRawTransaction = async () => { finalClientHookCalls++; throw new Error("final-client send hook used"); };
  client.estimateTransactionGas = async () => { finalClientHookCalls++; throw new Error("final-client estimate hook used"); };
  const originalFetch = globalThis.fetch, originalError = console.error;
  globalThis.fetch = mockFetch;
  console.error = () => {}; // Expected SDK rejections must not dump dummy signed request bodies.
  let result, error;
  try {
    result = await client.writeContract({ account, address: recipient, functionName: "write_entry",
      args: [0n, "honest", "{}"], value: 1000n, consensusMaxRotations: 3 });
  } catch (caught) { error = caught; }
  finally { globalThis.fetch = originalFetch; console.error = originalError; }
  return { result, error, protocolId, events, signCount, rawCount, guardCount, solvencyReads, finalClientHookCalls, fixture };
}

const success = await sdkScenario();
assert.ifError(success.error);
assert.equal(success.result, success.protocolId);
assert.equal(success.signCount, 1);
assert.equal(success.rawCount, 1);
assert.equal(success.guardCount, 1);
assert.equal(success.solvencyReads, 1);
assert.equal(success.finalClientHookCalls, 0, "the real SDK bypasses final-client hooks but retains the wrapped account");
assert.deepEqual(success.events, ["guard started", "fresh solvency", "guard passed", "sign", "send"]);
passes++;

for (const [name, setup, pattern] of [
  ["fresh insolvency", { balanced: false }, /fresh solvency guard/],
  ["untyped solvency", { balanced: "true" }, /fresh solvency guard/],
  ["pre-sign queue rewind", { queue: { head: 12n } }, /pending queue is not empty/],
  ["pre-sign protocol change", { queue: { version: "0.6.0" } }, /unverified consensus/],
  ["pre-sign foreign transaction", { queue: { transaction: { sender: "0x" + "11".repeat(20) } } }, /foreign transaction/],
]) {
  const stopped = await sdkScenario(setup);
  assert(stopped.error, name + " must fail");
  assert.match(String(stopped.error), pattern, name);
  assert(stopped.guardCount >= 1, name + " must reach the wrapped account guard");
  assert.equal(stopped.solvencyReads, stopped.guardCount, name + " must freshly read solvency before every attempted signature");
  assert.equal(stopped.signCount, 0, name + " must stop before account.signTransaction");
  assert.equal(stopped.rawCount, 0, name + " must stop before eth_sendRawTransaction");
  assert.equal(stopped.finalClientHookCalls, 0);
  if (Object.hasOwn(setup, "balanced")) assert.equal(stopped.fixture.calls.length, 0, "failed solvency must stop before queue reads");
  passes++;
}
console.log(passes + " queue progress checks passed (pinned SDK 1.1.8, dummy accounts and fake RPC only)");
