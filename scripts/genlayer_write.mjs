#!/usr/bin/env node
/* Payable writes using the SDK bundled with the installed GenLayer CLI.
 * CLI 0.39.1 hard-codes value: 0. Read an unlocked account from its OS keychain,
 * never export it, and checkpoint the returned protocol tx ID immediately.
 * node scripts/genlayer_write.mjs --request runs/request.json --manifest runs/bradbury.jsonl
 */
import { execFileSync } from "node:child_process";
import { appendFileSync, closeSync, fsyncSync, openSync, readFileSync, realpathSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { createHash } from "node:crypto";
import { assertBroadcastReconciled, createBroadcastFetch } from "./broadcast.mjs";
import { accountWithProgressGuard, readQueueProgress } from "./queue_progress.mjs";
import { localGate, envelopeHash } from "../web/lib.mjs";

function option(name) {
  const position = process.argv.indexOf(name);
  return position < 0 ? "" : process.argv[position + 1];
}
function fail(message) { throw new Error(message); }
function integers(value) {
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value)) fail("argument exceeds safe JSON integer range");
    return BigInt(value);
  }
  if (Array.isArray(value)) return value.map(integers);
  return value;
}

const requestPath = option("--request");
const manifest = option("--manifest");
if (!requestPath || !manifest) fail("--request and --manifest are required");
const request = JSON.parse(readFileSync(requestPath, "utf8"));
if (!/^0x[0-9a-f]{40}$/i.test(request.address)) fail("invalid contract address");
if (!/^0x[0-9a-f]{40}$/i.test(request.expected_account)) fail("expected_account is required");
if (!["deploy", "open_space", "write_entry", "challenge", "confirm_challenge", "rejudge", "expire", "withdraw", "fund_space"].includes(request.method)) fail("unknown Hearsay write method");
if (!Array.isArray(request.args) || !/^\d+$/.test(String(request.value))) fail("invalid args or value");
if (request.method === "write_entry" && !request.envelope_hash) fail("write requires envelope_hash metadata");
if (request.consensus_max_rotations !== undefined && (!Number.isSafeInteger(request.consensus_max_rotations) || request.consensus_max_rotations < 0)) fail("invalid rotation limit");
if (request.expected_nonce !== undefined &&
    ((typeof request.expected_nonce === "number" && (!Number.isSafeInteger(request.expected_nonce) || request.expected_nonce < 0)) ||
     !/^\d+$/.test(String(request.expected_nonce)))) fail("invalid expected_nonce");
let code;
if (request.method === "deploy") {
  if (String(request.value) !== "0") fail("deploy first, then fund open_space");
  code = readFileSync(request.code_file, "utf8");
  if (createHash("sha256").update(code).digest("hex") !== request.code_sha256) fail("deployment source hash differs from reviewed code");
}
const recorded = readFileSync(requestPath, "utf8");
if (process.argv.includes("--plan")) {
  console.log(recorded);
  process.exit(0);
}
// A restarted process must not choose a fresh nonce after a lost RPC reply or
// a crash between EVM acknowledgement and protocol-ID checkpointing.
assertBroadcastReconciled(manifest, { method: request.method, id: request.id });

