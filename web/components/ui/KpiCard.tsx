import type { ReactNode } from "react";

import { cx } from "./cx";

type Tone = "normal" | "attention" | "positive";

/** KPI Card (DS §5.1): label, main value, context; tone never conveyed by colour alone. */
export function KpiCard({
  label,
  value,
  context,
  icon,
  tone = "normal",
  testId,
}: {
  label: string;
  value: ReactNode;
  context?: ReactNode;
  icon?: ReactNode;
  tone?: Tone;
  testId?: string;
}) {
  return (
    <div
      className={cx(
        "rounded-[var(--radius-card)] border bg-surface p-5",
        tone === "attention"
          ? "border-warning/50"
          : tone === "positive"
            ? "border-success/50"
            : "border-line",
      )}
    >
      <div className="flex items-center justify-between text-[13px] font-medium text-fg-2">
        <span>{label}</span>
        {icon && (
          <span aria-hidden className="text-muted">
            {icon}
          </span>
        )}
      </div>
      <p className="tabular mt-2 text-[28px] leading-tight font-semibold" data-testid={testId}>
        {value}
      </p>
      {context && <p className="mt-1 text-[13px] text-fg-2">{context}</p>}
    </div>
  );
}
