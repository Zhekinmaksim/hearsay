import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { cascade, localGate, envelopeHash, dedupKey } from '../web/lib.mjs';

const envelope = { version: 'hearsay/1', space_id: 0, entry_class: 'honest', claim: 'A correctable claim', source_url: 'https://example.org/b' };
const failed = { entry_id: 0, status: 'UNSOURCED', envelope_hash: envelopeHash(envelope), dedup_key: dedupKey(0, envelope.claim) };
const admitted = { ...failed, entry_id: 1, status: 'ADMITTED' };
const cases = [
  { env: envelope, rows: [failed], retry: false },
  { env: envelope, rows: [failed], retry: true },
  { env: { ...envelope, source_url: 'https://example.org/c' }, rows: [failed], retry: false },
  { env: envelope, rows: [failed, admitted], retry: true },
  { env: { ...envelope, claim: ' a correctable  claim ' }, rows: [failed, admitted], retry: true },
];
const script = `import json,sys
sys.path.insert(0,'cli')
import gate
print(json.dumps([gate.run_gate(c['env'],c['rows'],retry_failed=c['retry'])[0] for c in json.load(sys.stdin)]))`;
const result = spawnSync('python3', ['-c', script], { input: JSON.stringify(cases), encoding: 'utf8' });
assert.equal(result.status, 0, result.stderr);
const python = JSON.parse(result.stdout);
assert.deepEqual(python, [1, 2, 2, 0, 1]);
for (let i = 0; i < cases.length; i++) {
  assert.equal(localGate(cases[i].env, cases[i].rows, cases[i].retry).code, python[i]);
}
const chain = Array.from({ length: 8 }, (_, i) => ({ entry_id: i, status: 'ADMITTED', supports: i ? [i - 1] : [], stands_alone: true }));
const pending = cascade(chain, 0, 1);
assert.equal(pending.state.get(1), 'ADMITTED');
for (let i = 2; i < chain.length; i++) assert.equal(pending.state.get(i), 'TAINTED');
assert.equal(pending.deferred.length, 6);
const batch = cascade(chain, 0, 1, 2);
assert.equal(batch.deferred.length, 4);
assert.equal(batch.state.get(4), 'TAINTED');
const complete = cascade(chain, 0, 1, 16);
assert.equal(complete.deferred.length, 0);
for (let i = 1; i < chain.length; i++) assert.equal(complete.state.get(i), 'ADMITTED');
const dependent = chain.map(row => ({ ...row, stands_alone: false }));
const dead = cascade(dependent, 0, 1, 16);
for (const status of dead.state.values()) assert.equal(status, 'REVOKED');
console.log('5 retry gate parity cases and deep cascade/batched completion regressions passed.');
