import { AbsoluteFill } from "remotion";

import { KineticText } from "../components/KineticText";
import { brl } from "../data/format";
import { CLEANING, CLEANING_DIFF, DRIFT_MONTHS, DRIFT_TOTAL, LEDGER } from "../data/demoFixtures";
import { alpha, C, FONT, RADIUS } from "../design/condoosTokens";
import { EASE_IN_OUT, lerp, ramp } from "../design/motion";
import { useT } from "../design/sceneTime";

/** 02 · 6–12 s — the camera flies through twelve monthly invoices; the gap grows. */
export const DRIFT_DUR = 200;
const GAP = 470;

export function CostDrift({ headline }: { headline: string }) {
  const t = useT();
  const camZ = lerp(-700, 11 * GAP + 300, ramp(t, 0, 188, 0, 1, EASE_IN_OUT));
  // months already passed by the camera (continuous)
  const passed = Math.min(12, Math.max(0, camZ / GAP + 0.5));
  const extra = Math.min(DRIFT_TOTAL, Math.max(0, passed - CLEANING.readjustMonth) * CLEANING_DIFF);

  const cards = LEDGER.map((m, i) => ({ ...m, i, z: camZ - i * GAP })).sort((a, b) => a.z - b.z);

  return (
    <AbsoluteFill style={{ fontFamily: FONT, color: C.fg }}>
      <KineticText
        text={headline}
        t={t}
        at={6}
        stagger={4}
        emColor={C.warning}
        size={84}
        style={{ position: "absolute", left: 92, right: 60, top: 270 }}
      />

      {/* Card tunnel */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 580,
          height: 560,
          perspective: 1000,
          perspectiveOrigin: "50% 40%",
          overflow: "visible",
        }}
      >
        {cards.map((c) => {
          const o = ramp(c.z, -4200, -2200) * (1 - ramp(c.z, 120, 420));
          if (o <= 0.001) return null;
          const side = c.i % 2 === 0 ? -1 : 1;
          return (
            <div
              key={c.i}
              style={{
                position: "absolute",
                left: 160,
                top: 170,
                width: 760,
                height: 200,
                transform: `translate3d(${side * 70}px, ${side * -18}px, ${c.z}px) rotateY(${side * -7}deg)`,
                opacity: o,
                borderRadius: RADIUS.card * 1.6,
                background: C.surface,
                border: `2px solid ${c.extra ? alpha(C.warning, 0.55) : C.line}`,
                boxShadow: "0 30px 60px rgba(0,0,0,0.35)",
                padding: "26px 34px",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 24 }}>
                <span style={{ color: C.muted, letterSpacing: "0.12em", fontWeight: 600 }}>
                  {c.month}
                </span>
                <span style={{ color: C.fg2 }}>{CLEANING.supplier}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "end" }}>
                <span style={{ fontSize: 54, fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
                  {brl(c.paid)}
                </span>
                {c.extra > 0 ? (
                  <span
                    style={{
                      fontSize: 24,
                      color: C.warning,
                      border: `2px solid ${alpha(C.warning, 0.6)}`,
                      borderRadius: 999,
                      padding: "4px 16px",
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    +{brl(c.extra)}
                  </span>
                ) : (
                  <span style={{ fontSize: 24, color: C.muted }}>valor do contrato</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <DriftChart t={t} passed={passed} extra={extra} />
    </AbsoluteFill>
  );
}

function DriftChart({ t, passed, extra }: { t: number; passed: number; extra: number }) {
  const x0 = 92;
  const w = 896;
  const top = 1300;
  const h = 230;
  const min = 18000;
  const max = 20600;
  const px = (i: number) => x0 + (i / 11) * w;
  const py = (v: number) => top + h - ((v - min) / (max - min)) * h;
  const upto = Math.max(0.0001, Math.min(11, passed - 0.5));
  const pts = (key: "paid" | "due") => {
    const out: string[] = [];
    for (let i = 0; i <= Math.floor(upto); i++) out.push(`${px(i)},${py(LEDGER[i][key])}`);
    const fi = Math.floor(upto);
    if (fi < 11) {
      const f = upto - fi;
      const v = lerp(LEDGER[fi][key], LEDGER[fi + 1][key], f);
      out.push(`${px(fi + f)},${py(v)}`);
    }
    return out;
  };
  const paid = pts("paid");
  const due = pts("due");
  const area = `M${paid.join(" L")} L${[...due].reverse().join(" L")} Z`;
  const appear = ramp(t, 20, 45);

  return (
    <div style={{ position: "absolute", left: 0, top: 0, opacity: appear }}>
      <div
        style={{
          position: "absolute",
          left: x0,
          top: 1150,
          width: w,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
        }}
      >
        <span style={{ fontSize: 26, color: C.fg2 }}>
          pagos acima do contrato
          <br />
          {monthsLabel(
            Math.max(0, Math.min(DRIFT_MONTHS, Math.round(passed - CLEANING.readjustMonth))),
          )}
        </span>
        <span
          style={{
            fontSize: 76,
            fontWeight: 700,
            color: C.warning,
            letterSpacing: "-0.03em",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {brl(extra)}
        </span>
      </div>
      <svg width={1080} height={1920} style={{ position: "absolute", left: 0, top: 0 }}>
        <line x1={x0} x2={x0 + w} y1={top + h} y2={top + h} stroke={C.line} strokeWidth={2} />
        <path d={area} fill={alpha(C.warning, 0.22)} />
        <polyline
          points={due.join(" ")}
          fill="none"
          stroke={C.fg2}
          strokeWidth={3}
          strokeDasharray="10 10"
        />
        <polyline
          points={paid.join(" ")}
          fill="none"
          stroke={C.warning}
          strokeWidth={5}
          strokeLinejoin="round"
        />
        <text x={x0} y={top + h + 40} fontSize={22} fill={C.muted} fontFamily={FONT}>
          JAN
        </text>
        <text
          x={x0 + w}
          y={top + h + 40}
          fontSize={22}
          fill={C.muted}
          fontFamily={FONT}
          textAnchor="end"
        >
          DEZ
        </text>
        <g fontFamily={FONT} fontSize={22}>
          <line
            x1={x0 + 260}
            x2={x0 + 300}
            y1={top + h + 32}
            y2={top + h + 32}
            stroke={C.warning}
            strokeWidth={5}
          />
          <text x={x0 + 312} y={top + h + 40} fill={C.fg2}>
            pago
          </text>
          <line
            x1={x0 + 420}
            x2={x0 + 460}
            y1={top + h + 32}
            y2={top + h + 32}
            stroke={C.fg2}
            strokeWidth={3}
            strokeDasharray="8 6"
          />
          <text x={x0 + 472} y={top + h + 40} fill={C.fg2}>
            previsto no contrato
          </text>
        </g>
      </svg>
    </div>
  );
}

function monthsLabel(n: number) {
  return n === 1 ? "em 1 mês" : `em ${n} meses`;
}
