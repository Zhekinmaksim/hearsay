import { continueRender, delayRender, staticFile } from "remotion";

/* The same tokens as web/template.html. The film is a still of the product
 * set in motion, so it does not get a palette of its own. */
export const LIGHT = {
  ink: "#15181d",
  soft: "#585f6b",
  faint: "#8d94a0",
  paper: "#f2f3f1",
  paper2: "#e7e9e5",
  rule: "#c9cdc6",
  flag: "#7c4a2d",
  flagBg: "#f0e5de",
};

export const DARK = {
  ink: "#e8eae6",
  soft: "#9aa1ab",
  faint: "#6c737e",
  paper: "#14161a",
  paper2: "#1b1e23",
  rule: "#2e333a",
  flag: "#d59a76",
  flagBg: "#2a211c",
};

export type Theme = typeof LIGHT;

export const SERIF = "Newsreader, Georgia, serif";
export const SANS = "Archivo, Helvetica, Arial, sans-serif";
export const MONO = "'DejaVu Sans Mono', Menlo, monospace";

/* Fonts are loaded before the first frame is captured. A frame rendered in a
 * fallback face still renders, and still looks almost right, which is exactly
 * why it must not be allowed to happen silently. */
const FACES: Array<[string, string, string]> = [
  ["Newsreader", "fonts/Newsreader-Light.ttf", "300"],
  ["Newsreader", "fonts/Newsreader-Regular.ttf", "400"],
  ["Archivo", "fonts/Archivo-Regular.ttf", "400"],
  ["Archivo", "fonts/Archivo-SemiBold.ttf", "600"],
];

let loaded = false;
export const loadFonts = () => {
  if (loaded) return;
  loaded = true;
  const handle = delayRender("loading the project faces");
  Promise.all(
    FACES.map(([family, file, weight]) => {
      const face = new FontFace(family, `url(${staticFile(file)})`, { weight });
      return face.load().then((f) => (document.fonts as any).add(f));
    })
  )
    .then(() => continueRender(handle))
    .catch((err) => {
      // Fail the render rather than ship a frame in the wrong face.
      throw err;
    });
};
