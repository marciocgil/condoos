"use client";

import { BellRing, CheckCheck, Eye } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { send } from "@/lib/client";
import { formatDate } from "@/lib/format";

export type DeadlineAlert = {
  id: string;
  kind: string;
  kind_label: string;
  title: string;
  due_date: string;
  level: "antes" | "vencido";
  status: "criado" | "visto" | "resolvido";
  seen_at: string | null;
  policy_version: number;
};

/** Deadline alerts (FR-026, D126): created by the alert policy, shown only here, marked as
 * seen by a person and resolved by themselves when the deadline is met. */
export function DeadlineAlerts({
  condominiumId,
  alerts,
}: {
  condominiumId: string;
  alerts: DeadlineAlert[];
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  if (alerts.length === 0) return null;

  async function seen(id: string) {
    setBusy(id);
    await send("POST", `/condominiums/${condominiumId}/alerts/${id}/seen`);
    setBusy(null);
    router.refresh();
  }

  return (
    <section aria-labelledby="deadline-alerts" className="space-y-2" data-testid="deadline-alerts">
      <h2 id="deadline-alerts" className="flex items-center gap-2 text-base font-semibold">
        <BellRing size={18} aria-hidden /> Alertas de prazo ({alerts.length})
      </h2>
      <ul className="space-y-2">
        {alerts.map((a) => (
          <li
            key={a.id}
            className="rounded-[var(--radius-card)] border border-line bg-surface p-3 text-sm"
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={a.level === "vencido" ? "danger" : "warning"}>
                {a.level === "vencido" ? "Vencido" : "Vence em breve"}
              </Badge>
              <span className="text-xs text-fg-2">{a.kind_label}</span>
              {a.status === "visto" && (
                <Badge tone="neutral" icon={<CheckCheck size={12} aria-hidden />}>
                  Visto
                </Badge>
              )}
            </div>
            <p className="mt-1">{a.title}</p>
            <p className="text-xs text-fg-2">Data: {formatDate(a.due_date)}</p>
            {a.status === "criado" && (
              <Button
                variant="ghost"
                size="sm"
                icon={<Eye size={14} aria-hidden />}
                disabled={busy === a.id}
                onClick={() => void seen(a.id)}
              >
                Marcar como visto
              </Button>
            )}
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted">
        Alertas só dentro do CondoOS (política de alertas v{alerts[0]?.policy_version}). Somem
        sozinhos quando o prazo é cumprido.
      </p>
    </section>
  );
}
