import Link from "next/link";

import { ControlStatusBadge } from "@/components/audit/ControlStatusBadge";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import { formatBRL, formatMonthTitle } from "@/lib/format";
import type { AuditResult } from "@/lib/types";

type Item = AuditResult & {
  condominium_id: string;
  condominium: string;
  competencia: string;
  control_id: string;
  name: string;
};

/** Results that need internal human review: divergences and differences in cents. */
export default async function AuditReviewPage() {
  const items = await apiGet<Item[]>("/audit/review-queue");
  return (
    <>
      <PageHeader
        title="Revisão da auditoria"
        subtitle="Resultados que só seguem depois de uma pessoa da equipe revisar, com motivo."
      />
      {items.length === 0 ? (
        <EmptyState title="Nada aguardando revisão">
          Divergências e diferenças em centavos aparecem aqui.
        </EmptyState>
      ) : (
        <ul className="space-y-3">
          {items.map((i) => (
            <li
              key={i.result_id}
              className="rounded-[var(--radius-card)] border border-line bg-surface p-4"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-[13px] text-fg-2">{i.control_id}</span>
                <Link
                  href={`/admin/audit/controle/${i.condominium_id}/${i.control_id}?competencia=${i.competencia}`}
                  className="font-medium hover:underline"
                >
                  {i.name}
                </Link>
                <ControlStatusBadge status={i.status} />
                {i.differences !== "0.00" && (
                  <span className="text-sm text-danger">{formatBRL(i.differences)}</span>
                )}
              </div>
              <p className="mt-1 text-[13px] text-fg-2">
                {i.condominium} · {formatMonthTitle(`${i.competencia}-01`)}
              </p>
              <p className="mt-1 text-sm">{i.rationale}</p>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
