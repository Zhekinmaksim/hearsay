/* The parts of the gate that can run without a chain, in the browser.
 *
 * Every function here is a third implementation of something that already
 * exists in Python twice: once in contracts/hearsay.py and once in cli/. A
 * third copy is only tolerable because test/parity.mjs runs this file and the
 * Python side over the same vectors and fails loudly when they part company.
 *
 * sha256 is written out rather than taken from crypto.subtle on purpose.
 * crypto.subtle needs a secure context and returns promises; this page is meant
 * to open from a saved file with no network and no origin, and hashing that
 * works in one of those places and not the other is worse than none.
 */

const K = [
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];

function rotr(x, n) { return (x >>> n) | (x << (32 - n)); }

function sha256(text) {
  const bytes = new TextEncoder().encode(text);
  const bitLen = bytes.length * 8;
  const padded = new Uint8Array((((bytes.length + 8) >> 6) + 1) << 6);
  padded.set(bytes);
  padded[bytes.length] = 0x80;
  const view = new DataView(padded.buffer);
  view.setUint32(padded.length - 4, bitLen >>> 0, false);
  view.setUint32(padded.length - 8, Math.floor(bitLen / 4294967296), false);

  const h = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  ];
  const w = new Uint32Array(64);

  for (let off = 0; off < padded.length; off += 64) {
    for (let i = 0; i < 16; i++) w[i] = view.getUint32(off + i * 4, false);
    for (let i = 16; i < 64; i++) {
      const s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >>> 3);
      const s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >>> 10);
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) >>> 0;
    }
    let [a, b, c, d, e, f, g, hh] = h;
    for (let i = 0; i < 64; i++) {
      const S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
      const ch = (e & f) ^ (~e & g);
      const t1 = (hh + S1 + ch + K[i] + w[i]) >>> 0;
      const S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const t2 = (S0 + maj) >>> 0;
      hh = g; g = f; f = e; e = (d + t1) >>> 0;
      d = c; c = b; b = a; a = (t1 + t2) >>> 0;
    }
    const next = [a, b, c, d, e, f, g, hh];
    for (let i = 0; i < 8; i++) h[i] = (h[i] + next[i]) >>> 0;
  }
  return h.map((x) => x.toString(16).padStart(8, "0")).join("");
}

const ZERO_WIDTH = new Set([0x200b, 0x200c, 0x200d, 0x2060, 0xfeff]);

/* Dedup normalization. NOT what gets judged: judging sees the claim byte for
 * byte, because zero-width characters and exotic spacing are themselves the
 * attack surface. Mirrors _flatten in contracts/hearsay.py. */
function flatten(text) {
  let out = "";
  for (const ch of text) {
    const o = ch.codePointAt(0);
    if (ZERO_WIDTH.has(o)) continue;
    if (/\s/.test(ch)) { out += " "; continue; }
    out += ch.toLowerCase();
  }
  while (out.includes("  ")) out = out.replace(/ {2}/g, " ");
  return out.trim();
}

function dedupKey(spaceId, claim) {
  return spaceId + ":" + sha256(flatten(claim));
}

const REQUIRED = ["version", "space_id", "claim", "source_url", "entry_class"];
const OPTIONAL = ["supports", "author_note", "expects"];

/* Drop unknown keys, drop empty optionals, sort, no spaces. Mirrors
 * canonical() in cli/entry.py. */
function canonical(env) {
  const kept = {};
  for (const k of REQUIRED) {
    if (!(k in env)) throw new Error("missing required field: " + k);
    kept[k] = env[k];
  }
  for (const k of OPTIONAL) {
    const v = env[k];
    if (v === undefined || v === null) continue;
    if ((typeof v === "string" || Array.isArray(v)) && v.length === 0) continue;
    kept[k] = v;
  }
  const keys = Object.keys(kept).sort();
  return "{" + keys.map((k) => JSON.stringify(k) + ":" + JSON.stringify(kept[k])).join(",") + "}";
}

function envelopeHash(env) { return sha256(canonical(env)); }

/* Break every run of the fence characters, so no payload can close its own
 * fence early whatever nonce it guesses. Mirrors _defuse. */
function defuse(text) {
  return text.split("<<<").join("< < <").split(">>>").join("> > >");
}

/* A delimiter derived from the content cannot be guessed by the content. */
function fence(label, text) {
  return label + "-" + sha256(text).slice(0, 16).toUpperCase();
}

/* Verdict assembly. The third implementation of `decide`, and the reason
 * test/parity.mjs exists. `a` and `b` are the two support framings: true,
 * false, or null for a round that came back unreadable. Null is never folded
 * into false. */
function decide(a, b, rounds, minRounds, conflict, fetched = true) {
  if (!fetched) return ["UNSOURCED", "source unreachable or empty", 0];
  if (rounds < minRounds) return ["INCONCLUSIVE", "fewer readable rounds than the space requires", 0];
  if (a === null || b === null || a !== b) return ["INCONCLUSIVE", "referee framings disagreed or were unreadable", 0];
  if (a === false) return ["UNSOURCED", "source does not support the claim", 0];
  if (conflict === null) return ["INCONCLUSIVE", "consistency check unreadable", 0];
  if (conflict >= 0) return ["CONTRADICTED", "conflicts with entry " + conflict, conflict];
  return ["ADMITTED", "", 0];
}

