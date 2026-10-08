/* Drive the actual app markup/module offline. These checks exercise public read
 * states, saved hashes, replay invalidation, and wallet account/chain changes. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';
import { mountApp } from '../web/app.mjs';
import { CONTRACT, CHAIN, BINDINGS, STORAGE_KEY, envelopeHash, json, claimIntentFromReceipt, replayableReceipt } from '../web/app-core.mjs';
import { abi, toRlp, toHex } from '../web/app-sdk.mjs';
import { sha256 } from '../web/lib.mjs';
const sender = '0x' + '12'.repeat(20), other = '0x' + '14'.repeat(20);
const hash = '0x' + '34'.repeat(32), evmHash = '0x' + '45'.repeat(32), blockHash = '0x' + '56'.repeat(32);
const env = { version: 'hearsay/1', space_id: 1, entry_class: 'honest', claim: 'An authoritative registry records this company as active.', source_url: 'https://example.org/official' };
const snapshot = 'Official registry source. Company status: Active.';
const calldata = (method = 'write_entry', args = [1n, 'honest', JSON.stringify(env)]) => toRlp([toHex(abi.calldata.encode({ method, args })), toHex(false)]);
const entry = { entry_id: 0n, space_id: 1n, author: sender, entry_class: 'honest', claim: env.claim, source_url: env.source_url, status: 'ADMITTED', note: '', rounds: 2n, snapshot_hash: sha256(snapshot), envelope_hash: envelopeHash(env), votes: { a: 'yes', b: 'yes', conflict: 'none' }, supports: [], bond: 1000n, bond_state: 'LOCKED' };
const baseReceipt = { id: hash, sender, recipient: CONTRACT, status: 5, statusName: 'Accepted', result: 1, resultName: 'Majority agree', txExecutionResult: 1, executionName: 'Finished with return', numOfInitialValidators: 5n, initialRotations: 3n, rounds: [{ votesCommitted: 5n, votesRevealed: 5n, validatorVotes: [1, 1, 1, 1, 1] }], status_basis: 'getTransactionAllData', consensus_version: '2.0.0', stored_block: { number: '33', hash: blockHash }, txCalldata: calldata(), eqBlocksOutputs: toRlp([toHex(new Uint8Array([0, ...abi.calldata.encode(snapshot)]))]), value: 1000n };
let passes = 0;
function check(title, fn) { fn(); passes++; console.log('ok ' + title); }
function fixture({ stored = null, receipt = baseReceipt, networkError = false, noProvider = false } = {}) {
  const dom = new JSDOM(readFileSync(new URL('../web/app.html', import.meta.url), 'utf8'), { url: 'https://hearsay.test/app.html', pretendToBeVisual: true });
  if (stored) dom.window.localStorage.setItem(STORAGE_KEY, json([stored]));
  let current = receipt, account = sender, chain = '0x107d', requests = [], callbacks = {};
  const provider = noProvider ? undefined : { on: (name, fn) => callbacks[name] = fn, removeListener: name => delete callbacks[name], async request({ method, params }) {
    requests.push({ method, params });
    if (method === 'eth_accounts' || method === 'eth_requestAccounts') return [account];
    if (method === 'eth_chainId') return chain;
    if (method === 'wallet_switchEthereumChain') { if (chain === '0x999') throw { code: 4902 }; chain = params[0].chainId; return null; }
    if (method === 'wallet_addEthereumChain') { chain = params[0].chainId; return null; }
    throw new Error('A write was not expected in this DOM read test');
  } };
  const live = {
    public: { async getBalance() { return 10000000n; }, async getTransaction() { return { from: sender, to: BINDINGS.main, nonce: 1, input: '0xdead', value: 1000n }; } },
    async verifiedBlock() { if (networkError) throw new Error('Public RPC offline'); return { block: { number: 33n }, version: '2.0.0' }; },
    async read(method, args = []) { if (networkError) throw new Error('Public RPC offline'); if (method === 'solvency') return { balanced: true, held: 1000n }; if (method === 'get_space') return { space_id: args[0], name: 'Registry memory', owner: sender, policy: 'Official sources', write_bond: 1000n, challenge_bond: 2000n, pool: 500000n, min_rounds: 2, admit_ttl: 1000, cascade_depth: 3, admitted: 1, open: true }; if (method === 'report') return { honest_attempts: 1, honest_admitted: 1, deferred: 0 }; if (method === 'get_entry') return entry; throw new Error('Unexpected read: ' + method); },
    async entries(id) { return Number(id) === 1 ? [entry] : []; },
    async receipt(tx, expected) { assert.equal(tx, hash); if (expected) assert.equal(expected, sender); return current; },
    async matchEntry(record) { assert.equal(record.envelopeHash, entry.envelope_hash); return entry; },
    async protocolFromEvm(record) { assert.equal(record.evmHash, evmHash); return { hash, evmBlock: '32' }; }
  };
  const app = mountApp({ window: dom.window, live, provider, autoStart: false, pollInterval: 1000000 });
  return { dom, app, requests, live, setReceipt(value) { current = value; }, changeAccount(value) { account = value; callbacks.accountsChanged?.([value]); }, changeChain(value) { chain = value; callbacks.chainChanged?.(value); } };
}
let f = fixture({ noProvider: true });
await f.app.refreshPublic();
check('public reads and empty memory work with no injected wallet', () => { assert.match(f.dom.window.document.getElementById('network-status').textContent, /connected/); assert.match(f.dom.window.document.getElementById('entries').textContent, /no recorded entries/); assert(f.dom.window.document.getElementById('claim-submit').disabled); });
f.dom.window.document.getElementById('example').click();
check('source example inserts the exact source URL without sending anything', () => { assert.match(f.dom.window.document.getElementById('claim').value, /TESCO PLC/); assert.equal(f.dom.window.document.getElementById('source-url').value, 'https://find-and-update.company-information.service.gov.uk/company/00445790'); assert.equal(f.requests.length, 0); });
f.app.destroy();
f = fixture({ networkError: true });
await f.app.refreshPublic();
check('network failure is shown explicitly and retry remains available', () => { const d = f.dom.window.document; assert.match(d.getElementById('global-error').textContent, /offline/); assert.equal(d.getElementById('network-status').textContent, 'Public read unavailable'); assert(!d.getElementById('refresh').disabled); });
f.app.destroy();
f = fixture(); await f.app.refreshWallet(); await f.app.loadSpace(0);
check('benchmark space is read-only while create-own-space remains enabled', () => { const d = f.dom.window.document; assert(d.getElementById('claim-submit').disabled); assert(!d.getElementById('create-submit').disabled); assert.match(d.getElementById('submit-blocked').textContent, /published benchmark/); });
await f.app.loadSpace(1);
check('own nonzero open space enables a genuine wallet submission', () => assert(!f.dom.window.document.getElementById('claim-submit').disabled));
await f.app.track(hash);
check('public accepted transaction binds canonical calldata to an actual application entry', () => { const d = f.dom.window.document; assert.match(d.getElementById('receipt-panel').textContent, /Accepted · provisional/); assert.match(d.getElementById('receipt-panel').textContent, /ADMITTED · provisional/); assert(d.getElementById('receipt-panel').textContent.includes(snapshot)); assert([...d.getElementById('receipt-panel').querySelectorAll('button')].some(button => button.textContent === 'Download replayable receipt')); assert.equal(f.app.journal.active(), undefined); assert(!d.getElementById('claim-submit').disabled); assert.equal(f.requests.filter(x => x.method === 'eth_sendTransaction').length, 0); });
check('protocol explorer links use the actual /tx/ route', () => assert([...f.dom.window.document.getElementById('receipt-panel').querySelectorAll('a')].some(a => a.href.includes('/tx/' + hash))));
f.setReceipt({ ...baseReceipt, status: 13, statusName: 'Leader timeout', txExecutionResult: 3, executionName: 'Timeout' });
await f.app.pollOnce();
check('replay timeout removes the old verdict and all proof/replay downloads', () => { const panel = f.dom.window.document.getElementById('receipt-panel'); assert.match(panel.textContent, /not a refusal/); assert(!panel.querySelector('.application')); assert(![...panel.querySelectorAll('button')].some(button => /snapshot|replayable/.test(button.textContent))); assert.equal(f.app.journal.records[0].entry, null); assert.equal(f.app.journal.records[0].proof, null); assert(!f.dom.window.document.getElementById('claim-submit').disabled); });
f.changeAccount(other); await new Promise(resolve => setTimeout(resolve, 0));
check('account change is immediately reflected in the reviewed wallet', () => assert.equal(f.app.state.account, other));
f.changeChain('0x999'); await new Promise(resolve => setTimeout(resolve, 0));
check('wrong chain disables writing and exposes the explicit switch control', () => { const d = f.dom.window.document; assert(d.getElementById('claim-submit').disabled); assert(!d.getElementById('switch-chain').hidden); });
await f.app.switchChain();
check('unknown Bradbury chain is added using exact chain/RPC/currency/explorer settings', () => { const request = f.requests.find(x => x.method === 'wallet_addEthereumChain'); assert.equal(request.params[0].chainId, '0x107d'); assert.equal(request.params[0].chainName, CHAIN.name); assert.deepEqual(request.params[0].rpcUrls, CHAIN.rpcUrls.default.http); assert.equal(f.app.state.chainId, 4221); });
f.app.destroy();
f = fixture({ stored: { version: 1, id: 'legacy-public-watch', contract: CONTRACT, sender, createdAt: Date.now(), method: 'tracked', phase: 'protocol_pending', protocolHash: hash, receipt: { ...baseReceipt, status: 7, statusName: 'Finalized' } } });
await f.app.pollOnce();
check('old saved public watches infer the claim safely from a fresh canonical receipt', () => { assert.equal(f.app.journal.records[0].envelopeHash, envelopeHash(env)); assert.equal(f.app.journal.records[0].readOnly, true); assert.equal(f.app.journal.active(), undefined); assert([...f.dom.window.document.getElementById('receipt-panel').querySelectorAll('button')].some(button => button.textContent === 'Download replayable receipt')); });
f.app.destroy();
const own = { version: 1, id: 'own-send', contract: CONTRACT, sender, createdAt: Date.now(), method: 'write_entry', phase: 'broadcast_pending', sendAttempted: true, evmHash, args: [1, 'honest', JSON.stringify(env)], envelope: env, envelopeHash: envelopeHash(env), spaceId: 1, value: '1000' };
f = fixture({ stored: own }); await f.app.refreshWallet(); await f.app.loadSpace(1);
check('saved own EVM acknowledgement blocks a duplicate while public tracking resumes', () => assert(f.dom.window.document.getElementById('claim-submit').disabled));
await f.app.pollOnce();
check('reload recovers the protocol ID from the existing EVM hash without wallet sends', () => { assert.equal(f.app.journal.records[0].protocolHash, hash); assert.equal(f.requests.filter(x => x.method === 'eth_sendTransaction').length, 0); });
f.app.destroy();
f = fixture({ stored: { ...own, phase: 'awaiting_wallet', evmHash: undefined, intent: { to: BINDINGS.main, nonce: '0x1', data: '0xbeef', value: '0x3e8' } } });
check('reload during wallet uncertainty keeps intent and stops duplicate sending', () => { assert.equal(f.app.journal.active().phase, 'broadcast_unknown'); assert(f.dom.window.document.getElementById('claim-submit').disabled); });
await assert.rejects(f.app.track(evmHash), /does not match/); passes++;
check('a mismatched EVM hash never reconciles an uncertain wallet send', () => assert.equal(f.app.journal.active().evmHash, undefined));
f.app.destroy();
check('stored public claim class/space/version mismatch is blocked', () => {
  assert.throws(() => claimIntentFromReceipt({ ...baseReceipt, txCalldata: calldata('write_entry', [1n, 'source_forgery', JSON.stringify(env)]) }), /does not match/);
  assert.throws(() => claimIntentFromReceipt({ ...baseReceipt, txCalldata: calldata('write_entry', [2n, 'honest', JSON.stringify(env)]) }), /does not match/);
  assert.throws(() => claimIntentFromReceipt({ ...baseReceipt, txCalldata: calldata('write_entry', [1n, 'honest', JSON.stringify({ ...env, version: 'other' })]) }), /does not match/);
  assert.throws(() => claimIntentFromReceipt({ ...baseReceipt, txCalldata: calldata('write_entry', [1n, 'honest', JSON.stringify({ ...env, ignoredKey: true })]) }), /cannot be reproduced/);
  assert.equal(claimIntentFromReceipt({ ...baseReceipt, txCalldata: calldata('fund_space', [1n]) }), null);
});
console.log(`app page: ${passes} checks passed (offline, zero real sends).`);
