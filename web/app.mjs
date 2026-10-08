import { LiveHearsay, TransactionJournal, CONTRACT, CHAIN, BINDINGS, STORAGE_KEY, STATUSES, json, plain, bounded, isHash, errorText, validateClaim, envelopeHash, phaseText, materialized, terminal, snapshotProof, sendWrite, claimIntentFromReceipt, replayableReceipt } from './app-core.mjs';
import { formatEther } from './app-sdk.mjs';

export function mountApp({ window: win = window, document: doc = win.document, live = new LiveHearsay(), provider = win.ethereum, storage, pollInterval = 7000, autoStart = true } = {}) {
  if (storage === undefined) {
    try { storage = win.localStorage; }
    catch { storage = { getItem() { throw new Error('This browser blocked transaction storage. Public reads work, but wallet submission is disabled until storage is available.'); }, setItem() { throw new Error('Transaction storage is blocked.'); } }; }
  }
  const $ = id => doc.getElementById(id);
  const state = { account: '', chainId: null, balance: null, space: null, entries: [], selected: null, busy: false, connectingWallet: false, refreshing: false, polling: false, timer: null, stopped: false, walletError: '', checkedAt: null };
  const text = (id, value) => { $(id).textContent = value; };
  const message = (id, value, error = false) => { const node = $(id); node.textContent = value; node.hidden = !value; node.classList.toggle('error', error); };
  const element = (tag, content, className) => { const node = doc.createElement(tag); if (content !== undefined) node.textContent = String(content); if (className) node.className = className; return node; };
  const link = (href, content, className) => { const node = element('a', content, className); node.href = href; node.target = '_blank'; node.rel = 'noopener noreferrer'; return node; };
  const facts = (rows) => { const dl = element('dl', undefined, 'facts'); for (const [label, value, hash = false] of rows) { const row = element('div'); row.append(element('dt', label)); const dd = element('dd', value, hash ? 'hash' : ''); row.append(dd); dl.append(row); } return dl; };
  const explorer = hash => CHAIN.blockExplorers.default.url.replace(/\/$/, '') + '/tx/' + hash;
  const date = value => new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
  const wei = value => `${String(value)} wei (${formatEther(BigInt(value))} GEN)`;
  const equal = (a, b) => String(a).toLowerCase() === String(b).toLowerCase();
  const journal = new TransactionJournal(storage, record => { if (!state.selected) state.selected = record.id; renderActivity(); renderControls(); });
  if (journal.error) message('global-error', journal.error, true);

  function renderControls() {
    const active = journal.active();
    const chainReady = state.chainId === CHAIN.id;
    $('connect').hidden = !!state.account;
    $('disconnect').hidden = !state.account;
    $('switch-chain').hidden = !state.account || chainReady;
    text('wallet-status', state.account ? state.account : 'No wallet connected.');
    text('wallet-balance', state.account ? `${chainReady ? 'GenLayer Bradbury Testnet · 4221' : 'Wallet is on another network'}${state.balance !== null ? ' · ' + formatEther(state.balance) + ' GEN' : ''}` : 'Your wallet approves each transaction.');
    const benchmark = Number(state.space?.space_id) === 0;
    const reason = journal.error || (state.busy ? 'A transaction is being prepared or approved.' : active ? 'An earlier attempt is unresolved. Resume its receipt below before submitting another transaction.' : !state.account ? 'Connect your wallet to submit.' : !chainReady ? 'Switch your wallet to GenLayer Bradbury Testnet.' : !state.space ? 'Load an open memory space.' : benchmark ? 'Space 0 holds the published benchmark. Create your own space below, or load a separate space.' : !state.space.open ? 'This space is closed.' : 'The wallet will show the bond and network fee before you approve.');
    text('submit-blocked', reason);
    $('claim-submit').disabled = !!journal.error || state.busy || !!active || !state.account || !chainReady || !state.space?.open || benchmark;
    $('create-submit').disabled = !!journal.error || state.busy || !!active || !state.account || !chainReady;
    text('claim-cost', state.space ? `Write bond: ${wei(state.space.write_bond)}. The wallet also pays network fees.` : 'Load a space to see its required write bond.');
    $('connect').disabled = state.busy || state.connectingWallet;
    $('refresh').disabled = state.refreshing;
  }
  function entryView(entry, { matched = false, receipt = null } = {}) {
    const node = element(matched ? 'div' : 'details', undefined, matched ? 'application' : 'entry');
    if (matched) node.append(element('h4', `${entry.status}${Number(receipt?.status) === 5 ? ' · provisional' : ''}`));
    else { const summary = element('summary'); summary.append(element('p', entry.claim, 'claim')); const meta = element('div', undefined, 'meta'); meta.append(element('strong', entry.status), element('span', `Entry ${entry.entry_id} · space ${entry.space_id}`), element('span', `${entry.rounds} readable support rounds`)); summary.append(meta); node.append(summary); }
    if (matched) node.append(element('p', entry.claim, 'claim'));
    if (entry.note) node.append(element('p', entry.note, 'small'));
    node.append(facts([
      ['Source', entry.source_url], ['Author', entry.author, true], ['Votes', `Framing A: ${entry.votes?.a || 'unasked'} · framing B: ${entry.votes?.b || 'unasked'} · consistency: ${entry.votes?.conflict || 'unasked'}`],
      ['Rounds', entry.rounds], ['Snapshot SHA-256', entry.snapshot_hash, true], ['Envelope SHA-256', entry.envelope_hash, true], ['Bond', `${String(entry.bond)} wei · ${entry.bond_state}`], ['Supports', (entry.supports || []).join(', ') || 'None']
    ]));
    try { const source = new URL(entry.source_url); if (['http:', 'https:'].includes(source.protocol)) node.append(link(source.href, 'Open the cited source', 'small')); } catch {}
    node.append(element('p', matched ? 'This application record matches the submitted envelope and sender, with Majority agree and Finished with return in the stored protocol receipt.' : 'Observed contract state. A source snapshot is historical evidence; opening the URL now does not reproduce the original fetch. This read alone does not prove protocol finality.', 'small'));
    return node;
  }
  function renderActivity() {
    const list = $('transactions'); list.replaceChildren();
    if (!journal.records.length) list.append(element('li', 'No local transactions yet.', 'empty'));
    for (const record of journal.records) {
      const item = element('li'); const button = element('button'); button.type = 'button'; button.setAttribute('aria-current', String(record.id === state.selected));
      const phase = phaseText(record); button.append(element('strong', `${record.method === 'open_space' ? 'Create space' : record.method === 'write_entry' ? 'Submit claim' : 'Public transaction'} · ${phase.title}`));
      button.append(element('span', record.protocolHash || record.evmHash || date(record.createdAt), 'hash'));
      button.addEventListener('click', () => { state.selected = record.id; renderActivity(); void pollOnce(); }); item.append(button); list.append(item);
    }
    const record = journal.records.find(item => item.id === state.selected) || journal.records[0];
    const panel = $('receipt-panel'); panel.replaceChildren();
    if (!record) { panel.append(element('p', 'Submit a claim or paste a protocol transaction ID to inspect its current receipt.', 'empty')); return; }
    state.selected = record.id;
    const phase = phaseText(record); panel.append(element('h3', phase.title), element('p', phase.detail, 'small'));
    if (record.error) panel.append(element('p', `${record.error}${record.receipt ? ' The displayed receipt is the last successful observation; it is not a fresh network read.' : ''}`, 'notice error'));
    if (!record.error && record.checkedAt) panel.append(element('p', `Last read ${date(record.checkedAt)}. ${!terminal(record) ? 'Tracking continues automatically while this page is open.' : ''}`, 'small'));
    if (!terminal(record) && Date.now() - record.createdAt > 120000) panel.append(element('p', 'This is taking longer than two minutes. Keep the saved hash; reloading resumes public reads and does not send another transaction.', 'notice'));
    const navigation = element('ol', undefined, 'progress');
    const stages = ['Wallet', 'EVM receipt', 'Pending', 'Proposing', 'Committing', 'Revealing', 'Accepted', 'Finalized'];
    for (const stage of stages) { const item = element('li', stage); if ((record.receipt?.statusName === stage) || (!record.receipt && (stage === 'Wallet' && !record.evmHash || stage === 'EVM receipt' && record.evmHash))) item.setAttribute('aria-current', 'step'); navigation.append(item); } panel.append(navigation);
    panel.append(facts([['Sender', record.sender, true], ['Contract', CONTRACT, true], ['Network', 'GenLayer Bradbury Testnet · 4221'], ['Value', record.value === undefined ? 'Not recorded by this browser' : wei(record.value)]]));
    if (record.evmHash) panel.append(link(explorer(record.evmHash, true), `EVM transaction ${record.evmHash}`, 'hash block'));
    if (record.protocolHash) panel.append(link(explorer(record.protocolHash), `Protocol transaction ${record.protocolHash}`, 'hash block'));
    if (record.receipt) {
      const receipt = record.receipt;
      panel.append(facts([['Protocol result', `${receipt.resultName} (${receipt.result})`], ['Execution', `${receipt.executionName} (${receipt.txExecutionResult})`], ['Stored block', `${receipt.stored_block.number} · ${receipt.stored_block.hash}`, true], ['Protocol rounds', receipt.rounds.length], ['Consensus', `${receipt.numOfInitialValidators} initial validators · ${receipt.initialRotations} rotations · v${receipt.consensus_version}`]]));
      if (materialized(receipt) && record.entry) {
        panel.append(entryView(record.entry, { matched: true, receipt }));
        if (record.proof) {
          const details = element('details', undefined, 'raw'); details.append(element('summary', 'Verified source snapshot bytes'));
          details.append(element('p', `Recovered from stored EQ output 0 and SHA-256 verified against entry ${record.entry.entry_id}. These are the source bytes at judging time, not a live fetch.`, 'small snapshot-note'), element('pre', record.proof.text, 'snapshot-text'));
          panel.append(details);
          const download = element('button', 'Download verified snapshot', 'secondary download'); download.type = 'button'; download.addEventListener('click', () => downloadFile(record.proof.text, `hearsay-entry-${record.entry.entry_id}-snapshot.txt`, 'text/plain;charset=utf-8')); panel.append(download);
          const replay = replayableReceipt(record, record.minRounds);
          if (replay) { const button = element('button', 'Download replayable receipt', 'secondary download'); button.type = 'button'; button.addEventListener('click', () => downloadFile(json(replay), `hearsay-entry-${record.entry.entry_id}-replay.json`, 'application/json')); panel.append(button); panel.append(element('p', 'This flat receipt reproduces the verdict from its recorded votes and verified source bytes with cli/gate.py verify --receipt <file>.', 'small')); }
        } else panel.append(element('p', 'Verified snapshot bytes are unavailable in this stored receipt. Only its hash is displayed; no cached text is offered as proof.', 'small snapshot-note'));
      } else if (materialized(receipt) && record.space) panel.append(element('p', `Space ${record.space.space_id} created for ${record.space.owner}. It is selected above.`, 'notice'));
      else panel.append(element('p', 'No matching application record is verified for this current receipt. The protocol state alone is not a Hearsay verdict.', 'notice'));
      const raw = element('details', undefined, 'raw'); raw.append(element('summary', 'Current canonical receipt & validator rounds'), element('pre', json(receipt))); panel.append(raw);
      const download = element('button', 'Download current receipt', 'secondary download'); download.type = 'button'; download.addEventListener('click', () => downloadFile(json({ transaction: record.protocolHash, evm_transaction: record.evmHash || null, checked_at: record.checkedAt, observation_error: record.error || null, receipt, application_entry: materialized(receipt) ? record.entry || null : null }), `hearsay-${record.protocolHash}.json`, 'application/json')); panel.append(download);
    }
    const refresh = element('button', 'Check receipt now', 'secondary download'); refresh.type = 'button'; refresh.disabled = state.polling; refresh.addEventListener('click', () => void pollOnce()); panel.append(refresh);
  }
  function downloadFile(content, name, type) {
    const url = win.URL.createObjectURL(new win.Blob([content], { type })); const a = element('a'); a.href = url; a.download = name; doc.body.append(a); a.click(); a.remove(); win.setTimeout(() => win.URL.revokeObjectURL(url), 1000);
  }
  function renderSpace() {
    const node = $('space-details'); node.replaceChildren();
    if (!state.space) return;
    const s = state.space;
    const rows = facts([['Space', `${s.space_id} · ${s.name}`], ['Owner', s.owner, true], ['Policy', s.policy], ['Minimum rounds', s.min_rounds], ['Write bond', wei(s.write_bond)], ['Challenge bond', wei(s.challenge_bond)], ['Pool', wei(s.pool)], ['Open', s.open ? 'Yes · anyone may submit' : 'No'], ['Window', `${s.admit_ttl} sequence units`], ['Cascade depth', s.cascade_depth]]);
    node.append(...rows.children); renderControls();
  }
  function renderMemory(report) {
    const node = $('entries'); node.replaceChildren();
    for (const entry of state.entries.slice().reverse()) node.append(entryView(entry));
    if (!state.entries.length) node.append(element('p', 'This space has no recorded entries yet. Submit its first sourced claim above.', 'empty'));
    text('memory-summary', `${state.entries.length} records read in space ${state.space.space_id} · ${date(state.checkedAt)} · current nonfinal contract state.`);
    const stats = $('report'); stats.replaceChildren();
    for (const [value, label] of [[report.honest_attempts, 'Recorded honest attempts'], [report.honest_admitted, 'Honest entries ever admitted'], [state.space.admitted, 'Currently admitted'], [report.deferred, 'Deferred cascade entries']]) { const p = element('p'); p.append(element('strong', value), element('span', label)); stats.append(p); }
    stats.append(element('p', 'The contract report counts materialized records. It does not count unresolved protocol attempts as refusals. Historical admission can differ from current status.', 'small'));
  }
  async function loadSpace(id = Number($('space-id').value)) {
    if (!Number.isSafeInteger(id) || id < 0) throw new Error('Enter a nonnegative integer space ID.');
    text('space-message', 'Reading current space, report, and entries…');
    state.space = null; state.entries = []; renderControls();
    const space = await live.read('get_space', [id]);
    const [report, entries] = await Promise.all([live.read('report', [id]), live.entries(id)]);
    state.space = space; state.entries = entries; state.checkedAt = Date.now(); $('space-id').value = String(id);
    text('space-message', id === 0 ? `Loaded ${space.name}. This benchmark space is read-only here. Create your own space to submit a claim.` : `Loaded ${space.name}. Writes are public; ownership is not required.`); renderSpace(); renderMemory(report); renderControls();
  }
  async function refreshPublic() {
    if (state.refreshing) return;
    state.refreshing = true; renderControls(); text('network-status', 'Checking Bradbury…');
    try {
      const verified = await bounded(live.verifiedBlock());
      const solvency = await live.read('solvency');
      text('solvency', json(solvency));
      await loadSpace();
      text('network-status', solvency.balanced === true ? 'Bradbury connected · accounting balanced' : 'Bradbury connected · accounting mismatch');
      text('network-meta', `Consensus 2.0.0 verified at block ${verified.block.number}. Contract reads use the latest nonfinal state.`);
      if (solvency.balanced !== true) throw new Error('Current contract accounting is unbalanced. Inspect the solvency read before submitting.');
      message('global-error', journal.error || '', !!journal.error);
      await refreshWallet();
    } catch (error) { text('network-status', 'Public read unavailable'); text('network-meta', 'Retry the read. Saved transaction hashes remain in activity.'); message('global-error', errorText(error), true); }
    finally { state.refreshing = false; renderControls(); }
  }
  async function refreshWallet({ request = false } = {}) {
    if (!provider) { if (request) message('wallet-message', 'No injected wallet was found. Open this page in a wallet-enabled browser.', true); return; }
    const accounts = await provider.request({ method: request ? 'eth_requestAccounts' : 'eth_accounts' });
    state.account = accounts[0] || ''; state.chainId = Number.parseInt(await provider.request({ method: 'eth_chainId' }), 16); state.balance = null;
    if (state.account && state.chainId === CHAIN.id) {
      try { state.balance = await live.public.getBalance({ address: state.account }); } catch (error) { message('wallet-message', errorText(error), true); }
    }
    renderControls();
  }
  async function connectWallet() {
    if (state.connectingWallet) return;
    state.connectingWallet = true;
    message('wallet-message', 'Open your wallet to approve this site connection.');
    renderControls();
    try {
      await refreshWallet({ request: true });
      if (state.account) message('wallet-message', 'Wallet connected.');
    } catch (error) {
      message('wallet-message', errorText(error), true);
      throw error;
    } finally {
      state.connectingWallet = false;
      renderControls();
    }
  }
  async function switchChain() {
    if (!provider) return;
    try { await provider.request({ method: 'wallet_switchEthereumChain', params: [{ chainId: '0x' + CHAIN.id.toString(16) }] }); }
    catch (error) { if (Number(error.code) !== 4902) throw error; await provider.request({ method: 'wallet_addEthereumChain', params: [{ chainId: '0x' + CHAIN.id.toString(16), chainName: CHAIN.name, nativeCurrency: CHAIN.nativeCurrency, rpcUrls: [...CHAIN.rpcUrls.default.http], blockExplorerUrls: [CHAIN.blockExplorers.default.url] }] }); }
    await refreshWallet();
  }
  function createRecord(method, data) {
    return { version: 1, id: win.crypto?.randomUUID?.() || 'attempt-' + Date.now(), contract: CONTRACT, chainId: CHAIN.id, sender: state.account, createdAt: Date.now(), phase: 'preparing', method, ...data };
  }
  async function submit(method) {
    if (state.busy) return;
    state.busy = true; renderControls(); let record;
    const msg = method === 'write_entry' ? 'claim-message' : 'wallet-message'; message(msg, 'Checking live state before the wallet prompt…');
    try {
      if (journal.error) throw new Error(journal.error);
      if (journal.active()) throw new Error('An earlier attempt is unresolved. Resume its receipt before submitting another.');
      await refreshWallet();
      if (!state.account || state.chainId !== CHAIN.id) throw new Error('Connect your wallet and switch to GenLayer Bradbury Testnet.');
      let args, value;
      if (method === 'write_entry') {
        const id = Number($('space-id').value);
        const space = await live.read('get_space', [id]);
        const [entries, solvency] = await Promise.all([live.entries(id), live.read('solvency')]);
        if (solvency.balanced !== true) throw new Error('Current contract accounting is unbalanced. Submission is paused.');
        const claim = validateClaim(space, $('claim').value, $('source-url').value, entries);
        args = [BigInt(id), 'honest', claim.serialized]; value = claim.value;
        record = createRecord(method, { args, value: value.toString(), spaceId: id, envelope: claim.envelope, envelopeHash: claim.hash });
      } else {
        const name = $('space-name').value.trim(), policy = $('space-policy').value.trim(), pool = $('pool-value').value.trim();
        if (!name || !policy || !/^\d+$/.test(pool) || BigInt(pool) >= 2n ** 256n) throw new Error('Enter a space name, policy, and a nonnegative wei pool value.');
        const firstSpace = await live.nextSpace();
        args = [name, policy, 1000n, 3n, 2n, 1000n, 2000n]; value = BigInt(pool);
        record = createRecord(method, { args, value: value.toString(), spaceName: name, firstSpace });
      }
      state.selected = record.id;
      await sendWrite({ live, provider, account: state.account, journal, record, functionName: method, args, value, getWallet: () => state.account, onSent: () => { message(msg, 'Transaction sent. Follow its saved EVM and protocol hashes below.'); schedulePoll(0); } });
      message(msg, 'Submitted to GenLayer consensus. The application verdict is not available until a matching record is verified.');
      await pollOnce();
    } catch (error) { message(msg, errorText(error), true); }
    finally { state.busy = false; renderActivity(); renderControls(); schedulePoll(); }
  }
  async function pollRecord(record) {
    if (!record.protocolHash && record.evmHash) {
      const evm = await bounded(live.protocolFromEvm(record));
      if (evm.reverted) { record.phase = 'evm_reverted'; record.entry = null; record.proof = null; record.error = ''; journal.save(record); return; }
      record.protocolHash = evm.hash; record.evmBlock = evm.evmBlock; record.phase = 'protocol_pending'; journal.save(record);
    }
    if (!record.protocolHash) return;
    const receipt = await bounded(live.receipt(record.protocolHash, record.method === 'tracked' ? undefined : record.sender));
    record.receipt = receipt; record.checkedAt = Date.now(); record.error = ''; record.entry = null; record.proof = null; record.space = null;
    if (record.method === 'tracked') {
      record.readOnly = true;
      const intent = claimIntentFromReceipt(receipt);
      if (intent) Object.assign(record, intent);
    }
    // Clear any previous application view as soon as replay changes its status.
    journal.save(record);
    if (materialized(receipt)) {
      if (record.method === 'write_entry') {
        const intent = claimIntentFromReceipt(receipt);
        if (!intent || intent.envelopeHash !== record.envelopeHash) throw new Error('The current stored calldata no longer matches this saved claim intent.');
        record.entry = await live.matchEntry(record);
        if (record.entry) { record.proof = snapshotProof(receipt, record.entry); record.minRounds = Number((await live.read('get_space', [record.spaceId])).min_rounds); }
      }
      if (record.method === 'open_space') { record.space = await live.matchSpace(record); if (record.space) { await loadSpace(Number(record.space.space_id)); } }
      journal.save(record);
    }
  }
  async function pollOnce() {
    if (state.polling || state.stopped) return;
    state.polling = true; renderActivity();
    const selected = journal.records.find(record => record.id === state.selected);
    const records = [...new Set([selected, ...journal.records.filter(record => !terminal(record))].filter(Boolean))];
    for (const record of records) {
      if (!record.evmHash && !record.protocolHash) continue;
      try { await pollRecord(record); }
      catch (error) { record.error = errorText(error); try { journal.save(record); } catch (storageError) { message('global-error', errorText(storageError), true); } }
    }
    state.polling = false; renderActivity(); renderControls(); schedulePoll();
  }
  function schedulePoll(delay = pollInterval) {
    if (state.timer) win.clearTimeout(state.timer);
    if (!state.stopped && journal.records.some(record => !terminal(record) && (record.evmHash || record.protocolHash))) state.timer = win.setTimeout(() => void pollOnce(), delay);
  }
  async function track(hash) {
    hash = hash.trim();
    if (!isHash(hash)) throw new Error('Enter a full 0x-prefixed transaction hash.');
    const existing = journal.records.find(record => equal(record.protocolHash, hash) || equal(record.evmHash, hash));
    if (existing) { state.selected = existing.id; await pollOnce(); return; }
    const ambiguous = journal.records.find(record => record.sendAttempted && !record.evmHash && !record.protocolHash && !terminal(record));
    if (ambiguous) {
      const tx = await live.public.getTransaction({ hash });
      const intent = ambiguous.intent;
      if (!intent || !equal(tx.from, ambiguous.sender) || !equal(tx.to, intent.to) || tx.nonce !== Number(BigInt(intent.nonce)) || !equal(tx.input, intent.data) || BigInt(tx.value) !== BigInt(intent.value)) throw new Error('This EVM transaction does not match the saved wallet intent. No new transaction is sent.');
      ambiguous.evmHash = hash; ambiguous.phase = 'broadcast_pending'; ambiguous.error = ''; journal.save(ambiguous); state.selected = ambiguous.id; await pollOnce(); return;
    }
    const receipt = await live.receipt(hash);
    const intent = claimIntentFromReceipt(receipt);
    const record = { version: 1, id: 'tracked-' + hash, contract: CONTRACT, chainId: CHAIN.id, sender: receipt.sender, createdAt: Date.now(), phase: 'protocol_pending', method: 'tracked', protocolHash: hash, receipt, checkedAt: Date.now(), ...(intent || {}), readOnly: true };
    state.selected = record.id; journal.save(record); await pollOnce(); renderActivity(); schedulePoll();
  }
  const handlers = [];
  const on = (id, event, fn) => { const node = $(id); node.addEventListener(event, fn); handlers.push(() => node.removeEventListener(event, fn)); };
  const action = fn => event => { event.preventDefault(); void fn().catch(error => message('global-error', errorText(error), true)); };
  on('connect', 'click', action(connectWallet));
  on('switch-chain', 'click', action(switchChain));
  on('disconnect', 'click', () => { state.account = ''; state.balance = null; renderControls(); message('wallet-message', 'Disconnected from this page. Saved public transaction hashes keep tracking.'); });
  on('refresh', 'click', () => void refreshPublic());
  on('space-form', 'submit', action(async () => { try { await loadSpace(); } catch (error) { message('space-message', errorText(error), true); throw error; } }));
  on('claim-form', 'submit', event => { event.preventDefault(); void submit('write_entry'); });
  on('create-form', 'submit', event => { event.preventDefault(); void submit('open_space'); });
  on('pool-value', 'input', () => { const value = $('pool-value').value; text('pool-note', /^\d+$/.test(value) ? `${wei(value)} goes to the space pool. The wallet also pays network fees.` : 'Enter the pool value as a nonnegative integer in wei.'); });
  on('example', 'click', () => { $('claim').value = 'Companies House records TESCO PLC (company number 00445790) as an active public limited company incorporated on 27 November 1947.'; $('source-url').value = 'https://find-and-update.company-information.service.gov.uk/company/00445790'; $('example-note').hidden = false; message('claim-message', 'Example inserted. Review the source and submit with your own wallet.'); });
  on('track-form', 'submit', event => { event.preventDefault(); text('track-message', 'Reading the saved or public transaction…'); void track($('track-hash').value).then(() => text('track-message', 'Receipt loaded. Tracking uses public reads only.')).catch(error => text('track-message', errorText(error))); });
  on('entry-form', 'submit', event => { event.preventDefault(); const id = Number($('entry-id').value); text('entry-message', 'Reading entry…'); if (!Number.isSafeInteger(id) || id < 0) { text('entry-message', 'Enter a nonnegative entry ID.'); return; } void live.read('get_entry', [id]).then(entry => { $('entry-detail').replaceChildren(entryView(entry)); text('entry-message', `Entry ${id} loaded from the current nonfinal state.`); }).catch(error => text('entry-message', errorText(error))); });
  const walletChanged = () => { state.account = ''; state.chainId = null; state.balance = null; renderControls(); message('wallet-message', 'Wallet account or network changed. Review the current account before submitting.'); void refreshWallet().catch(error => message('wallet-message', errorText(error), true)); };
  if (provider?.on) { provider.on('accountsChanged', walletChanged); provider.on('chainChanged', walletChanged); provider.on('disconnect', walletChanged); handlers.push(() => { provider.removeListener?.('accountsChanged', walletChanged); provider.removeListener?.('chainChanged', walletChanged); provider.removeListener?.('disconnect', walletChanged); }); }
  renderControls(); renderActivity();
  const ready = autoStart ? Promise.allSettled([refreshPublic(), pollOnce()]) : Promise.resolve();
  return { state, journal, live, ready, refreshPublic, loadSpace, refreshWallet, switchChain, submit, pollOnce, track, renderActivity, destroy() { state.stopped = true; if (state.timer) win.clearTimeout(state.timer); handlers.forEach(fn => fn()); } };
}
if (typeof window !== 'undefined' && typeof document !== 'undefined' && document.getElementById('claim-form')) mountApp();
