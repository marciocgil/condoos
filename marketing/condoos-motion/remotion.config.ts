import { Config } from "@remotion/cli/config";

// Entry point and output defaults. Rendering is deterministic and offline (no network).
Config.setEntryPoint("src/index.ts");
Config.setVideoImageFormat("jpeg");
Config.setJpegQuality(95);
Config.setOverwriteOutput(true);
Config.setPixelFormat("yuv420p");

// Optional: point to a local Chrome headless shell (e.g. in CI or sandboxes without downloads).
if (process.env.REMOTION_BROWSER) {
  Config.setBrowserExecutable(process.env.REMOTION_BROWSER);
}
