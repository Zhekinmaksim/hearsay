import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { inspect } from "node:util";
import { assertBroadcastReconciled, broadcastWithJournal, createBroadcastFetch } from "../scripts/broadcast.mjs";

const folder = mkdtempSync(join(tmpdir(), "hearsay-broadcast-"));
const expectedHash = "0x" + "ab".repeat(32);
const parameters = { serializedTransaction: "signed bytes must never enter the journal" };
const records = path => readFileSync(path, "utf8").trim().split("\n").map(JSON.parse);
let passes = 0;
try {
  const path = join(folder, "success.jsonl");
  const result = await broadcastWithJournal(parameters, async () => {
    assert.equal(records(path)[0].state, "broadcast_attempt");
    assert.equal(records(path)[0].evm_tx, expectedHash);
    return expectedHash;
  }, { path, expectedHash, method: "write_entry", id: "one" });
  assert.equal(result, expectedHash);
  assert.deepEqual(records(path).map(row => row.state), ["broadcast_attempt", "broadcast_acknowledged"]);
  passes++;
  assert(!readFileSync(path, "utf8").includes(parameters.serializedTransaction));
  passes++;

  const lost = join(folder, "lost.jsonl");
  await assert.rejects(broadcastWithJournal(parameters, async () => { throw new Error(parameters.serializedTransaction); }, { path: lost, expectedHash }), /not acknowledged/);
  assert.deepEqual(records(lost).map(row => row.state), ["broadcast_attempt", "broadcast_unacknowledged"]);
  assert.equal(records(lost)[0].evm_tx, expectedHash);
  passes++;

  let sent = false;
  await assert.rejects(broadcastWithJournal(parameters, async () => { sent = true; return expectedHash; }, { path: join(folder, "missing", "journal"), expectedHash }));
  assert.equal(sent, false);
  passes++;

  const mismatch = join(folder, "mismatch.jsonl");
  await assert.rejects(broadcastWithJournal(parameters, async () => "0x" + "cd".repeat(32), { path: mismatch, expectedHash }), /unexpected EVM/);
  assert.equal(records(mismatch).length, 2);
  passes++;

  const bounded = join(folder, "bounded.jsonl");
  let boundedAttempts = 0;
  await assert.rejects(broadcastWithJournal(parameters, async () => {
    boundedAttempts++;
    throw { code: -32005, message: "transaction gas rate limit exceeded: node is at capacity", data: { retryAfterMs: 110 } };
  }, { path: bounded, expectedHash }, { maxAttempts: 2, wait: async () => {} }), /capacity retries exhausted/);
  assert.equal(boundedAttempts, 2);
  assert.equal(records(bounded).at(-1).state, "capacity_exhausted");
  passes++;

  // Exercise the actual SDK path, including its captured client copies,
  // signing, raw transport request, receipt wait, and protocol-ID extraction.
  // Prefer the CI npm dependency; local runs use the CLI's bundled SDK.
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

  async function sdkScenario(name, setup = {}) {
    const chain = { ...chains.testnetBradbury, rpcUrls: { default: { http: ["http://hearsay.invalid/rpc"] } } };
    const path = setup.badJournal ? join(folder, "absent", name) : join(folder, name + ".jsonl");
    const signingAccount = sdk.createAccount(); // Ephemeral key stays in RAM.
    let signCount = 0, rawCount = 0, estimateCount = 0;
    const account = { ...signingAccount, signTransaction: async request => {
      signCount++;
      return signingAccount.signTransaction(request);
    } };
    const address = "0x" + "12".repeat(20);
    const protocolId = "0x" + "34".repeat(32);
    const blockHash = "0x" + "56".repeat(32);
    const delays = [], rawBodies = [], rawBytes = [], errorLogs = [];
    let rawHash;
    const reply = (body, value) => Response.json({ jsonrpc: "2.0", id: body.id, ...value });
    const mockFetch = async (url, init) => {
      assert.equal(url, chain.rpcUrls.default.http[0]);
      const body = JSON.parse(init.body);
      switch (body.method) {
        case "eth_getTransactionCount": return reply(body, { result: "0x270" }); // 624
        case "eth_estimateGas":
          estimateCount++;
          return reply(body, setup.estimateError ? { error: { code: -32000, message: "estimate rejected" } } : { result: "0x186a0" });
        case "eth_gasPrice": return reply(body, { result: "0x1" });
        case "eth_sendRawTransaction": {
          rawCount++;
          const signed = body.params[0];
          rawBodies.push(init.body); rawBytes.push(signed);
          rawHash = viem.keccak256(signed);
          assert.equal(records(path).at(-1).state, "broadcast_attempt");
          assert.equal(records(path).at(-1).evm_tx, rawHash);
          assert(!readFileSync(path, "utf8").includes(signed));
          const transaction = viem.parseTransaction(signed);
          assert.equal(transaction.gas, 125000n);
          assert.equal(transaction.nonce, 624);
          assert.equal(transaction.chainId, 4221);
          const submission = viem.decodeFunctionData({ abi: chain.consensusMainContract.abi, data: transaction.data });
          assert.equal(submission.functionName, "addTransaction");
          assert.equal(submission.args[2], 5n);
          assert.equal(submission.args[3], 3n);
          if (setup.ambiguous) throw new Error("lost response with secret signed bytes " + signed);
          if (rawCount <= (setup.capacityRejections || 0)) return reply(body, { error: { code: -32005, message: "transaction gas rate limit exceeded: node is at capacity", data: { retryAfterMs: 110 } } });
          return reply(body, { result: rawHash });
        }
        case "eth_blockNumber": return reply(body, { result: "0x100" });
        case "eth_getTransactionReceipt": return reply(body, { result: {
          transactionHash: rawHash, transactionIndex: "0x0", blockHash, blockNumber: "0x100",
          from: account.address, to: chain.consensusMainContract.address, contractAddress: null,
          cumulativeGasUsed: "0x186a0", gasUsed: "0x186a0", effectiveGasPrice: "0x1", status: "0x1", type: "0x0",
          logsBloom: "0x" + "00".repeat(256), logs: [{
            address: chain.consensusMainContract.address, blockHash, blockNumber: "0x100", transactionHash: rawHash,
            transactionIndex: "0x0", logIndex: "0x0", removed: false, data: "0x",
            topics: viem.encodeEventTopics({ abi: chain.consensusMainContract.abi, eventName: "NewTransaction", args: { txId: protocolId, recipient: address, activator: account.address } }),
          }],
        } });
        default: throw new Error("Unexpected mock RPC method " + body.method);
      }
    };
    const originalFetch = globalThis.fetch, originalError = console.error;
    const client = sdk.createClient({ chain, account });
    globalThis.fetch = createBroadcastFetch(mockFetch, {
      rpcUrl: chain.rpcUrls.default.http[0], hashTransaction: viem.keccak256, parseTransaction: viem.parseTransaction,
      journal: { path, method: "write_entry", id: name }, expectedNonce: setup.wrongNonce ? 625 : 624,
      retry: { wait: async ms => delays.push(ms) },
    });
    console.error = (...items) => errorLogs.push(items.map(item => item?.message || String(item)).join(" "));
    let result, error;
    try {
      // Reproduce the former ineffective final-client hooks. They must stay
      // unused while the transport intercepts the SDK's actual lexical calls.
      client.sendRawTransaction = async () => { throw new Error("final-client send hook invoked"); };
      client.estimateTransactionGas = async () => { throw new Error("final-client estimate hook invoked"); };
      result = await client.writeContract({ account, address, functionName: "write_entry", args: [0n, "honest", "{}"], value: 1000n, consensusMaxRotations: 3 });
      if (setup.doubleSend) await client.writeContract({ account, address, functionName: "write_entry", args: [0n, "honest", "{}"], value: 1000n, consensusMaxRotations: 3 });
    } catch (caught) { error = caught; }
    finally { globalThis.fetch = originalFetch; console.error = originalError; }
    for (const signed of rawBytes) {
      assert(!String(error).includes(signed));
      assert(!inspect(error, { depth: null }).includes(signed));
      assert(!errorLogs.join("\n").includes(signed));
      assert(!readFileSync(path, "utf8").includes(signed));
    }
    return { result, error, protocolId, path, signCount, rawCount, estimateCount, delays, rawBodies, rawBytes };
  }

  const integrated = await sdkScenario("sdk-capacity", { capacityRejections: 2 });
  assert.ifError(integrated.error);
  assert.equal(integrated.result, integrated.protocolId);
  assert.equal(integrated.signCount, 1);
  assert.equal(integrated.estimateCount, 1);
  assert.equal(integrated.rawCount, 3);
  assert.equal(new Set(integrated.rawBytes).size, 1);
  assert.equal(new Set(integrated.rawBodies).size, 1);
  assert.deepEqual(integrated.delays, [110, 200]);
  assert.equal(records(integrated.path).at(-1).state, "broadcast_acknowledged");
  passes++;

  const gasFailure = await sdkScenario("sdk-estimate-failure", { estimateError: true });
  assert.match(String(gasFailure.error), /fallback broadcast blocked/);
  assert.equal(gasFailure.rawCount, 0);
  assert(!existsSync(gasFailure.path));
  passes++;

  const nonceFailure = await sdkScenario("sdk-nonce-failure", { wrongNonce: true });
  assert.match(String(nonceFailure.error), /expected_nonce/);
  assert.equal(nonceFailure.rawCount, 0);
  assert(!existsSync(nonceFailure.path));
  passes++;

  const journalFailure = await sdkScenario("sdk-journal-failure", { badJournal: true });
  assert(journalFailure.error);
  assert.equal(journalFailure.rawCount, 0);
  passes++;

  const ambiguous = await sdkScenario("sdk-ambiguous", { ambiguous: true });
  assert.match(String(ambiguous.error), /not acknowledged/);
  assert.equal(ambiguous.rawCount, 1);
  assert.equal(ambiguous.signCount, 1);
  assert.deepEqual(ambiguous.delays, []);
  assert.equal(records(ambiguous.path).at(-1).state, "broadcast_unacknowledged");
  passes++;

  const duplicate = await sdkScenario("sdk-second-broadcast", { doubleSend: true });
  assert.match(String(duplicate.error), /Another SDK broadcast blocked/);
  assert.equal(duplicate.rawCount, 1);
  passes++;

  const resumeManifest = join(folder, "resume.jsonl");
  const resumeRequest = join(folder, "resume-request.json");
  const resumeMeta = { method: "write_entry", id: "resume" };
  writeFileSync(resumeManifest + ".broadcasts.jsonl", JSON.stringify({ ...resumeMeta, state: "broadcast_acknowledged", evm_tx: expectedHash }) + "\n");
  writeFileSync(resumeRequest, JSON.stringify({ ...resumeMeta, address: "0x" + "12".repeat(20), expected_account: "0x" + "34".repeat(20), args: [], value: "1000", envelope_hash: "56".repeat(32) }));
  const stopped = spawnSync(process.execPath, [resolve("scripts/genlayer_write.mjs"), "--request", resumeRequest, "--manifest", resumeManifest], { encoding: "utf8" });
  assert.equal(stopped.status, 1);
  assert.match(stopped.stderr, /reconciliation before another SDK send/);
  writeFileSync(resumeManifest, JSON.stringify({ ...resumeMeta, tx: "0x" + "78".repeat(32) }) + "\n");
  assert.doesNotThrow(() => assertBroadcastReconciled(resumeManifest, resumeMeta));
  passes++;
  console.log(passes + " broadcast recovery checks passed");
} finally { rmSync(folder, { recursive: true }); }
