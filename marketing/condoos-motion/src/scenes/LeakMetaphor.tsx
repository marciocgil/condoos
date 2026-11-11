import { AbsoluteFill } from "remotion";

import { Building } from "../components/Building";
import { KineticText } from "../components/KineticText";
import { C } from "../design/condoosTokens";
import { EASE_IN, EASE_IN_OUT, lerp, ramp } from "../design/motion";
import { useT } from "../design/sceneTime";

/** 01 · 0–6 s — the building at night; invisible leaks at the contract joints. */
export const LEAK_DUR = 180;

export function LeakMetaphor({ headline }: { headline: string }) {
  const t = useT();
  const push = ramp(t, 0, 160, 0, 1, EASE_IN_OUT);
  const dive = ramp(t, 150, 182, 0, 1, EASE_IN);
  const scale = lerp(1, 1.12, push) * lerp(1, 2.8, dive);
  const tilt = lerp(10, 3, push);
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ perspective: 1800 }}>
        <AbsoluteFill
          style={{
            transformOrigin: "540px 760px",
            transform: `translateY(${-dive * 140}px) rotateX(${tilt}deg) scale(${scale})`,
            opacity: 1 - ramp(t, 160, 182),
            filter: `blur(${dive * 8}px)`,
          }}
        >
          <Building t={t} mode="leak" draw={ramp(t, -50, 40, 0, 1, (x) => x)} leakFrom={-30} />
        </AbsoluteFill>
      </AbsoluteFill>
      <KineticText
        text={headline}
        t={t}
        at={46}
        out={150}
        stagger={5}
        emColor={C.warning}
        size={92}
        style={{ position: "absolute", left: 92, right: 60, top: 1336 }}
      />
    </AbsoluteFill>
  );
}
