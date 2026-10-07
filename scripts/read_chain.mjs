#!/usr/bin/env node
/* Machine-readable, read-only RPC receipt using the CLI's installed SDK. */
import { execFileSync } from "node:child_process";
import { realpathSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { createHash } from "node:crypto";

const input = process.argv.slice(2);
const tx = input[0];
const endpoint = input[1] && !input[1].startsWith("--") ? input[1] : "";
const marker = input.indexOf("--snapshot");
const snapshotHash = marker < 0 ? "" : input[marker + 1];
if (!/^0x[0-9a-f]{64}$/i.test(tx || "")) throw new Error("invalid transaction ID");
const entry = realpathSync(execFileSync("which", ["genlayer"], { encoding: "utf8" }).trim());
const root = resolve(dirname(entry), "..");
const sdk = await import(pathToFileURL(join(root, "node_modules/genlayer-js/dist/index.js")));
const chains = await import(pathToFileURL(join(root, "node_modules/genlayer-js/dist/chains/index.js")));
const client = sdk.createClient({ chain: chains.testnetBradbury, endpoint: endpoint || undefined });
const receipt = await client.getTransaction({ hash: tx });
if (!snapshotHash) {
  console.log(JSON.stringify(receipt, (_, value) => typeof value === "bigint" ? value.toString() : value));
} else {
  if (!/^[0-9a-f]{64}$/.test(snapshotHash)) throw new Error("unsupported snapshot hash");
  const digest = bytes => createHash("sha256").update(bytes).digest("hex");
  let found = null;
  if (snapshotHash === digest(Buffer.alloc(0))) found = { snapshot_excerpt: "", snapshot_hash: snapshotHash, trace_round: null };
  const count = Math.max(1, Number(receipt.numOfRounds || 1));
  for (let round = 0; round < count && !found; round++) {
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