const EXIT = { ADMITTED: 0, UNSOURCED: 1, CONTRADICTED: 1, INCONCLUSIVE: 2 };

/* The half of cli/gate.py that needs no chain. Structural checks and the dedup
 * collision are settled here, because a caller should not spend a bond to be
 * told its envelope was malformed. */
function localGate(env, rows) {
  const problems = [];
  if (!env || typeof env !== "object" || Array.isArray(env)) return { code: 3, verdict: null, problems: ["envelope must be an object"] };
  if (env.version !== "hearsay/1") problems.push("version must be exactly hearsay/1");
  if (typeof env.claim !== "string" || !env.claim) problems.push("claim is required");
  else if (new TextEncoder().encode(env.claim).length > 2048) problems.push("claim exceeds 2048 bytes");
  if (typeof env.source_url !== "string" || !env.source_url.trim()) problems.push("source_url is required");
  else if (!/^https?:\/\//.test(env.source_url)) problems.push("source_url must be http or https");
  if (!["honest", "direct_injection", "source_forgery", "citation_laundering", "slow_poison", "stale_truth", "flooding"].includes(env.entry_class)) problems.push("unknown entry_class");
  const supports = env.supports === undefined ? [] : env.supports;
  if (!Array.isArray(supports)) problems.push("supports must be a list");
  else if (supports.length > 8) problems.push("supports exceeds 8 entries");
  else if (supports.some(value => value !== null && typeof value === "object")) problems.push("supports contains an unhashable value");
  else if (new Set(supports.map(value => typeof value === "boolean" ? Number(value) : value)).size !== supports.length) problems.push("supports contains duplicates");
  if (problems.length) return { code: 3, verdict: null, problems };

  const hash = envelopeHash(env);
  const hit = rows.find((r) => r.envelope_hash === hash);
  if (hit) {
    return { code: EXIT[hit.status] ?? 2, verdict: hit.status, entry_id: hit.entry_id, note: hit.note, hash };
  }
  const key = dedupKey(env.space_id, env.claim);
  const twin = rows.find((r) => r.dedup_key === key);
  if (twin) {
    return { code: 1, verdict: null, duplicate_of: twin.entry_id, duplicate_claim: twin.claim, hash };
  }
  return { code: 2, verdict: null, hash };
}

/* Replay a revocation across the recorded dependency graph.
 *
 * This is a replay of the contract's rules over facts the run recorded, not a
 * simulation of a model. Who leans on whom, and whether an entry's own source
 * carried it, are both in the corpus. What is being re-executed here is the
 * breadth-first walk, the depth bound, and the rule that a tainted entry has to
 * restand without the dead premise.
 */
function cascade(rows, rootId, depthBound) {
  const byId = new Map(rows.map((r) => [r.entry_id, r]));
  const children = new Map();
  for (const r of rows) {
    for (const s of r.supports || []) {
      if (!children.has(s)) children.set(s, []);
      children.get(s).push(r.entry_id);
    }
  }

  const state = new Map();
  for (const r of rows) state.set(r.entry_id, r.status);
  state.set(rootId, "REVOKED");

  const tainted = [];
  const deferred = [];
  const steps = [{ id: rootId, depth: 0, became: "REVOKED" }];
  let frontier = [[rootId, 0]];

  while (frontier.length) {
    const [current, depth] = frontier.shift();
    for (const kid of children.get(current) || []) {
      if (state.get(kid) !== "ADMITTED") continue;
      if (depth + 1 > depthBound) {
        deferred.push(kid);
        steps.push({ id: kid, depth: depth + 1, became: "DEFERRED" });
        continue;
      }
      state.set(kid, "TAINTED");
      tainted.push(kid);
      steps.push({ id: kid, depth: depth + 1, became: "TAINTED" });
      frontier.push([kid, depth + 1]);
    }
  }

  // Rejudge, in the order the taint spread. An entry whose own source carried
  // the claim comes back; one that only ever stood on the revoked premise is
  // revoked in turn, and the walk continues from it.
  const survived = [];
  const died = [];
  for (const id of tainted) {
    if (state.get(id) !== "TAINTED") continue;
    if (byId.get(id).stands_alone) {
      state.set(id, "ADMITTED");
      survived.push(id);
      steps.push({ id, depth: null, became: "ADMITTED", rejudged: true });
    } else {
      state.set(id, "REVOKED");
      died.push(id);
      steps.push({ id, depth: null, became: "REVOKED", rejudged: true });
      for (const kid of children.get(id) || []) {
        if (state.get(kid) === "ADMITTED") {
          state.set(kid, "TAINTED");
          tainted.push(kid);
          steps.push({ id: kid, depth: null, became: "TAINTED" });
        }
      }
    }
  }

  return { state, tainted, deferred, survived, died, steps };
}

export { sha256, flatten, dedupKey, canonical, envelopeHash, defuse, fence, decide, localGate, cascade };
