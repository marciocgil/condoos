// QA stills: bundles once and renders selected frames of a composition to out/stills/.
// Usage: node scripts/stills.mjs [HeroFilm60] [0,180,420,...]
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import { mkdirSync } from "node:fs";
import path from "node:path";

const id = process.argv[2] ?? "HeroFilm60";
const frames = (process.argv[3] ?? "0,180,420,720,1020,1320,1620,1770").split(",").map(Number);
const browserExecutable = process.env.REMOTION_BROWSER ?? null;

const serveUrl = await bundle({ entryPoint: path.resolve("src/index.ts") });
const composition = await selectComposition({ serveUrl, id, browserExecutable });
mkdirSync("out/stills", { recursive: true });
for (const frame of frames) {
  const output = `out/stills/${id}-${String(frame).padStart(4, "0")}.png`;
  await renderStill({ composition, serveUrl, frame, output, browserExecutable, scale: 0.5 });
  console.log(output);
}
