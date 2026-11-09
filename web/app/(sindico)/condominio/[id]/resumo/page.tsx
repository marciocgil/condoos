import { Download, Gavel, Upload } from "lucide-react";
import Link from "next/link";

import { ActionsPreview } from "@/components/condoos/ActionsPreview";
import { AgendaPreview } from "@/components/condoos/AgendaPreview";
import { BriefingView } from "@/components/condoos/BriefingView";
import { DelegationBoard } from "@/components/condoos/DelegationBoard";
import { OpportunitiesPreview } from "@/components/condoos/OpportunitiesPreview";
import { InsightCard } from "@/components/condoos/InsightCard";
import { JourneyCard, JourneyReopen } from "@/components/condoos/JourneyCard";
import { MonthRoutine } from "@/components/condoos/MonthRoutine";
import { SEVERITY_DOT } from "@/components/condoos/SeverityBadge";
import { MonthSelect } from "@/components/MonthSelect";
import { buttonClass } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import {
  competenceParam,
  formatBRL,
  formatBRLShort,
  formatMonth,
  formatMonthTitle,
} from "@/lib/format";
import { SEVERITY_PLURAL } from "@/lib/labels";
import type {
  Briefing,
  Competence,
  Condominium,
  DelegationBoard as Board,
  Launch,
  LaunchMonth,
  Severity,
  Summary,
} from "@/lib/types";

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
  const [condo, competences, summary, briefing, launch, board, routine] = await Promise.all([
    apiGet<Condominium>(`/condominiums/${id}`),
    apiGet<Competence[]>(`/condominiums/${id}/competences`),
    apiGet<Summary>(`/condominiums/${id}/summary${mes ? `?competence=${mes}` : ""}`),
    apiGet<Briefing>(`/condominiums/${id}/briefing`),
    apiGet<Launch>(`/condominiums/${id}/launch`),
    apiGet<Board>(`/condominiums/${id}/delegations/board`),
    apiGet<LaunchMonth>(`/condominiums/${id}/launch/month`),
  ]);
  // Launch (D89): the implementation journey above the briefing while it is not hidden.
  const journey = launch.dismissed ? (
    launch.can_manage ? (
      <div className="flex justify-end">
        <JourneyReopen condominiumId={id} />
      </div>
    ) : null
  ) : (
    <JourneyCard condominiumId={id} launch={launch} />
  );
  // Hoje (VS-04): the day's briefing first; the month's audit summary follows, unchanged.
  const today = (
    <>
      <MonthRoutine condominiumId={id} routine={routine} />
      {journey}
      <BriefingView
        compact
        briefing={briefing}
        paths={{
          finding: `/condominio/${id}/achados/{id}`,
          case: `/condominio/${id}/assuntos/{id}`,
          opportunity: `/condominio/${id}/oportunidades/{id}`,
          action: `/condominio/${id}/aprovacoes/{id}`,
          agenda: `/condominio/${id}/agenda`,
          compliance: `/condominio/${id}/conformidade/{id}`,
        }}
      />
      <DelegationBoard condominiumId={id} board={board} />
    </>
  );

  if (!summary.competence) {
    return (
      <>
        <h1 className="text-xl font-semibold">{condo.name}</h1>
        {today}
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
      {today}
      <h2 className="pt-2 text-lg font-semibold">Auditoria do mês</h2>
      {/* Which month this is and why (LB-083, D108): by default the last closed month, the
          report's view; later months with points waiting are named right below. */}
      <p className="text-sm text-fg-2" data-testid="audit-month">
        {summary.competence_status === "fechada"
          ? `${mes ? "Mês fechado" : "Último mês fechado"}: ${formatMonth(summary.competence)}`
          : `Mês em aberto (prévia): ${formatMonth(summary.competence)}`}
      </p>
      <MonthSelect competences={competences} value={summary.competence} />
      {(summary.later_waiting ?? []).map((w) => (
        <Link
          key={w.competence}
          href={`/condominio/${id}/achados?mes=${competenceParam(w.competence)}&status=publicado`}
          className="flex items-center gap-2 rounded-[var(--radius-card)] border border-line bg-surface p-3 text-sm hover:bg-elevated"
          data-testid="later-waiting"
        >
          <Gavel size={14} aria-hidden className="shrink-0 text-info" />
          <span>
            {formatMonthTitle(w.competence)} (em aberto): {w.waiting}{" "}
            {w.waiting === 1 ? "ponto aguarda decisão" : "pontos aguardam decisão"} ·{" "}
            {formatBRLShort(w.amount_at_risk)}
          </span>
        </Link>
      ))}

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

      <ActionsPreview
        condominiumId={id}
        detailPath={`/condominio/${id}/aprovacoes/{id}`}
        listHref={`/condominio/${id}/aprovacoes`}
      />

      <OpportunitiesPreview condominiumId={id} />

      <AgendaPreview condominiumId={id} />

      <div className="grid grid-cols-2 gap-2">
        <Link href={`/condominio/${id}/enviar`} className={buttonClass("secondary")}>
          <Upload size={16} aria-hidden /> Enviar documentos
        </Link>
        {summary.competence ? (
          <a
            href={`/api/condominiums/${id}/reports/${competenceParam(summary.competence)}.pdf`}
            className={buttonClass("secondary")}
            title={
              summary.competence_status === "fechada"
                ? "Relatório do mês"
                : "Prévia: a competência ainda está aberta"
            }
          >
            <Download size={16} aria-hidden /> Baixar relatório em PDF
          </a>
        ) : (
          <button type="button" disabled className={buttonClass("secondary")}>
            <Download size={16} aria-hidden /> Baixar relatório em PDF
          </button>
        )}
      </div>
    </>
  );
}
