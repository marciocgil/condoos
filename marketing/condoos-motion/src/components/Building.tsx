/**
 * The narrative motif: a building blueprint whose pipes are the condominium's contracts.
 * Opening ("leak"): amber drops escape at the joints. Closing ("sealed"): each joint is
 * sealed by a lime ring and the flow runs steady. Same geometry in both, for the match cut.
 */
import { alpha, C, FONT } from "../design/condoosTokens";
import { EASE_IN, ramp } from "../design/motion";

export const RISER_X = 540;
export const JOINTS = [
  { y: 520, x: 320, label: "Limpeza", hero: true },
  { y: 670, x: 760, label: "Elevadores", hero: false },
  { y: 820, x: 320, label: "Portaria", hero: false },
  { y: 970, x: 760, label: "Água e esgoto", hero: false },
  { y: 1120, x: 320, label: "Jardinagem", hero: false },
];

const OUTLINE = "M250 1230 V330 H830 V1230";
const ROOF = "M330 330 V270 H560 V330 M640 330 V290 H760 V330";
const GROUND = "M110 1230 H970";
const FLOORS = [480, 630, 780, 930, 1080].map((y) => `M250 ${y} H830`).join(" ");
const RISER = `M${RISER_X} 250 V1230`;

function branch(j: (typeof JOINTS)[number]) {
  return `M${RISER_X} ${j.y} H${j.x}`;
}

