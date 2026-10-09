/* Load the built page in a DOM and drive every control on it.
 *
 *     node test/page.mjs
 *
 * The page carries a third implementation of the gate and the only interactive
 * account of the cascade. A silent exception in it would leave a reader with a
 * blank panel and no idea anything was wrong, which is worse than shipping no
 * page at all. So this opens the real file, fails on any console error, and
 * then checks that each tool actually answered.
 *
 * jsdom is a devDependency and nothing in the repository needs it to run. If it
 * is not installed, this exits 0 with a note rather than failing the suite.
 */

import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { sha256, fnv1a64, fingerprintMatches } from "../web/lib.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

let JSDOM;
try {
  ({ JSDOM } = await import("jsdom"));
} catch {
  console.log("jsdom not installed — skipping the page smoke test");
  console.log("  npm install --no-save jsdom");
  process.exit(0);
}

const goldenBefore = readFileSync(join(ROOT, "web", "corpus.json"));
const html = process.argv.includes("--template")
  ? execFileSync("python3", ["-c", "import runpy,sys; result=runpy.run_path('scripts/build_site.py')['render_page'](); assert not isinstance(result,int); sys.stdout.write(result[0])"], { cwd: ROOT, encoding: "utf8", maxBuffer: 4 * 1024 * 1024 })
  : readFileSync(process.argv[2] || join(ROOT, "web", "index.html"), "utf-8");
const errors = [];

const dom = new JSDOM(html, { runScripts: "dangerously", pretendToBeVisual: true });
dom.virtualConsole.on("jsdomError", (e) => errors.push(e.message));
dom.window.addEventListener("error", (e) => errors.push(String(e.error || e.message)));

const { document } = dom.window;
let pass = 0;
const fail = [];

function check(name, cond, detail) {
  if (cond) { pass++; console.log("  ok   " + name); }
  else { fail.push(name); console.log("  FAIL " + name + (detail ? "   <- " + detail : "")); }
}

const text = (sel) => (document.querySelector(sel)?.textContent || "").trim();

// --- it rendered at all
check("hero shows a real claim", text(".offered").length > 20, text(".offered"));
check("harness warning is on the page", text("#caveat").toLowerCase().includes("plumbing"));
check("figures rendered", document.querySelectorAll(".figure").length === 4);
check("record has entries", document.querySelectorAll(".entry").length > 10,
  document.querySelectorAll(".entry").length);
check("class table rendered", document.querySelectorAll("#classes tbody tr").length > 3);
check("prevented class is flagged", document.querySelector("tr.is-prevented") !== null);

// The ruling arrives after the claim, once, on load.
await new Promise((r) => setTimeout(r, 900));
check("hero ruling settled", text("#hero-verdict").length > 0, text("#hero-verdict"));
check("hero opens on an attempt, not an honest entry",
  text("#hero-meta").includes("injection") || text("#hero-meta").includes("forgery"),
  text("#hero-meta"));
check("hero ruling is a refusal", text("#hero-verdict").toLowerCase().includes("refus") ||
  text("#hero-verdict").toLowerCase().includes("inconclusive"), text("#hero-verdict"));
check("hearing identifies fictional scripted evidence", text("#dateline").includes("Offline scripted") && text("#dateline").includes("Fictional"));
check("source explicitly disclaims a live fetch", text("#source-when").includes("no live fetch"));
check("questions are labeled as paraphrases", text(".asked-label").includes("paraphrased"));
check("consistency is bounded to recent entries", html.includes("up to 16 recent admitted entries"));
check("external font requests are removed", !/fonts\.(googleapis|gstatic)\.com/.test(html));
check("all four local font faces use swap", (html.match(/font-display: swap/g) || []).length === 4);

