import type { ReactNode } from "react";

import { cx } from "./cx";

export type BadgeTone = "danger" | "warning" | "success" | "info" | "neutral" | "accent";

const TONE: Record<BadgeTone, string> = {
  danger: "border-danger/60 text-danger",
  warning: "border-warning/60 text-warning",
  success: "border-success/60 text-success",
  info: "border-info/60 text-info",
  neutral: "border-control text-fg-2",
  accent: "border-accent/70 text-accent",
};

/** Status Badge (DS §5.6): always text (and usually an icon), never colour alone. */
export function Badge({
  tone,
  icon,
  children,
}: {
  tone: BadgeTone;
  icon?: ReactNode;
  children: ReactNode;
}) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap",
        TONE[tone],
      )}
    >
      {icon && (
        <span aria-hidden className="inline-flex">
          {icon}
        </span>
      )}
      {children}
    </span>
  );
}
