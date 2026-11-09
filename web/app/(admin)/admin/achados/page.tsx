import { ListChecks } from "lucide-react";

import { CondoFilter } from "@/components/condoos/CondoFilter";
import { SeverityBadge } from "@/components/condoos/SeverityBadge";
import { PageHeader } from "@/components/layout/PageHeader";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { FilterChips } from "@/components/ui/FilterChips";
import { apiGet } from "@/lib/api";
import { formatBRL, formatBRLShort, formatMonth } from "@/lib/format";
import { STATUS_LABEL } from "@/lib/labels";
import type { Finding, Portfolio } from "@/lib/types";

type Search = Record<string, string | string[] | undefined>;
type Row = Finding & { condominium_id: string; condominium: string };

// Same as the Carteira's "Achados abertos" card (portfolio OPEN).
const OPEN = ["aguardando_validacao", "publicado", "contestado"];
const STATUSES = [
  "aguardando_validacao",
  "publicado",
  "pendente_evidencia",
  "contestado",
  "confirmado",
  "ignorado",
  "descartado",
  "superado",
];

function many(v: string | string[] | undefined): string[] {
  return v === undefined ? [] : Array.isArray(v) ? v : [v];
}

/** Findings of the portfolio on the desktop: the list behind the Carteira's "Achados abertos"
 * card, by condominium, situation and severity. Each row opens the finding to analyse and
 * decide (the actions shown depend on the role). */
export default async function AchadosAdminPage({
  searchParams,
}: {
  searchParams: Promise<Search>;
}) {
  const sp = await searchParams;
  const portfolio = await apiGet<Portfolio>("/portfolio");
  const condos = portfolio.condominiums;
  const condominio = many(sp.condominio)[0];
  const selected = condos.some((c) => c.id === condominio) ? condominio! : null;
  const status = many(sp.status);
  const severidade = many(sp.severidade);
  const wanted = status.length > 0 ? status : OPEN;

  const targets = selected ? condos.filter((c) => c.id === selected) : condos;
  const qs = new URLSearchParams();
  wanted.forEach((s) => qs.append("status", s));
  severidade.forEach((s) => qs.append("severity", s));
  const lists = await Promise.all(
    targets.map(async (c) =>
      (await apiGet<Finding[]>(`/condominiums/${c.id}/findings?${qs.toString()}`)).map(
        (f): Row => ({ ...f, condominium_id: c.id, condominium: c.name }),
      ),
    ),
  );
  const rows = lists.flat().sort((a, b) => Number(b.amount_at_risk) - Number(a.amount_at_risk));
  const total = rows.reduce((s, f) => s + Number(f.amount_at_risk), 0);

  const pathname = "/admin/achados";
  const current: Record<string, string[]> = {
    status,
    severidade,
    ...(selected ? { condominio: [selected] } : {}),
  };
  return (
    <>
      <PageHeader
        title="Achados"
        subtitle={`${status.length === 0 ? "Abertos" : "Filtrados"} · ${rows.length} ${rows.length === 1 ? "achado" : "achados"} · ${formatBRLShort(total)} em risco`}
      />
      <CondoFilter pathname={pathname} condos={condos} selected={selected} />
      <div className="mb-4 space-y-2">
        <FilterChips
          name="status"
          label="Situação"
          pathname={pathname}
          params={current}
          selected={status}
          options={STATUSES.map((s) => ({ value: s, label: STATUS_LABEL[s] ?? s }))}
        />
        <FilterChips
          name="severidade"
          label="Gravidade"
          pathname={pathname}
          params={current}
          selected={severidade}
          options={[
            { value: "alta", label: "Graves" },
            { value: "media", label: "Médios" },
            { value: "baixa", label: "Baixos" },
          ]}
        />
      </div>
      <p className="mb-4 text-sm text-fg-2">
        Sem filtro de situação, mostra os abertos: aguardando validação, novos para o condomínio e
        contestados. Achados são indícios para verificação, não conclusões.
      </p>
      <DataTable<Row>
        caption="Achados"
        rows={rows}
        rowKey={(r) => r.id}
        rowHref={(r) => `/admin/achados/${r.condominium_id}/${r.id}`}
        empty={
          <EmptyState icon={<ListChecks size={28} />} title="Nenhum achado com esses filtros">
            Remova um filtro para ver mais resultados.
          </EmptyState>
        }
        columns={[
          ...(selected
            ? []
            : [{ key: "condo", header: "Condomínio", cell: (r: Row) => r.condominium }]),
          {
            key: "title",
            header: "Achado",
            cell: (r) => (
              <span>
                <span className="block font-medium">{r.title}</span>
                <span className="block text-xs text-muted">
                  {r.rule_code}
                  {r.supplier_name ? ` · ${r.supplier_name}` : ""}
                </span>
              </span>
            ),
          },
          { key: "sev", header: "Gravidade", cell: (r) => <SeverityBadge severity={r.severity} /> },
          { key: "status", header: "Situação", cell: (r) => STATUS_LABEL[r.status] ?? r.status },
          { key: "month", header: "Competência", cell: (r) => formatMonth(r.competence) },
          {
            key: "risk",
            header: "Em risco",
            align: "right",
            cell: (r) => formatBRL(r.amount_at_risk),
          },
        ]}
      />
    </>
  );
}
