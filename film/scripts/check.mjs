import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createHash } from 'node:crypto';
import { cascade, decide } from '../src/lib.mjs';

const corpus = JSON.parse(fs.readFileSync('src/corpus.json'));
const checkpoint = JSON.parse(fs.readFileSync('src/checkpoint.json'));
const beats = JSON.parse(fs.readFileSync('src/beats.json'));
const sha = value => createHash('sha256').update(value).digest('hex');
assert.equal(corpus.run, 'offline-scripted');
assert.equal(corpus.entries.length, 18);
assert.equal(corpus.report.honest_attempts, 9);
assert.equal(corpus.report.honest_admitted, 9);
for (const row of corpus.entries) {
  assert.equal(sha(row.snapshot_excerpt), row.snapshot_hash, row.id);
  const answer = raw => raw === 'yes' ? true : raw === 'no' ? false : null;
  const a = answer(row.votes.a), b = answer(row.votes.b);
  const conflict = row.votes.conflict === 'none' ? -1 : row.votes.conflict === 'unread' ? null : /^\d+$/.test(row.votes.conflict) ? Number(row.votes.conflict) : -1;
  const result = decide(a, b, Number(a !== null) + Number(b !== null), corpus.policy.min_rounds, conflict, row.votes.a !== 'unasked');
  assert.equal(result[0], row.status, row.id);
}
const walk = cascade(corpus.entries, 0, corpus.policy.cascade_depth);
assert(walk.steps.some(row => row.became === 'DEFERRED'));
assert(walk.steps.some(row => row.rejudged && row.became === 'ADMITTED'));
assert.equal(checkpoint.complete, false);
assert.equal(checkpoint.defence_conclusion, null);
assert.equal(checkpoint.published_checkpoint_sha256, sha(fs.readFileSync('../web/bradbury-prompt-checkpoint.json')));
const videoEvidence = JSON.parse(fs.readFileSync('../web/demo/evidence.json'));
assert.deepEqual(videoEvidence.checkpoint, checkpoint, 'Published video has stale checkpoint metadata; render it again.');
assert.equal(videoEvidence.video_sha256, sha(fs.readFileSync('../web/demo/hearsay.mp4')));
for (const [file, hash] of Object.entries(videoEvidence.input_sha256)) assert.equal(sha(fs.readFileSync(file)), hash, `Video input changed: ${file}`);
assert.equal(beats.duration, 60);
assert.equal(beats.fps, 30);
assert(beats.downbeats.every((value, index, list) => value >= 0 && value < 60 && (!index || value > list[index - 1])));
console.log('18 source pins and vote replays, bounded cascade, checkpoint/video binding and beat timeline verified.');
