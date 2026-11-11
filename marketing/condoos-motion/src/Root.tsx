import { Composition, Folder } from "remotion";

import { HERO15_FRAMES, HeroFilm15 } from "./compositions/HeroFilm15";
import { HERO60_FRAMES, HeroFilm60 } from "./compositions/HeroFilm60";
import "./design/fonts";
import { defaultFilmProps, filmSchema } from "./schema";

const common = {
  fps: 30,
  width: 1080,
  height: 1920,
  schema: filmSchema,
  defaultProps: defaultFilmProps,
};

export function RemotionRoot() {
  return (
    <Folder name="CondoOS-Optimize">
      <Composition
        id="HeroFilm60"
        component={HeroFilm60}
        durationInFrames={HERO60_FRAMES}
        {...common}
      />
      <Composition
        id="HeroFilm15"
        component={HeroFilm15}
        durationInFrames={HERO15_FRAMES}
        {...common}
      />
    </Folder>
  );
}
