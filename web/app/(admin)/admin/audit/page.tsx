import { ArrowRight, ListChecks } from "lucide-react";
import Link from "next/link";

import { AuditToolbar } from "@/components/audit/AuditToolbar";
import { ControlStatusBadge } from "@/components/audit/ControlStatusBadge";
import { RunAuditButton } from "@/components/audit/RunAuditButton";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardTitle } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { KpiCard } from "@/components/ui/KpiCard";
import { apiGet } from "@/lib/api";
import { auditCondos, lastMonth, pct, REVIEW_LABEL } from "@/lib/audit";
import { formatBRL, formatDateTime } from "@/lib/format";
import type { ControlStatusCode, Farol, Me } from "@/lib/types";

const ORDER: ControlStatusCode[] = [
  "VALIDADO",
  "COM_RESSALVA",
  "PENDENTE",
  "DIVERGENTE",
  "NAO_AVALIADO",
  "NAO_APLICAVEL",
];
const EQUATION: Record<string, string> = {
  confere: "fecha ao centavo",
  diverge: "não fecha",
  sem_extrato: "sem extrato",
  sem_saldo_final: "sem saldo final",
  sem_saldo_inicial: "sem saldo inicial",
};

/** Audit home: the farol of the 25 controls for one condominium and month (D122). */
export default async function AuditHomePage({
  searchParams,
}: {
  searchParams: Promise<{ condominio?: string; competencia?: string }>;
}) {
  const sp = await searchParams;
  const me = await apiGet<Me>("/me");
  const condos = auditCondos(me);
  if (condos.length === 0)
    return (
      <EmptyState title="Sem acesso à auditoria">
        Seu papel não vê o farol de nenhum condomínio.
      </EmptyState>
    );
  const selected = condos.some((c) => c.id === sp.condominio) ? sp.condominio! : condos[0]!.id;
  const competencia = /^\d{4}-\d{2}$/.test(sp.competencia ?? "") ? sp.competencia! : lastMonth();
  const farol = await apiGet<Farol>(
    `/condominiums/${selected}/audit/farol?competencia=${competencia}`,
  );
  const q = `condominio=${selected}&competencia=${competencia}`;
  const pillars = [...new Set(farol.controls.map((c) => c.pillar_label))];
  const run = farol.runs[0];
  return (
    <>
      <PageHeader
        title="Farol da auditoria"
        subtitle={`${farol.condominium.name}: os 25 controles do mês, cada um com regra, evidência e quem produziu. Resultado interno até a revisão e a publicação.`}
        actions={
          farol.can_run ? (
            <RunAuditButton condominiumId={selected} competencia={competencia} />
          ) : undefined
        }
      />
      <AuditToolbar
        pathname="/admin/audit"
        condos={condos}
        selected={selected}
        competencia={competencia}
      />
      {!run ? (
        <EmptyState title="Auditoria ainda não executada neste mês">
          Rode a auditoria para ver os 25 controles. Falta de documento vira “Pendente”, nunca
          verde.
        </EmptyState>
      ) : (
        <>
          <section
            aria-label="Contagem por estado"
            className="mb-4 flex flex-wrap gap-2"
            data-testid="farol-counts"
          >
            {ORDER.map((s) => (
              <span key={s} className="inline-flex items-center gap-2 text-sm">
                <ControlStatusBadge status={s} />
                <span className="tabular font-medium">{farol.counts[s] ?? 0}</span>
              </span>
            ))}
          </section>
          <section className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-4" aria-label="Indicadores">
            <KpiCard
              label="Cobertura documental"
              value={pct(farol.indicators.cobertura_documental)}
              context="documentos lidos do acervo do mês (DOC-01)"
            />
            <KpiCard
              label="Liquidação demonstrada"
              value={pct(farol.indicators.liquidacao_demonstrada)}
              context="despesas vencidas com documento e débito (DES-01)"
            />
            <KpiCard
              label="Aguardando revisão humana"
              value={farol.indicators.aguardando_revisao}
              tone={farol.indicators.aguardando_revisao ? "attention" : "normal"}
            />
            <KpiCard
              label="Diferenças apontadas"
              value={formatBRL(farol.indicators.diferenca_total)}
              context="soma das diferenças em centavos dos controles"
            />
          </section>
          <Card className="mb-6">
            <CardTitle>Contas bancárias (conciliação por conta, nunca “todas as contas”)</CardTitle>
            {farol.indicators.contas.length === 0 ? (
              <p className="mt-2 text-sm text-fg-2">Nenhum lançamento bancário no mês.</p>
            ) : (
              <ul className="mt-2 space-y-1 text-sm">
                {farol.indicators.contas.map((a) => (
                  <li key={a.conta}>
                    <span className="font-medium">{a.conta}</span>: {a.lancamentos} lançamento(s),
                    saldo {EQUATION[a.equacao] ?? a.equacao}
                    {a.diferenca && a.diferenca !== "0.00"
                      ? ` (diferença ${formatBRL(a.diferenca)})`
                      : ""}
                  </li>
                ))}
              </ul>
            )}
            <Link
              href={`/admin/audit/conciliacao?${q}`}
              className="mt-3 inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg"
            >
              Abrir a conciliação <ArrowRight size={14} aria-hidden />
            </Link>
          </Card>
          {pillars.map((p) => (
            <section key={p} className="mb-6" aria-labelledby={`pilar-${p}`}>
              <h2
                id={`pilar-${p}`}
                className="mb-2 text-xs font-semibold tracking-wide text-fg-2 uppercase"
              >
                {p}
              </h2>
              <div className="overflow-hidden rounded-[var(--radius-card)] border border-line">
                <table className="w-full text-sm">
                  <tbody>
                    {farol.controls
                      .filter((c) => c.pillar_label === p)
                      .map((c) => (
                        <tr
                          key={c.id}
                          className="border-b border-line last:border-0"
                          data-testid={`control-${c.id}`}
                        >
                          <td className="w-[90px] px-4 py-3 font-mono text-[13px] text-fg-2">
                            {c.id}
                          </td>
                          <td className="px-4 py-3">
                            <Link
                              href={`/admin/audit/controle/${selected}/${c.id}?competencia=${competencia}`}
                              className="font-medium hover:underline"
                            >
                              {c.name}
                            </Link>
                            <p className="mt-0.5 line-clamp-2 text-[13px] text-fg-2">
                              {c.rationale}
                            </p>
                          </td>
                          <td className="w-[170px] px-4 py-3">
                            <ControlStatusBadge status={c.status} />
                            {c.review_state === "NEEDS_HUMAN_REVIEW" && (
                              <p className="mt-1 text-xs text-warning">
                                {REVIEW_LABEL[c.review_state]}
                              </p>
                            )}
                          </td>
                          <td className="w-[110px] px-4 py-3 text-right text-[13px] text-fg-2">
                            {c.coverage ? `cobertura ${pct(c.coverage)}` : ""}
                            {c.differences && c.differences !== "0.00" ? (
                              <span className="block text-danger">{formatBRL(c.differences)}</span>
                            ) : null}
                          </td>
                          <td className="w-[150px] px-4 py-3 text-[12px] text-muted">
                            {c.previous_status ? (
                              <>
                                mês anterior: <ControlStatusBadge status={c.previous_status} />
                              </>
                            ) : (
                              "sem mês anterior"
                            )}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </section>
          ))}
          <Card>
            <CardTitle>Execuções do mês</CardTitle>
            <ul className="mt-2 space-y-1 text-sm">
              {farol.runs.map((r) => (
                <li key={r.id}>
                  <Link
                    href={`/admin/audit/execucao/${selected}/${r.id}`}
                    className="inline-flex items-center gap-1 hover:underline"
                  >
                    <ListChecks size={14} aria-hidden /> Execução {r.number}
                  </Link>{" "}
                  · {formatDateTime(r.started_at)} · {String(r.summary.novos_resultados ?? 0)}{" "}
                  novo(s), {String(r.summary.reutilizados ?? 0)} sem mudança
                </li>
              ))}
            </ul>
          </Card>
        </>
      )}
    </>
  );
}
