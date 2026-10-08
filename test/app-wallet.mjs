/* Offline, real bundled SDK -> EIP-1193 adapter -> fake public RPC.
 * No signed transactions, secrets, or network calls occur in this test. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { abi, fromRlp, hexToBytes, decodeFunctionData, encodeEventTopics, toRlp, toHex } from '../web/app-sdk.mjs';
import { LiveHearsay, TransactionJournal, CONTRACT, CHAIN, BINDINGS, STORAGE_KEY, json, validateClaim, walletProvider, sendWrite, materialized, normalizeReceipt, phaseText, snapshotProof, terminal, errorText } from '../web/app-core.mjs';
import { sha256 } from '../web/lib.mjs';
import { VERIFIED_BINDINGS } from '../scripts/queue_progress.mjs';
const sender = '0x' + '12'.repeat(20), other = '0x' + '13'.repeat(20);
const evmHash = '0x' + '23'.repeat(32), protocolHash = '0x' + '34'.repeat(32), blockHash = '0x' + '45'.repeat(32);
const store = () => { const values = new Map(); return { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value) }; };
const space = { space_id: 1, open: true, write_bond: 1000n };
const claim = validateClaim(space, 'The registry records this company as active.', 'https://find-and-update.company-information.service.gov.uk/company/00445790');
const record = () => ({ version: 1, id: 'review', contract: CONTRACT, sender, createdAt: Date.now(), method: 'write_entry', phase: 'preparing', args: [1n, 'honest', claim.serialized], value: '1000', envelope: claim.envelope, envelopeHash: claim.hash, spaceId: 1 });
let passes = 0;
function check(title, fn) { fn(); passes++; console.log('ok ' + title); }
check('receipt bindings match the production queue verifier', () => assert.deepEqual(BINDINGS, VERIFIED_BINDINGS));
check('benchmark space cannot be written through this frontend', () => assert.throws(() => validateClaim({ ...space, space_id: 0 }, 'test', 'https://example.org'), /benchmark/));
check('multi-byte oversized claims fail before the wallet', () => assert.throws(() => validateClaim(space, 'é'.repeat(1025), 'https://example.org'), /UTF-8 bytes/));
check('normalized duplicate and unsafe source credentials are rejected', () => {
  assert.throws(() => validateClaim(space, '  A  COMPANY ', 'https://example.org', [{ space_id: 1, claim: 'a company' }]), /already recorded/);
  assert.throws(() => validateClaim(space, 'a', 'https://user:password@example.org'), /credentials/);
});
async function scenario(setup = {}) {
  const storage = store(), row = record(), journal = new TransactionJournal(storage);
  if (setup.openSpace) { row.method = 'open_space'; row.args = ['Visitor registry memory', 'Primary company registry facts only', 1000n, 3n, 2n, 1000n, 2000n]; row.value = '500000'; delete row.envelope; delete row.envelopeHash; delete row.spaceId; }
  let account = sender, chainId = '0x107d', sends = 0, publicCalls = [], callback = false;
  const injected = { async request({ method, params }) {
    if (method === 'eth_accounts') return [account];
    if (method === 'eth_chainId') return chainId;
    if (method === 'eth_sendTransaction') {
      sends++;
      const saved = JSON.parse(storage.getItem(STORAGE_KEY))[0];
      assert.equal(saved.phase, 'awaiting_wallet'); assert.equal(saved.sendAttempted, true); assert(saved.intent.data);
      const tx = params[0]; assert.equal(tx.from, sender); assert.equal(tx.to.toLowerCase(), BINDINGS.main); assert.equal(tx.chainId, '0x107d'); assert.equal(tx.value, '0x' + BigInt(row.value).toString(16)); assert.equal(tx.gas, '0x1e848');
      const outer = decodeFunctionData({ abi: CHAIN.consensusMainContract.abi, data: tx.data });
      assert.equal(outer.functionName, 'addTransaction'); assert.equal(outer.args[1], CONTRACT); assert.equal(outer.args[2], 5n); assert.equal(outer.args[3], 3n);
      const call = abi.calldata.decode(hexToBytes(fromRlp(outer.args[4], 'hex')[0]));
      assert.equal(call.get('method'), row.method); assert.deepEqual(call.get('args'), row.args);
      if (setup.reject) throw Object.assign(new Error('User rejected the request.'), { code: 4001 });
      if (setup.ambiguous) throw new Error('Wallet transport connection lost');
      return evmHash;
    }
    throw new Error('Unexpected wallet method: ' + method);
  } };
  const live = { async verifiedBlock() { if (setup.bindingError) throw new Error('Unverified consensus implementation'); return { block: { number: 1n }, version: '2.0.0' }; }, public: {
    async estimateGas() { if (setup.estimateError || setup.sdkEstimateFallback) throw new Error('Estimate rejected'); return 100000n; }, async getGasPrice() { return 1n; }, async getBalance() {
      if (setup.accountChanges) account = other;
      if (setup.chainChanges) chainId = '0x1';
      return setup.unfunded ? 0n : 10000000n;
    }
  } };
  const originalFetch = globalThis.fetch, originalWarn = console.warn, originalError = console.error;
  globalThis.fetch = async (url, options) => {
    assert.equal(url, CHAIN.rpcUrls.default.http[0]); const body = JSON.parse(options.body); publicCalls.push(body.method);
    const reply = result => Response.json({ jsonrpc: '2.0', id: body.id, result });
    switch (body.method) {
      case 'eth_getTransactionCount': return reply('0x12');
      case 'eth_estimateGas': return setup.sdkEstimateFallback ? Response.json({ jsonrpc: '2.0', id: body.id, error: { code: -32000, message: 'Estimation unavailable' } }) : reply('0x186a0');
      case 'eth_gasPrice': return reply('0x1');
      case 'eth_blockNumber': return reply('0x100');
      case 'eth_getTransactionReceipt': return reply({ transactionHash: evmHash, transactionIndex: '0x0', blockHash, blockNumber: '0x100', from: sender, to: CHAIN.consensusMainContract.address, contractAddress: null, cumulativeGasUsed: '0x186a0', gasUsed: '0x186a0', effectiveGasPrice: '0x1', status: '0x1', type: '0x0', logsBloom: '0x' + '00'.repeat(256), logs: [{ address: CHAIN.consensusMainContract.address, blockHash, blockNumber: '0x100', transactionHash: evmHash, transactionIndex: '0x0', logIndex: '0x0', removed: false, data: '0x', topics: encodeEventTopics({ abi: CHAIN.consensusMainContract.abi, eventName: 'NewTransaction', args: { txId: protocolHash, recipient: CONTRACT, activator: sender } }) }] });
      default: throw new Error('Unexpected public RPC: ' + body.method);
    }
  };
  console.warn = () => {}; console.error = () => {};
  let result, error;
  try {
    result = await sendWrite({ live, provider: injected, account: sender, journal, record: row, functionName: setup.wrongMethod ? 'fund_space' : row.method, args: setup.wrongClaim ? [1n, 'honest', '{}'] : setup.wrongSpace ? [2n, 'honest', claim.serialized] : row.args, value: setup.wrongValue ? 2000n : BigInt(row.value), getWallet: () => account, onSent() { callback = true; assert.equal(JSON.parse(storage.getItem(STORAGE_KEY))[0].evmHash, evmHash); } });
    if (setup.double) await sendWrite({ live, provider: injected, account: sender, journal, record: row, functionName: 'write_entry', args: row.args, value: 1000n, getWallet: () => account });
  } catch (caught) { error = caught; }
  finally { globalThis.fetch = originalFetch; console.warn = originalWarn; console.error = originalError; }
  return { result, error, row, journal, storage, sends, callback, publicCalls };
}
let result = await scenario();
check('actual SDK reaches the injected wallet with exact reviewed payable calldata', () => { assert.ifError(result.error); assert.equal(result.sends, 1); assert(result.callback); assert.equal(result.row.evmHash, evmHash); assert.equal(result.row.protocolHash, protocolHash); });
check('SDK never routes wallet sends to the public RPC', () => assert(!result.publicCalls.includes('eth_sendTransaction') && !result.publicCalls.includes('eth_sendRawTransaction')));
const resumed = new TransactionJournal(result.storage);
check('reload restores both hashes without a second wallet prompt', () => { assert.equal(resumed.records[0].evmHash, evmHash); assert.equal(resumed.records[0].protocolHash, protocolHash); assert.equal(resumed.active().id, 'review'); });
result = await scenario({ openSpace: true });
check('actual SDK opens a space for the connected visitor with the disclosed funding and seven arguments', () => { assert.ifError(result.error); assert.equal(result.sends, 1); assert.equal(result.row.value, '500000'); assert.equal(result.row.method, 'open_space'); assert.equal(result.row.protocolHash, protocolHash); });
result = await scenario({ double: true });
check('an accidental second SDK write is blocked before a second send', () => { assert(result.error); assert.equal(result.sends, 1); assert.equal(result.row.evmHash, evmHash); });
result = await scenario({ reject: true });
check('wallet rejection is explicit, stores no hashes, and permits a new reviewed attempt', () => { assert.equal(result.sends, 1); assert.equal(result.row.phase, 'wallet_rejected'); assert.equal(result.row.evmHash, undefined); assert.equal(result.journal.active(), undefined); assert.match(errorText(result.error), /declined/); });
result = await scenario({ ambiguous: true });
check('lost wallet response retains intent and blocks duplicate submissions', () => { assert.equal(result.sends, 1); assert.equal(result.row.phase, 'broadcast_unknown'); assert(result.row.intent.data); assert(result.journal.active()); assert.equal(new TransactionJournal(result.storage).active().phase, 'broadcast_unknown'); });
for (const option of ['unfunded', 'estimateError', 'sdkEstimateFallback', 'bindingError', 'wrongValue', 'wrongMethod', 'wrongClaim', 'wrongSpace', 'accountChanges', 'chainChanges']) {
  result = await scenario({ [option]: true });
  check(option + ' fails before the wallet send', () => { assert(result.error); assert.equal(result.sends, 0); assert.equal(result.row.phase, 'safe_error'); });
}
check('storage failure blocks sending', () => assert.throws(() => new TransactionJournal({ getItem: () => null, setItem: () => { throw new Error('quota'); } }).save(record()), /storage/));
const transaction = { id: protocolHash, sender, recipient: CONTRACT, status: 5, result: 1, txExecutionResult: 1, numOfInitialValidators: 5n, initialRotations: 3n };
const block = { number: 33n, hash: blockHash, timestamp: 123n };
for (let status = 1; status < STATUSES_COUNT(); status++) {
  const receipt = normalizeReceipt({ ...transaction, status }, [], block, '2.0.0');
  check('canonical status ' + status + ' is interpreted only by verified 2.0.0', () => { assert(receipt.statusName); assert.equal(materialized(receipt), [5, 7].includes(status)); if ([12, 13].includes(status)) assert.match(phaseText({ receipt }).detail, /not a refusal/); });
}
function STATUSES_COUNT() { return 15; }
check('unknown version, wrong settings, and unknown status are refused', () => { assert.throws(() => normalizeReceipt(transaction, [], block, '0.6'), /version/); assert.throws(() => normalizeReceipt({ ...transaction, status: 99 }, [], block, '2.0.0'), /unknown status/); assert.throws(() => normalizeReceipt({ ...transaction, initialRotations: 4 }, [], block, '2.0.0'), /settings/); });
check('error execution is never an application verdict', () => { assert(!materialized({ ...transaction, txExecutionResult: 2 })); assert.match(phaseText({ receipt: { ...transaction, txExecutionResult: 2 } }).title, /failed/); });
const snapshot = 'Pinned original source.\nNot a new web fetch.';
const outputs = toRlp([toHex(new Uint8Array([0, ...abi.calldata.encode(snapshot)]))]);
const receipt = { ...transaction, status_basis: 'getTransactionAllData', eqBlocksOutputs: outputs, stored_block: { number: '33', hash: blockHash } };
check('proof requires exact stored EQ source bytes and a matching SHA-256', () => { assert.equal(snapshotProof(receipt, { snapshot_hash: sha256(snapshot) }).text, snapshot); assert.equal(snapshotProof(receipt, { snapshot_hash: '00'.repeat(32) }), null); assert.equal(snapshotProof({ ...receipt, status: 12 }, { snapshot_hash: sha256(snapshot) }), null); assert.equal(snapshotProof({ ...receipt, eqBlocksOutputs: '0xc0' }, { snapshot_hash: sha256(snapshot) }), null); });
const allReads = [];
const publicClient = {
  async getBlock() { return block; },
  async getStorageAt(args) { allReads.push(args); const impl = args.address === BINDINGS.main ? BINDINGS.mainImplementation : args.address === BINDINGS.data ? BINDINGS.dataImplementation : BINDINGS.queueImplementation; return '0x' + '00'.repeat(12) + impl.slice(2); },
  async readContract(args) { allReads.push(args); if (args.functionName === 'VERSION') return '2.0.0'; if (args.functionName === 'addressManager') return BINDINGS.manager; if (args.functionName === 'getAddress') return BINDINGS.queues; if (args.functionName === 'getTransactionAllData') return [transaction, []]; throw new Error('Unexpected read'); }
};
const live = new LiveHearsay({ publicClient, readClient: { readContract: async () => new Map() } });
const pinned = await live.receipt(protocolHash, sender);
check('canonical receipt and version/binding/implementation guards share one pinned block', () => { assert.equal(pinned.status_basis, 'getTransactionAllData'); assert.equal(allReads.length, 7); assert(allReads.every(read => read.blockNumber === 33n)); });
await assert.rejects(live.receipt(protocolHash, other), /different wallet/); passes++;
check('application matching requires exact envelope and author, not protocol success alone', () => { assert(!materialized({ ...transaction, result: 2 })); });
const userError = toHex(abi.calldata.encode({ data: 'unknown space', kind: 'UserError' }));
check('encoded GenVM read errors are decoded without exposing its entire trace', () => assert.equal(errorText({ cause: { data: userError } }), 'unknown space'));
console.log(`app wallet/core: ${passes} checks passed (offline, zero real sends).`);
