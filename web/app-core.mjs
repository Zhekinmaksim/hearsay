/* Live Hearsay contract access. Consensus enum/bindings are pinned to the verified
 * Bradbury 2.0.0 implementation; see scripts/read_chain.mjs and queue_progress.mjs.
 * SDK 1.1.8 signs only through the caller's injected EIP-1193 provider. */
import { createClient, testnetBradbury, createPublicClient, http, fromRlp, hexToBytes, parseEventLogs, decodeFunctionData, abi } from './app-sdk.mjs';
import { canonical, envelopeHash, sha256, flatten, decide } from './lib.mjs';
export { envelopeHash };
export const CONTRACT = '0x2a5c1aA4Ae9e2292B737FE574aF44A2d8a5bB3F7';
export const CHAIN = testnetBradbury;
export const STORAGE_KEY = 'hearsay.bradbury.app.v1';
export const STATUSES = ['Uninitialized', 'Pending', 'Proposing', 'Committing', 'Revealing', 'Accepted', 'Undetermined', 'Finalized', 'Canceled', 'Appeal revealing', 'Appeal committing', 'Ready to finalize', 'Validators timeout', 'Leader timeout', 'Leader revealing'];
export const RESULTS = ['Idle', 'Majority agree', 'Majority disagree', 'Majority timeout', 'Deterministic violation', 'No majority'];
export const EXECUTIONS = ['Not voted', 'Finished with return', 'Finished with error', 'Timeout', 'Nondeterministic disagreement'];
export const BINDINGS = {
  main: '0x0112bf6e83497965a5fdd6dad1e447a6e004271d', mainImplementation: '0x0a2c393975da79505ed930efc55ae4aeb88b0d62',
  data: '0x85d7bf947a512fc640c75327a780c90847267697', dataImplementation: '0x7ee629530e70e2a3a772f8522d8835060abf0755',
  manager: '0x8ace036c8c3c5d603db546b031302fcf149648e8', queues: '0x56a05a9bb7b261ad720020a08b9fd5a13177b949',
  queueImplementation: '0x7559ebdbc6f59e5dd2a048a1a1539ac14bf93db0'
};
const SLOT = '0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc';
const MANAGER_ABI = [{ type: 'function', name: 'getAddress', stateMutability: 'view', inputs: [{ name: 'name', type: 'string' }], outputs: [{ name: '', type: 'address' }] }];
const CREATED_EVENT = [{ type: 'event', name: 'CreatedTransaction', inputs: [{ indexed: true, name: 'txId', type: 'bytes32' }, { indexed: false, name: 'txSlot', type: 'uint256' }] }];
export const isHash = value => /^0x[0-9a-f]{64}$/i.test(value || '');
const isAddress = value => /^0x[0-9a-f]{40}$/i.test(value || '');
const equal = (a, b) => String(a).toLowerCase() === String(b).toLowerCase();
const demand = (condition, message) => { if (!condition) throw new Error(message); };
export const plain = value => value instanceof Map ? Object.fromEntries([...value].map(([key, item]) => [key, plain(item)])) : Array.isArray(value) ? value.map(plain) : value && typeof value === 'object' && !(value instanceof Uint8Array) ? Object.fromEntries(Object.entries(value).map(([key, item]) => [key, plain(item)])) : value;
export const json = value => JSON.stringify(value, (_, item) => typeof item === 'bigint' ? item.toString() : item, 2);
export async function bounded(promise, message = 'The public RPC did not answer. Retry the read; your transaction is preserved.', ms = 16000) {
  let timer;
  try { return await Promise.race([promise, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(message)), ms); })]); }
  finally { clearTimeout(timer); }
}
export function errorText(error) {
  let current = error;
  for (let i = 0; i < 6 && current; i++, current = current.cause) {
    if (Number(current.code) === 4001 || /user rejected|user denied/i.test(current.message || '')) return 'You declined the wallet request. No transaction was submitted.';
    if (Number(current.code) === -32002) return 'A wallet request is already open. Finish it in your wallet.';
    if (/insufficient funds|not enough funds/i.test(current.message || '')) return 'Your wallet needs testnet GEN for the bond and network fees. Use the Bradbury faucet, then retry.';
    if (typeof current.data === 'string' && /^(0x)?[0-9a-f]+$/i.test(current.data)) {
      try { const detail = plain(abi.calldata.decode(hexToBytes(current.data.startsWith('0x') ? current.data : '0x' + current.data))); if (typeof detail?.data === 'string') return detail.data.slice(0, 600); } catch {}
    }
  }
  return String(error?.shortMessage || error?.message || error?.details || 'The network request failed.').slice(0, 600);
}
export function validateClaim(space, claim, sourceURL, entries = []) {
  demand(space?.open === true, 'Load an open memory space before submitting.');
  demand(Number(space.space_id) !== 0, 'Space 0 is the published benchmark. Create or load a separate space for your claim.');
  demand(typeof claim === 'string' && claim.trim(), 'Write a claim.');
  demand(new TextEncoder().encode(claim).length <= 2048, 'The claim must contain at most 2,048 UTF-8 bytes.');
  let source;
  try { source = new URL(sourceURL.trim()); } catch { throw new Error('Enter a full http or https source URL.'); }
  demand(['https:', 'http:'].includes(source.protocol) && !source.username && !source.password, 'Use a public http or https source URL without credentials.');
  demand(!entries.some(entry => Number(entry.space_id) === Number(space.space_id) && flatten(entry.claim) === flatten(claim)), 'This claim is already recorded in this space. Read its existing verdict.');
  const envelope = { version: 'hearsay/1', space_id: Number(space.space_id), entry_class: 'honest', claim, source_url: source.href };
  return { envelope, serialized: canonical(envelope), hash: envelopeHash(envelope), value: BigInt(space.write_bond) };
}
export function normalizeReceipt(transaction, rounds, block, version) {
  demand(version === '2.0.0', 'The protocol version changed. This app cannot interpret the receipt safely.');
  const status = Number(transaction.status);
  demand(STATUSES[status] !== undefined && Array.isArray(rounds), 'The stored receipt has an unknown status.');
  demand(Number(transaction.numOfInitialValidators) === 5 && Number(transaction.initialRotations) === 3, 'This transaction uses different consensus settings.');
  return { ...transaction, status, statusName: STATUSES[status], resultName: RESULTS[Number(transaction.result)] || 'Unknown', executionName: EXECUTIONS[Number(transaction.txExecutionResult)] || 'Unknown',
    rounds, consensus_version: version, status_basis: 'getTransactionAllData', stored_block: { number: String(block.number), hash: block.hash, timestamp: String(block.timestamp) } };
}
export function materialized(receipt) { return [5, 7].includes(Number(receipt?.status)) && Number(receipt.result) === 1 && Number(receipt.txExecutionResult) === 1; }
export function claimIntentFromReceipt(receipt) {
  demand(receipt.status_basis === 'getTransactionAllData' && equal(receipt.recipient, CONTRACT), 'Claim calldata must come from this contract’s canonical receipt.');
  const payload = fromRlp(receipt.txCalldata, 'hex');
  demand(Array.isArray(payload) && payload.length === 2 && payload[1] === '0x00', 'Unsupported stored transaction calldata.');
  const call = plain(abi.calldata.decode(hexToBytes(payload[0])));
  if (call.method !== 'write_entry') return null;
  demand(Array.isArray(call.args) && call.args.length === 3 && typeof call.args[2] === 'string', 'Malformed write_entry calldata.');
  const spaceId = Number(call.args[0]), entryClass = call.args[1], envelope = JSON.parse(call.args[2]);
  demand(Number.isSafeInteger(spaceId) && spaceId >= 0 && envelope && !Array.isArray(envelope) && envelope.version === 'hearsay/1' && Number(envelope.space_id) === spaceId && envelope.entry_class === entryClass, 'The stored envelope does not match its call arguments.');
  demand(['honest', 'direct_injection', 'source_forgery', 'citation_laundering', 'slow_poison', 'stale_truth', 'flooding'].includes(entryClass), 'Unknown entry class in stored calldata.');
  demand(typeof envelope.claim === 'string' && envelope.claim && typeof envelope.source_url === 'string' && /^https?:\/\//.test(envelope.source_url), 'Malformed claim or source in stored calldata.');
  const actualHash = sha256(JSON.stringify(Object.fromEntries(Object.keys(envelope).sort().map(key => [key, envelope[key]]))));
  // Unsupported extras or empty optionals can change the contract envelope
  // hash. Do not silently drop them when constructing a replayable receipt.
  demand(actualHash === envelopeHash(envelope), 'This stored envelope cannot be reproduced by the public gate format.');
  return { method: 'write_entry', args: call.args, spaceId, envelope, envelopeHash: actualHash, value: String(receipt.value) };
}
export function replayableReceipt(record, minRounds) {
  const { receipt, entry, proof, envelope } = record;
  if (!materialized(receipt) || !entry || !proof || !envelope || !Number.isSafeInteger(Number(minRounds))) return null;
  if (!equal(entry.author, receipt.sender) || entry.claim !== envelope.claim || entry.source_url !== envelope.source_url || entry.entry_class !== envelope.entry_class || Number(entry.space_id) !== Number(envelope.space_id) || entry.envelope_hash !== envelopeHash(envelope) || proof.hash !== entry.snapshot_hash || sha256(proof.text) !== entry.snapshot_hash) return null;
  const votes = entry.votes || {}, vote = value => value === 'yes' ? true : value === 'no' ? false : null;
  const a = vote(votes.a), b = vote(votes.b), rounds = Number(a !== null) + Number(b !== null);
  let conflict;
  if (['none', '', 'unasked'].includes(votes.conflict)) conflict = -1;
  else if (votes.conflict === 'unread') conflict = null;
  else if (/^\d+$/.test(String(votes.conflict))) conflict = Number(votes.conflict);
  else return null;
  const [verdict] = decide(a, b, rounds, Number(minRounds), conflict, votes.a !== 'unasked');
  if (verdict !== entry.status || rounds !== Number(entry.rounds)) return null;
  return { ...entry, envelope, min_rounds: Number(minRounds), snapshot_excerpt: proof.text, snapshot_verified: true,
    snapshot_provenance: { source: proof.source, transaction_id: proof.transaction, eq_block_index: proof.eq_block_index, stored_block: proof.stored_block },
    tx: record.protocolHash, receipt_status: receipt.statusName, consensus_checkpoint: receipt };
}
export function terminal(record) { return ['wallet_rejected', 'safe_error', 'evm_reverted'].includes(record.phase) || [7, 8].includes(Number(record.receipt?.status)); }
export function phaseText(record) {
  if (record.receipt) {
    const receipt = record.receipt;
    if (Number(receipt.txExecutionResult) === 2 && [5, 7].includes(Number(receipt.status))) return { title: 'Contract execution failed', detail: 'The protocol recorded an execution error. There is no application verdict for this attempt.' };
    if ([12, 13].includes(Number(receipt.status)) || Number(receipt.txExecutionResult) === 3) return { title: receipt.statusName, detail: 'Consensus timed out. This is an unresolved protocol outcome, not a refusal of the claim. Tracking continues.' };
    if (Number(receipt.status) === 8) return { title: 'Canceled by the protocol', detail: 'No application verdict is counted. Review the current receipt before starting another attempt.' };
    if (Number(receipt.status) === 5) return { title: 'Accepted · provisional', detail: 'The decision can be appealed or replayed. The app keeps checking until finalization.' };
    if (Number(receipt.status) === 7) return { title: 'Finalized', detail: 'The protocol is finalized. An application verdict is shown only when a matching contract record exists.' };
    if (Number(receipt.status) === 6) return { title: 'Undetermined', detail: 'Validators did not establish a decision. There is no claim verdict; tracking continues.' };
    return { title: receipt.statusName, detail: 'The GenLayer protocol is processing this attempt. Keep this hash to resume tracking.' };
  }
  const phases = {
    preparing: ['Checking the transaction', 'Reading current contract settings and wallet balance.'],
    awaiting_wallet: ['Approve in your wallet', 'Review the GEN value and network fee. Closing or reloading this page will not resubmit the request.'],
    broadcast_pending: ['EVM transaction sent', 'Waiting for the EVM receipt and the GenLayer protocol transaction ID.'],
    broadcast_unknown: ['Submission needs reconciliation', 'The wallet did not confirm whether it sent the transaction. Do not resubmit. Find its EVM hash in wallet activity and resume it below.'],
    wallet_rejected: ['Wallet request declined', 'No transaction was submitted. You can review the form and try again.'],
    safe_error: ['Transaction not submitted', record.error || 'A preflight check failed.'],
    evm_reverted: ['EVM transaction reverted', 'The EVM receipt failed. This is not an application refusal.'],
    protocol_pending: ['Waiting for protocol data', 'The EVM receipt succeeded. Consensus has not yet exposed this transaction.']
  };
  const pair = phases[record.phase] || ['Tracking transaction', 'Reading the current public receipt.'];
  return { title: pair[0], detail: pair[1] };
}
export function snapshotProof(receipt, entry) {
  if (!materialized(receipt) || receipt.status_basis !== 'getTransactionAllData' || !/^[0-9a-f]{64}$/i.test(entry?.snapshot_hash || '')) return null;
  try {
    const outputs = fromRlp(receipt.eqBlocksOutputs, 'hex');
    if (!Array.isArray(outputs) || !/^0x00[0-9a-f]+$/i.test(outputs[0] || '')) return null;
    const text = abi.calldata.decode(hexToBytes(outputs[0]).subarray(1));
    if (typeof text !== 'string' || sha256(text) !== entry.snapshot_hash) return null;
    return { text, hash: entry.snapshot_hash, source: 'getTransactionAllData.eqBlocksOutputs', transaction: receipt.id, eq_block_index: 0, stored_block: receipt.stored_block };
  } catch { return null; }
}
export class LiveHearsay {
  constructor({ publicClient, readClient } = {}) {
    this.public = publicClient || createPublicClient({ chain: CHAIN, transport: http(CHAIN.rpcUrls.default.http[0], { retryCount: 0, timeout: 12000 }) });
    this.reader = readClient || createClient({ chain: CHAIN });
  }
  async read(functionName, args = []) { return plain(await bounded(this.reader.readContract({ address: CONTRACT, functionName, args: args.map(arg => typeof arg === 'number' ? BigInt(arg) : arg), jsonSafeReturn: false, transactionHashVariant: 'latest-nonfinal' }))); }
  async verifiedBlock() {
    demand(equal(CHAIN.consensusMainContract.address, BINDINGS.main) && equal(CHAIN.consensusDataContract.address, BINDINGS.data), 'The SDK consensus binding changed.');
    const block = await this.public.getBlock();
    const read = (spec, functionName, args = []) => this.public.readContract({ ...spec, functionName, args, blockNumber: block.number });
    const checks = await Promise.all([
      read(CHAIN.consensusMainContract, 'VERSION'), read(CHAIN.consensusMainContract, 'addressManager'),
      read({ address: BINDINGS.manager, abi: MANAGER_ABI }, 'getAddress', ['Queues']),
      ...[[BINDINGS.main, BINDINGS.mainImplementation], [BINDINGS.data, BINDINGS.dataImplementation], [BINDINGS.queues, BINDINGS.queueImplementation]].map(async ([address, implementation]) => {
        const storage = await this.public.getStorageAt({ address, slot: SLOT, blockNumber: block.number });
        demand(storage?.slice(-40).toLowerCase() === implementation.slice(2), 'A consensus proxy implementation changed. Tracking is paused until the app is updated.');
      })
    ]);
    demand(checks[0] === '2.0.0' && equal(checks[1], BINDINGS.manager) && equal(checks[2], BINDINGS.queues), 'Unverified consensus version or bindings.');
    return { block, version: checks[0] };
  }
  async receipt(hash, expectedSender) {
    demand(isHash(hash), 'Enter a full transaction hash.');
    const { block, version } = await bounded(this.verifiedBlock());
    const [transaction, rounds] = await this.public.readContract({ ...CHAIN.consensusDataContract, functionName: 'getTransactionAllData', args: [hash], blockNumber: block.number });
    demand(equal(transaction.id, hash), 'The protocol transaction is not available yet.');
    demand(equal(transaction.recipient, CONTRACT), 'This transaction belongs to a different contract.');
    if (expectedSender) demand(equal(transaction.sender, expectedSender), 'This transaction belongs to a different wallet.');
    return normalizeReceipt(transaction, rounds, block, version);
  }
  async entries(spaceId, limit = 1000) {
    const count = Number(await this.read('entry_count'));
    demand(Number.isSafeInteger(count) && count <= limit, 'The entry scan exceeds the browser limit. No duplicate check or verdict match can be claimed; use the CLI to inspect this space.');
    const rows = [];
    for (let start = 0; start < count; start += 8) {
      const batch = await Promise.all(Array.from({ length: Math.min(8, count - start) }, (_, offset) => this.read('get_entry', [start + offset])));
      rows.push(...batch.filter(entry => Number(entry.space_id) === Number(spaceId)));
    }
    return rows;
  }
  async matchEntry(record) {
    if (!materialized(record.receipt) || !record.envelopeHash) return null;
    const rows = await this.entries(record.spaceId);
    return rows.find(entry => entry.envelope_hash === record.envelopeHash && equal(entry.author, record.sender) && entry.entry_class === record.envelope.entry_class && entry.claim === record.envelope.claim && entry.source_url === record.envelope.source_url) || null;
  }
  async matchSpace(record) {
    if (!materialized(record.receipt) || record.method !== 'open_space') return null;
    for (let id = record.firstSpace || 0; id < (record.firstSpace || 0) + 128; id++) {
      let space;
      try { space = await this.read('get_space', [id]); }
      catch (error) { if (/unknown space|does not exist|not found/i.test(errorText(error))) return null; throw error; }
      if (equal(space.owner, record.sender) && space.name === record.spaceName && Number(space.min_rounds) === 2 && String(space.write_bond) === '1000') return space;
    }
    throw new Error('Space scan limit reached. Use the public space selector to locate your new space.');
  }
  async nextSpace() {
    for (let id = 0; id < 128; id++) {
      try { await this.read('get_space', [id]); }
      catch (error) { if (/unknown space|does not exist|not found/i.test(errorText(error))) return id; throw error; }
    }
    throw new Error('Space scan limit reached. Select an existing space for this browser workflow.');
  }
  async protocolFromEvm(record) {
    const receipt = await this.public.getTransactionReceipt({ hash: record.evmHash });
    if (receipt.status === 'reverted') return { reverted: true };
    const logs = receipt.logs.filter(log => equal(log.address, BINDINGS.main));
    const events = [...parseEventLogs({ abi: CHAIN.consensusMainContract.abi, eventName: 'NewTransaction', logs }), ...parseEventLogs({ abi: CREATED_EVENT, eventName: 'CreatedTransaction', logs })];
    demand(equal(receipt.from, record.sender) && equal(receipt.to, BINDINGS.main), 'The EVM receipt belongs to a different submission.');
    const matching = events.find(event => (!event.args.recipient || equal(event.args.recipient, CONTRACT)) && (!event.args.activator || equal(event.args.activator, record.sender)));
    demand(isHash(matching?.args?.txId), 'The EVM receipt has no matching protocol transaction event. No application verdict is counted.');
    return { hash: matching.args.txId, evmBlock: String(receipt.blockNumber) };
  }
}
export class TransactionJournal {
  constructor(storage, notify = () => {}) {
    this.storage = storage; this.notify = notify; this.records = []; this.error = '';
    try {
      const raw = storage.getItem(STORAGE_KEY);
      if (raw) {
        const records = JSON.parse(raw);
        demand(Array.isArray(records) && records.every(record => record.version === 1 && record.contract === CONTRACT && isAddress(record.sender) && (!record.protocolHash || isHash(record.protocolHash)) && (!record.evmHash || isHash(record.evmHash))), 'Saved transaction data is invalid. Preserve wallet activity before clearing this site storage.');
        this.records = records;
        for (const record of this.records) if (['preparing', 'awaiting_wallet'].includes(record.phase)) record.phase = record.sendAttempted ? 'broadcast_unknown' : 'safe_error';
      }
    } catch (error) { this.error = errorText(error); }
  }
  save(record) {
    demand(!this.error, this.error);
    const at = this.records.findIndex(item => item.id === record.id);
    if (at < 0) this.records.unshift(record); else this.records[at] = record;
    // Only public intent, transaction hashes, and reads. Never signed bytes or secrets.
    try { this.storage.setItem(STORAGE_KEY, json(this.records)); }
    catch { this.error = 'Transaction storage is unavailable or full. A wallet send is blocked until the journal can be saved.'; throw new Error(this.error); }
    this.notify(record);
  }
  active() { return this.records.find(record => !terminal(record) && record.readOnly !== true && record.method !== 'tracked'); }
}
export function walletProvider(provider, record, journal, live, getWallet, { onSent = () => {} } = {}) {
  return {
    request: async ({ method, params = [] }) => {
      if (method !== 'eth_sendTransaction') return provider.request({ method, params });
      demand(!record.sendAttempted && !record.evmHash && !record.protocolHash, 'This attempt already reached the wallet. Resume its receipt; do not submit it again.');
      const [accounts, chain] = await Promise.all([provider.request({ method: 'eth_accounts' }), provider.request({ method: 'eth_chainId' })]);
      demand(Number.parseInt(chain, 16) === CHAIN.id, 'Switch your wallet to GenLayer Bradbury Testnet (4221).');
      demand(equal(accounts[0], record.sender) && equal(getWallet(), record.sender), 'The connected wallet account changed. Review the form again.');
      const tx = { ...params[0] };
      demand(equal(tx.from, record.sender) && equal(tx.to, BINDINGS.main) && (tx.chainId === undefined || Number.parseInt(tx.chainId, 16) === CHAIN.id), 'The SDK proposed an unexpected transaction.');
      tx.chainId = '0x' + CHAIN.id.toString(16);
      const decoded = decodeFunctionData({ abi: CHAIN.consensusMainContract.abi, data: tx.data });
      demand(decoded.functionName === 'addTransaction' && equal(decoded.args[0], record.sender) && equal(decoded.args[1], CONTRACT) && Number(decoded.args[2]) === 5 && Number(decoded.args[3]) === 3, 'The SDK proposed different contract or consensus parameters.');
      demand(BigInt(tx.value || '0x0') === BigInt(record.value), 'The SDK proposed a different GEN value.');
      const payload = fromRlp(decoded.args[4], 'hex');
      const call = plain(abi.calldata.decode(hexToBytes(payload[0])));
      demand(call.method === record.method && json(call.args) === json(record.args), 'The SDK proposed different application calldata.');
      await live.verifiedBlock();
      // Measure again immediately before prompting. A failed estimate is never
      // replaced by the SDK's unsafe 200,000 gas fallback.
      const gas = await live.public.estimateGas({ account: record.sender, to: tx.to, data: tx.data, value: BigInt(tx.value || '0x0') });
      tx.gas = '0x' + ((gas * 125n + 99n) / 100n).toString(16);
      const price = await live.public.getGasPrice();
      tx.gasPrice = '0x' + price.toString(16);
      const balance = await live.public.getBalance({ address: record.sender });
      demand(balance >= BigInt(tx.value || '0x0') + BigInt(tx.gas) * price, 'Insufficient funds for the write bond and network fees.');
      const [currentAccounts, currentChain] = await Promise.all([provider.request({ method: 'eth_accounts' }), provider.request({ method: 'eth_chainId' })]);
      demand(equal(currentAccounts[0], record.sender) && equal(getWallet(), record.sender) && Number.parseInt(currentChain, 16) === CHAIN.id, 'Wallet account or network changed during preflight. Review the transaction again.');
      record.phase = 'awaiting_wallet'; record.sendAttempted = true;
      record.intent = { ...tx }; // Unsigned, public calldata; used to reconcile a lost response.
      journal.save(record);
      try {
        const hash = await provider.request({ method, params: [tx] });
        demand(isHash(hash), 'The wallet returned an invalid EVM hash.');
        record.evmHash = hash; record.phase = 'broadcast_pending'; record.error = ''; journal.save(record); onSent(record);
        return hash;
      } catch (error) {
        const rejected = /declined the wallet/.test(errorText(error));
        record.phase = rejected ? 'wallet_rejected' : 'broadcast_unknown'; record.error = errorText(error);
        journal.save(record); throw error;
      }
    }
  };
}
export async function sendWrite({ live, provider, account, journal, record, functionName, args, value = 0n, getWallet, onSent }) {
  demand(!journal.active() || journal.active().id === record.id, 'An earlier transaction is still unresolved. Resume tracking before submitting another.');
  journal.save(record);
  try {
    const wrapped = walletProvider(provider, record, journal, live, getWallet, { onSent });
    const client = createClient({ chain: CHAIN, account, provider: wrapped });
    const hash = await client.writeContract({ address: CONTRACT, functionName, args, value, consensusMaxRotations: 3 });
    demand(isHash(hash), 'The SDK returned an invalid protocol hash.');
    record.protocolHash = hash; record.phase = 'protocol_pending'; record.error = ''; journal.save(record);
    return record;
  } catch (error) {
    if (!record.sendAttempted) record.phase = 'safe_error';
    // A known EVM hash remains resumable even if SDK receipt polling failed.
    record.error = errorText(error); journal.save(record); throw error;
  }
}
