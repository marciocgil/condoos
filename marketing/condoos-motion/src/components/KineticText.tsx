import type { CSSProperties } from "react";

import { C, FONT } from "../design/condoosTokens";
import { ramp } from "../design/motion";

type Word = { text: string; em: boolean };

/**
 * "Nem todo vazamento / faz *barulho*." → lines split by " / ", emphasis between asterisks
 * (may span several words). Editable from the Studio props panel.
 */
export function parseHeadline(src: string): Word[][] {
  let em = false;
  return src.split(/\s*\/\s*/).map((line) =>
    line
      .split(/\s+/)
      .filter(Boolean)
      .map((raw) => {
        let text = raw;
        let wordEm = em;
        if (text.startsWith("*")) {
          em = true;
          wordEm = true;
          text = text.slice(1);
        }
        const closeIdx = text.indexOf("*");
        if (closeIdx >= 0) {
          text = text.slice(0, closeIdx) + text.slice(closeIdx + 1);
          em = false;
        }
        return { text, em: wordEm };
      }),
  );
}

/** Kinetic headline: each word rises out of a blur; optional exit. */
export function KineticText({
  text,
  t,
  at,
  out,
  size = 86,
  emColor = C.accent,
  stagger = 4,
  align = "left",
  style,
}: {
  text: string;
  t: number;
  at: number;
  out?: number;
  size?: number;
  emColor?: string;
  stagger?: number;
  align?: "left" | "center";
  style?: CSSProperties;
}) {
  const lines = parseHeadline(text);
  let idx = 0;
  return (
    <div
      style={{
        fontFamily: FONT,
        fontSize: size,
        lineHeight: 1.04,
        letterSpacing: "-0.04em",
        textAlign: align,
        color: C.fg,
        ...style,
      }}
    >
      {lines.map((line, li) => (
        <div key={li} style={{ whiteSpace: "nowrap" }}>
          {line.map((w, wi) => {
            const i = idx++;
            const p = ramp(t, at + i * stagger, at + i * stagger + 20);
            const q = out === undefined ? 0 : ramp(t, out + i * 2, out + i * 2 + 14);
            return (
              <span
                key={wi}
                style={{
                  display: "inline-block",
                  marginRight: "0.24em",
                  opacity: p * (1 - q),
                  transform: `translateY(${(1 - p) * 0.45 - q * 0.25}em)`,
                  filter: `blur(${(1 - p) * 14 + q * 10}px)`,
                  fontWeight: w.em ? 400 : 800,
                  color: w.em ? emColor : C.fg,
                }}
              >
                {w.text}
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
}
