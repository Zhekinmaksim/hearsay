#!/usr/bin/env node
/* Machine-readable, read-only RPC receipt using the CLI's installed SDK. */
import { execFileSync } from "node:child_process";
import { realpathSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { createHash } from "node:crypto";

// Stored Consensus 2.0 statuses differ from the SDK's older projected enum.
const STORED_STATUSES = [
  "UNINITIALIZED", "PENDING", "PROPOSING", "COMMITTING", "REVEALING",
  "ACCEPTED", "UNDETERMINED", "FINALIZED", "CANCELED", "APPEAL_REVEALING",
  "APPEAL_COMMITTING", "VALIDATORS_TIMEOUT", "LEADER_TIMEOUT", "LEADER_REVEALING",
];
const RESULTS = ["IDLE", "AGREE", "DISAGREE", "TIMEOUT", "DETERMINISTIC_VIOLATION", "NO_MAJORITY", "MAJORITY_AGREE", "MAJORITY_DISAGREE"];
const EXECUTION_RESULTS = ["NOT_VOTED", "FINISHED_WITH_RETURN", "FINISHED_WITH_ERROR"];

export function storedReceipt(projected, transaction, rounds, block) {
  const status = Number(transaction?.status);
  if (transaction?.status == null || !Number.isInteger(status) || !STORED_STATUSES[status] || !Array.isArray(rounds)) {
    throw new Error("invalid stored consensus receipt");
  }
  if (transaction.numOfInitialValidators === undefined) {
    throw new Error("stored receipt has no initial validator count");
  }
  const stored = {
    ...transaction,
    txId: transaction.id,
    status,
    statusName: STORED_STATUSES[status],
    numOfInitialValidators: String(transaction.numOfInitialValidators),
    // Trace round arguments and numOfRounds use the array index. A stored
    // round's own `round` field can repeat after an idle leader replacement.
    numOfRounds: String(Math.max(0, rounds.length - 1)),
    lastRound: rounds.at(-1) ?? null,
    readStateBlockRange: transaction.readStateBlockRanges?.at(-1) ?? projected.readStateBlockRange,
    resultName: RESULTS[Number(transaction.result)] ?? "UNKNOWN",
    txExecutionResult: Number(transaction.txExecutionResult),
    txExecutionResultName: EXECUTION_RESULTS[Number(transaction.txExecutionResult)] ?? "UNKNOWN",
  };
  return {
    ...projected,
    ...stored,
    currentTimestamp: String(block.timestamp),
    status_basis: "getTransactionAllData",
    stored_block: { number: String(block.number), hash: block.hash, timestamp: String(block.timestamp) },
    stored_receipt: stored,
    stored_rounds: rounds,
    projected_receipt: projected,
  };
}

export function snapshotFromStoredOutputs(receipt, snapshotHash, decodeRlp, decodeCalldata) {
  if (receipt.status_basis !== "getTransactionAllData") return null;
  try {
    const outputs = decodeRlp(receipt.stored_receipt.eqBlocksOutputs, "hex");
    if (!Array.isArray(outputs) || !/^0x00[0-9a-f]+$/i.test(outputs[0] || "")) return null;
    const bytes = Buffer.from(outputs[0].slice(2), "hex");
    const value = decodeCalldata(new Uint8Array(bytes.subarray(1)));
    if (typeof value !== "string" || createHash("sha256").update(value, "utf8").digest("hex") !== snapshotHash) return null;
    return { snapshot_excerpt: value, snapshot_hash: snapshotHash,
      source: "getTransactionAllData.eqBlocksOutputs", transaction_id: receipt.txId,
      eq_block_index: 0, stored_block: receipt.stored_block };
  } catch { return null; }
}

async function main() {
const input = process.argv.slice(2);
const call = input[0] === "--call";
const tx = input[0];
const endpoint = call ? (input[4] || "") : (input[1] && !input[1].startsWith("--") ? input[1] : "");
const marker = input.indexOf("--snapshot");
const snapshotHash = marker < 0 ? "" : input[marker + 1];
if (!call && !/^0x[0-9a-f]{64}$/i.test(tx || "")) throw new Error("invalid transaction ID");
const entry = realpathSync(execFileSync("which", ["genlayer"], { encoding: "utf8" }).trim());
const root = resolve(dirname(entry), "..");
const sdk = await import(pathToFileURL(join(root, "node_modules/genlayer-js/dist/index.js")));
const chains = await import(pathToFileURL(join(root, "node_modules/genlayer-js/dist/chains/index.js")));
const client = sdk.createClient({ chain: chains.testnetBradbury, endpoint: endpoint || undefined });
if (call) {
  const address = input[1], method = input[2], args = JSON.parse(input[3] || "[]");
  if (!/^0x[0-9a-f]{40}$/i.test(address) || !Array.isArray(args)) throw new Error("invalid read arguments");
  if (!["get_space", "get_entry", "get_challenge", "entry_count", "report", "deferred_queue", "solvency"].includes(method)) throw new Error("unknown read-only Hearsay method");
  const value = await client.readContract({ address, functionName: method, args: args.map(arg => typeof arg === "number" ? BigInt(arg) : arg) });
  console.log(JSON.stringify(value, (_, item) => {
    if (typeof item === "bigint") return { $bigint: item.toString() };
    if (typeof item === "number" && !Number.isSafeInteger(item)) throw new Error("unsafe numeric chain result");
    return item instanceof Map ? Object.fromEntries(item) : item;
  }));
} else {
const { createPublicClient, http, fromRlp } = await import(pathToFileURL(join(root, "node_modules/viem/_esm/index.js")));
const publicClient = createPublicClient({ chain: chains.testnetBradbury, transport: http(endpoint || undefined) });
const block = await publicClient.getBlock();
const spec = chains.testnetBradbury.consensusDataContract;
const [projected, allData] = await Promise.all([
  client.getTransaction({ hash: tx }),
  publicClient.readContract({ address: spec.address, abi: spec.abi, functionName: "getTransactionAllData", args: [tx], blockNumber: block.number }),
]);
const [transaction, rounds] = allData;
if (transaction.id.toLowerCase() !== tx.toLowerCase()) throw new Error("stored transaction ID differs from request");
const receipt = storedReceipt(projected, transaction, rounds, block);
if (!snapshotHash) {
  console.log(JSON.stringify(receipt, (_, value) => typeof value === "bigint" ? value.toString() : value));
} else {
  if (!/^[0-9a-f]{64}$/.test(snapshotHash)) throw new Error("unsupported snapshot hash");
  const digest = bytes => createHash("sha256").update(bytes).digest("hex");
  let found = null;
  if (snapshotHash === digest(Buffer.alloc(0))) found = { snapshot_excerpt: "", snapshot_hash: snapshotHash, trace_round: null };
  if (!found) found = snapshotFromStoredOutputs(receipt, snapshotHash, fromRlp, sdk.abi.calldata.decode);
  // Bradbury numbers the initial round 0; numOfRounds is the last index.
  const lastRound = Math.max(0, Number(receipt.numOfRounds || 0));
  for (let round = 0; round <= lastRound && !found; round++) {
    let trace;
    try { trace = await client.request({ method: "gen_dbg_traceTransaction", params: [{ txID: tx, round }] }); }
    catch { continue; }
    if (trace?.result_code !== 0 || !trace.return_data) continue;
    const decoded = sdk.abi.calldata.decode(new Uint8Array(Buffer.from(trace.return_data.slice(2), "hex")));
    const changes = decoded instanceof Map ? decoded.get("storage_changes") : null;
    for (const [key, value] of changes || []) {
      if (!(value instanceof Uint8Array)) continue;
      const bytes = Buffer.from(value);
      // Storage strings occupy padded 32-byte cells. Try only trailing NUL
      // padding; the authoritative hash selects the exact byte length.
      let padding = 0;
      while (padding < bytes.length && bytes[bytes.length - padding - 1] === 0) padding++;
      for (let remove = 0; remove <= padding; remove++) {
        const candidate = bytes.subarray(0, bytes.length - remove);
        if (digest(candidate) !== snapshotHash) continue;
        const text = new TextDecoder("utf-8", { fatal: true }).decode(candidate);
        found = { snapshot_excerpt: text, snapshot_hash: snapshotHash, trace_round: round, trace_transaction_id: tx, storage_key: Buffer.from(key).toString("hex") };
        break;
      }
      if (found) break;
    }
  }
  if (!found) throw new Error("no trace storage value matches the pinned snapshot hash");
  console.log(JSON.stringify(found));
}
}
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) await main();
