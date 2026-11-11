import { AbsoluteFill } from "remotion";

import { Building } from "../components/Building";
import { KineticText } from "../components/KineticText";
import { EASE_IN_OUT, lerp, ramp } from "../design/motion";
import { useT } from "../design/sceneTime";

/** 07 · 49–55 s — match cut back to the opening building: every joint gets sealed. */
export const SEALED_DUR = 180;

export function SealedBuilding({ headline }: { headline: string }) {
  const t = useT();
  const pull = ramp(t, 0, 170, 0, 1, EASE_IN_OUT);
  const converge = ramp(t, 150, 182, 0, 1, EASE_IN_OUT);
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ perspective: 1800 }}>
        <AbsoluteFill
          style={{
            transformOrigin: "540px 760px",
            transform: `rotateX(${lerp(3, 10, pull)}deg) scale(${lerp(1.14, 1, pull) * lerp(1, 0.6, converge)}) translateY(${converge * 60}px)`,
            opacity: 1 - ramp(t, 156, 182),
          }}
        >
          <Building
            t={t}
            mode="sealed"
            draw={ramp(t, 0, 34, 0, 1, (x) => x)}
            leakFrom={0}
            sealAt={[40, 54, 68, 82, 96]}
            flowFrom={44}
          />
        </AbsoluteFill>
      </AbsoluteFill>
      <KineticText
        text={headline}
        t={t}
        at={62}
        out={152}
        stagger={5}
        size={92}
        style={{ position: "absolute", left: 92, right: 60, top: 1336 }}
      />
    </AbsoluteFill>
  );
}
