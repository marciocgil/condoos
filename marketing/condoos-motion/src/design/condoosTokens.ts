/**
 * CondoOS Design System v1.0 tokens, copied from web/app/globals.css (dark theme).
 * The film never imports from web/: the product app stays untouched.
 */
export const C = {
  bg: "#22262C",
  bg2: "#292E35",
  surface: "#30363E",
  elevated: "#3A424B",
  line: "#434B54",
  control: "#797F85",
  fg: "#F5F6F3",
  fg2: "#B7BEC7",
  muted: "#A6AEB8",
  accent: "#D9FC00", // lime: only CondoOS actions, active items and the brand
  accentFg: "#202500",
  success: "#69C8A3",
  warning: "#F0BD70", // the "leaks" (problem) use warning, never the accent
  danger: "#E7837D",
  info: "#84AADF",
} as const;

export const RADIUS = { card: 14, panel: 16, control: 8, button: 10 } as const;

export const FONT = "Inter, ui-sans-serif, system-ui, sans-serif";

/** Hex colour with alpha (0..1). */
export function alpha(hex: string, a: number): string {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
}
