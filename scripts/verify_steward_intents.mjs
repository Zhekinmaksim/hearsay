#!/usr/bin/env node
/* Bind saved live intents to canonical calldata; public data, no signer. */
import { readFileSync, realpathSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
const [runDir, receiptsDir] = process.argv.slice(2);
if (!runDir || !receiptsDir) throw new Error('run directory and receipt directory required');
const cli = resolve(dirname(realpathSync(execFileSync('which', ['genlayer'], { encoding: 'utf8' }).trim())), '..');
const sdk = await import(pathToFileURL(join(cli, 'node_modules/genlayer-js/dist/index.js')));
const { toHex, toRlp } = await import(pathToFileURL(join(cli, 'node_modules/viem/_esm/index.js')));
const read = path => JSON.parse(readFileSync(path));
const ints = x => typeof x === 'number' ? BigInt(x) : Array.isArray(x) ? x.map(ints) : x;
const demand = (ok, why) => { if (!ok) throw new Error(why); };
const manifest = readFileSync(join(runDir, 'transactions.jsonl'), 'utf8').split('\n').filter(Boolean).map(JSON.parse);
const output = [];
for (const row of manifest) {
  const receipt = read(join(receiptsDir, row.id + '.json'));
  const request = read(join(runDir, row.method === 'deploy' ? 'deploy-request.json' : row.id + '.request.json'));
  demand(receipt.status_basis === 'getTransactionAllData' && receipt.txId.toLowerCase() === row.tx.toLowerCase(), 'canonical receipt/id missing');
  demand(receipt.sender.toLowerCase() === request.expected_account.toLowerCase() && String(receipt.value) === String(request.value), 'sender/value mismatch');
  demand(Number(receipt.numOfInitialValidators) === 5 && Number(receipt.initialRotations) === 3, 'consensus policy mismatch');
  const data = toHex(sdk.abi.calldata.encode({ ...(row.method === 'deploy' ? {} : { method: row.method }),
    ...(request.args.length ? { args: request.args.map(ints) } : {}) }));
  let wire;
  if (row.method === 'deploy') {
    const code = readFileSync(request.code_file, 'utf8');
    demand(createHash('sha256').update(code).digest('hex') === request.code_sha256, 'deployment source mismatch');
    wire = toRlp([toHex(code), data, toHex(false)]);
  } else {
    demand(receipt.recipient.toLowerCase() === request.address.toLowerCase(), 'recipient mismatch');
    wire = toRlp([data, toHex(false)]);
  }
  demand(wire.toLowerCase() === receipt.txCalldata.toLowerCase(), 'calldata mismatch: ' + row.id);
  output.push({ id: row.id, tx: row.tx, method: row.method, args: request.args, value: request.value,
    ...(request.envelope_hash ? { envelope_hash: request.envelope_hash } : {}),
    calldata_sha256: createHash('sha256').update(Buffer.from(wire.slice(2), 'hex')).digest('hex'), verified: true });
}
console.log(JSON.stringify(output, null, 2));
