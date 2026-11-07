import {
  Bot,
  Clock,
  FileCheck2,
  PiggyBank,
  Receipt,
  ShieldAlert,
  Target,
  Users,
} from "lucide-react";
import Link from "next/link";

import { CondoFilter } from "@/components/condoos/CondoFilter";
import { PageHeader } from "@/components/layout/PageHeader";
import { CardTitle } from "@/components/ui/Card";
import { cx } from "@/components/ui/cx";
import { DataTable } from "@/components/ui/DataTable";
import { KpiCard } from "@/components/ui/KpiCard";
import { apiGet } from "@/lib/api";
import { formatBRL, formatMonth } from "@/lib/format";
import type { MetricSummary, Metrics, Portfolio } from "@/lib/types";

const PERIODS = [3, 6, 12] as const;

function pct(v: number | null): string {
  return v === null ? "—" : `${(v * 100).toLocaleString("pt-BR", { maximumFractionDigits: 0 })}%`;
}

function hours(v: number | null): string {
  if (v === null) return "—";
  if (v < 48) return `${v.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} h`;
  return `${(v / 24).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} dias`;
}

function usd(v: string): string {
  return Number(v).toLocaleString("pt-BR", { style: "currency", currency: "USD" });
}

const COLUMNS = [
  {
    key: "precision",
    header: "Precisão",
    cell: (r: MetricSummary) => (
      <span title={`${r.findings_confirmed} confirmados de ${r.findings_reviewed} revisados`}>
        {pct(r.precision)} <span className="text-fg-2">({r.findings_reviewed})</span>
      </span>
    ),
    align: "right" as const,
  },
  {
    key: "auto",
    header: "Extração automática",
    cell: (r: MetricSummary) => (
      <span title={`${r.docs_automatic} de ${r.docs_processed} documentos`}>
        {pct(r.automatic_rate)} <span className="text-fg-2">({r.docs_processed})</span>
      </span>
    ),
    align: "right" as const,
  },
  {
    key: "review",
    header: "Tempo de revisão (mediana)",
    cell: (r: MetricSummary) => hours(r.review_hours_median),
    align: "right" as const,
  },
  {
    key: "cost",
    header: "Custo de IA",
    cell: (r: MetricSummary) => (
      <span title={`${r.llm_calls} chamadas`}>{usd(r.llm_cost_usd)}</span>
    ),
    align: "right" as const,
  },
];

