import { PiggyBank } from "lucide-react";

import { OpportunityStatusBadge } from "@/components/condoos/OpportunityStatusBadge";
import { PageHeader } from "@/components/layout/PageHeader";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import { formatBRL } from "@/lib/format";
import { OPPORTUNITY_TYPE_LABEL, SAVINGS_STAGE_LABEL } from "@/lib/labels";
import type { OpportunityRow } from "@/lib/types";

/** Opportunities of the portfolio (D81). CondoOS staff see drafts under review; others see
 * only what the review approved. */
export default async function OportunidadesAdminPage({
  searchParams,
}: {
  searchParams: Promise<{ condominio?: string }>;
}) {
  const { condominio } = await searchParams;
  const rows = await apiGet<OpportunityRow[]>(
    `/portfolio/opportunities${condominio ? `?condominium_id=${condominio}` : ""}`,
  );
  return (
    <>
      <PageHeader
        title="Oportunidades"
        subtitle="Economia calculada a partir dos achados; nada chega ao condomínio sem a revisão CondoOS."
      />
      <DataTable
        caption="Oportunidades"
        rows={rows}
        rowKey={(r) => r.id}
        rowHref={(r) => `/admin/oportunidades/${r.condominium_id}/${r.id}`}
        empty={
          <EmptyState icon={<PiggyBank size={24} />} title="Nenhuma oportunidade">
            Gere uma oportunidade a partir de um achado de cobrança acima do contrato (R02) ou de
            reajuste acima do índice (R03).
          </EmptyState>
        }
        columns={[
          {
            key: "number",
            header: "Nº",
            cell: (r) => <span className="tabular-nums">{r.number}</span>,
          },
          {
            key: "title",
            header: "Oportunidade",
            cell: (r) => (
              <span>
                <span className="block font-medium">{r.title}</span>
                <span className="text-xs text-muted">
                  {r.condominium_name} ·{" "}
                  {OPPORTUNITY_TYPE_LABEL[r.opportunity_type] ?? r.opportunity_type}
                </span>
              </span>
            ),
          },
          {
            key: "status",
            header: "Estado",
            cell: (r) => <OpportunityStatusBadge status={r.status} />,
          },
          {
            key: "value",
            header: "Economia (por ano)",
            align: "right",
            cell: (r) =>
              r.headline_stage && r.headline_annualized ? (
                <span>
                  <span className="block tabular-nums">{formatBRL(r.headline_annualized)}</span>
                  <span className="text-xs text-muted">
                    {SAVINGS_STAGE_LABEL[r.headline_stage]}
                  </span>
                </span>
              ) : (
                "—"
              ),
          },
        ]}
      />
    </>
  );
}