const cliEntry = realpathSync(execFileSync("which", ["genlayer"], { encoding: "utf8" }).trim());
const cliRoot = resolve(dirname(cliEntry), "..");
const sdk = await import(pathToFileURL(join(cliRoot, "node_modules/genlayer-js/dist/index.js")));
const chains = await import(pathToFileURL(join(cliRoot, "node_modules/genlayer-js/dist/chains/index.js")));
const { keccak256, parseTransaction, createPublicClient, http } = await import(pathToFileURL(join(cliRoot, "node_modules/viem/_esm/index.js")));
const keytarModule = await import(pathToFileURL(join(cliRoot, "node_modules/keytar/lib/keytar.js")));
const keytar = keytarModule.default || keytarModule;
const configPath = process.env.GENLAYER_CONFIG || join(process.env.HOME, ".genlayer/genlayer-config.json");
const config = JSON.parse(readFileSync(configPath, "utf8"));
if (!config.activeAccount) fail("no active GenLayer account");
const privateKey = await keytar.getPassword("genlayer-cli", "account:" + config.activeAccount);
if (!privateKey) fail("unlock the active account with genlayer account unlock");
const signingAccount = sdk.createAccount(privateKey);
let progressProof;
if (request.progress_guard && request.method !== "write_entry") fail("progress guard is only for independent entry writes");
const account = request.progress_guard ? accountWithProgressGuard(signingAccount, async () => {
  const envelope = JSON.parse(request.args[2]);
  if (localGate(envelope, []).code === 3) fail("progress guard requires a valid entry envelope");
  if (envelopeHash(envelope) !== request.envelope_hash) fail("progress guard envelope hash differs from request metadata");
  const independentClasses = ["honest", "direct_injection", "source_forgery", "citation_laundering", "slow_poison", "stale_truth", "flooding"];
  if (request.progress_guard.scan_complete !== true || request.progress_guard.solvency_balanced !== true || request.args[0] !== 0 || !independentClasses.includes(request.args[1])) fail("progress guard requires complete absence scan, solvency and a known independent input class");
  if (envelope.version !== "hearsay/1" || envelope.space_id !== request.args[0] || envelope.entry_class !== request.args[1]) fail("progress guard envelope differs from entry arguments");
  const supports = envelope.supports === undefined ? [] : envelope.supports;
  if (!Array.isArray(supports) || supports.length) fail("unresolved progress cannot use dependent premises");
  const solvency = await client.readContract({ address: request.address, functionName: "solvency", args: [] });
  const currentSolvency = solvency instanceof Map ? Object.fromEntries(solvency) : solvency;
  if (currentSolvency?.balanced !== true) fail("fresh before-sign solvency failed");
  const publicClient = createPublicClient({ chain: chains.testnetBradbury, transport: http() });
  progressProof = await readQueueProgress(publicClient, chains.testnetBradbury, request.address, request.expected_account, request.progress_guard.transactions);
  progressProof.solvency = JSON.parse(JSON.stringify(currentSolvency, (_, value) => typeof value === "bigint" ? value.toString() : value));
}) : signingAccount;
if (account.address.toLowerCase() !== request.expected_account.toLowerCase()) fail("active account differs from expected_account");
const client = sdk.createClient({ chain: chains.testnetBradbury, account });
// SDK 1.1.8 closes over intermediate client copies. Its lexical fetch transport
// bypasses changes to finalClient.sendRawTransaction/estimateTransactionGas.
// Intercept the actual transport, preserving SDK encoding/signing and receipts.
const originalFetch = globalThis.fetch;
globalThis.fetch = createBroadcastFetch(originalFetch, {
  rpcUrl: client.chain.rpcUrls.default.http[0], hashTransaction: keccak256, parseTransaction,
  journal: { path: manifest + ".broadcasts.jsonl", method: request.method, id: request.id },
  expectedNonce: request.expected_nonce,
  gasMarginNumerator: request.method === "deploy" ? 100n : 125n,
});
let hash;
try {
hash = request.method === "deploy" ? await client.deployContract({
  account, code, args: request.args.map(integers), consensusMaxRotations: request.consensus_max_rotations,
}) : await client.writeContract({
  account, address: request.address, functionName: request.method,
  args: request.args.map(integers), value: BigInt(request.value), consensusMaxRotations: request.consensus_max_rotations,
});
} finally { globalThis.fetch = originalFetch; }
const row = {
  tx: hash, method: request.method, address: request.address,
  sender: account.address, value: String(request.value),
  consensus_max_rotations: request.consensus_max_rotations ?? client.chain.defaultConsensusMaxRotations,
  ...(request.envelope_hash ? { envelope_hash: request.envelope_hash } : {}),
  ...(request.file ? { file: request.file } : {}),
  ...(request.id ? { id: request.id } : {}),
  ...(request.code_sha256 ? { code_sha256: request.code_sha256 } : {}),
  ...(progressProof ? { progress_guard: progressProof } : {}),
};
const descriptor = openSync(manifest, "a");
try {
  appendFileSync(descriptor, JSON.stringify(row) + "\n");
  fsyncSync(descriptor);
} finally { closeSync(descriptor); }
console.log(JSON.stringify(row));
