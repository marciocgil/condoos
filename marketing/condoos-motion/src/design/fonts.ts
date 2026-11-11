import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";

// Inter (SIL OFL 1.1), bundled locally so the render never needs the network.
const WEIGHTS = ["400", "500", "600", "700", "800"] as const;

export const fontsReady = Promise.all(
  WEIGHTS.map((w) =>
    loadFont({
      family: "Inter",
      url: staticFile(`assets/fonts/inter-latin-${w}-normal.woff2`),
      weight: w,
      format: "woff2",
    }),
  ),
);
