import { AbsoluteFill } from "remotion";

import { alpha, C, FONT } from "../design/condoosTokens";
import { EASE_IN_OUT, EASE_OUT, lerp, ramp } from "../design/motion";
import { useT } from "../design/sceneTime";

/** 08 · 55–60 s — the pipes converge and draw the CondoOS mark. */
export const BRAND_DUR = 150;

const CX = 540;
const CY = 840;
const SIZE = 240; // final mark (same proportions as layout/Logo.tsx: radius ≈ 29%)
const R = 64; // "C" arc radius

// "C" opening to the right: from -45° around to +45° (counter-clockwise through the left)
const a0 = (-40 * Math.PI) / 180;
const a1 = (40 * Math.PI) / 180;
const ARC = `M${CX + R * Math.cos(a0)} ${CY + R * Math.sin(a0)} A ${R} ${R} 0 1 0 ${CX + R * Math.cos(a1)} ${CY + R * Math.sin(a1)}`;

export function BrandOutro({
  tagline1,
  tagline2,
  demoLabel,
}: {
  tagline1: string;
  tagline2: string;
  demoLabel: string;
}) {
  const t = useT();
  const lines = ramp(t, 0, 26, 0, 1, EASE_IN_OUT);
  const arc = ramp(t, 18, 48, 0, 1, EASE_IN_OUT);
  const fill = ramp(t, 44, 66, 0, 1, EASE_OUT);
  const retract = ramp(t, 50, 72, 0, 1, EASE_IN_OUT);
  const glyph = ramp(t, 60, 66);
  const arcOut = ramp(t, 58, 64);
  const word = ramp(t, 66, 92);
  const tag1 = ramp(t, 90, 110);
  const tag2 = ramp(t, 98, 118);
  const foot = ramp(t, 112, 128);
  const half = SIZE / 2;
  // lime pipes from both edges meet the mark
  const leftEnd = lerp(0, CX - R - 6, lines);
  const rightEnd = lerp(1080, CX + R * Math.cos(a0) + 4, lines);

  return (
    <AbsoluteFill style={{ fontFamily: FONT, color: C.fg }}>
      <svg width={1080} height={1920} style={{ position: "absolute" }}>
        <g stroke={C.accent} strokeWidth={10} strokeLinecap="round" opacity={1 - retract}>
          <line x1={lerp(0, CX - R - 6, retract)} y1={CY} x2={leftEnd} y2={CY} />
          <line x1={lerp(1080, CX + 60, retract)} y1={CY} x2={rightEnd} y2={CY} />
        </g>
        <rect
          x={CX - half * fill}
          y={CY - half * fill}
          width={SIZE * fill}
          height={SIZE * fill}
          rx={SIZE * 0.29 * fill}
          fill={C.accent}
          style={{ filter: `drop-shadow(0 0 ${60 * fill}px ${alpha(C.accent, 0.35)})` }}
        />
        <path
          d={ARC}
          fill="none"
          stroke={fill > 0.5 ? C.accentFg : C.accent}
          strokeWidth={26}
          strokeLinecap="round"
          pathLength={1}
          strokeDasharray={1}
          strokeDashoffset={1 - arc}
          opacity={1 - arcOut}
        />
      </svg>
      {/* The real logo glyph (Inter bold "C") takes over from the drawn arc */}
      <div
        style={{
          position: "absolute",
          left: CX - half,
          top: CY - half,
          width: SIZE,
          height: SIZE,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: SIZE * 0.47,
          fontWeight: 700,
          color: C.accentFg,
          opacity: glyph,
        }}
      >
        C
      </div>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: CY + half + 50,
          textAlign: "center",
          fontSize: 150,
          fontWeight: 600,
          letterSpacing: "-0.04em",
          opacity: word,
          transform: `translateY(${(1 - word) * 30}px)`,
          filter: `blur(${(1 - word) * 12}px)`,
        }}
      >
        CondoOS
      </div>
      <div
        style={{
          position: "absolute",
          left: 60,
          right: 60,
          top: CY + half + 260,
          textAlign: "center",
          fontSize: 46,
          lineHeight: 1.3,
          letterSpacing: "-0.02em",
        }}
      >
        <div style={{ opacity: tag1, fontWeight: 600 }}>{tagline1}</div>
        <div style={{ opacity: tag2, color: C.fg2 }}>{tagline2}</div>
      </div>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 1460,
          textAlign: "center",
          fontSize: 22,
          color: C.muted,
          opacity: foot,
          letterSpacing: "0.04em",
        }}
      >
        {demoLabel} · valores ilustrativos · a decisão é sempre do condomínio
      </div>
    </AbsoluteFill>
  );
}
