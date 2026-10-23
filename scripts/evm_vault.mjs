/* Reviewed native-EVM vault operations. Keys stay in the CLI OS keychain;
 * only public intent, hashes and receipts are persisted. Default is read-only. */
import { readFileSync, writeFileSync, existsSync, appendFileSync, realpathSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
import { broadcastWithJournal } from './broadcast.mjs';
import { VERIFIED_BINDINGS } from './queue_progress.mjs';

const option = name => { const i = process.argv.indexOf(name); return i < 0 ? '' : process.argv[i + 1]; };
const demand = (ok, message) => { if (!ok) throw new Error(message); };
const normalize = value => JSON.stringify(value, (_, v) => typeof v === 'bigint' ? v.toString() : v, 2);
const rows = path => existsSync(path) ? readFileSync(path, 'utf8').split('\n').filter(Boolean).map(JSON.parse) : [];
const sha = data => createHash('sha256').update(data).digest('hex');
const GENESIS = '0xef97917ce9bd9fa7d12ad6a8d81ea26c80ac1d727acc37cbb9799ae199788dc5';

async function main() {
  const requestPath = option('--request'), manifest = option('--manifest');
  demand(requestPath && manifest, '--request and --manifest required');
  const r = JSON.parse(readFileSync(requestPath));
  demand(['deploy', 'bindController', 'claim', 'claim_failure', 'protocol_idle', 'protocol_finalize', 'protocol_appeal'].includes(r.method), 'unknown vault operation');
  const protocol = r.method.startsWith('protocol_');
  demand(/^0x[0-9a-f]{40}$/i.test(r.expected_account) && typeof r.id === 'string', 'reviewed account/id required');
  const previous = rows(manifest).find(x => x.id === r.id);
  if (previous) { console.log(normalize({ resumed: true, ...previous })); return; }
  demand(!rows(manifest + '.broadcasts.jsonl').some(x => x.id === r.id), 'reconcile the existing broadcast before any retry');
  demand(r.max_fee_wei && BigInt(r.max_fee_wei) <= 50_000_000_000_000_000n, 'fee cap missing or too high');
  const cli = resolve(dirname(realpathSync(execFileSync('which', ['genlayer'], { encoding: 'utf8' }).trim())), '..');
  const viem = await import(pathToFileURL(join(cli, 'node_modules/viem/_esm/index.js')));
  const chains = await import(pathToFileURL(join(cli, 'node_modules/genlayer-js/dist/chains/index.js')));
  const { createPublicClient, createWalletClient, http, encodeFunctionData, keccak256, parseTransaction } = viem;
  const chain = chains.testnetBradbury;
  const publicClient = createPublicClient({ chain, transport: http(undefined, { retryCount: 0 }) });
  const [genesis, chainId, block, version, pending, mined, balance, gasPrice] = await Promise.all([
    publicClient.getBlock({ blockNumber: 0n }), publicClient.getChainId(), publicClient.getBlock(),
    publicClient.readContract({ ...chain.consensusMainContract, functionName: 'VERSION' }),
    publicClient.getTransactionCount({ address: r.expected_account, blockTag: 'pending' }),
    publicClient.getTransactionCount({ address: r.expected_account, blockTag: 'latest' }),
    publicClient.getBalance({ address: r.expected_account }), publicClient.getGasPrice(),
  ]);
  demand(chainId === 4221 && genesis.hash === GENESIS && version === '2.0.0', 'wrong Bradbury deployment');
  for (const [address, expected] of [[VERIFIED_BINDINGS.main, VERIFIED_BINDINGS.mainImplementation], [VERIFIED_BINDINGS.data, VERIFIED_BINDINGS.dataImplementation]]) {
    const value = await publicClient.getStorageAt({ address, slot: '0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc', blockNumber: block.number });
    demand(value?.slice(-40).toLowerCase() === expected.slice(2), 'unverified consensus implementation');
  }
  demand(pending === mined && pending === r.expected_nonce, 'nonce changed or a previous account transaction is pending');
  const artifactBytes = readFileSync(r.artifact);
  demand(sha(artifactBytes) === r.artifact_sha256, 'artifact differs from reviewed pin');
  const artifact = JSON.parse(artifactBytes);
  if (protocol) {
    demand(r.address?.toLowerCase() === VERIFIED_BINDINGS.main, 'protocol target must be verified ConsensusMain');
    demand(/^0x[0-9a-f]{64}$/i.test(r.argument) && /^0x[0-9a-f]{40}$/i.test(r.required_recipient), 'protocol transaction/recipient pin required');
    const [tx] = await publicClient.readContract({ ...chain.consensusDataContract, functionName: 'getTransactionAllData', args: [r.argument] });
    demand(tx.id.toLowerCase() === r.argument.toLowerCase() && tx.recipient.toLowerCase() === r.required_recipient.toLowerCase() && tx.sender.toLowerCase() === r.expected_account.toLowerCase(), 'foreign protocol transaction');
  }
  const data = r.method === 'deploy' ? '0x' + artifact.evm.bytecode.object : encodeFunctionData({ abi: artifact.abi, functionName: protocol ? ({ protocol_idle: 'processIdleness', protocol_finalize: 'finalizeTransaction', protocol_appeal: 'submitAppeal' }[r.method]) : r.method === 'bindController' ? 'bindController' : 'claim', args: [r.argument] });
  const to = r.method === 'deploy' ? undefined : r.address;
  if (to && !protocol) {
    demand(/^0x[0-9a-f]{40}$/i.test(to), 'invalid vault address');
    let expected = artifact.evm.deployedBytecode.object;
    for (const references of Object.values(artifact.evm.deployedBytecode.immutableReferences)) {
      for (const ref of references) {
        const value = r.expected_account.slice(2).toLowerCase().padStart(ref.length * 2, '0');
        expected = expected.slice(0, ref.start * 2) + value + expected.slice((ref.start + ref.length) * 2);
      }
    }
    demand((await publicClient.getCode({ address: to }))?.toLowerCase() === '0x' + expected.toLowerCase(), 'vault runtime differs from reviewed artifact');
    const binder = await publicClient.readContract({ address: to, abi: artifact.abi, functionName: 'binder' });
    demand(binder.toLowerCase() === r.expected_account.toLowerCase(), 'foreign vault binder');
  }
  let gas;
  if (r.method === 'claim_failure') {
    demand(r.argument?.toLowerCase() === to.toLowerCase(), 'failure test must use vault itself as rejecting recipient');
    let refused = false;
    try { await publicClient.call({ account: r.expected_account, to, data }); }
    catch (error) { refused = /delivery failed/i.test(error.shortMessage || error.message); }
    demand(refused, 'expected payment refusal not reproduced by eth_call');
    gas = 200000n;
  } else {
    gas = (await publicClient.estimateGas({ account: r.expected_account, to, data, value: 0n }) * 125n + 99n) / 100n;
  }
  demand(gas * gasPrice <= BigInt(r.max_fee_wei) && balance >= gas * gasPrice, 'fee budget/balance insufficient');
  const plan = { id: r.id, method: r.method, account: r.expected_account, to: to || null, nonce: pending,
    chain_id: chainId, genesis: genesis.hash, block: String(block.number), gas: String(gas), gas_price: String(gasPrice), maximum_fee_wei: String(gas * gasPrice),
    calldata_sha256: sha(Buffer.from(data.slice(2), 'hex')), artifact_sha256: r.artifact_sha256 };
  writeFileSync(requestPath + '.plan.json', normalize(plan) + '\n');
  if (!process.argv.includes('--send')) { console.log(normalize(plan)); return; }
  const configPath = process.env.GENLAYER_CONFIG || join(process.env.HOME, '.genlayer/genlayer-config.json');
  const config = JSON.parse(readFileSync(configPath));
  const keytar = (await import(pathToFileURL(join(cli, 'node_modules/keytar/lib/keytar.js')))).default;
  const key = await keytar.getPassword('genlayer-cli', 'account:' + config.activeAccount);
  demand(key, 'unlock the active GenLayer CLI account');
  const sdk = await import(pathToFileURL(join(cli, 'node_modules/genlayer-js/dist/index.js')));
  const account = sdk.createAccount(key);
  demand(account.address.toLowerCase() === r.expected_account.toLowerCase(), 'active account differs from reviewed account');
  const current = await publicClient.getTransactionCount({ address: account.address, blockTag: 'pending' });
  demand(current === pending, 'nonce changed before signing');
  const wallet = createWalletClient({ chain, account, transport: http(undefined, { retryCount: 0 }) });
  const signed = await wallet.signTransaction({ account, chain, chainId, nonce: pending, to, data, gas, gasPrice, type: 'legacy', value: 0n });
  const parsed = parseTransaction(signed);
  demand(Number(parsed.chainId) === chainId && Number(parsed.nonce) === pending && parsed.gas === gas && parsed.gasPrice === gasPrice &&
    (parsed.to || '').toLowerCase() === (to || '').toLowerCase() && (parsed.value || 0n) === 0n && parsed.data === data,
    'signed transaction differs from reviewed plan');
  const hash = keccak256(signed);
  await broadcastWithJournal({ serializedTransaction: signed }, args => publicClient.sendRawTransaction(args),
    { path: manifest + '.broadcasts.jsonl', expectedHash: hash, method: r.method, id: r.id });
  const record = { ...plan, tx: hash };
  appendFileSync(manifest, normalize(record).replace(/\n\s*/g, '') + '\n');
  console.log(normalize(record));
}

main().catch(error => { console.error(error.shortMessage || error.message); process.exitCode = 1; });
