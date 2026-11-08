import { CheckCircle2, Clock, FileQuestion, FileSearch, FileWarning } from "lucide-react";
import type { ReactNode } from "react";

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Card, CardTitle } from "@/components/ui/Card";
import type { CoverageStatus, MonthCoverage } from "@/lib/types";

const STATUS: Record<CoverageStatus, { label: string; tone: BadgeTone; icon: ReactNode }> = {
  faturado: { label: "Recebida", tone: "success", icon: <CheckCircle2 size={12} /> },
  em_conferencia: { label: "Chegou, em conferência", tone: "info", icon: <FileSearch size={12} /> },
  aguardando: { label: "No prazo", tone: "neutral", icon: <Clock size={12} /> },
  sem_nf: { label: "Cobrança sem nota", tone: "warning", icon: <FileWarning size={12} /> },
  sem_faturamento: {
    label: "Não recebida",
    tone: "warning",
    icon: <FileQuestion size={12} />,
  },
};

const CHANNEL: Record<string, string> = {
  upload: "enviada pelo app",
  email: "chegou por e-mail",
  pedido: "chegou pelo link de pedido",
  seed: "carga inicial",
};

function monthLabel(month: string): string {
  const [y, m] = month.split("-");
  return `${m}/${y}`;
}

/** LB-055 (D102): the invoices the contracts expect in a month and whether each arrived, by
 * which channel, or is in review. Follow-up only; a gap is "not received", never an
 * accusation. */
export function MonthCoverageCard({
  coverage,
  title,
}: {
  coverage: MonthCoverage;
  title?: string;
}) {
  const label = monthLabel(coverage.month);
  return (
    <Card aria-label="Documentos esperados do mês">
      <CardTitle>{title ?? `Notas dos contratos · ${label}`}</CardTitle>
      {coverage.expected === 0 ? (
        <p className="text-sm text-fg-2">Nenhum contrato espera nota fiscal em {label}.</p>
      ) : (
        <>
          <p className="text-sm">
            <span className="font-semibold">
              {coverage.received} de {coverage.expected}
            </span>{" "}
            recebidas
            {coverage.in_review > 0 && ` · ${coverage.in_review} em conferência`}
            {coverage.waiting > 0 && ` · ${coverage.waiting} no prazo`}
            {coverage.missing > 0 && ` · ${coverage.missing} não recebidas`}
          </p>
          {coverage.missing > 0 && (
            <p className="mt-1 text-[13px] text-fg-2">
              Não recebida por nenhum canal (app, e-mail ou link de pedido). Pode ter sido emitida e
              não enviada.
              {coverage.unread > 0 &&
                ` Há ${coverage.unread} documento(s) ainda em leitura que podem ser alguma delas.`}
            </p>
          )}
          <ul className="mt-3 divide-y divide-line border-t border-line text-[13px]">
            {coverage.contracts.map((c) => {
              const look = STATUS[c.status];
              const via = c.origin ?? c.arrived[0]?.origin ?? null;
              return (
                <li key={c.contract_id} className="py-2">
                  <span className="flex flex-wrap items-start justify-between gap-2">
                    <span className="font-medium">{c.supplier}</span>
                    <Badge tone={look.tone} icon={look.icon}>
                      {look.label}
                    </Badge>
                  </span>
                  <span className="block text-fg-2">
                    {c.object}
                    {c.invoice_number && ` · NF ${c.invoice_number}`}
                    {via && CHANNEL[via] && ` · ${CHANNEL[via]}`}
                  </span>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </Card>
  );
}
