#!/usr/bin/env node
/* Public, read-only deployment verification. No wallet/keychain access. */
import { readFileSync, realpathSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';

const sha = value => createHash('sha256').update(value).digest('hex');
const demand = (ok, message) => { if (!ok) throw new Error(message); };
const meta = JSON.parse(readFileSync(process.argv[2] || 'deployments/bradbury-steward-final.json'));
const artifactBytes = readFileSync('deployments/hearsay-payout-vault.json');
demand(sha(artifactBytes) === meta.vault.artifact_sha256, 'vault artifact pin mismatch');
const artifact = JSON.parse(artifactBytes);
const cli = resolve(dirname(realpathSync(execFileSync('which', ['genlayer'], { encoding: 'utf8' }).trim())), '..');
const sdk = await import(pathToFileURL(join(cli, 'node_modules/genlayer-js/dist/index.js')));
const chains = await import(pathToFileURL(join(cli, 'node_modules/genlayer-js/dist/chains/index.js')));
const { createPublicClient, http } = await import(pathToFileURL(join(cli, 'node_modules/viem/_esm/index.js')));
const client = createPublicClient({ chain: chains.testnetBradbury, transport: http(meta.rpc, { retryCount: 0 }) });
const intelligent = sdk.createClient({ chain: chains.testnetBradbury, endpoint: meta.rpc });
const block = await client.getBlock();
const genesis = await client.getBlock({ blockNumber: 0n });
demand((await client.getChainId()) === meta.chain_id && genesis.hash === meta.genesis, 'wrong chain: chain ID alone is insufficient');
const code = await intelligent.getContractCode(meta.address);
demand(sha(code) === meta.deployment_source_sha256, 'Intelligent Contract deployment source mismatch');
demand(sha(readFileSync('contracts/hearsay.py')) === meta.source_sha256, 'local IC source differs from deployed source pin');
demand(sha(readFileSync('contracts/HearsayPayoutVault.sol')) === meta.vault.source_sha256, 'local vault source differs from deployed source pin');
let expected = artifact.evm.deployedBytecode.object;
for (const refs of Object.values(artifact.evm.deployedBytecode.immutableReferences)) {
  for (const ref of refs) {
    const binder = meta.vault.binder.slice(2).toLowerCase().padStart(ref.length * 2, '0');
    expected = expected.slice(0, ref.start * 2) + binder + expected.slice((ref.start + ref.length) * 2);
  }
}
const runtime = await client.getCode({ address: meta.vault.address, blockNumber: block.number });
demand(runtime?.toLowerCase() === '0x' + expected.toLowerCase(), 'vault runtime mismatch');
const view = functionName => client.readContract({ address: meta.vault.address, abi: artifact.abi, functionName, blockNumber: block.number });
const [binder, controller, deployment, binding] = await Promise.all([
  view('binder'), view('controller'),
  client.getTransactionReceipt({ hash: meta.vault.deployment_tx }),
  client.getTransactionReceipt({ hash: meta.vault.binding_tx }),
]);
demand(binder.toLowerCase() === meta.vault.binder.toLowerCase() && controller.toLowerCase() === meta.address.toLowerCase(), 'vault controller/binder mismatch');
demand(deployment.status === 'success' && binding.status === 'success' && deployment.contractAddress.toLowerCase() === meta.vault.address.toLowerCase(), 'vault deployment/binding failed');
console.log(JSON.stringify({ checked_at: new Date().toISOString(), network: meta.network, genesis: genesis.hash,
  block: { number: String(block.number), hash: block.hash }, address: meta.address,
  deployment_source_verified: true, deployment_source_sha256: sha(code),
  vault: { address: meta.vault.address, binder, controller, runtime_verified: true,
    runtime_sha256: sha(Buffer.from(runtime.slice(2), 'hex')), deployment, binding } },
(_, value) => typeof value === 'bigint' ? value.toString() : value, 2));
