import { AlertTriangle, CheckCircle2, Repeat } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card, CardTitle } from "@/components/ui/Card";
import { formatMonth } from "@/lib/format";
import type { Reconciliation } from "@/lib/types";

/** Two-way reconciliation (LB-031, D94): month by month, contracts with and without the
 * invoice and the queue, worded as coverage (never "completo"); and suppliers charged
 * without a contract in two or more months, which may be a contract not sent yet. */
export function ReconciliationCard({ name, data }: { name: string; data: Reconciliation }) {
  return (
    <Card aria-label={`Cobertura de ${name}`} data-testid="reconciliation">
      <CardTitle>
        Cobertura dos últimos {data.months.length} meses · {name}
      </CardTitle>
      <ul className="divide-y divide-line text-sm">
        {data.months.map((m) => (
          <li key={m.month} className="flex items-start justify-between gap-3 py-2.5">
            <span>
              <span className="font-medium capitalize">{formatMonth(m.month)}</span>
              <span className="block text-[13px] text-fg-2">{m.label}</span>
            </span>
            {m.covered ? (
              <Badge tone="success" icon={<CheckCircle2 size={12} />}>
                Coberto
              </Badge>
            ) : (
              <Badge tone="warning" icon={<AlertTriangle size={12} />}>
                Parcial
              </Badge>
            )}
          </li>
        ))}
      </ul>
      {data.recurring_without_contract.length > 0 && (
        <div className="mt-4 border-t border-line pt-3">
          <p className="text-[13px] font-medium">Cobranças recorrentes sem contrato</p>
          <ul className="mt-1 space-y-1.5 text-[13px] text-fg-2">
            {data.recurring_without_contract.map((r) => (
              <li key={r.supplier_id} className="flex items-start gap-2">
                <Repeat size={14} aria-hidden className="mt-0.5 shrink-0 text-muted" />
                {r.label}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
