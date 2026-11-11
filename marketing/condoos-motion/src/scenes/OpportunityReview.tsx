import { ChevronLeft, MousePointer2 } from "lucide-react";
import { AbsoluteFill } from "remotion";

import {
  AppScale,
  Badge,
  Button,
  Card,
  Logo,
  OpportunityCard,
  OpportunityStatusBadge,
  SavingsStageCard,
} from "../components/CondoOSMockUI";
import { KineticText } from "../components/KineticText";
import { OPPORTUNITIES, OPPORTUNITIES_BY_VALUE } from "../data/demoFixtures";
import { alpha, C, FONT } from "../design/condoosTokens";
import { EASE_IN_OUT, lerp, ramp } from "../design/motion";
import { useT } from "../design/sceneTime";

/** 05 · 29–39 s — detect, prioritise, recommend; the CondoOS reviewer approves. */
export const REVIEW_DUR = 300;

const S = 2.0; // app px → video px
const PHONE = { x: 130, y: 540, w: 410, h: 500 }; // app px for w/h
const CARD_H = 112; // app px, card + gap

export function OpportunityReview({ headline }: { headline: string }) {
  const t = useT();
  const enter = ramp(t, 0, 30);
  const tilt = 1 - ramp(t, 0, 120, 0, 1, EASE_IN_OUT);
  const reorder = ramp(t, 76, 112, 0, 1, EASE_IN_OUT);
  const tap = ramp(t, 142, 150) * (1 - ramp(t, 150, 160));
  const detail = ramp(t, 150, 184);
  const press = ramp(t, 226, 232) * (1 - ramp(t, 232, 240));
  const approved = t >= 232;
  const swap = ramp(t, 232, 246);
  const opt1 = OPPORTUNITIES[0];

  // Cursor path (video px): from bottom right → OPT-001 card → "Aprovar" button
  const cardTarget = { x: PHONE.x + 300 * S, y: PHONE.y + (56 + CARD_H + 50) * S };
  const btnTarget = { x: PHONE.x + 110 * S, y: PHONE.y + 452 * S };
  const toCard = ramp(t, 116, 142, 0, 1, EASE_IN_OUT);
  const toBtn = ramp(t, 196, 224, 0, 1, EASE_IN_OUT);
  const cx = lerp(lerp(980, cardTarget.x, toCard), btnTarget.x, toBtn);
  const cy = lerp(lerp(1640, cardTarget.y, toCard), btnTarget.y, toBtn);
  const cursorO = ramp(t, 112, 122) * (1 - ramp(t, 252, 264));

  return (
    <AbsoluteFill style={{ fontFamily: FONT, color: C.fg }}>
      <KineticText
        text={headline}
        t={t}
        at={10}
        stagger={66}
        size={84}
        style={{ position: "absolute", left: 92, right: 60, top: 268 }}
      />

      <AbsoluteFill style={{ perspective: 2000 }}>
        <div
          style={{
            position: "absolute",
            left: PHONE.x,
            top: PHONE.y,
            width: PHONE.w * S,
            height: PHONE.h * S,
            opacity: enter,
            transform: `translateY(${(1 - enter) * 100}px) rotateY(${-10 * tilt}deg) rotateX(${6 * tilt}deg)`,
            borderRadius: 28 * S * 0.6,
            border: `3px solid ${C.line}`,
            background: C.bg,
            overflow: "hidden",
            boxShadow: "0 60px 120px rgba(0,0,0,0.5)",
          }}
        >
          <AppScale scale={S} width={PHONE.w}>
            <div style={{ padding: 16, height: PHONE.h, position: "relative" }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 14,
                }}
              >
                <Logo size={24} />
                <span style={{ fontSize: 13, color: C.fg2 }}>Oportunidades</span>
              </div>

              {/* List: appears in detection order, then sorts by value */}
              <div
                style={{
                  position: "relative",
                  filter: `blur(${detail * 5}px)`,
                  opacity: 1 - detail * 0.7,
                }}
              >
                {OPPORTUNITIES.map((o, i) => {
                  const target = OPPORTUNITIES_BY_VALUE.findIndex((x) => x.number === o.number);
                  const p = ramp(t, 14 + i * 14, 40 + i * 14);
                  const y = lerp(i, target, reorder) * CARD_H;
                  const isHero = o.number === opt1.number;
                  return (
                    <div
                      key={o.number}
                      style={{
                        position: "absolute",
                        left: 0,
                        right: 0,
                        top: y,
                        opacity: p,
                        transform: `translateX(${(1 - p) * 40}px) scale(${isHero ? 1 - tap * 0.03 : 1})`,
                      }}
                    >
                      <OpportunityCard o={o} highlight={isHero ? ramp(t, 136, 146) : 0} />
                    </div>
                  );
                })}
                {/* priority rank chips while sorting */}
                {[0, 1, 2].map((r) => (
                  <div
                    key={r}
                    style={{
                      position: "absolute",
                      right: 12,
                      top: r * CARD_H + 12,
                      fontSize: 11,
                      fontWeight: 600,
                      color: C.fg2,
                      opacity: ramp(t, 100, 116) * (1 - detail),
                    }}
                  >
                    #{r + 1}
                  </div>
                ))}
                <div
                  style={{
                    position: "absolute",
                    top: 3 * CARD_H + 6,
                    fontSize: 12,
                    color: C.muted,
                    opacity: ramp(t, 104, 120),
                  }}
                >
                  Ordenadas pela economia potencial · valores ilustrativos
                </div>
              </div>

              {/* Detail (OpportunityDetailView) */}
              <div
                style={{
                  position: "absolute",
                  left: 0,
                  right: 0,
                  top: 0,
                  bottom: 0,
                  padding: 16,
                  background: alpha(C.bg, 0.94),
                  opacity: detail,
                  transform: `translateY(${(1 - detail) * 60}px) scale(${lerp(0.96, 1, detail)})`,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                    fontSize: 13,
                    color: C.fg2,
                  }}
                >
                  <ChevronLeft size={16} /> Oportunidades
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 12 }}>
                  <span style={{ fontSize: 13, color: C.muted }}>{opt1.number}</span>
                  <span style={{ position: "relative", display: "inline-flex" }}>
                    <OpportunityStatusBadge
                      status="em_revisao_interna"
                      style={{ opacity: 1 - swap }}
                    />
                    <OpportunityStatusBadge
                      status="aprovada_para_cliente"
                      style={{
                        position: "absolute",
                        left: 0,
                        top: 0,
                        opacity: swap,
                        transform: `scale(${lerp(0.8, 1, swap)})`,
                      }}
                    />
                  </span>
                  <span style={{ marginLeft: 44 }}>
                    <Badge tone="neutral">{opt1.type}</Badge>
                  </span>
                </div>
                <h1 style={{ margin: "8px 0 2px", fontSize: 19, fontWeight: 600 }}>{opt1.title}</h1>
                <p style={{ margin: 0, fontSize: 13, color: C.fg2 }}>
                  {opt1.supplier}
                  {approved
                    ? " · apresentada ao condomínio"
                    : " · ainda não apresentada ao condomínio"}
                </p>
                <Card title="Recomendação" style={{ marginTop: 12, padding: 14 }}>
                  <p style={{ margin: 0, fontSize: 13 }}>
                    Pedir ao fornecedor a correção do reajuste para o IPCA previsto na cláusula 7.2
                    e a revisão das faturas desde março.
                  </p>
                  <p style={{ margin: "6px 0 0", fontSize: 12, color: C.muted }}>
                    Estimativa calculada a partir dos dados; não é economia já capturada.
                  </p>
                </Card>
                <div style={{ marginTop: 10 }}>
                  <SavingsStageCard o={opt1} value={opt1.annual * ramp(t, 160, 200)} />
                </div>
                <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
                  <Button
                    variant="primary"
                    pressed={press}
                    style={{ opacity: approved ? 0.45 : 1 }}
                  >
                    Aprovar para o condomínio
                  </Button>
                  <Button variant="secondary" style={{ opacity: approved ? 0.45 : 1 }}>
                    Devolver
                  </Button>
                </div>
              </div>
            </div>
          </AppScale>
        </div>
      </AbsoluteFill>

      {/* Review caption */}
      <div
        style={{
          position: "absolute",
          left: 108,
          right: 92,
          top: 470,
          fontSize: 26,
          color: C.fg2,
          opacity: ramp(t, 236, 252),
        }}
      >
        <span style={{ color: C.accent, fontWeight: 600 }}>Revisão interna CondoOS</span> antes de
        chegar ao condomínio.
      </div>

      {/* Cursor and tap ripple */}
      <div
        style={{
          position: "absolute",
          left: cx,
          top: cy,
          opacity: cursorO,
          filter: "drop-shadow(0 6px 10px rgba(0,0,0,0.5))",
        }}
      >
        <MousePointer2 size={56} color={C.bg} fill={C.fg} strokeWidth={1.5} />
      </div>
      {[146, 228].map((at) => {
        const p = ramp(t, at, at + 22);
        if (p <= 0 || p >= 1) return null;
        return (
          <div
            key={at}
            style={{
              position: "absolute",
              left: cx - 50 * p,
              top: cy - 50 * p,
              width: 100 * p,
              height: 100 * p,
              borderRadius: "50%",
              border: `3px solid ${C.accent}`,
              opacity: 1 - p,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
}
