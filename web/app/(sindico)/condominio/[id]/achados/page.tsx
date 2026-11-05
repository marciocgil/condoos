import { ListChecks } from "lucide-react";

import { InsightCard } from "@/components/condoos/InsightCard";
import { FilterChips } from "@/components/ui/FilterChips";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import { formatBRLShort, formatMonth } from "@/lib/format";
import { STATUS_LABEL } from "@/lib/labels";
import type { Finding } from "@/lib/types";

type Search = Record<string, string | string[] | undefined>;

function many(v: string | string[] | undefined): string[] {
  return v === undefined ? [] : Array.isArray(v) ? v : [v];
}

export default async function AchadosPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Search>;
}) {
  const { id } = await params;
  const sp = await searchParams;
  const mes = many(sp.mes)[0];
  const severidade = many(sp.severidade);
  const status = many(sp.status);
  const categoria = many(sp.categoria);

  const qs = new URLSearchParams();
  if (mes) qs.set("competence", mes);
  const all = await apiGet<Finding[]>(`/condominiums/${id}/findings?${qs.toString()}`);
  const findings = all.filter(
    (f) =>
      (severidade.length === 0 || severidade.includes(f.severity)) &&
      (status.length === 0 || status.includes(f.status)) &&
      (categoria.length === 0 || (f.category !== null && categoria.includes(f.category))),
  );
  const categories = [
    ...new Map(
      all.filter((f) => f.category).map((f) => [f.category!, f.category_label ?? f.category!]),
    ),
  ];
  const pathname = `/condominio/${id}/achados`;
  const current: Record<string, string[]> = {
    severidade,
    status,
    categoria,
    ...(mes ? { mes: [mes] } : {}),
  };
  const total = findings.reduce((s, f) => s + Number(f.amount_at_risk), 0);

  return (
    <>
      <div>
        <h1 className="text-xl font-semibold">Achados</h1>
        <p className="text-sm text-fg-2">
          {mes ? formatMonth(`${mes}-01`) : "Todos os meses"} · {findings.length}{" "}
          {findings.length === 1 ? "achado" : "achados"} · {formatBRLShort(total)}
        </p>
      </div>
      <div className="space-y-2">
        <FilterChips
          name="severidade"
          label="Severidade"
          pathname={pathname}
          params={current}
          selected={severidade}
          options={[
            { value: "alta", label: "Graves" },
            { value: "media", label: "Médios" },
            { value: "baixa", label: "Baixos" },
          ]}
        />
        <FilterChips
          name="status"
          label="Situação"
          pathname={pathname}
          params={current}
          selected={status}
          options={["publicado", "confirmado", "contestado", "ignorado"].map((s) => ({
            value: s,
            label: STATUS_LABEL[s]!,
          }))}
        />
        {categories.length > 1 && (
          <FilterChips
            name="categoria"
            label="Categoria"
            pathname={pathname}
            params={current}
            selected={categoria}
            options={categories.map(([value, label]) => ({ value, label }))}
          />
        )}
      </div>
      {findings.length === 0 ? (
        <EmptyState icon={<ListChecks size={28} />} title="Nenhum achado com esses filtros">
          Remova um filtro para ver mais resultados.
        </EmptyState>
      ) : (
        <div className="space-y-2">
          {findings.map((f) => (
            <InsightCard key={f.id} finding={f} href={`${pathname}/${f.id}`} showStatus />
          ))}
        </div>
      )}
    </>
  );
}
