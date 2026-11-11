import Link from "next/link";

import { AuditToolbar } from "@/components/audit/AuditToolbar";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Card, CardTitle } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import { auditCondos, lastMonth } from "@/lib/audit";
import { formatBRL, formatDate } from "@/lib/format";
import type { Me, Reconciliation } from "@/lib/types";

const LEVELS: [keyof Reconciliation["accounts"][number]["lines"][number]["levels"], string][] = [
  ["a_saldo", "a) saldo"],
  ["b_classificado", "b) classificado"],
  ["c_comprovante", "c) comprovante"],
  ["d_favorecido", "d) favorecido"],
  ["e_obrigacao", "e) obrigação"],
];
const SITUATION: Record<string, string> = {
  confere: "Saldo inicial + movimentos = saldo final (fecha ao centavo).",
  diverge: "A equação do saldo não fecha.",
  sem_extrato: "Sem extrato do mês para esta conta.",
  sem_saldo_final: "O extrato não traz saldo final.",
  sem_saldo_inicial: "Sem saldo inicial (nem no extrato nem no mês anterior).",
  sem_mes_anterior: "Sem extrato do mês anterior com saldo final.",
  sem_saldo: "O extrato não traz saldo.",
};

/** Bank reconciliation per account (A4): balances, continuity and each line with the five
 * levels shown apart (never one checkbox). */
export default async function ReconciliationPage({
  searchParams,
}: {
  searchParams: Promise<{ condominio?: string; competencia?: string }>;
}) {
  const sp = await searchParams;
  const me = await apiGet<Me>("/me");
  const condos = auditCondos(me);
  if (condos.length === 0)
    return <EmptyState title="Sem acesso à auditoria">Seu papel não vê a conciliação.</EmptyState>;
  const selected = condos.some((c) => c.id === sp.condominio) ? sp.condominio! : condos[0]!.id;
  const competencia = /^\d{4}-\d{2}$/.test(sp.competencia ?? "") ? sp.competencia! : lastMonth();
  const data = await apiGet<Reconciliation>(
    `/condominiums/${selected}/audit/reconciliation?competencia=${competencia}`,
  );
  return (
    <>
      <PageHeader
        title="Conciliação bancária"
        subtitle={`Por conta e competência. Classificação por regra (${data.classification_version}); sugestão da IA nunca muda o estado de um lançamento.`}
      />
      <AuditToolbar
        pathname="/admin/audit/conciliacao"
        condos={condos}
        selected={selected}
        competencia={competencia}
      />
      {data.accounts.length === 0 ? (
        <EmptyState title="Nenhum lançamento bancário no mês">
          Envie o extrato do mês em OFX (traz a conta e o saldo final).
        </EmptyState>
      ) : (
        <div className="space-y-6">
          {data.accounts.map((a) => (
            <Card key={a.key} data-testid={`account-${a.key}`}>
              <CardTitle>{a.label}</CardTitle>
              <div className="mt-2 grid grid-cols-1 gap-2 text-sm md:grid-cols-2">
                <p>
                  <span className="font-medium">Equação do saldo:</span>{" "}
                  {SITUATION[a.balance.situacao ?? ""] ?? a.balance.situacao}
                  {a.balance.saldo_inicial && (
                    <span className="block text-fg-2">
                      {formatBRL(a.balance.saldo_inicial)} ({a.balance.origem_saldo_inicial}) +{" "}
                      {formatBRL(a.balance.movimentos ?? "0")} ={" "}
                      {formatBRL(a.balance.saldo_final_calculado ?? "0")}; declarado{" "}
                      {formatBRL(a.balance.saldo_final_declarado ?? "0")}
                      {a.balance.diferenca && a.balance.diferenca !== "0.00"
                        ? `, diferença ${formatBRL(a.balance.diferenca)}`
                        : ""}
                    </span>
                  )}
                </p>
                <p>
                  <span className="font-medium">Continuidade:</span>{" "}
                  {SITUATION[a.continuity.situacao ?? ""] ??
                    (a.continuity.situacao === "confere"
                      ? "Abertura = fechamento anterior."
                      : a.continuity.situacao)}
                  {a.continuity.fechamento_anterior && (
                    <span className="block text-fg-2">
                      Fechamento anterior {formatBRL(a.continuity.fechamento_anterior)}, abertura{" "}
                      {formatBRL(a.continuity.abertura ?? "0")} ({a.continuity.metodo})
                    </span>
                  )}
                </p>
              </div>
              {a.statement?.document_id && (
                <a
                  href={`/api/condominiums/${selected}/documents/${a.statement.document_id}/file`}
                  className="mt-2 inline-block text-sm text-fg-2 underline-offset-2 hover:underline"
                >
                  Abrir o extrato
                </a>
              )}
              <p className="mt-2 text-sm text-fg-2">
                {a.classified} de {a.lines.length} lançamento(s) classificados por regra nesta
                conta.
              </p>
              <div className="mt-3 overflow-auto">
                <table className="w-full text-[13px]">
                  <thead className="text-left text-fg-2">
                    <tr>
                      <th className="py-2 pr-3">Data</th>
                      <th className="py-2 pr-3">Descrição</th>
                      <th className="py-2 pr-3 text-right">Valor</th>
                      <th className="py-2 pr-3">Classificação</th>
                      <th className="py-2">Níveis</th>
                    </tr>
                  </thead>
                  <tbody>
                    {a.lines.map((l) => (
                      <tr key={l.id} className="border-t border-line align-top">
                        <td className="py-2 pr-3 whitespace-nowrap">{formatDate(l.date)}</td>
                        <td className="py-2 pr-3">
                          {l.description}
                          {l.expense && (
                            <span className="block text-fg-2">
                              → {l.expense.description} ({formatBRL(l.expense.amount)})
                            </span>
                          )}
                          {l.paired_with && (
                            <span className="block text-fg-2">
                              pareado com estorno/débito original
                            </span>
                          )}
                          {l.intermediary && (
                            <span className="block text-warning">pago por intermediário</span>
                          )}
                        </td>
                        <td className="tabular py-2 pr-3 text-right whitespace-nowrap">
                          {formatBRL(l.amount)}
                        </td>
                        <td className="py-2 pr-3">
                          <Badge
                            tone={
                              l.kind === "nao_identificado"
                                ? "warning"
                                : l.strength === "sugerido"
                                  ? "info"
                                  : "neutral"
                            }
                          >
                            {l.classification}
                            {l.strength === "sugerido" ? " (indício)" : ""}
                          </Badge>
                        </td>
                        <td className="py-2">
                          <div className="flex flex-wrap gap-1">
                            {LEVELS.map(([k, label]) => (
                              <span
                                key={k}
                                className={
                                  l.levels[k]
                                    ? "rounded border border-success/60 px-1 text-[11px] text-success"
                                    : "rounded border border-control px-1 text-[11px] text-muted"
                                }
                              >
                                {l.levels[k] ? "✓" : "—"} {label}
                              </span>
                            ))}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          ))}
        </div>
      )}
      <p className="mt-6 text-sm text-fg-2">
        <Link
          href={`/admin/audit?condominio=${selected}&competencia=${competencia}`}
          className="underline-offset-2 hover:underline"
        >
          Voltar ao farol
        </Link>
        . Conciliado financeiramente não é aprovado contratualmente.
      </p>
    </>
  );
}
