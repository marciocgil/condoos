import { CalendarClock, Plus } from "lucide-react";
import Link from "next/link";

import { CondoFilter } from "@/components/condoos/CondoFilter";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { buttonClass } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/DataTable";
import { KpiCard } from "@/components/ui/KpiCard";
import { apiGet } from "@/lib/api";
import { indexLabel } from "@/lib/labels";
import { contractValue, formatBRL, formatBRLShort, formatDate } from "@/lib/format";
import type { Portfolio, PortfolioContract } from "@/lib/types";

function days(iso: string | null): number | null {
  return iso ? Math.ceil((new Date(`${iso}T00:00:00`).getTime() - Date.now()) / 86_400_000) : null;
}

export default async function ContratosPage({
  searchParams,
}: {
  searchParams: Promise<{ condominio?: string }>;
}) {
  const { condominio } = await searchParams;
  const [all, portfolio] = await Promise.all([
    apiGet<PortfolioContract[]>("/portfolio/contracts"),
    apiGet<Portfolio>("/portfolio"),
  ]);
  const condos = portfolio.condominiums;
  const selected = condos.some((c) => c.id === condominio) ? condominio! : null;
  const rows = selected ? all.filter((r) => r.condominium_id === selected) : all;
  const active = rows.filter((r) => (days(r.end_date) ?? 1) >= 0);
  const expiring = rows.filter((r) => {
    const d = days(r.end_date);
    return d !== null && d >= 0 && d <= 60;
  });
  const annual = active.reduce((s, r) => s + Number(r.monthly_value ?? 0) * 12, 0);
  return (
    <>
      <PageHeader
        title="Contratos"
        subtitle="Contratos de todos os condomínios da carteira. Clique no fornecedor para editar."
        actions={
          <Link
            href={`/admin/contratos/novo${selected ? `?condominio=${selected}` : ""}`}
            className={buttonClass("secondary", "sm")}
          >
            <Plus size={14} aria-hidden /> Novo contrato
          </Link>
        }
      />
      <CondoFilter pathname="/admin/contratos" condos={condos} selected={selected} />
      <section className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-3" aria-label="Indicadores">
        <KpiCard label="Contratos ativos" value={active.length} />
        <KpiCard
          label="Valor anual contratado"
          value={formatBRLShort(annual)}
          context="valor mensal atual × 12, sem reajustes futuros"
        />
        <KpiCard
          label="Vencem em até 60 dias"
          value={expiring.length}
          tone={expiring.length ? "attention" : "normal"}
        />
      </section>
      <DataTable<PortfolioContract>
        caption="Contratos da carteira"
        rows={rows}
        rowKey={(r) => r.id}
        rowHref={(r) => `/admin/contratos/${r.condominium_id}/${r.id}`}
        columns={[
          {
            key: "supplier",
            header: "Fornecedor",
            cell: (r) => (
              <>
                <span className="font-medium">{r.supplier_name}</span>
                <p className="text-xs text-muted">
                  {r.object}
                  {r.amendments
                    ? ` · ${r.amendments} ${r.amendments === 1 ? "aditivo" : "aditivos"}`
                    : ""}
                </p>
              </>
            ),
          },
          { key: "condo", header: "Condomínio", cell: (r) => r.condominium_name },
          {
            key: "value",
            header: "Valor",
            cell: (r) =>
              r.nature === "pontual"
                ? `${contractValue(r)}${r.billed_total ? ` · faturado ${formatBRL(r.billed_total)}` : ""}`
                : formatBRL(r.monthly_value ?? 0),
            align: "right",
          },
          {
            key: "index",
            header: "Índice",
            cell: (r) => indexLabel(r.adjustment_index, r.adjustment_index_other),
          },
          {
            key: "next",
            header: "Próximo reajuste",
            cell: (r) => (r.next_adjustment ? formatDate(r.next_adjustment).slice(3) : "—"),
          },
          {
            key: "end",
            header: "Fim da vigência",
            cell: (r) => {
              const d = days(r.end_date);
              if (r.end_date === null) return "Indeterminado";
              if (d !== null && d < 0)
                return <Badge tone="danger">Vencido em {formatDate(r.end_date)}</Badge>;
              if (d !== null && d <= 60)
                return (
                  <Badge tone="warning" icon={<CalendarClock size={12} />}>
                    {formatDate(r.end_date)}
                  </Badge>
                );
              return formatDate(r.end_date);
            },
          },
        ]}
      />
    </>
  );
}
