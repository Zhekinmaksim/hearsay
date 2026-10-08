/* Read-only progress proof for the verified Bradbury 2.0.0 queue. */
import { assertConsensusVersion } from "./protocol_version.mjs";

const ZERO_HASH = "0x" + "00".repeat(32);
const IMPLEMENTATION_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc";
export const VERIFIED_BINDINGS = {
  main: "0x0112bf6e83497965a5fdd6dad1e447a6e004271d", mainImplementation: "0x0a2c393975da79505ed930efc55ae4aeb88b0d62",
  data: "0x85d7bf947a512fc640c75327a780c90847267697", dataImplementation: "0x7ee629530e70e2a3a772f8522d8835060abf0755",
  manager: "0x8ace036c8c3c5d603db546b031302fcf149648e8", queues: "0x56a05a9bb7b261ad720020a08b9fd5a13177b949",
  queueImplementation: "0x7559ebdbc6f59e5dd2a048a1a1539ac14bf93db0",
};
const view = (name, inputs, output) => ({ type: "function", name, stateMutability: "view", inputs: inputs.map((type, index) => ({ name: "arg" + index, type })), outputs: [{ name: "", type: output }] });
const ADDRESS_MANAGER_ABI = [view("getAddress", ["string"], "address")];
const QUEUES_ABI = [
  view("getPendingHead", ["address"], "uint256"), view("getPendingTail", ["address"], "uint256"),
  view("getPendingHeadTxId", ["address"], "bytes32"), view("getAcceptedHeadTxId", ["address"], "bytes32"),
  view("getTxQueueType", ["address", "bytes32"], "uint8"), view("isAtPendingQueueHead", ["address", "bytes32"], "bool"),
];
// Undetermined is unresolved application evidence, but its separate queue
// permits independent provisional writes under the same empty-pending proof.
const KNOWN_UNSETTLED = new Set([2, 3, 4, 6, 9, 10, 12, 13, 14]);
function check(condition, message) { if (!condition) throw new Error("queue progress guard: " + message); }

export async function readQueueProgress(publicClient, chain, recipient, expectedAccount, transactions) {
  check(/^0x[0-9a-f]{40}$/i.test(recipient) && /^0x[0-9a-f]{40}$/i.test(expectedAccount), "invalid target/account");
  check(Array.isArray(transactions) && transactions.length > 0 && new Set(transactions).size === transactions.length && transactions.every(tx => /^0x[0-9a-f]{64}$/i.test(tx)), "invalid unresolved transaction list");
  const block = await publicClient.getBlock();
  const read = (spec, functionName, args = []) => publicClient.readContract({ ...spec, functionName, args, blockNumber: block.number });
  const main = chain.consensusMainContract;
  check(main.address.toLowerCase() === VERIFIED_BINDINGS.main && chain.consensusDataContract.address.toLowerCase() === VERIFIED_BINDINGS.data, "unknown consensus binding");
  const version = await read(main, "VERSION");
  assertConsensusVersion(version);
  const addressManager = await read(main, "addressManager");
  check(addressManager.toLowerCase() === VERIFIED_BINDINGS.manager, "unknown AddressManager binding");
  const queueAddress = await read({ address: addressManager, abi: ADDRESS_MANAGER_ABI }, "getAddress", ["Queues"]);
  check(queueAddress.toLowerCase() === VERIFIED_BINDINGS.queues, "unknown Queues binding");
  for (const [address, implementation] of [[main.address, VERIFIED_BINDINGS.mainImplementation], [chain.consensusDataContract.address, VERIFIED_BINDINGS.dataImplementation], [queueAddress, VERIFIED_BINDINGS.queueImplementation]]) {
    const stored = await publicClient.getStorageAt({ address, slot: IMPLEMENTATION_SLOT, blockNumber: block.number });
    check(stored?.slice(-40).toLowerCase() === implementation.slice(2), "unknown proxy implementation");
  }
  const queues = { address: queueAddress, abi: QUEUES_ABI };
  const [head, tail, headTx, acceptedHead] = await Promise.all([
    read(queues, "getPendingHead", [recipient]), read(queues, "getPendingTail", [recipient]),
    read(queues, "getPendingHeadTxId", [recipient]), read(queues, "getAcceptedHeadTxId", [recipient]),
  ]);
  check(head === tail && headTx.toLowerCase() === ZERO_HASH, "pending queue is not empty; replay or another write needs reconciliation");
  const observed = [];
  for (const tx of transactions) {
    const [[transaction], queueType, atPendingHead] = await Promise.all([
      read(chain.consensusDataContract, "getTransactionAllData", [tx]),
      read(queues, "getTxQueueType", [recipient, tx]), read(queues, "isAtPendingQueueHead", [recipient, tx]),
    ]);
    check(transaction.id.toLowerCase() === tx.toLowerCase(), "transaction ID changed");
    check(transaction.recipient.toLowerCase() === recipient.toLowerCase() && transaction.sender.toLowerCase() === expectedAccount.toLowerCase(), "foreign transaction");
    check(KNOWN_UNSETTLED.has(Number(transaction.status)), "transaction settled or has an unknown state; recollect");
    check(Number(transaction.numOfInitialValidators) === 5 && Number(transaction.initialRotations) === 3, "consensus settings changed");
    check([2, 3].includes(Number(queueType)) && atPendingHead === false, "unresolved transaction is still in the pending queue");
    observed.push({ tx, status_code: Number(transaction.status), queue_type: Number(queueType), at_pending_head: atPendingHead });
  }
  return { consensus_version: version, recipient, expected_account: expectedAccount, consensus_main: main.address,
    consensus_data: chain.consensusDataContract.address, address_manager: addressManager, queues: queueAddress,
    stored_block: { number: String(block.number), hash: block.hash, timestamp: String(block.timestamp) },
    pending_head: String(head), pending_tail: String(tail), pending_head_tx: headTx, accepted_head_tx: acceptedHead,
    transactions: observed, provisional: true, finalization_guaranteed: false };
}

export function accountWithProgressGuard(account, guard) {
  return { ...account, signTransaction: async parameters => { await guard(); return account.signTransaction(parameters); } };
}
