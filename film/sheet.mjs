/* The contact sheet: render stills at the moments that matter and tile them,
 * so the whole cut can be checked at a glance before an hour goes into a
 * full render. Each still is taken just after a hit, where a mistake shows. */
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import fs from "node:fs";
import path from "node:path";
const B = JSON.parse(fs.readFileSync("src/beats.json", "utf8"));
const D = B.downbeats;
const at = [0.9, D[0] + 0.5, D[1] + 0.5, D[2] + 0.5, D[3] + 1.2, D[4] + 1.5, D[5] + 0.3, D[5] + 1.8,
  D[6] + 0.8, D[7] + 1.4, D[8] + 1.2, D[9] + 2.2, D[10] + 0.2, D[10] + 2.2, D[11] + 1.0,
  D[12] + 2.4, D[13] + 1.5, D[14] + 1.0, D[15] + 1.5, D[16] + 2.4, D[17] + 1.0, D[19] + 0.5, D[21] + 0.5, 59.9];
const serveUrl = await bundle({ entryPoint: path.resolve("src/index.ts") });
const browser = process.env.CHROME_PATH ? { browserExecutable: process.env.CHROME_PATH, chromeMode: "chrome-for-testing" } : {};
const opts = { serveUrl, ...browser, chromiumOptions: { gl: "swangle" } };
const composition = await selectComposition({ ...opts, id: "Hearsay" });
fs.mkdirSync("sheet", { recursive: true });
for (const [i, s] of at.entries()) {
  const frame = Math.min(1799, Math.round(s * 30));
  await renderStill({ ...opts, composition, frame, output: `sheet/${String(i).padStart(2, "0")}.png`, scale: 0.4 });
}
console.log("stills", at.length);
