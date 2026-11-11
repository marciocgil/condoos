import { TrendingUp } from "lucide-react";
import { AbsoluteFill } from "remotion";

import { Building, JOINTS } from "../components/Building";
import { AppScale, EvidenceItem, Logo } from "../components/CondoOSMockUI";
import { KineticText } from "../components/KineticText";
import { brl, pct } from "../data/format";
import { CLEANING, CLEANING_PAID, EVIDENCE } from "../data/demoFixtures";
import { alpha, C, FONT, RADIUS } from "../design/condoosTokens";
import { EASE_IN_OUT, lerp, ramp } from "../design/motion";
import { useT } from "../design/sceneTime";

/** 03 · 12–20 s — the leaks converge into CondoOS; the contract is scanned. */
export const SCAN_DUR = 250;

const DOC = { x: 110, y: 580, w: 860, h: 560 };
const CENTER = { x: 540, y: 860 };

export function ContractAnalysis({ headline }: { headline: string }) {
  const t = useT();
  const converge = ramp(t, 0, 34, 0, 1, EASE_IN_OUT);
  const mark = ramp(t, 22, 40);
  const markOut = ramp(t, 52, 72);
  const docIn = ramp(t, 52, 96);
  const scanP = ramp(t, 98, 172, 0, 1, EASE_IN_OUT);
  const scanY = DOC.y + 40 + scanP * (DOC.h - 80);
  const clause72Y = DOC.y + 300;
  const hl = ramp(scanY, clause72Y - 10, clause72Y + 30);
  const callout = ramp(t, 140, 166);

  return (
    <AbsoluteFill style={{ fontFamily: FONT, color: C.fg }}>
      {/* Leak lines converge to one point that becomes the CondoOS mark */}
      <svg width={1080} height={1920} style={{ position: "absolute", opacity: 1 - markOut }}>
        {JOINTS.map((j, i) => {
          const x = lerp(j.x, CENTER.x, converge);
          const y = lerp(j.y, CENTER.y, converge);
          return (
            <g key={i}>
              <line
                x1={j.x}
                y1={j.y}
                x2={x}
                y2={y}
                stroke={C.warning}
                strokeWidth={4}
                opacity={0.7 * (1 - mark)}
              />
              <circle cx={x} cy={y} r={10} fill={C.warning} opacity={1 - mark} />
            </g>
          );
        })}
        <circle
          cx={CENTER.x}
          cy={CENTER.y}
          r={40 + 260 * ramp(t, 30, 64)}
          fill="none"
          stroke={C.accent}
          strokeWidth={3}
          opacity={mark * (1 - ramp(t, 40, 64))}
        />
      </svg>
      {/* A faint memory of the building fades out behind */}
      <AbsoluteFill style={{ opacity: 0.25 * (1 - ramp(t, 0, 30)) }}>
        <Building t={t + 180} mode="leak" draw={1} leakFrom={0} />
      </AbsoluteFill>
      <div
        style={{
          position: "absolute",
          left: CENTER.x - 60,
          top: CENTER.y - 60,
          transform: `scale(${mark * (1 - markOut * 0.6)})`,
          opacity: mark * (1 - markOut),
        }}
      >
        <Logo size={120} compact />
      </div>

      <KineticText
        text={headline}
        t={t}
        at={34}
        stagger={4}
        size={80}
        style={{ position: "absolute", left: 92, right: 60, top: 268 }}
      />

      {/* Contract document */}
      <div style={{ position: "absolute", inset: 0, perspective: 1600 }}>
        <div
          style={{
            position: "absolute",
            left: DOC.x,
            top: DOC.y,
            width: DOC.w,
            height: DOC.h,
            borderRadius: RADIUS.panel * 1.5,
            background: C.surface,
            border: `2px solid ${C.line}`,
            boxShadow: "0 40px 80px rgba(0,0,0,0.45)",
            padding: "40px 48px",
            opacity: docIn,
            transform: `translateY(${(1 - docIn) * 120}px) rotateX(${lerp(22, 5, docIn)}deg) rotateY(${lerp(-16, -4, docIn)}deg)`,
            transformOrigin: "50% 100%",
            overflow: "hidden",
          }}
        >
          <div style={{ fontSize: 20, letterSpacing: "0.14em", color: C.muted, fontWeight: 600 }}>
            CONTRATO · {CLEANING.supplier.toUpperCase()}
          </div>
          <div style={{ fontSize: 34, fontWeight: 600, marginTop: 10, letterSpacing: "-0.02em" }}>
            Prestação de serviços de limpeza
          </div>
          <Bars widths={[92, 84, 88]} />
          <Clause
            n="7.1"
            text={`Valor mensal: ${brl(CLEANING.monthly)}.`}
            top={0}
            hl={ramp(scanY, DOC.y + 230, DOC.y + 260) * 0.5}
          />
          <Clause
            n="7.2"
            text="O valor será reajustado anualmente pela variação do IPCA."
            top={0}
            hl={hl}
          />
          <Bars widths={[90, 76, 94, 60]} />

          {/* Scan line */}
          <div
            style={{
              position: "absolute",
              left: 0,
              right: 0,
              top: scanY - DOC.y,
              height: 0,
              opacity: scanP > 0 && scanP < 1 ? 1 : 0,
            }}
          >
            <div
              style={{
                position: "absolute",
                left: 0,
                right: 0,
                top: -140,
                height: 140,
                background: `linear-gradient(to bottom, transparent, ${alpha(C.accent, 0.12)})`,
              }}
            />
            <div
              style={{
                position: "absolute",
                left: 0,
                right: 0,
                top: -2,
                height: 4,
                background: C.accent,
                boxShadow: `0 0 24px 6px ${alpha(C.accent, 0.45)}`,
              }}
            />
          </div>
        </div>
      </div>

      {/* Callout: applied readjustment vs. the contract index */}
      <div
        style={{
          position: "absolute",
          right: 70,
          top: DOC.y + DOC.h - 170,
          width: 520,
          borderRadius: RADIUS.card * 1.5,
          background: C.elevated,
          border: `2px solid ${alpha(C.warning, 0.6)}`,
          padding: "22px 28px",
          opacity: callout,
          transform: `translateY(${(1 - callout) * 40}px) scale(${lerp(0.94, 1, callout)})`,
          boxShadow: "0 30px 60px rgba(0,0,0,0.4)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            color: C.warning,
            fontSize: 24,
            fontWeight: 600,
          }}
        >
          <TrendingUp size={28} /> Divergência no reajuste
        </div>
        <div
          style={{ marginTop: 10, fontSize: 26, color: C.fg2, fontVariantNumeric: "tabular-nums" }}
        >
          Aplicado <b style={{ color: C.fg }}>{pct(CLEANING.appliedRate)}</b> · IPCA do período{" "}
          <b style={{ color: C.fg }}>{pct(CLEANING.ipcaRate)}</b>
        </div>
      </div>

      {/* Evidence list */}
      <div style={{ position: "absolute", left: 110, top: 1176 }}>
        <AppScale scale={1.8} width={478}>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {EVIDENCE.map((e, i) => {
              const p = ramp(t, 176 + i * 12, 200 + i * 12);
              return (
                <EvidenceItem
                  key={i}
                  icon={e.icon}
                  label={e.label.replace("{paid}", brl(CLEANING_PAID))}
                  excerpt={e.excerpt}
                  style={{
                    opacity: p,
                    transform: `translateX(${(1 - p) * 60}px)`,
                  }}
                />
              );
            })}
          </div>
        </AppScale>
      </div>
    </AbsoluteFill>
  );
}

function Bars({ widths }: { widths: number[] }) {
  return (
    <div style={{ margin: "26px 0", display: "flex", flexDirection: "column", gap: 16 }}>
      {widths.map((w, i) => (
        <div
          key={i}
          style={{ width: `${w}%`, height: 12, borderRadius: 6, background: alpha(C.fg2, 0.16) }}
        />
      ))}
    </div>
  );
}

function Clause({ n, text, hl }: { n: string; text: string; top: number; hl: number }) {
  return (
    <div
      style={{
        position: "relative",
        margin: "6px -14px",
        padding: "10px 14px",
        borderRadius: RADIUS.control * 1.5,
        border: `2px solid ${alpha(C.accent, 0.8 * hl)}`,
        background: alpha(C.accent, 0.08 * hl),
        fontSize: 27,
        lineHeight: 1.35,
        color: hl > 0.5 ? C.fg : C.fg2,
      }}
    >
      <b style={{ color: hl > 0.5 ? C.accent : C.muted, marginRight: 12 }}>{n}</b>
      {text}
    </div>
  );
}
