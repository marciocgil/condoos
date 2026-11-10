import { CalendarClock, FileSearch, FileSignature } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { buttonClass } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import { indexLabel } from "@/lib/labels";
import { contractValue, formatBRL, formatDate } from "@/lib/format";
import type { Contract, Launch } from "@/lib/types";

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
  const [contracts, launch] = await Promise.all([
    apiGet<Contract[]>(`/condominiums/${id}/contracts`),
    apiGet<Launch>(`/condominiums/${id}/launch`),
  ]);
  // Contracts sent and still with the CondoOS team (LB-081, D108): they become contracts
  // only after the review (D59), so the screen says they are on the way.
  const inReview = launch.in_review.by_type.contrato ?? 0;
  const today = new Date();
  return (
    <section aria-labelledby="contracts-title" className="space-y-3">
      <h1 id="contracts-title" className="text-xl font-semibold">
        Contratos
      </h1>
      {inReview > 0 && (
        <div
          role="note"
          data-testid="contracts-in-review"
          className="flex items-start gap-2 rounded-[var(--radius-card)] border border-line bg-surface p-3 text-sm"
        >
          <FileSearch size={16} aria-hidden className="mt-0.5 shrink-0 text-info" />
          <span>
            {inReview === 1
              ? "1 contrato em conferência pela equipe CondoOS. Ele aparece aqui assim que a conferência terminar."
              : `${inReview} contratos em conferência pela equipe CondoOS. Eles aparecem aqui assim que a conferência terminar.`}
          </span>
        </div>
      )}
      {contracts.length === 0 && inReview === 0 && (
        <EmptyState
          icon={<FileSignature size={28} />}
          title="Nenhum contrato cadastrado"
          action={
            <Link
              href={`/condominio/${id}/enviar?passo=enviar_contrato`}
              className={buttonClass("primary", "sm")}
            >
              Enviar contrato
            </Link>
          }
        >
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
                  <dt className="text-muted">
                    {c.nature === "pontual" ? "Valor total" : "Valor mensal"}
                  </dt>
                  <dd>
                    {c.nature === "pontual" ? contractValue(c) : formatBRL(c.monthly_value ?? 0)}
                    {c.nature === "pontual" && c.billed_total
                      ? ` · faturado ${formatBRL(c.billed_total)}`
                      : ""}
                  </dd>
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
