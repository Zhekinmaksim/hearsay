import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync, realpathSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { accountWithProgressGuard, readQueueProgress, VERIFIED_BINDINGS } from "../scripts/queue_progress.mjs";
import { localGate, envelopeHash } from "../web/lib.mjs";

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

function queueFixture(change = {}, targetTx = unresolvedTx) {
  const state = {
    version: "2.0.0", manager: bindings.manager, queues: bindings.queues,
    head: 13n, tail: 13n, headTx: zeroHash, acceptedHead,
    queueType: 2, atPendingHead: false,
    transaction: { id: targetTx, recipient, sender: expectedAccount,
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
  state.transaction = { id: targetTx, recipient, sender: expectedAccount,
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
        assert.deepEqual(request.args, [targetTx]);
      } else {
        assert.equal(address, bindings.queues);
        assert.equal(request.args[0], recipient);
        if (["getTxQueueType", "isAtPendingQueueHead"].includes(name)) assert.equal(request.args[1], targetTx);
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

// These checks execute the exact saved bridge callback. No keychain bridge,
// network RPC, model, final-client method override, or persistent key is used.
const bridgeSource = readFileSync(new URL("../scripts/genlayer_write.mjs", import.meta.url), "utf8");
const marker = "accountWithProgressGuard(signingAccount, async () => {";
const guardStart = bridgeSource.indexOf(marker), guardEnd = bridgeSource.indexOf("}) : signingAccount;", guardStart);
assert(guardStart >= 0 && guardEnd > guardStart, "the bridge must retain its account signing callback");
const guardBody = bridgeSource.slice(guardStart + marker.length, guardEnd);
const guardCallback = new Function("request", "client", "createPublicClient", "chains", "http", "readQueueProgress", "fail", "localGate", "envelopeHash",
  `return (async () => { let progressProof; ${guardBody}; return progressProof; })();`);

function makeRequest(setup) {
  let envelope = { version: "hearsay/1", space_id: 0, entry_class: setup.klass || "honest",
    claim: "Fixture registry company is active.", source_url: "https://example.org/fixture", ...setup.envelope };
  if (setup.deleteField) delete envelope[setup.deleteField];
  let fingerprint;
  try { fingerprint = envelopeHash(envelope); } catch { fingerprint = "00".repeat(32); }
  const request = { address: recipient, expected_account: expectedAccount,
    args: [setup.argumentSpace ?? 0, setup.argumentClass ?? envelope.entry_class,
      setup.rawEnvelope === undefined ? JSON.stringify(envelope) : setup.rawEnvelope],
    envelope_hash: setup.hashMismatch ? "ff".repeat(32) : fingerprint,
    progress_guard: { scan_complete: true, solvency_balanced: true, transactions: [unresolvedTx], ...setup.proof } };
  if (setup.missingProof) delete request.progress_guard;
  return request;
}

async function sdkScenario(setup = {}) {
  const request = makeRequest(setup);
  const chain = { ...chains.testnetBradbury, rpcUrls: { default: { http: ["http://hearsay.invalid/rpc"] } } };
  const signingAccount = sdk.createAccount(); // Dummy ephemeral key remains in RAM.
  request.expected_account = signingAccount.address;
  const protocolId = "0x" + "34".repeat(32);
  const events = [];
  const fixture = queueFixture({ ...setup.queue, transaction: { sender: signingAccount.address, ...setup.queue?.transaction } });
  let signCount = 0, rawCount = 0, guardCount = 0, solvencyReads = 0;
  let rawHash, client;
  const originalAccount = { ...signingAccount, signTransaction: async parameters => {
    events.push("sign"); signCount++;
    assert.equal(events.at(-2), "guard passed", "the asynchronous guard must finish before signing");
    return signingAccount.signTransaction(parameters);
  } };
  const account = accountWithProgressGuard(originalAccount, async () => {
    guardCount++; events.push("guard started");
    const proof = await guardCallback(request, client, options => {
      assert.equal(options.chain, chains.testnetBradbury);
      return fixture.client;
    }, chains, () => ({}), readQueueProgress, message => { throw new Error(message); }, localGate, envelopeHash);
    assert.equal(proof.provisional, true);
    assert.equal(proof.finalization_guaranteed, false);
    assert.equal(proof.solvency.balanced, true);
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
  const originalFetch = globalThis.fetch, originalError = console.error;
  globalThis.fetch = mockFetch; // Install fake transport before createClient captures anything.
  console.error = () => {}; // Suppress expected SDK dummy-account request errors.
  let result, error;
  try {
    client = sdk.createClient({ chain, account }); // The account wrapper already exists.
    result = await client.writeContract({ account, address: recipient, functionName: "write_entry",
      args: [BigInt(request.args[0]), request.args[1], request.args[2]], value: 1000n, consensusMaxRotations: 3 });
  } catch (caught) { error = caught; }
  finally { globalThis.fetch = originalFetch; console.error = originalError; }
  return { result, error, protocolId, events, signCount, rawCount, guardCount, solvencyReads, fixture };
}

let passes = 0;
const cases = JSON.parse(readFileSync(new URL("../corpus/live.json", import.meta.url), "utf8")).entries;
const independent = cases.filter(candidate => candidate.class !== "honest" && !candidate.supports?.length);
assert.equal(independent.length, 9);
for (const candidate of [{ id: "honest", class: "honest" }, ...independent]) {
  const success = await sdkScenario({ klass: candidate.class, envelope: candidate.claim ? {
    claim: candidate.claim, source_url: candidate.source_url, ...(candidate.author_note ? { author_note: candidate.author_note } : {}) } : {} });
  assert.ifError(success.error);
  assert.equal(success.result, success.protocolId);
  assert.equal(success.signCount, 1);
  assert.equal(success.rawCount, 1);
  assert.equal(success.guardCount, 1);
  assert.equal(success.solvencyReads, 1);
  assert.equal(success.fixture.blockReads, 1);
  assert.deepEqual(success.events, ["guard started", "fresh solvency", "guard passed", "sign", "send"]);
  passes++;
}

const rejected = [
  ["malformed JSON", { rawEnvelope: "{" }],
  ["null envelope", { rawEnvelope: "null" }],
  ["array envelope", { rawEnvelope: "[]" }],
  ["scalar envelope", { rawEnvelope: "7" }],
  ["missing claim", { deleteField: "claim" }],
  ["empty claim", { envelope: { claim: "" } }],
  ["non-string claim", { envelope: { claim: 1 } }],
  ["oversized UTF-8 claim", { envelope: { claim: "😀".repeat(513) } }],
  ["missing source", { deleteField: "source_url" }],
  ["non-HTTP source", { envelope: { source_url: "file:///fixture" } }],
  ["unknown class", { klass: "unknown" }],
  ["invalid version", { envelope: { version: "hearsay/2" } }],
  ["class argument mismatch", { argumentClass: "source_forgery" }],
  ["envelope space mismatch", { envelope: { space_id: 1 } }],
  ["nonzero argument space", { argumentSpace: 1 }],
  ["metadata hash mismatch", { hashMismatch: true }],
  ["null supports", { envelope: { supports: null } }],
  ["object supports", { envelope: { supports: {} } }],
  ["dependent support", { envelope: { supports: [0] } }],
  ["impossible citation is construction only", { klass: "citation_laundering", envelope: { supports: [999999] } }],
  ["missing progress proof", { missingProof: true }],
  ["incomplete absence proof", { proof: { scan_complete: false } }],
  ["untyped absence proof", { proof: { scan_complete: "true" } }],
  ["missing solvency proof", { proof: { solvency_balanced: false } }],
  ["fresh insolvency", { balanced: false }],
  ["untyped fresh solvency", { balanced: "true" }],
  ["queue rewind", { queue: { head: 12n } }],
  ["new pending write", { queue: { tail: 14n } }],
  ["changed protocol", { queue: { version: "0.6.0" } }],
  ["foreign unresolved sender", { queue: { transaction: { sender: "0x" + "11".repeat(20) } } }],
];
for (const [name, setup] of rejected) {
  const stopped = await sdkScenario(setup);
  assert(stopped.error, name + " must fail");
  assert(stopped.guardCount >= 1, name + " must reach the exact bridge guard");
  assert.equal(stopped.signCount, 0, name + " must stop before any signature");
  assert.equal(stopped.rawCount, 0, name + " must stop before any send");
  assert(!stopped.events.includes("guard passed"));
  if (!Object.hasOwn(setup, "balanced") && !setup.queue) {
    assert.equal(stopped.solvencyReads, 0, name + " must stop before the fresh chain read");
    assert.equal(stopped.fixture.blockReads, 0);
  }
  passes++;
}
console.log(passes + " submission signing checks passed (actual SDK 1.1.8, exact bridge guard, dummy accounts, fake RPC only)");
