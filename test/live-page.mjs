/* Verify the live artifact's counters, filters and replay controls. */
import { readFileSync } from "node:fs";
let JSDOM;
try { ({ JSDOM } = await import("jsdom")); }
catch { console.log("jsdom not installed — skipping live page checks"); process.exit(0); }

const html = readFileSync(process.argv[2] || "web/live.html", "utf8");
const errors = [];
const dom = new JSDOM(html, { runScripts: "dangerously" });
dom.virtualConsole.on("jsdomError", error => errors.push(error.message));
const document = dom.window.document;
const data = JSON.parse(document.getElementById("live-data").textContent);
let passes = 0;
function check(name, condition) {
  if (!condition) throw new Error(name);
  passes++;
}
check("no template markers", !html.includes("/*__"));
check("actual Bradbury data", data.run === "bradbury");
check("rendered count matches records", document.querySelectorAll("#records tr").length === data.entries.length);
check("headline count matches records", Number(document.getElementById("judged-count").textContent) === data.entries.length);
check("false rejection rate matches chain", document.getElementById("false-rate").textContent === data.report.false_rejection_milli + "/1000");
check("snapshot provenance is disclosed", document.body.textContent.includes("Pinned source bytes are recovered from GenVM traces"));
check("all snapshot bytes verified", data.entries.every(row=>row.snapshot_verified&&typeof row.snapshot_excerpt==='string'));
check("acceptance limitation is disclosed", document.body.textContent.includes("provisional until finalization"));
check("every judged row has a receipt", document.querySelectorAll('#records a[href*="/tx/"]').length === data.entries.length);
check("downloadable corpus", !!document.querySelector('a[href="live-corpus.json"]'));
const gateInput = document.getElementById("gate-input");
const gateCheck = document.getElementById("gate-check");
const gateResult = () => JSON.parse(document.getElementById("gate-output").textContent);
for (const button of document.querySelectorAll("[data-gate]")) {
  button.click();
  const row = data.entries[Number(button.dataset.gate)];
  const expected = { ADMITTED: 0, UNSOURCED: 1, CONTRADICTED: 1, INCONCLUSIVE: 2 }[row.status];
  check("live gate matches recorded verdict " + row.id, gateResult().code === expected);
}
const envelope = data.entries[0].envelope;
gateInput.value = JSON.stringify({ ...envelope, claim: envelope.claim + " new unjudged assertion" });
gateCheck.click();
check("live gate never admits an unjudged claim", gateResult().code === 2);
gateInput.value = JSON.stringify({ ...envelope, claim: "  " + envelope.claim + "  " });
gateCheck.click();
check("live gate refuses a whitespace duplicate", gateResult().code === 1);
gateInput.value = JSON.stringify({ ...envelope, version: "broken" });
gateCheck.click();
check("live gate rejects malformed version", gateResult().code === 3);
gateInput.value = JSON.stringify({ ...envelope, entry_class: "unknown" });
gateCheck.click();
check("live gate rejects malformed class", gateResult().code === 3);
gateInput.value = "{";
gateCheck.click();
check("live gate handles malformed JSON", gateResult().code === 3);
const buttons = [...document.querySelectorAll("[data-replay]")];
for (const button of buttons) {
  button.click();
  check("actual votes reproduce for row " + button.dataset.replay, document.getElementById("verify-output").textContent.startsWith("Reproduces."));
}
const input = document.getElementById("receipt-input");
const submit = document.getElementById("verify");
const receipt = JSON.parse(input.value);
input.value = JSON.stringify({ ...receipt, status: receipt.status === "ADMITTED" ? "UNSOURCED" : "ADMITTED" });
submit.click();
check("forged verdict is caught", document.getElementById("verify-output").textContent.startsWith("Does not reproduce."));
input.value = JSON.stringify({ ...receipt, envelope: { ...receipt.envelope, claim: "</script><script>window.injected=1</script>" } });
submit.click();
check("altered claim is caught", document.getElementById("verify-output").textContent.startsWith("Does not reproduce."));
check("edited claim does not execute", dom.window.injected === undefined);
input.value = JSON.stringify({ ...receipt, snapshot_excerpt: receipt.snapshot_excerpt + "forged source" });
submit.click();
check("reattributed snapshot is caught", document.getElementById("verify-output").textContent.includes("Pinned snapshot hash does not match"));
input.value = JSON.stringify({ ...receipt, votes: { ...receipt.votes, conflict: "garbage" } });
submit.click();
check("malformed consistency cannot reproduce", document.getElementById("verify-output").textContent.startsWith("Malformed receipt."));
input.value = "{";
submit.click();
check("malformed JSON is handled", document.getElementById("verify-output").textContent.startsWith("Malformed receipt."));
const filter = document.getElementById("class-filter");
filter.value = data.report.classes[0].class;
filter.dispatchEvent(new dom.window.Event("change"));
check("class filter shows only the chosen class", [...document.querySelectorAll("#records tr")].filter(row => !row.hidden).every(row => row.dataset.class === filter.value));
filter.value = "";
filter.dispatchEvent(new dom.window.Event("change"));
check("all classes can be restored", [...document.querySelectorAll("#records tr")].every(row => !row.hidden));
check("no console errors", errors.length === 0);
console.log(passes + " live page checks passed");
dom.window.close();
