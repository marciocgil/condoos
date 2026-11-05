import { Download, Upload } from "lucide-react";
import Link from "next/link";

import { InsightCard } from "@/components/condoos/InsightCard";
import { SEVERITY_DOT } from "@/components/condoos/SeverityBadge";
import { MonthSelect } from "@/components/MonthSelect";
import { buttonClass } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import { competenceParam, formatBRL, formatBRLShort, formatMonth } from "@/lib/format";
import { SEVERITY_PLURAL } from "@/lib/labels";
import type { Competence, Condominium, Severity, Summary } from "@/lib/types";

const SEVERITIES: Severity[] = ["alta", "media", "baixa"];
const CHIP_BORDER: Record<Severity, string> = {
  alta: "border-danger/70",
  media: "border-warning/70",
  baixa: "border-info/70",
};

export default async function ResumoPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ mes?: string }>;
}) {
  const { id } = await params;
  const { mes } = await searchParams;
  const [condo, competences, summary] = await Promise.all([
    apiGet<Condominium>(`/condominiums/${id}`),
    apiGet<Competence[]>(`/condominiums/${id}/competences`),
    apiGet<Summary>(`/condominiums/${id}/summary${mes ? `?competence=${mes}` : ""}`),
  ]);

  if (!summary.competence) {
    return (
      <>
        <h1 className="text-xl font-semibold">{condo.name}</h1>
        <EmptyState title="Ainda não há meses processados">
          Envie as notas, boletos e o extrato do mês para começar a auditoria.
        </EmptyState>
      </>
    );
  }
  const month = competenceParam(summary.competence);
  const findingsHref = `/condominio/${id}/achados?mes=${month}`;
  return (
    <>
      <div>
        <h1 className="text-xl leading-tight font-semibold">{condo.name}</h1>
        <p className="text-sm text-fg-2">{formatMonth(summary.competence)}</p>
      </div>
      <MonthSelect competences={competences} value={summary.competence} />

      <Card tone="highlight" aria-label="Destaque do mês">
        <p className="tabular text-[32px] leading-tight font-semibold" data-testid="amount-at-risk">
          {formatBRLShort(summary.amount_at_risk)}
        </p>
        <p className="mt-1 text-fg-2">em risco este mês</p>
        <p className="mt-1 text-sm text-fg-2">
          {summary.findings} {summary.findings === 1 ? "achado" : "achados"} ·{" "}
          {summary.by_severity.alta} {summary.by_severity.alta === 1 ? "grave" : "graves"}
        </p>
        <p className="tabular mt-3 border-t border-line pt-3 text-[13px] text-muted">
          {summary.expenses} despesas analisadas · {formatBRL(summary.expenses_total)}
        </p>
      </Card>

      <ul className="flex flex-wrap gap-2" aria-label="Achados por severidade">
        {SEVERITIES.map((s) => (
          <li key={s}>
            <Link
              href={`${findingsHref}&severidade=${s}`}
              className={`transition-ui inline-flex h-9 items-center gap-2 rounded-full border bg-surface px-4 text-sm hover:bg-elevated ${CHIP_BORDER[s]}`}
            >
              <span className={`h-2 w-2 rounded-full ${SEVERITY_DOT[s]}`} aria-hidden />
              {summary.by_severity[s]} {SEVERITY_PLURAL[s]}
            </Link>
          </li>
        ))}
      </ul>

      <section aria-labelledby="top-title">
        <CardTitle
          action={
            summary.findings > 3 ? (
              <Link href={findingsHref} className="text-[13px] text-fg-2 hover:text-fg">
                Ver todos
              </Link>
            ) : undefined
          }
        >
          <span id="top-title">Principais achados</span>
        </CardTitle>
        {summary.top.length === 0 ? (
          <EmptyState title="Nenhum ponto de atenção neste mês">
            As despesas analisadas não apresentaram divergências.
          </EmptyState>
        ) : (
          <div className="space-y-2">
            {summary.top.map((f) => (
              <InsightCard key={f.id} finding={f} href={`/condominio/${id}/achados/${f.id}`} />
            ))}
          </div>
        )}
      </section>

      <div className="grid grid-cols-2 gap-2">
        <Link href={`/condominio/${id}/enviar`} className={buttonClass("secondary")}>
          <Upload size={16} aria-hidden /> Enviar documentos
        </Link>
        <button
          type="button"
          disabled
          className={buttonClass("secondary")}
          title="O relatório em PDF chega no Marco 5"
        >
          <Download size={16} aria-hidden /> Baixar relatório em PDF
        </button>
      </div>
    </>
  );
}
