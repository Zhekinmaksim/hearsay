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
if (!["open_space", "write_entry", "challenge", "confirm_challenge", "rejudge", "expire", "withdraw", "fund_space"].includes(request.method)) fail("unknown Hearsay write method");
if (!Array.isArray(request.args) || !/^\d+$/.test(String(request.value))) fail("invalid args or value");
if (request.method === "write_entry" && !request.envelope_hash) fail("write requires envelope_hash metadata");
const recorded = readFileSync(requestPath, "utf8");
if (process.argv.includes("--plan")) {
  console.log(recorded);
  process.exit(0);
}

const cliEntry = realpathSync(execFileSync("which", ["genlayer"], { encoding: "utf8" }).trim());
const cliRoot = resolve(dirname(cliEntry), "..");
const sdk = await import(pathToFileURL(join(cliRoot, "node_modules/genlayer-js/dist/index.js")));
const chains = await import(pathToFileURL(join(cliRoot, "node_modules/genlayer-js/dist/chains/index.js")));
const keytarModule = await import(pathToFileURL(join(cliRoot, "node_modules/keytar/lib/keytar.js")));
const keytar = keytarModule.default || keytarModule;
const configPath = process.env.GENLAYER_CONFIG || join(process.env.HOME, ".genlayer/genlayer-config.json");
const config = JSON.parse(readFileSync(configPath, "utf8"));
if (!config.activeAccount) fail("no active GenLayer account");
const privateKey = await keytar.getPassword("genlayer-cli", "account:" + config.activeAccount);
if (!privateKey) fail("unlock the active account with genlayer account unlock");
const account = sdk.createAccount(privateKey);
if (account.address.toLowerCase() !== request.expected_account.toLowerCase()) fail("active account differs from expected_account");
const client = sdk.createClient({ chain: chains.testnetBradbury, account });
const hash = await client.writeContract({
  account, address: request.address, functionName: request.method,
  args: request.args.map(integers), value: BigInt(request.value),
});
const row = {
  tx: hash, method: request.method, address: request.address,
  sender: account.address, value: String(request.value),
  ...(request.envelope_hash ? { envelope_hash: request.envelope_hash } : {}),
  ...(request.file ? { file: request.file } : {}),
  ...(request.id ? { id: request.id } : {}),
};
const descriptor = openSync(manifest, "a");
try {
  appendFileSync(descriptor, JSON.stringify(row) + "\n");
  fsyncSync(descriptor);
} finally { closeSync(descriptor); }
console.log(JSON.stringify(row));
