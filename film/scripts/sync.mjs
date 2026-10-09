/* Build film inputs from the reviewed published data. Never write back to web. */
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';

const film = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const root = path.resolve(film, '..');
const sha = text => createHash('sha256').update(text).digest('hex');
const corpus = JSON.parse(fs.readFileSync(path.join(root, 'web/corpus.json'), 'utf8'));
const seed = JSON.parse(fs.readFileSync(path.join(root, 'corpus/seed.json'), 'utf8'));
const pages = Object.fromEntries(seed.entries.filter(row => row.page !== null).map(row => [row.source_url, row.page]));
if (corpus.run !== 'offline-scripted') throw new Error('The explainer requires the offline scripted corpus; do not mix live and fictional rows.');
for (const row of corpus.entries) {
  const candidate = seed.entries.find(item => item.id === row.id);
  if (!candidate || candidate.claim !== row.claim || candidate.source_url !== row.source_url) throw new Error(`Seed mismatch: ${row.id}`);
  const text = pages[row.source_url] ?? '';
  if (sha(text) !== row.snapshot_hash) throw new Error(`Source pin mismatch: ${row.id}`);
  row.snapshot_excerpt = text;
}
const checkpointBytes = fs.readFileSync(path.join(root, 'web/bradbury-prompt-checkpoint.json'));
const checkpoint = JSON.parse(checkpointBytes);
if (checkpoint.complete !== false || checkpoint.defence_conclusion !== null || checkpoint.consensus_version !== '2.0.0'
  || !checkpoint.report_matches_verified_entries || !checkpoint.solvency.balanced
  || checkpoint.coverage.honest_judged !== checkpoint.entries.filter(row => row.entry_class === 'honest').length)
  throw new Error('Checkpoint must be a verified, explicitly incomplete snapshot.');
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'hearsay-film-verify-'));
try {
  for (const row of checkpoint.entries) {
    if (!row.snapshot_verified || sha(row.snapshot_excerpt) !== row.snapshot_hash) throw new Error(`Live source pin mismatch: ${row.id}`);
    const receipt = path.join(temp, 'receipt.json');
    fs.writeFileSync(receipt, JSON.stringify(row));
    const result = spawnSync('python3', ['cli/gate.py', 'verify', '--receipt', receipt], { cwd: root, encoding: 'utf8' });
    if (result.error || result.status !== 0) throw new Error(`Live receipt does not reproduce: ${row.id}: ${result.stderr || result.stdout}`);
  }
} finally { fs.rmSync(temp, { recursive: true, force: true }); }
const summary = {
  checked_at: checkpoint.checked_at, contract_address: checkpoint.contract_address,
  complete: checkpoint.complete, defence_conclusion: checkpoint.defence_conclusion,
  required_honest_judgements: checkpoint.required_honest_judgements,
  coverage: checkpoint.coverage, source_sha256: checkpoint.source_sha256,
  published_checkpoint_sha256: sha(checkpointBytes),
};
fs.writeFileSync(path.join(film, 'src/corpus.json'), JSON.stringify(corpus, null, 2) + '\n');
fs.copyFileSync(path.join(root, 'web/lib.mjs'), path.join(film, 'src/lib.mjs'));
fs.writeFileSync(path.join(film, 'src/checkpoint.json'), JSON.stringify(summary, null, 2) + '\n');
console.log(`Synced ${corpus.entries.length} offline receipts and dated checkpoint ${summary.coverage.honest_judged}/${summary.required_honest_judgements}; published web files unchanged.`);
