/* Compare browser admission codes with the Python CLI, including malformed input. */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { localGate } from "../web/lib.mjs";

const corpus = JSON.parse(readFileSync("web/corpus.json", "utf8"));
const good = JSON.parse(readFileSync("examples/entries/01-honest-dissolution.json", "utf8"));
const cases = [
  good, { ...good, claim: good.claim + " a new unjudged assertion" },
  { ...good, claim: "  " + good.claim + "  " },
  { ...good, version: "broken" }, { ...good, claim: 1 },
  { ...good, claim: "" }, { ...good, claim: "é".repeat(1025) },
  { ...good, source_url: null }, { ...good, source_url: "example.org" },
  { ...good, entry_class: "unknown" }, { ...good, supports: null },
  { ...good, supports: [1, 1] }, { ...good, supports: [true, 1] },
  { ...good, supports: Array.from({ length: 9 }, (_, index) => index) },
  { ...good, supports: [{}] }, null, [],
];
const script = `import json,sys
sys.path.insert(0,'cli')
import gate
data=json.load(sys.stdin)
results=[]
for env in data['cases']:
    try: results.append(gate.run_gate(env,data['corpus'])[0])
    except Exception: results.append(3)
print(json.dumps(results))`;
const python = spawnSync("python3", ["-c", script], { input: JSON.stringify({ corpus, cases }), encoding: "utf8" });
assert.equal(python.status, 0, python.stderr);
const expected = JSON.parse(python.stdout);
for (let index = 0; index < cases.length; index++) {
  let actual;
  try { actual = localGate(cases[index], corpus.entries).code; }
  catch { actual = 3; }
  assert.equal(actual, expected[index], "gate code differs on case " + index);
}
console.log(cases.length + " admission gate parity checks passed");