/** Internal pilot metrics (spec §13, D60): for the management company, not for the board. */
export default async function MetricasPage({
  searchParams,
}: {
  searchParams: Promise<{ meses?: string; condominio?: string }>;
}) {
  const sp = await searchParams;
  const months = PERIODS.find((p) => String(p) === sp.meses) ?? 6;
  const portfolio = await apiGet<Portfolio>("/portfolio");
  const condos = portfolio.condominiums;
  const selected = condos.some((c) => c.id === sp.condominio) ? sp.condominio! : null;
  const m = await apiGet<Metrics>(
    `/portfolio/metrics?months=${months}${selected ? `&condominium_id=${selected}` : ""}`,
  );
  const t = m.totals;
  const span =
    m.months.length > 0
      ? `${formatMonth(m.months[0] ?? "")} a ${formatMonth(m.months[m.months.length - 1] ?? "")}`
      : "";
  return (
    <>
      <PageHeader
        title="Métricas do piloto"
        subtitle={`Indicadores internos · ${span}`}
        actions={
          <nav aria-label="Período" className="flex gap-1">
            {PERIODS.map((p) => (
              <Link
                key={p}
                href={`/admin/metricas?meses=${p}${selected ? `&condominio=${selected}` : ""}`}
                aria-current={p === months ? "page" : undefined}
                className={cx(
                  "transition-ui rounded-full border px-3 py-1.5 text-[13px]",
                  p === months
                    ? "border-accent/70 bg-surface font-medium text-fg"
                    : "border-line text-fg-2 hover:border-control hover:text-fg",
                )}
              >
                {p} meses
              </Link>
            ))}
          </nav>
        }
      />
      <CondoFilter
        pathname="/admin/metricas"
        condos={condos}
        selected={selected}
        extra={{ meses: String(months) }}
      />
      <section
        className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4"
        aria-label="Indicadores"
      >
        <KpiCard
          label="Precisão dos achados"
          value={pct(t.precision)}
          context={`${t.findings_confirmed} confirmados de ${t.findings_reviewed} revisados pelo síndico`}
          icon={<Target size={18} />}
        />
        <KpiCard
          label="Extração automática"
          value={pct(t.automatic_rate)}
          context={`${t.docs_automatic} de ${t.docs_processed} documentos sem revisão manual`}
          icon={<FileCheck2 size={18} />}
          tone={t.automatic_rate !== null && t.automatic_rate < 0.9 ? "attention" : "normal"}
        />
        <KpiCard
          label="Tempo de revisão do síndico"
          value={hours(t.review_hours_median)}
          context={`mediana de ${t.review_count} achados, da publicação à primeira decisão`}
          icon={<Clock size={18} />}
        />
        <KpiCard
          label="Custo de IA no período"
          value={usd(t.llm_cost_usd)}
          context={`${t.llm_calls} chamadas · por condomínio na tabela`}
          icon={<Bot size={18} />}
        />
      </section>

      <section className="mt-8" aria-labelledby="base-piloto">
        <CardTitle>
          <span id="base-piloto">Base do piloto (protocolo §4)</span>
        </CardTitle>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <KpiCard
            label="Despesas analisadas"
            value={t.expenses.toLocaleString("pt-BR")}
            context={`${pct(t.disputed_rate)} dos achados decididos foram contestados ou ignorados`}
            icon={<Receipt size={18} />}
          />
          <KpiCard
            label="Divergências confirmadas"
            value={formatBRL(t.confirmed_at_risk)}
            context="valor em risco dos achados confirmados; não é economia realizada"
            icon={<Target size={18} />}
          />
          <KpiCard
            label="Economia por estágio (por ano)"
            value={formatBRL(t.savings_validated_annual)}
            context={`estimada validada · realizada e comprovada: ${formatBRL(t.savings_realized_annual)} (nunca somadas)`}
            icon={<PiggyBank size={18} />}
          />
          <KpiCard
            label="Segurança e política"
            value={`${t.cross_tenant_attempts + t.denied_by_policy}`}
            context={`${t.cross_tenant_attempts} tentativas entre condomínios · ${t.denied_by_policy} ações negadas pela política (meta: zero)`}
            icon={<ShieldAlert size={18} />}
            tone={t.cross_tenant_attempts + t.denied_by_policy > 0 ? "attention" : "normal"}
          />
          <KpiCard
            label="Sessões do corpo diretivo"
            value={t.board_sessions.toLocaleString("pt-BR")}
            context="entradas no período de síndico, subsíndico e conselho (uso recorrente)"
            icon={<Users size={18} />}
          />
        </div>
        <p className="mt-3 text-xs text-fg-2">
          Horas poupadas e falso positivo real dependem do diário de tempo e da revisão amostral
          (fora do produto). Contestados ou ignorados é só um sinal de falso positivo.
        </p>
      </section>

      <section className="mt-8" aria-labelledby="por-condominio">
        <CardTitle>
          <span id="por-condominio">Por condomínio</span>
        </CardTitle>
        <DataTable<Metrics["condominiums"][number]>
          caption="Métricas por condomínio no período"
          rows={m.condominiums}
          rowKey={(r) => r.id}
          columns={[{ key: "name", header: "Condomínio", cell: (r) => r.name }, ...COLUMNS]}
        />
      </section>

      <section className="mt-8" aria-labelledby="por-mes">
        <CardTitle>
          <span id="por-mes">Por mês (carteira)</span>
        </CardTitle>
        <DataTable<Metrics["by_month"][number]>
          caption="Métricas da carteira por mês"
          rows={[...m.by_month].reverse()}
          rowKey={(r) => r.month}
          columns={[{ key: "month", header: "Mês", cell: (r) => formatMonth(r.month) }, ...COLUMNS]}
        />
        <p className="mt-3 text-xs text-fg-2">
          Precisão: achados confirmados dividido pelos achados com decisão do síndico (confirmar,
          contestar ou ignorar), pela competência do achado. Extração automática: documentos fiscais
          recebidos que não passaram por revisão manual. Custo de IA em dólares, pela data da
          chamada. Meta de extração automática: 90%.
        </p>
      </section>
    </>
  );
}
