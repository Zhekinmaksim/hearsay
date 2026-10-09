/* Render without the CLI. CHROME_PATH lets a machine with no downloadable
 * Chrome point at one it has; elsewhere Remotion fetches its own. */
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import path from "node:path";
import fs from "node:fs";
import { createHash } from "node:crypto";
const browser = process.env.CHROME_PATH
  ? { browserExecutable: process.env.CHROME_PATH, chromeMode: "chrome-for-testing" } : {};
const serveUrl = await bundle({ entryPoint: path.resolve("src/index.ts") });
const opts = { serveUrl, ...browser, chromiumOptions: { gl: "swangle" } };
const composition = await selectComposition({ ...opts, id: "Hearsay" });
fs.mkdirSync("out", { recursive: true });
let last = -1;
await renderMedia({
  ...opts, composition, concurrency: 2, codec: "h264", crf: 17, audioCodec: "aac", audioBitrate: "320k",
  pixelFormat: "yuv420p", outputLocation: "out/hearsay.mp4",
  onProgress: ({ progress }) => { const p = Math.floor(progress * 20); if (p !== last) { last = p; console.log(`${p * 5}%`); } },
});
console.log("wrote out/hearsay.mp4");
const sha = file => createHash("sha256").update(fs.readFileSync(file)).digest("hex");
const inputs = ["src/Film.tsx", "src/Root.tsx", "src/index.ts", "src/corpus.json", "src/checkpoint.json", "src/lib.mjs", "src/beats.json", "src/time.ts", "src/tokens.ts",
  "public/track.wav", "public/fonts/Newsreader-Light.ttf", "public/fonts/Newsreader-Regular.ttf", "public/fonts/Archivo-Regular.ttf", "public/fonts/Archivo-SemiBold.ttf",
  "package.json", "package-lock.json", "render.mjs"];
fs.writeFileSync("out/evidence.json", JSON.stringify({
  format: "hearsay-film/1", duration_frames: composition.durationInFrames,
  fps: composition.fps, width: composition.width, height: composition.height,
  checkpoint: JSON.parse(fs.readFileSync("src/checkpoint.json", "utf8")),
  input_sha256: Object.fromEntries(inputs.map(file => [file, sha(file)])),
  video_sha256: sha("out/hearsay.mp4"),
}, null, 2) + "\n");
