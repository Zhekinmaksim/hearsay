import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { broadcastWithJournal } from "../scripts/broadcast.mjs";

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
  await assert.rejects(broadcastWithJournal(parameters, async () => { throw new Error("HTTP reply lost"); }, { path: lost, expectedHash }), /HTTP reply lost/);
  assert.deepEqual(records(lost).map(row => row.state), ["broadcast_attempt"]);
  assert.equal(records(lost)[0].evm_tx, expectedHash);
  passes++;

  let sent = false;
  await assert.rejects(broadcastWithJournal(parameters, async () => { sent = true; return expectedHash; }, { path: join(folder, "missing", "journal"), expectedHash }));
  assert.equal(sent, false);
  passes++;

  const mismatch = join(folder, "mismatch.jsonl");
  await assert.rejects(broadcastWithJournal(parameters, async () => "0x" + "cd".repeat(32), { path: mismatch, expectedHash }), /unexpected EVM/);
  assert.equal(records(mismatch).length, 1);
  passes++;
  console.log(passes + " broadcast recovery checks passed");
} finally { rmSync(folder, { recursive: true }); }
