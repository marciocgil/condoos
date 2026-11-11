import { Easing, interpolate, random } from "remotion";

export const EASE_OUT = Easing.bezier(0.16, 1, 0.3, 1);
export const EASE_IN_OUT = Easing.bezier(0.65, 0, 0.35, 1);
export const EASE_IN = Easing.bezier(0.55, 0, 1, 0.45);

/** Clamped 0..1 progress between frames a and b (eased), mapped to [from, to]. */
export function ramp(
  t: number,
  a: number,
  b: number,
  from = 0,
  to = 1,
  easing: (n: number) => number = EASE_OUT,
): number {
  return interpolate(t, [a, b], [from, to], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing,
  });
}

export const lerp = (a: number, b: number, p: number) => a + (b - a) * p;

/** Deterministic pseudo-random number (same frame, same value). */
export const rnd = (seed: string | number) => random(seed);
