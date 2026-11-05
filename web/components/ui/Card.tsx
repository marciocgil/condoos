import type { HTMLAttributes, ReactNode } from "react";

import { cx } from "./cx";

type Tone = "default" | "highlight";

export function Card({
  tone = "default",
  className,
  children,
  ...rest
}: HTMLAttributes<HTMLElement> & { tone?: Tone }) {
  return (
    <section
      {...rest}
      className={cx(
        "rounded-[var(--radius-card)] border p-5",
        tone === "highlight" ? "border-accent/60 bg-surface" : "border-line bg-surface",
        className,
      )}
    >
      {children}
    </section>
  );
}

export function CardTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3">
      <h2 className="text-[15px] font-semibold">{children}</h2>
      {action}
    </div>
  );
}
