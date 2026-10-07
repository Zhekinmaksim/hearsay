import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { storedReceipt, snapshotFromStoredOutputs } from "../scripts/read_chain.mjs";

const hash = "0x" + "ab".repeat(32);
const block = { number: 100n, timestamp: 200n, hash: "0x" + "cd".repeat(32) };
const transaction = { id: hash, status: 3, numOfInitialValidators: 5n, result: 0, txExecutionResult: 0 };
const projected = {
  txId: hash, status: 5, statusName: "ACCEPTED", numOfInitialValidators: "0",
  numOfRounds: "4", currentTimestamp: "999", lastRound: { round: "4", votesCommitted: "0" },
};
const earlierRound = { round: 4n, votesCommitted: 0n };
const latestRound = { round: 4n, votesCommitted: 9n };
const rounds = [earlierRound, { round: 0n }, latestRound];
const receipt = storedReceipt(projected, transaction, rounds, block);
assert.equal(receipt.statusName, "COMMITTING", "a projected admission cannot settle a stored commit round");
assert.equal(receipt.numOfInitialValidators, "5", "rotations are not the initial validator count");
assert.equal(receipt.lastRound, latestRound, "repeated round numbers must retain the latest stored round");
assert.equal(receipt.numOfRounds, "2", "trace round index follows the stored round array");
assert.equal(receipt.currentTimestamp, "200", "the canonical observation uses the chain block time");
assert.equal(receipt.projected_receipt, projected, "the original SDK view remains available");
assert.equal(projected.statusName, "ACCEPTED", "normalization must not rewrite historical projection evidence");
assert.equal(receipt.stored_receipt.status, 3);
assert.equal(receipt.stored_block.number, "100");
for (const [status, name] of [[11, "VALIDATORS_TIMEOUT"], [12, "LEADER_TIMEOUT"], [13, "LEADER_REVEALING"]]) {
  assert.equal(storedReceipt(projected, { ...transaction, status }, rounds, block).statusName, name);
}
assert.equal(storedReceipt(projected, { ...transaction, status: 7, result: 3 }, rounds, block).resultName, "TIMEOUT");
assert.throws(() => storedReceipt(projected, { ...transaction, status: 99 }, rounds, block), /invalid stored/);
assert.throws(() => storedReceipt(projected, { status: 5 }, rounds, block), /initial validator/);
const text = "Registry lists ACME as Active.";
const digest = createHash("sha256").update(text).digest("hex");
const withOutputs = { ...receipt, stored_receipt: { ...receipt.stored_receipt, eqBlocksOutputs: "encoded" } };
const recovered = snapshotFromStoredOutputs(withOutputs, digest, () => ["0x0001"], () => text);
assert.equal(recovered.snapshot_excerpt, text);
assert.equal(recovered.transaction_id, hash);
assert.equal(recovered.source, "getTransactionAllData.eqBlocksOutputs");
assert.equal(recovered.eq_block_index, 0);
assert.equal(snapshotFromStoredOutputs(withOutputs, "00".repeat(32), () => ["0x0001"], () => text), null);
assert.equal(snapshotFromStoredOutputs(withOutputs, digest, () => ["0x0101"], () => text), null);
assert.equal(snapshotFromStoredOutputs(withOutputs, digest, () => ["0x0001"], () => true), null);
assert.equal(snapshotFromStoredOutputs({ ...withOutputs, status_basis: "projected" }, digest, () => ["0x0001"], () => text), null);
assert.equal(snapshotFromStoredOutputs(withOutputs, digest, () => { throw new Error("bad RLP"); }, () => text), null);
console.log("stored receipt normalization: passed");
