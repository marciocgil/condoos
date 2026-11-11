import type { ReactNode } from "react";
import {
  AbsoluteFill,
  Audio,
  interpolate,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

import { Backdrop, Fade, Hud } from "../components/Stage";
import { SceneTime } from "../design/sceneTime";
import type { FilmProps } from "../schema";

export type Segment = {
  name: string;
  chapter: string;
  from: number;
  dur: number;
  speed?: number;
  startAt?: number;
  fadeIn?: number;
  fadeOut?: number;
  render: () => ReactNode;
};

/** Shared film shell: backdrop, scenes as cross-faded sequences, HUD and optional audio. */
export function Film({ segments, props }: { segments: Segment[]; props: FilmProps }) {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const current = [...segments].reverse().find((s) => frame >= s.from) ?? segments[0];
  const last = segments[segments.length - 1];
  return (
    <AbsoluteFill style={{ backgroundColor: "#22262C" }}>
      <Backdrop />
      {segments.map((s) => (
        <Sequence key={s.name} name={s.name} from={s.from} durationInFrames={s.dur}>
          <Fade dur={s.dur} fadeIn={s.fadeIn ?? 10} fadeOut={s.fadeOut ?? 10}>
            <SceneTime speed={s.speed} startAt={s.startAt}>
              {s.render()}
            </SceneTime>
          </Fade>
        </Sequence>
      ))}
      {props.showHud && (
        <Hud
          chapter={current.chapter}
          demoLabel={props.demoLabel}
          visible={frame < last.from + 10}
        />
      )}
      {props.audioSrc && (
        <Audio
          src={staticFile(props.audioSrc)}
          volume={(f) =>
            props.audioVolume *
            interpolate(f, [0, 10, durationInFrames - 30, durationInFrames], [0, 1, 1, 0], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            })
          }
        />
      )}
    </AbsoluteFill>
  );
}
