import { Calculator } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { formatBRL, formatDate, formatDateTime } from "@/lib/format";
import { CONFIDENCE_LABEL, PERIODICITY_LABEL, SAVINGS_STAGE_LABEL } from "@/lib/labels";
import type { SavingsStage } from "@/lib/types";

/** Each savings stage on its own card (DV-04, D76): stages are never added up, and an
 * estimate is never presented as a saving already captured. */
export function SavingsStages({ stages }: { stages: SavingsStage[] }) {
  return (
    <ul className="space-y-3" aria-label="Estágios da economia">
      {stages.map((s) => (
        <li
          key={s.stage}
          className="rounded-[var(--radius-card)] border border-line bg-surface p-4"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-[13px] font-medium text-fg-2">
              {SAVINGS_STAGE_LABEL[s.stage] ?? s.stage}
            </p>
            <Badge
              tone={s.confidence === "alta" ? "success" : "warning"}
              icon={<Calculator size={12} />}
            >
              {CONFIDENCE_LABEL[s.confidence] ?? s.confidence}
            </Badge>
          </div>
          <p className="mt-1 text-2xl font-semibold tabular-nums">
            {formatBRL(s.annualized_amount)}{" "}
            <span className="text-sm font-normal text-fg-2">por ano</span>
          </p>
          <p className="text-[13px] text-fg-2 tabular-nums">
            {formatBRL(s.amount)} {PERIODICITY_LABEL[s.periodicity] ?? s.periodicity} · custo para
            implementar {formatBRL(s.one_time_cost)} · líquido {formatBRL(s.net_amount)}
          </p>
          <p className="mt-1 text-xs text-muted">
            Base: {formatBRL(s.baseline_amount)} em {formatDate(s.baseline_period_start)} · método{" "}
            {s.method_code} · por {s.recorded_by} em {formatDateTime(s.recorded_at)}
          </p>
          {s.assumptions.length > 0 && (
            <details className="mt-2 text-[13px]">
              <summary className="cursor-pointer text-fg-2">
                Premissas ({s.assumptions.length})
              </summary>
              <ul className="mt-1 list-disc space-y-0.5 pl-5">
                {s.assumptions.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </details>
          )}
          {s.quality_risks && (
            <p className="mt-1 text-[13px] text-warning">Atenção: {s.quality_risks}</p>
          )}
        </li>
      ))}
    </ul>
  );
}
