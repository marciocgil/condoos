import { createContext, useContext, type ReactNode } from "react";
import { useCurrentFrame } from "remotion";

/**
 * Scene clock. Every scene is written on its own base timeline (frames at 30 fps);
 * the 15 s cut reuses the same scenes faster (`speed`) or trimmed (`startAt`).
 */
const Ctx = createContext({ speed: 1, startAt: 0 });

export function SceneTime({
  speed = 1,
  startAt = 0,
  children,
}: {
  speed?: number;
  startAt?: number;
  children: ReactNode;
}) {
  return <Ctx.Provider value={{ speed, startAt }}>{children}</Ctx.Provider>;
}

/** Current time in the scene's base timeline. */
export function useT(): number {
  const frame = useCurrentFrame();
  const { speed, startAt } = useContext(Ctx);
  return startAt + frame * speed;
}
