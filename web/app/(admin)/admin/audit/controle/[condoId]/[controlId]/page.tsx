import { ChevronLeft, CircleCheck, CircleX, CircleDashed, FileText } from "lucide-react";
import Link from "next/link";

import { CalculationMemory } from "@/components/audit/CalculationMemory";
import { ControlReviewForm } from "@/components/audit/ControlReviewForm";
import { ControlStatusBadge } from "@/components/audit/ControlStatusBadge";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Card, CardTitle } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import { lastMonth, pct, REVIEW_LABEL } from "@/lib/audit";
import { formatBRL, formatDateTime, formatMonthTitle } from "@/lib/format";
import type { ControlDetail } from "@/lib/types";

const RESULT_ICON = { passou: CircleCheck, falhou: CircleX, "não rodou": CircleDashed } as const;

export default async function ControlPage({
  params,
  searchParams,
}: {
  params: Promise<{ condoId: string; controlId: string }>;
  searchParams: Promise<{ competencia?: string }>;
}) {
  const { condoId, controlId } = await params;
  const sp = await searchParams;
  const competencia = /^\d{4}-\d{2}$/.test(sp.competencia ?? "") ? sp.competencia! : lastMonth();
  const d = await apiGet<ControlDetail>(
    `/condominiums/${condoId}/audit/controls/${controlId}?competencia=${competencia}`,
  );
  const c = d.current;
  const def = d.definition;
  return (
    <>
      <Link
        href={`/admin/audit?condominio=${condoId}&competencia=${competencia}`}
        className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg"
      >
        <ChevronLeft size={16} aria-hidden /> Farol
      </Link>
      <PageHeader
        title={`${def.id} — ${def.name}`}
        subtitle={`${def.pillar} · ${formatMonthTitle(`${competencia}-01`)} · regra versão ${def.rule_version}`}
      />
      {!c ? (
        <EmptyState title="Controle ainda não avaliado neste mês">
          Rode a auditoria do mês no Farol.
        </EmptyState>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_360px]">
          <div className="space-y-6">
            <Card>
              <div className="flex flex-wrap items-center gap-2">
                <ControlStatusBadge status={c.status} />
                <Badge tone={c.review_state === "NEEDS_HUMAN_REVIEW" ? "warning" : "neutral"}>
                  {REVIEW_LABEL[c.review_state] ?? c.review_state}
                </Badge>
                {c.coverage && (
                  <span className="text-sm text-fg-2">Cobertura {pct(c.coverage)}</span>
                )}
                {c.differences !== "0.00" && (
                  <span className="text-sm text-danger">Diferença {formatBRL(c.differences)}</span>
                )}
              </div>
              <p className="mt-3 text-sm" data-testid="control-rationale">
                {c.rationale}
              </p>
              {c.missing.length > 0 && (
                <div className="mt-3">
                  <p className="text-sm font-medium">O que falta</p>
                  <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-fg-2">
                    {c.missing.map((m) => (
                      <li key={m}>{m}</li>
                    ))}
                  </ul>
                  <Link
                    href={`/admin/pedidos/novo?condominio=${condoId}&item=${encodeURIComponent(c.missing[0] ?? "")}`}
                    className="mt-2 inline-block text-sm text-fg-2 underline-offset-2 hover:underline"
                  >
                    Pedir documento
                  </Link>
                </div>
              )}
            </Card>
            <Card>
              <CardTitle>Testes</CardTitle>
              <ul className="mt-2 space-y-2 text-sm">
                {c.tests.map((t) => {
                  const Icon = RESULT_ICON[t.resultado as keyof typeof RESULT_ICON] ?? CircleDashed;
                  return (
                    <li key={t.teste} className="flex gap-2">
                      <Icon
                        size={16}
                        aria-hidden
                        className={
                          t.resultado === "passou"
                            ? "mt-0.5 shrink-0 text-success"
                            : t.resultado === "falhou"
                              ? "mt-0.5 shrink-0 text-danger"
                              : "mt-0.5 shrink-0 text-fg-2"
                        }
                      />
                      <span>
                        <span className="font-medium">{t.teste}</span>{" "}
                        <span className="text-fg-2">({t.resultado})</span>
                        <span className="block text-fg-2">{t.detalhe}</span>
                      </span>
                    </li>
                  );
                })}
              </ul>
            </Card>
            <Card>
              <CardTitle>Evidências usadas ({c.evidence_refs.length})</CardTitle>
              {c.evidence_refs.length === 0 ? (
                <p className="mt-2 text-sm text-fg-2">
                  Nenhuma evidência: a ausência está declarada em “O que falta”.
                </p>
              ) : (
                <ul className="mt-2 max-h-[420px] space-y-1 overflow-auto text-sm">
                  {c.evidence_refs.map((e) => {
                    const docId = e.tipo === "documento" ? e.id : e.documento_id;
                    return (
                      <li key={`${e.tipo}-${e.id}`} className="flex gap-2">
                        <span className="w-[90px] shrink-0 text-xs text-fg-2 uppercase">
                          {e.tipo}
                        </span>
                        {docId ? (
                          <a
                            href={`/api/condominiums/${condoId}/documents/${docId}/file`}
                            className="inline-flex items-center gap-1 hover:underline"
                          >
                            <FileText size={14} aria-hidden /> {e.rotulo}
                          </a>
                        ) : (
                          <span>{e.rotulo}</span>
                        )}
                        {e.classificacao && <span className="text-fg-2">· {e.classificacao}</span>}
                      </li>
                    );
                  })}
                </ul>
              )}
            </Card>
            <CalculationMemory lines={c.calculation ?? []} />
            <details
              className="rounded-[var(--radius-card)] border border-line bg-surface p-5"
              open
              data-testid="produced-by"
            >
              <summary className="cursor-pointer text-[15px] font-semibold">
                Como este resultado foi produzido?
              </summary>
              <div className="mt-3 space-y-2 text-sm">
                <p>
                  Execução {c.produced_by.run_number ?? "—"}, regra{" "}
                  <span className="font-mono">
                    {def.id} v{c.produced_by.rule_version}
                  </span>
                  . {c.produced_by.deterministic}
                </p>
                <ul className="space-y-1">
                  {c.produced_by.agents.map((a) => (
                    <li key={a.agent_id}>
                      <Link
                        href={`/admin/audit/agentes/${a.agent_id}`}
                        className="font-medium hover:underline"
                      >
                        {a.agent_id}
                      </Link>{" "}
                      · prompt versão {a.version ?? "arquivo"} (
                      <span className="font-mono">{a.agent_sha256.slice(0, 12)}</span>) ·{" "}
                      {a.llm_invoked
                        ? `IA chamada (${a.model ?? "modelo"}), prompt da execução ${a.runtime_sha256.slice(0, 12)}`
                        : "IA não chamada nesta execução"}
                    </li>
                  ))}
                </ul>
                <p className="text-fg-2">
                  Impressão digital das entradas:{" "}
                  <span className="font-mono">{c.produced_by.input_fingerprint.slice(0, 16)}</span>.
                  Mesmas entradas, mesma regra: mesmo resultado.{" "}
                  <Link
                    href={`/admin/audit/execucao/${condoId}/${c.produced_by.run_id}`}
                    className="underline-offset-2 hover:underline"
                  >
                    Ver a execução
                  </Link>
                </p>
              </div>
            </details>
            {d.can_review && (
              <Card>
                <CardTitle>Revisão humana</CardTitle>
                <ControlReviewForm
                  condominiumId={condoId}
                  resultId={c.result_id}
                  current={c.status}
                />
              </Card>
            )}
          </div>
          <aside className="space-y-6">
            <Card>
              <CardTitle>Critérios de “Validado”</CardTitle>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                {def.criteria.map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ul>
              <p className="mt-3 text-sm font-medium">Fontes obrigatórias</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-fg-2">
                {def.sources.map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ul>
              {Object.keys(def.parameters).length > 0 && (
                <p className="mt-3 text-sm text-fg-2">
                  Parâmetros:{" "}
                  {Object.entries(def.parameters)
                    .map(([k, v]) => `${k}: ${v}`)
                    .join(" · ")}
                </p>
              )}
              <p className="mt-3 text-sm text-fg-2">Agentes: {def.agents.join(", ")}</p>
            </Card>
            <Card>
              <CardTitle>Histórico no mês</CardTitle>
              <ul className="mt-2 space-y-2 text-sm">
                {d.history.map((h) => (
                  <li key={h.result_id}>
                    <ControlStatusBadge status={h.status} /> {h.current ? "atual" : "substituído"} ·
                    execução {h.run_number ?? "—"} · {formatDateTime(h.created_at)}
                    {h.source === "revisao" && (
                      <span className="block text-xs text-fg-2">
                        reclassificado por revisão humana
                      </span>
                    )}
                  </li>
                ))}
              </ul>
              {d.reviews.length > 0 && (
                <>
                  <p className="mt-4 text-sm font-medium">Revisões</p>
                  <ul className="mt-1 space-y-1 text-sm text-fg-2">
                    {d.reviews.map((r) => (
                      <li key={r.at}>
                        {formatDateTime(r.at)} · {r.user ?? "—"} · {r.decision}: {r.reason}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </Card>
          </aside>
        </div>
      )}
    </>
  );
}
