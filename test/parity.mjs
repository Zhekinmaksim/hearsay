/* The page implements hashing, flattening and verdict assembly a third time,
 * in JavaScript. This is what makes that tolerable.
 *
 *     node test/parity.mjs
 *
 * Vectors are emitted by the Python side (test/vectors.json, written by
 * test/run_tests.py) and checked here. A drift in either direction is a failure
 * with the offending vector printed, because a gate that disagrees with the
 * contract about what counts as a duplicate is worse than no gate.
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { sha256, flatten, dedupKey, canonical, envelopeHash, defuse, fence, decide } from "../web/lib.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const V = JSON.parse(readFileSync(join(ROOT, "test", "vectors.json"), "utf-8"));

let pass = 0;
const fail = [];

function check(name, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (ok) { pass++; } else { fail.push({ name, got, want }); }
  console.log((ok ? "  ok   " : "  FAIL ") + name);
}

for (const [i, v] of V.sha256.entries()) {
  check(`sha256 vector ${i}`, sha256(v.input), v.want);
}
for (const [i, v] of V.flatten.entries()) {
  check(`flatten vector ${i}`, flatten(v.input), v.want);
}
for (const [i, v] of V.dedup.entries()) {
  check(`dedup key vector ${i}`, dedupKey(v.space_id, v.claim), v.want);
}
for (const [i, v] of V.canonical.entries()) {
  check(`canonical vector ${i}`, canonical(v.input), v.want);
  check(`envelope hash vector ${i}`, envelopeHash(v.input), v.hash);
}
for (const [i, v] of V.defuse.entries()) {
  check(`defuse vector ${i}`, defuse(v.input), v.want);
  check(`fence vector ${i}`, fence(v.label, v.input), v.fence);
}
for (const [i, v] of V.decide.entries()) {
  check(`decide vector ${i}`, decide(v.a, v.b, v.rounds, v.min_rounds, v.conflict, v.fetched), v.want);
}

console.log();
console.log(`${pass} passed, ${fail.length} failed`);
if (fail.length) {
  for (const f of fail) {
    console.log(`  ${f.name}\n    js:     ${JSON.stringify(f.got)}\n    python: ${JSON.stringify(f.want)}`);
  }
  process.exit(1);
}
