import {
  Calculator,
  ClipboardCheck,
  FileSignature,
  Lightbulb,
  Search,
  ShieldCheck,
} from "lucide-react";
import type { ReactNode } from "react";
import { AbsoluteFill } from "remotion";

import { AppScale, Badge, KpiCard } from "../components/CondoOSMockUI";
import { KineticText } from "../components/KineticText";
import { brl } from "../data/format";
import {
  CONTRACTS_ANALYZED,
  OPPORTUNITIES,
  OPPORTUNITIES_BY_VALUE,
  POTENTIAL_TOTAL,
} from "../data/demoFixtures";
import { alpha, C, FONT, RADIUS } from "../design/condoosTokens";
import { EASE_IN_OUT, EASE_OUT, ramp } from "../design/motion";
import { useT } from "../design/sceneTime";

/** 06 · 39–49 s — numbers come alive and the path from diagnosis to decision. */
export const IMPACT_DUR = 300;

const NODES: { label: string; icon: (c: string) => ReactNode; x: number; y: number }[] = [
  { label: "Análise", icon: (c) => <Search size={38} color={c} />, x: 170, y: 1200 },
  {
    label: "Revisão interna|CondoOS",
    icon: (c) => <ClipboardCheck size={38} color={c} />,
    x: 420,
    y: 1130,
  },
  { label: "Recomendação", icon: (c) => <Lightbulb size={38} color={c} />, x: 670, y: 1200 },
  {
    label: "Decisão do|condomínio",
    icon: (c) => <ShieldCheck size={38} color={c} />,
    x: 910,
    y: 1130,
  },
];
const FLOW = `M40 1170 C 110 1170, 120 1200, 170 1200 S 360 1130, 420 1130 S 610 1200, 670 1200 S 850 1130, 910 1130 S 1020 1160, 1080 1160`;

