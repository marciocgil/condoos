import { CalendarClock, FileSignature } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import { indexLabel } from "@/lib/labels";
import { formatBRL, formatDate } from "@/lib/format";
import type { Contract } from "@/lib/types";

function nextAdjustment(baseMonth: number | null, index: string, today: Date): string | null {
  if (!baseMonth || !["IPCA", "IGPM", "INPC"].includes(index)) return null;
  const year = baseMonth > today.getMonth() + 1 ? today.getFullYear() : today.getFullYear() + 1;
  return `${String(baseMonth).padStart(2, "0")}/${year}`;
}

function daysUntil(iso: string, today: Date): number {
  return Math.ceil((new Date(`${iso}T00:00:00`).getTime() - today.getTime()) / 86_400_000);
}

export default async function ContratosPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const contracts = await apiGet<Contract[]>(`/condominiums/${id}/contracts`);
  const today = new Date();
  return (
    <section aria-labelledby="contracts-title" className="space-y-3">
      <h1 id="contracts-title" className="text-xl font-semibold">
        Contratos
      </h1>
      {contracts.length === 0 && (
        <EmptyState icon={<FileSignature size={28} />} title="Nenhum contrato cadastrado">
          Envie os contratos em PDF para que os reajustes e a vigência sejam conferidos.
        </EmptyState>
      )}
      <ul className="space-y-3">
        {contracts.map((c) => {
          const days = c.end_date ? daysUntil(c.end_date, today) : null;
          const expiring = days !== null && days >= 0 && days <= 60;
          const expired = days !== null && days < 0;
          return (
            <li
              key={c.id}
              className="rounded-[var(--radius-card)] border border-line bg-surface p-4"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-medium">{c.supplier_name}</p>
                  <p className="text-[13px] text-fg-2">
                    {c.object}
                    {c.amendments
                      ? ` · ${c.amendments} ${c.amendments === 1 ? "aditivo" : "aditivos"}`
                      : ""}
                  </p>
                </div>
                {expiring && (
                  <Badge tone="warning" icon={<CalendarClock size={12} />}>
                    Vence em {days} {days === 1 ? "dia" : "dias"}
                  </Badge>
                )}
                {expired && <Badge tone="danger">Contrato vencido</Badge>}
              </div>
              <dl className="tabular mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-[13px]">
                <div>
                  <dt className="text-muted">Valor mensal</dt>
                  <dd>{formatBRL(c.monthly_value)}</dd>
                </div>
                <div>
                  <dt className="text-muted">Índice</dt>
                  <dd>{indexLabel(c.adjustment_index, c.adjustment_index_other)}</dd>
                </div>
                <div>
                  <dt className="text-muted">Próximo reajuste</dt>
                  <dd>
                    {nextAdjustment(c.adjustment_base_month, c.adjustment_index, today) ?? "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted">Fim da vigência</dt>
                  <dd>{c.end_date ? formatDate(c.end_date) : "Indeterminado"}</dd>
                </div>
                <div>
                  <dt className="text-muted">Aviso prévio</dt>
                  <dd>
                    {c.notice_days ? `${c.notice_days} dias` : "Não disponível"}
                    {c.auto_renewal && " · renova sozinho"}
                  </dd>
                </div>
              </dl>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