export function Building({
  t,
  mode,
  draw, // 0..1 outline and pipes drawn
  sealAt = [], // per joint: frame at which the joint is sealed (sealed mode)
  leakFrom = 0, // frame at which drops start
  flowFrom = 0, // sealed mode: frame at which the lime flow starts
}: {
  t: number;
  mode: "leak" | "sealed";
  draw: number;
  sealAt?: number[];
  leakFrom?: number;
  flowFrom?: number;
}) {
  const pipeColor = mode === "leak" ? C.fg2 : C.accent;
  const pipeOpacity = mode === "leak" ? 0.55 : 0.75;
  const dash = (p: number) => ({ strokeDasharray: 1, strokeDashoffset: 1 - p });
  const pOutline = ramp(draw, 0, 0.7, 0, 1, (x) => x);
  const pPipes = ramp(draw, 0.25, 1, 0, 1, (x) => x);
  const flow = mode === "sealed" ? ramp(t, flowFrom, flowFrom + 20) : 0;

  return (
    <svg width={1080} height={1920} viewBox="0 0 1080 1920" style={{ position: "absolute" }}>
      <defs>
        <radialGradient id="leakGlow">
          <stop offset="0%" stopColor={C.warning} stopOpacity={0.9} />
          <stop offset="100%" stopColor={C.warning} stopOpacity={0} />
        </radialGradient>
        <radialGradient id="sealGlow">
          <stop offset="0%" stopColor={C.accent} stopOpacity={0.6} />
          <stop offset="100%" stopColor={C.accent} stopOpacity={0} />
        </radialGradient>
        <linearGradient id="drop" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={C.warning} stopOpacity={0} />
          <stop offset="100%" stopColor={C.warning} stopOpacity={1} />
        </linearGradient>
      </defs>

      {/* Structure */}
      <g fill="none" stroke={alpha(C.fg2, 0.35)} strokeWidth={2}>
        <path d={OUTLINE} pathLength={1} style={dash(pOutline)} />
        <path d={ROOF} pathLength={1} style={dash(pOutline)} />
        <path d={GROUND} pathLength={1} style={dash(pOutline)} strokeWidth={3} />
      </g>
      <path
        d={FLOORS}
        fill="none"
        stroke={alpha(C.line, 0.9)}
        strokeWidth={1.5}
        strokeDasharray="6 10"
        opacity={pOutline}
      />
      {/* Windows */}
      <g opacity={pOutline * 0.5}>
        {[330, 480, 630, 780, 930, 1080].map((fy) =>
          [290, 400, 610, 720].map((wx) => (
            <rect
              key={`${fy}-${wx}`}
              x={wx}
              y={fy + 46}
              width={70}
              height={56}
              rx={4}
              fill="none"
              stroke={alpha(C.line, 0.9)}
              strokeWidth={1.5}
            />
          )),
        )}
      </g>

      {/* Pipes: riser and branches (the contracts) */}
      <g fill="none" strokeLinecap="round">
        <path
          d={RISER}
          stroke={pipeColor}
          strokeOpacity={pipeOpacity}
          strokeWidth={10}
          pathLength={1}
          style={dash(pPipes)}
        />
        {JOINTS.map((j, i) => (
          <path
            key={i}
            d={branch(j)}
            stroke={pipeColor}
            strokeOpacity={pipeOpacity}
            strokeWidth={8}
            pathLength={1}
            style={dash(ramp(pPipes, 0.3 + i * 0.1, 0.7 + i * 0.06, 0, 1, (x) => x))}
          />
        ))}
        {/* Steady lime flow once sealed */}
        {flow > 0 && (
          <g stroke={C.accent} strokeWidth={4} opacity={flow}>
            <path d={RISER} strokeDasharray="22 46" strokeDashoffset={-t * 4} />
            {JOINTS.map((j, i) => (
              <path key={i} d={branch(j)} strokeDasharray="16 40" strokeDashoffset={-t * 3} />
            ))}
          </g>
        )}
      </g>

      {/* Joints */}
      {JOINTS.map((j, i) => {
        const sealed = mode === "sealed" ? ramp(t, sealAt[i] ?? 0, (sealAt[i] ?? 0) + 18) : 0;
        const leaking = mode === "leak" || sealed < 1;
        const jointOn = ramp(pPipes, 0.6 + i * 0.06, 0.8 + i * 0.04);
        const pulse = 0.6 + 0.4 * Math.sin((t + i * 13) / 9);
        return (
          <g key={i} opacity={jointOn}>
            {leaking && t >= leakFrom && (
              <circle
                cx={j.x}
                cy={j.y}
                r={(j.hero ? 70 : 46) * pulse}
                fill="url(#leakGlow)"
                opacity={(1 - sealed) * (j.hero ? 0.75 : 0.45)}
              />
            )}
            {sealed > 0 && (
              <>
                <circle cx={j.x} cy={j.y} r={60} fill="url(#sealGlow)" opacity={sealed * 0.5} />
                <circle
                  cx={j.x}
                  cy={j.y}
                  r={14 + 50 * ramp(t, sealAt[i], sealAt[i] + 22)}
                  fill="none"
                  stroke={C.accent}
                  strokeWidth={3}
                  opacity={1 - ramp(t, sealAt[i] + 6, sealAt[i] + 24)}
                />
              </>
            )}
            <circle
              cx={j.x}
              cy={j.y}
              r={13}
              fill={C.bg}
              stroke={sealed > 0.5 ? C.accent : j.hero ? C.warning : C.fg2}
              strokeWidth={4}
            />
            {/* Drops */}
            {mode === "leak" || sealed < 1
              ? [0, 1, 2].map((k) => {
                  const period = j.hero ? 42 : 66;
                  const start = leakFrom + k * (period / 3) + i * 7;
                  if (t < start) return null;
                  const cycle = Math.floor((t - start) / period);
                  const birth = start + cycle * period;
                  // no new drop after the joint is sealed
                  if (mode === "sealed" && birth > (sealAt[i] ?? 0)) return null;
                  const p = (t - birth) / period;
                  const fall = EASE_IN(Math.min(1, p * 1.25));
                  const len = j.hero ? 46 : 30;
                  const y = j.y + 16 + fall * (j.hero ? 170 : 120);
                  return (
                    <g key={k} opacity={(1 - p) * (j.hero ? 1 : 0.7)}>
                      <rect
                        x={j.x - 2.5}
                        y={y - len}
                        width={5}
                        height={len}
                        rx={2.5}
                        fill="url(#drop)"
                      />
                      <circle cx={j.x} cy={y} r={j.hero ? 6 : 4.5} fill={C.warning} />
                    </g>
                  );
                })
              : null}
            <text
              x={j.x + (j.x < RISER_X ? -0 : 0)}
              y={j.y - 26}
              textAnchor={j.x < RISER_X ? "start" : "end"}
              fontFamily={FONT}
              fontSize={24}
              fontWeight={500}
              fill={sealed > 0.5 ? C.fg : j.hero && mode === "leak" ? C.warning : C.fg2}
              letterSpacing="0.02em"
            >
              {j.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