export function ImpactDashboard({ headline }: { headline: string }) {
  const t = useT();
  const k1 = ramp(t, 16, 44);
  const k2 = ramp(t, 26, 54);
  const big = ramp(t, 50, 84);
  const count = (a: number, b: number) => ramp(t, a, b, 0, 1, EASE_OUT);
  const flowDraw = ramp(t, 132, 170, 0, 1, EASE_IN_OUT);
  const pulse = ramp(t, 160, 250, 0, 1, EASE_IN_OUT);
  const maxV = OPPORTUNITIES_BY_VALUE[0].annual;

  return (
    <AbsoluteFill style={{ fontFamily: FONT, color: C.fg }}>
      <KineticText
        text={headline}
        t={t}
        at={4}
        stagger={5}
        size={88}
        style={{ position: "absolute", left: 92, right: 60, top: 268 }}
      />

      {/* KPI row */}
      <div style={{ position: "absolute", left: 92, top: 480, display: "flex", gap: 24 }}>
        <div style={{ opacity: k1, transform: `translateY(${(1 - k1) * 40}px)` }}>
          <AppScale scale={1.8} width={242}>
            <KpiCard
              label="Contratos analisados"
              icon={<FileSignature size={16} />}
              value={Math.round(CONTRACTS_ANALYZED * count(24, 80))}
              context="de 12 no condomínio"
            />
          </AppScale>
        </div>
        <div style={{ opacity: k2, transform: `translateY(${(1 - k2) * 40}px)` }}>
          <AppScale scale={1.8} width={242}>
            <KpiCard
              label="Oportunidades"
              icon={<Lightbulb size={16} />}
              value={Math.round(OPPORTUNITIES.length * count(34, 80))}
              context="aguardando decisão"
            />
          </AppScale>
        </div>
      </div>

      {/* Potential (one stage, illustrative sum of the three opportunities) */}
      <div
        style={{
          position: "absolute",
          left: 92,
          top: 700,
          opacity: big,
          transform: `translateY(${(1 - big) * 40}px)`,
        }}
      >
        <AppScale scale={1.8} width={498}>
          <div
            style={{
              borderRadius: RADIUS.card,
              border: `1px solid ${alpha(C.success, 0.5)}`,
              background: C.surface,
              padding: 20,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 13, fontWeight: 500, color: C.fg2 }}>
                Economia potencial identificada
              </span>
              <Badge tone="warning" icon={<Calculator size={12} />}>
                Estimativa
              </Badge>
            </div>
            <div
              style={{
                marginTop: 6,
                fontSize: 30,
                fontWeight: 600,
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {brl(POTENTIAL_TOTAL * count(56, 140))}{" "}
              <span style={{ fontSize: 14, fontWeight: 400, color: C.fg2 }}>por ano</span>
            </div>
            <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
              {OPPORTUNITIES_BY_VALUE.map((o, i) => {
                const p = ramp(t, 80 + i * 10, 130 + i * 10);
                return (
                  <div key={o.number} style={{ fontSize: 12 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", color: C.fg2 }}>
                      <span>
                        {o.number} · {o.type}
                      </span>
                      <span style={{ fontVariantNumeric: "tabular-nums" }}>{brl(o.annual)}</span>
                    </div>
                    <div style={{ marginTop: 4, height: 6, borderRadius: 3, background: C.bg2 }}>
                      <div
                        style={{
                          width: `${(o.annual / maxV) * 100 * p}%`,
                          height: 6,
                          borderRadius: 3,
                          background: C.success,
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
            <div style={{ marginTop: 10, fontSize: 11, color: C.muted }}>
              Soma ilustrativa das três estimativas. Não é economia já capturada.
            </div>
          </div>
        </AppScale>
      </div>

      {/* Flow: analysis → internal review → recommendation → condominium decision */}
      <svg width={1080} height={1920} style={{ position: "absolute", left: 0, top: 0 }}>
        <path
          d={FLOW}
          fill="none"
          stroke={C.line}
          strokeWidth={4}
          pathLength={1}
          strokeDasharray={1}
          strokeDashoffset={1 - flowDraw}
        />
        <path
          d={FLOW}
          fill="none"
          stroke={C.accent}
          strokeWidth={5}
          pathLength={1}
          strokeDasharray={1}
          strokeDashoffset={1 - pulse}
          style={{ filter: `drop-shadow(0 0 10px ${alpha(C.accent, 0.6)})` }}
        />
      </svg>
      {NODES.map((n, i) => {
        const appear = ramp(t, 140 + i * 6, 160 + i * 6);
        const lit = ramp(pulse, 0.12 + i * 0.25, 0.2 + i * 0.25);
        return (
          <div
            key={n.label}
            style={{
              position: "absolute",
              left: n.x - 50,
              top: n.y - 50,
              width: 100,
              opacity: appear,
              transform: `scale(${0.8 + 0.2 * appear + 0.08 * lit * (1 - ramp(pulse, 0.25 + i * 0.25, 0.4 + i * 0.25))})`,
            }}
          >
            <div
              style={{
                width: 100,
                height: 100,
                borderRadius: 50,
                background: C.surface,
                border: `3px solid ${lit > 0.5 ? C.accent : C.line}`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: lit ? `0 0 ${30 * lit}px ${alpha(C.accent, 0.35)}` : "none",
              }}
            >
              {n.icon(lit > 0.5 ? C.accent : C.fg2)}
            </div>
            <div
              style={{
                position: "absolute",
                left: -70,
                width: 240,
                top: 116,
                textAlign: "center",
                fontSize: 26,
                lineHeight: 1.2,
                fontWeight: lit > 0.5 ? 600 : 400,
                color: lit > 0.5 ? C.fg : C.fg2,
              }}
            >
              {n.label.split("|").map((s) => (
                <div key={s}>{s}</div>
              ))}
            </div>
          </div>
        );
      })}
      <div
        style={{
          position: "absolute",
          left: 92,
          right: 92,
          top: 1446,
          textAlign: "center",
          fontSize: 30,
          lineHeight: 1.35,
          color: C.fg2,
          opacity: ramp(t, 244, 264),
        }}
      >
        <span style={{ color: C.fg, fontWeight: 600 }}>A decisão é sempre do condomínio.</span>
        <br />
        Nada é pago ou contratado pelo sistema.
      </div>
    </AbsoluteFill>
  );
}