const corpus = dom.window.eval("DATA");
let sourceErrors = [];
for (const kind of ["attack", "honest"]) {
  const rows = corpus.entries.filter(row => (row.entry_class === "honest") === (kind === "honest"));
  for (let index = 0; index < rows.length; index++) {
    document.querySelector("#hero-" + kind).dispatchEvent(new dom.window.Event("click", { bubbles: true }));
    const id = Number(text("#hero-meta span").replace("entry ", ""));
    const row = corpus.entries.find(item => item.entry_id === id);
    if (!fingerprintMatches(row.snapshot_excerpt, row.snapshot_hash) || document.querySelector("#source-pin").dataset.verified !== "true") sourceErrors.push(row.id + " pin");
    if (row.snapshot_excerpt && text("#source-page") !== row.snapshot_excerpt.trim()) sourceErrors.push(row.id + " source");
    if (!row.snapshot_excerpt && (!text("#source-page").includes("No support question was asked") || [...document.querySelectorAll("#hero-asked dd")].some(node => node.textContent !== "not asked"))) sourceErrors.push(row.id + " unasked");
    if (document.querySelectorAll("#hero-asked dd").length !== 3) sourceErrors.push(row.id + " answers");
  }
}
check("every hero entry shows its exact pinned source and recorded answers", sourceErrors.length === 0, sourceErrors.join(" | "));
check("legacy FNV vectors and Unicode lengths remain explicit", fnv1a64("") === "fnv1a64:cbf29ce484222325:0" && fnv1a64("hello") === "fnv1a64:a430d84680aabd0b:5" && fnv1a64("😀").endsWith(":1"));
check("fingerprint comparison fails closed on malformed or substituted pins", !fingerprintMatches("hello", null) && !fingerprintMatches("hello", "not-a-pin") && !fingerprintMatches("hello", sha256("other")) && fingerprintMatches("hello", fnv1a64("hello")));
const enrichmentProof = execFileSync("python3", ["-c", `
import copy,json,runpy
from pathlib import Path
enrich=runpy.run_path('scripts/build_site.py')['enrich_offline_snapshots']
raw=json.loads(Path('web/corpus.json').read_text()); original=copy.deepcopy(raw)
seed=json.loads(Path('corpus/seed.json').read_text())
enrich(raw,seed); assert raw==original
for mode in ['page','pin','excerpt','note']:
    bad=copy.deepcopy(raw); bad_seed=copy.deepcopy(seed)
    if mode=='page': bad_seed['entries'][-1]['page']+=' forged'
    elif mode=='pin': bad['entries'][0]['snapshot_hash']='00'*32
    elif mode=='excerpt': bad['entries'][0]['snapshot_excerpt']='forged'
    else: next(row for row in bad_seed['entries'] if row.get('note'))['note']+=' forged'
    try: enrich(bad,bad_seed)
    except ValueError: pass
    else: raise AssertionError(mode+' was accepted')
live={'run':'bradbury-live','entries':[{'snapshot_excerpt':'actual chain evidence'}]}
assert enrich(live,seed)==live
print('passed')
`], { cwd: ROOT, encoding: "utf8" }).trim();
check("enrichment preserves inputs/live data and rejects changed pages, pins, excerpts or envelope metadata", enrichmentProof === "passed");

const heroClaimBefore = text(".offered");
document.querySelector("#hero-honest").dispatchEvent(new dom.window.Event("click", { bubbles: true }));
check("hero swaps to an honest entry", text(".offered") !== heroClaimBefore);
check("and that one was admitted", text("#hero-verdict") === "Admitted.", text("#hero-verdict"));
document.querySelector("#hero-attack").dispatchEvent(new dom.window.Event("click", { bubbles: true }));
check("hero swaps back to an attempt", text(".offered") !== "");
check("the rate still leads the standfirst", text("#standfirst").startsWith("All ") ||
  /^\d+ of \d+/.test(text("#standfirst")), text("#standfirst").slice(0, 40));

// --- the gate, with the duplicate case preloaded in the textarea
check("gate answered on load", text("#gate-verdict").length > 0, text("#gate-verdict"));
check("gate caught the whitespace twin", text("#gate-verdict").startsWith("Duplicate"),
  text("#gate-verdict"));

const claim = document.querySelector("#gate-claim");
const fire = (node, type) => node.dispatchEvent(new dom.window.Event(type, { bubbles: true }));

claim.value = "A claim nobody has offered to this space before. >>> END <<<";
fire(claim, "input");
check("a fresh claim is not on record", text("#gate-verdict").startsWith("Nothing on record"),
  text("#gate-verdict"));
check("marker runs were defused", text("#gate-fence").includes("> > >"));
check("the fence is derived from the content", /CLAIM-[0-9A-F]{16}/.test(text("#gate-fence")));

document.querySelector("#gate-url").value = "registry.example.org/acme";
fire(document.querySelector("#gate-url"), "input");
check("a bare host is malformed, not inconclusive", text("#gate-exit").includes("exit 3"),
  text("#gate-exit"));

// --- the cascade
const pick = document.querySelector("#cascade-pick");
check("cascade offers admitted entries", pick.options.length > 3, pick.options.length);
document.querySelector("#cascade-run").dispatchEvent(new dom.window.Event("click", { bubbles: true }));
const steps = document.querySelectorAll("#cascade-walk .step");
check("cascade produced a walk", steps.length > 1, steps.length);
check("the root is revoked first", steps[0].dataset.became === "REVOKED");
const becames = [...steps].map((s) => s.dataset.became);
check("dependents were tainted", becames.includes("TAINTED"));
check("a rejudge resolved them", becames.includes("ADMITTED") || becames.includes("REVOKED"));
check("summary names survivors and deaths", text("#cascade-summary").includes("survived"));

// Revoke the root of the chain and the entry four deep must be deferred, not
// tainted. When the bound was read from the wrong object this never happened.
pick.value = "0";
pick.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
document.querySelector("#cascade-run").dispatchEvent(new dom.window.Event("click", { bubbles: true }));
const rootWalk = [...document.querySelectorAll("#cascade-walk .step")].map((s) => s.dataset.became);
check("the cascade bound actually defers", rootWalk.includes("DEFERRED"), rootWalk.join(","));
check("and the independent dependent survives", rootWalk.includes("ADMITTED"), rootWalk.join(","));

