import { ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import { AbsoluteFill } from "remotion";

import {
  AdminShell,
  Button,
  OpportunityCard,
  OpportunityStatusBadge,
} from "../components/CondoOSMockUI";
import { KineticText } from "../components/KineticText";
import { brl } from "../data/format";
import { CONTRACT_ROWS, OPPORTUNITIES_BY_VALUE } from "../data/demoFixtures";
import { alpha, C, FONT, RADIUS } from "../design/condoosTokens";
import { EASE_IN, EASE_IN_OUT, lerp, ramp } from "../design/motion";
import { useT } from "../design/sceneTime";

/** 04 · 20–29 s — the product explodes into its four layers and comes back together. */
export const LAYERS_DUR = 270;

// Plane size in app px; drawn at SCALE inside the 3D group.
const W = 1000;
const H = 620;
const SCALE = 0.7;

export function LayeredProduct({ headline }: { headline: string }) {
  const t = useT();
  const open = ramp(t, 36, 100, 0, 1, EASE_IN_OUT);
  const close = ramp(t, 206, 244, 0, 1, EASE_IN_OUT);
  const iso = open * (1 - close);
  const sep = ramp(t, 56, 116, 0, 1, EASE_IN_OUT) * (1 - ramp(t, 196, 236, 0, 1, EASE_IN_OUT));
  const zoom = ramp(t, 236, 272, 0, 1, EASE_IN);
  const rotX = lerp(0, 56, iso);
  const rotZ = lerp(
    0,
    lerp(
      -34,
      -24,
      ramp(t, 100, 206, 0, 1, (x) => x),
    ),
    iso,
  );
  const enter = ramp(t, 0, 30);
  const labels = ramp(t, 96, 124) * (1 - ramp(t, 190, 206));

  const layers: { tag: string; node: ReactNode }[] = [
    { tag: "01  CONTRATOS E DESPESAS", node: <BaseLayer /> },
    { tag: "02  OPORTUNIDADES", node: <OppLayer /> },
    { tag: "03  REVISÃO INTERNA CONDOOS", node: <ReviewLayer /> },
    { tag: "04  DECISÃO DO CONDOMÍNIO", node: <DecisionLayer /> },
  ];

  return (
    <AbsoluteFill style={{ fontFamily: FONT, color: C.fg }}>
      <KineticText
        text={headline}
        t={t}
        at={8}
        out={238}
        stagger={4}
        size={80}
        style={{ position: "absolute", left: 92, right: 60, top: 268 }}
      />
      <AbsoluteFill style={{ perspective: 2400, perspectiveOrigin: "50% 45%" }}>
        <div
          style={{
            position: "absolute",
            left: 540 - (W * SCALE) / 2,
            top: 1120 - (H * SCALE) / 2,
            width: W * SCALE,
            height: H * SCALE,
            transformStyle: "preserve-3d",
            transform: `translateY(${(1 - enter) * 80 - zoom * 120}px) scale(${lerp(0.92, 1, enter) * lerp(1, 2.4, zoom)}) rotateX(${rotX}deg) rotateZ(${rotZ}deg)`,
            opacity: enter * (1 - ramp(t, 250, 272)),
          }}
        >
          {layers.map((l, i) => (
            <div
              key={i}
              style={{
                position: "absolute",
                inset: 0,
                transformStyle: "preserve-3d",
                transform: `translateZ(${i * 150 * sep}px)`,
              }}
            >
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  borderRadius: RADIUS.panel,
                  border: `2px solid ${alpha(C.accent, 0.55 * sep)}`,
                  background: i === 0 ? "transparent" : alpha(C.bg2, 0.35 * sep),
                  boxShadow: sep > 0 ? `0 0 ${40 * sep}px ${alpha(C.accent, 0.08)}` : "none",
                }}
              />
              <div
                style={{
                  width: W,
                  height: H,
                  transform: `scale(${SCALE})`,
                  transformOrigin: "top left",
                  position: "relative",
                }}
              >
                {l.node}
              </div>
              <div
                style={{
                  position: "absolute",
                  left: -4,
                  top: -58,
                  fontSize: 34,
                  fontWeight: 700,
                  letterSpacing: "0.1em",
                  color: C.accent,
                  opacity: labels,
                  whiteSpace: "nowrap",
                }}
              >
                {l.tag}
              </div>
            </div>
          ))}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
}

function BaseLayer() {
  return (
    <AdminShell active="Oportunidades" title="Oportunidades" width={W} height={H}>
      <div style={{ fontSize: 13, color: C.fg2, marginBottom: 10 }}>Contratos vigentes</div>
      <div style={{ width: 420, fontSize: 13 }}>
        {CONTRACT_ROWS.map((r, i) => (
          <div
            key={r.name}
            style={{
              display: "flex",
              justifyContent: "space-between",
              padding: "10px 0",
              borderTop: i ? `1px solid ${C.line}` : "none",
            }}
          >
            <span>
              {r.name}
              <span style={{ display: "block", color: C.muted, fontSize: 12 }}>{r.kind}</span>
            </span>
            <span style={{ fontVariantNumeric: "tabular-nums", color: C.fg2 }}>
              {brl(r.value)}/mês
            </span>
          </div>
        ))}
      </div>
    </AdminShell>
  );
}

function OppLayer() {
  return (
    <div
      style={{
        position: "absolute",
        left: 660,
        top: 70,
        width: 320,
        display: "flex",
        flexDirection: "column",
        gap: 10,
        fontFamily: FONT,
        color: C.fg,
        fontSize: 14,
      }}
    >
      {OPPORTUNITIES_BY_VALUE.map((o) => (
        <OpportunityCard key={o.number} o={o} style={{ padding: 12 }} />
      ))}
    </div>
  );
}

function ReviewLayer() {
  return (
    <div
      style={{
        position: "absolute",
        left: 240,
        top: 430,
        width: 400,
        borderRadius: RADIUS.card,
        border: `1px solid ${C.line}`,
        background: C.surface,
        padding: 16,
        fontFamily: FONT,
        color: C.fg,
        fontSize: 14,
      }}
    >
      <OpportunityStatusBadge status="em_revisao_interna" />
      <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
        <Button variant="primary">Aprovar para o condomínio</Button>
        <Button variant="secondary">Devolver</Button>
      </div>
    </div>
  );
}

function DecisionLayer() {
  return (
    <div
      style={{
        position: "absolute",
        left: 240,
        top: 330,
        width: 400,
        borderRadius: RADIUS.card,
        border: `1px solid ${alpha(C.success, 0.5)}`,
        background: C.surface,
        padding: 16,
        fontFamily: FONT,
        color: C.fg,
        fontSize: 14,
        display: "flex",
        alignItems: "center",
        gap: 12,
      }}
    >
      <ShieldCheck size={22} color={C.success} />
      <span>
        Decisão do corpo diretivo
        <span style={{ display: "block", color: C.fg2, fontSize: 13 }}>
          Aprovar e seguir · Recusar
        </span>
      </span>
    </div>
  );
}
