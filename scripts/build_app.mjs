#!/usr/bin/env node
// Vercel serves web/ without a build. Rebuild this checked-in browser asset explicitly.
import { build } from './app-build/node_modules/esbuild/lib/main.js';
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const modules = resolve(root, 'scripts/app-build/node_modules');
for (const [name, version] of [['genlayer-js', '1.1.8'], ['viem', '2.50.4']]) {
  if (JSON.parse(readFileSync(resolve(modules, name, 'package.json'))).version !== version) throw new Error('Unexpected dependency version: ' + name);
}
await build({
  stdin: { contents: `export {createClient, abi} from 'genlayer-js';
export {testnetBradbury} from 'genlayer-js/chains';
export {createPublicClient, http, fromRlp, hexToBytes, parseEventLogs, decodeFunctionData, formatEther, parseEther, encodeEventTopics, toRlp, toHex} from 'viem';`, resolveDir: modules, sourcefile: 'hearsay-app-sdk-entry.mjs' },
  outfile: resolve(root, 'web/app-sdk.mjs'), bundle: true, minify: true, format: 'esm', platform: 'browser', target: ['es2022'],
  legalComments: 'eof', banner: { js: '/* Hearsay browser dependencies: genlayer-js 1.1.8 (MIT), viem 2.50.4 (MIT). Rebuild with node scripts/build_app.mjs. */' }
});
writeFileSync(resolve(root, 'web/app-sdk-LICENSE.txt'), ['genlayer-js', 'viem'].map(name => name + '\n' + readFileSync(resolve(modules, name, 'LICENSE'), 'utf8')).join('\n\n'));
console.log('Built web/app-sdk.mjs from pinned browser dependencies.');