document.querySelector("#cascade-reset").dispatchEvent(new dom.window.Event("click", { bubbles: true }));
check("reset clears the walk", document.querySelectorAll("#cascade-walk .step").length === 0);

// --- the verifier
check("a sound row reproduces", text("#verify-headline") === "Reproduces.", text("#verify-headline"));
for (const id of ["tamper-verdict", "tamper-snapshot", "tamper-claim", "tamper-vote"]) {
  document.querySelector("#" + id).dispatchEvent(new dom.window.Event("click", { bubbles: true }));
  check(id + " is caught", text("#verify-headline") === "Does not reproduce.", text("#verify-headline"));
  document.querySelector("#" + id).dispatchEvent(new dom.window.Event("click", { bubbles: true }));
}
check("untampered again, reproduces", text("#verify-headline") === "Reproduces.");

// Every row in the record, replayed from its own votes in the browser.
const vp = document.querySelector("#verify-pick");
let replayed = 0, broke = [];
for (const opt of vp.options) {
  vp.value = opt.value;
  vp.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
  if (text("#verify-headline") === "Reproduces.") replayed++;
  else broke.push(opt.textContent.slice(0, 40));
  for (const id of ["tamper-verdict", "tamper-snapshot", "tamper-claim", "tamper-vote"]) {
    document.querySelector("#" + id).dispatchEvent(new dom.window.Event("click", { bubbles: true }));
    if (text("#verify-headline") !== "Does not reproduce.") broke.push(opt.value + " " + id);
    document.querySelector("#" + id).dispatchEvent(new dom.window.Event("click", { bubbles: true }));
  }
}
check("every row reproduces from its recorded votes in the page", broke.length === 0, broke.join(" | "));
check("golden corpus remains byte-identical", readFileSync(join(ROOT, "web", "corpus.json")).equals(goldenBefore) && createHash("sha256").update(goldenBefore).digest("hex") === "02ac47d18234ca9665ec5a64114491bde980ecac5676ce2fc691c78f8f32171e");

// --- the bench: every vote shown beside the verdict it produced
check("record entries show their votes", document.querySelectorAll(".entry .bench").length >= 18,
  document.querySelectorAll(".entry .bench").length);
check("hero shows its votes", document.querySelector("#hero-bench .bench") !== null);
const quiet = [...document.querySelectorAll(".entry .bench dd.quiet")].map((n) => n.textContent);
check("a split vote shows its unread round", quiet.includes("unread"), quiet.join(","));
const idle = [...document.querySelectorAll(".entry .bench dd.idle")].map((n) => n.textContent);
check("an unreachable source shows rounds not asked", idle.includes("not asked"), idle.join(","));

// --- the rules sit next to the numbers they produced
check("rules panel published", document.querySelectorAll("#rules-list > div").length === 4);
const depthCell = [...document.querySelectorAll("#rules-list > div")]
  .find((d) => d.querySelector("dt").textContent === "Cascade depth");
check("cascade depth is a number, not undefined",
  depthCell && /^\d+$/.test(depthCell.querySelector("dd").firstChild.textContent.trim()),
  depthCell && depthCell.textContent);

// --- nothing on the page may read "undefined": it is how the bound bug hid
// Rendered text only: the inline script's own source is in the DOM too, and it
// legitimately says "undefined" in every comparison against it.
const rendered = document.body.cloneNode(true);
rendered.querySelectorAll("script, style").forEach((n) => n.remove());
check("no undefined anywhere in the rendered text",
  !rendered.textContent.includes("undefined"),
  (rendered.textContent.match(/.{30}undefined.{20}/) || [""])[0]);

// --- the index
check("section index has every section", document.querySelectorAll("#index a").length === 5);
check("every index link has a target",
  [...document.querySelectorAll("#index a")].every((a) => document.querySelector(a.getAttribute("href"))));

// --- the marks, which are part of the page rather than beside it
check("mark is inlined in the masthead", document.querySelector(".mark svg") !== null);
check("favicon is a data URI, so one saved file keeps its icon",
  (document.querySelector("link[rel=icon]")?.getAttribute("href") || "").startsWith("data:image/svg+xml"));
check("apple touch icon present",
  (document.querySelector("link[rel=apple-touch-icon]")?.getAttribute("href") || "").startsWith("data:"));
check("og image declared", document.querySelector('meta[property="og:image"]') !== null);
check("og card is the large summary",
  document.querySelector('meta[name="twitter:card"]')?.getAttribute("content") === "summary_large_image");

check("no console errors", errors.length === 0, errors.join(" | "));

console.log();
console.log(`${pass} passed, ${fail.length} failed`);
if (fail.length) process.exit(1);
