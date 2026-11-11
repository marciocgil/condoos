import type { ReactNode } from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";

import { alpha, C, FONT } from "../design/condoosTokens";
import { ramp } from "../design/motion";

/** Persistent backdrop: dark gradient, a slow blueprint grid and a vignette. */
export function Backdrop() {
  const frame = useCurrentFrame();
  const drift = (frame * 0.35) % 90;
  return (
    <AbsoluteFill style={{ background: C.bg }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse 80% 55% at 50% 45%, ${C.bg2} 0%, ${C.bg} 70%)`,
        }}
      />
      <AbsoluteFill
        style={{
          backgroundImage: `linear-gradient(${alpha(C.line, 0.18)} 1px, transparent 1px), linear-gradient(90deg, ${alpha(C.line, 0.18)} 1px, transparent 1px)`,
          backgroundSize: "90px 90px",
          backgroundPosition: `0px ${drift}px`,
          maskImage: "radial-gradient(ellipse 70% 60% at 50% 50%, black 20%, transparent 80%)",
          WebkitMaskImage:
            "radial-gradient(ellipse 70% 60% at 50% 50%, black 20%, transparent 80%)",
        }}
      />
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse 120% 90% at 50% 50%, transparent 55%, rgba(0,0,0,0.45) 100%)",
        }}
      />
    </AbsoluteFill>
  );
}

function timecode(frame: number, fps: number) {
  const s = Math.floor(frame / fps);
  const ff = String(frame % fps).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  const mm = String(Math.floor(s / 60)).padStart(2, "0");
  return `00:${mm}:${ss}:${ff}`;
}

const mono: React.CSSProperties = {
  fontFamily: FONT,
  fontSize: 22,
  letterSpacing: "0.16em",
  color: C.muted,
  fontWeight: 500,
  fontVariantNumeric: "tabular-nums",
};

/**
 * Frame HUD: brand line, demo-data notice and timecode. Kept inside the 9:16 safe area
 * (top ~180 px and bottom ~320 px are covered by the Reels/LinkedIn interface).
 */
export function Hud({
  chapter,
  demoLabel,
  visible = true,
}: {
  chapter: string;
  demoLabel: string;
  visible?: boolean;
}) {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const o = ramp(frame, 4, 24) * (visible ? 1 : 0);
  const bracket = (pos: React.CSSProperties, rot: number) => (
    <div
      style={{
        position: "absolute",
        width: 28,
        height: 28,
        borderTop: `2px solid ${alpha(C.fg2, 0.5)}`,
        borderLeft: `2px solid ${alpha(C.fg2, 0.5)}`,
        transform: `rotate(${rot}deg)`,
        ...pos,
      }}
    />
  );
  return (
    <AbsoluteFill style={{ opacity: o, pointerEvents: "none" }}>
      {bracket({ left: 48, top: 176 }, 0)}
      {bracket({ right: 48, top: 176 }, 90)}
      {bracket({ right: 48, bottom: 300 }, 180)}
      {bracket({ left: 48, bottom: 300 }, 270)}
      <div
        style={{
          ...mono,
          position: "absolute",
          top: 196,
          left: 92,
          right: 92,
          display: "flex",
          justifyContent: "space-between",
        }}
      >
        <span>CONDOOS OPTIMIZE</span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
          <span
            style={{ width: 9, height: 9, borderRadius: 9, background: C.info, opacity: 0.9 }}
          />
          {demoLabel.toUpperCase()}
        </span>
      </div>
      <div
        style={{
          ...mono,
          fontSize: 20,
          position: "absolute",
          bottom: 316,
          left: 92,
          right: 92,
          display: "flex",
          justifyContent: "space-between",
        }}
      >
        <span>{chapter}</span>
        <span>{timecode(Math.min(frame, durationInFrames - 1), fps)}</span>
      </div>
    </AbsoluteFill>
  );
}

/** Cross-fade wrapper for a scene inside its <Sequence>. */
export function Fade({
  dur,
  fadeIn = 10,
  fadeOut = 10,
  children,
}: {
  dur: number;
  fadeIn?: number;
  fadeOut?: number;
  children: ReactNode;
}) {
  const frame = useCurrentFrame();
  const o =
    (fadeIn > 0 ? ramp(frame, 0, fadeIn) : 1) *
    (fadeOut > 0 ? 1 - ramp(frame, dur - fadeOut, dur) : 1);
  return <AbsoluteFill style={{ opacity: o }}>{children}</AbsoluteFill>;
}
