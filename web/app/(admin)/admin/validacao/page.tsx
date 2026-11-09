import Link from "next/link";

import { CondoFilter } from "@/components/condoos/CondoFilter";
import { DataIssueCard } from "@/components/condoos/DataIssueCard";
import { HealthAlertCard } from "@/components/condoos/HealthAlertCard";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import { ALERT_KINDS, type DataIssue, type Portfolio, type QueueItem } from "@/lib/types";

/** Validation Centre (D93, LB-032): open conflicts between documents, the largest amount in
 * play first. The exception queue (extraction, matching, serious findings) stays in its own
 * screen. */
export default async function ValidacaoPage({
  searchParams,
}: {
  searchParams: Promise<{ condominio?: string }>;
}) {
  const sp = await searchParams;
  const portfolio = await apiGet<Portfolio>("/portfolio");
  const condos = portfolio.condominiums;
  const selected = condos.some((c) => c.id === sp.condominio) ? sp.condominio! : null;
  const [issues, queue] = await Promise.all([
    apiGet<DataIssue[]>(`/portfolio/data-issues${selected ? `?condominium_id=${selected}` : ""}`),
    apiGet<QueueItem[]>("/queue"),
  ]);
  // Health alerts (D110) and conflicts between documents (D93) are listed apart.
  const alerts = issues.filter((i) => ALERT_KINDS.has(i.kind));
  const conflicts = issues.filter((i) => !ALERT_KINDS.has(i.kind));
  const n = conflicts.length;
  return (
    <>
      <PageHeader
        title="Conflitos de dados"
        subtitle={`${n} ${n === 1 ? "divergência aberta" : "divergências abertas"} entre documentos`}
      />
      <CondoFilter pathname="/admin/validacao" condos={condos} selected={selected} />
      <p className="mb-6 text-sm text-fg-2">
        Enquanto uma divergência está aberta, as funções que dependem do contrato ficam em análise
        parcial e nenhuma ação com o fornecedor é aprovada.{" "}
        <Link href="/admin/fila" className="text-fg underline-offset-2 hover:underline">
          Fila de exceções: {queue.length} {queue.length === 1 ? "item" : "itens"}
        </Link>
        .
      </p>
      {n === 0 ? (
        <EmptyState title="Nenhuma divergência aberta">
          Os documentos de contratos e aditivos não se contradizem.
        </EmptyState>
      ) : (
        <div className="space-y-4">
          {conflicts.map((i) => (
            <DataIssueCard key={i.id} issue={i} />
          ))}
        </div>
      )}
      <section className="mt-8 space-y-4" aria-labelledby="alertas-titulo">
        <h2 id="alertas-titulo" className="text-lg font-semibold">
          Alertas de saúde ({alerts.length})
        </h2>
        <p className="text-sm text-fg-2">
          Verificados todo dia: canal parado, contrato aditado, revisora ausente, acesso do síndico
          e ações sem execução. Alertas não mudam permissões nem bloqueiam ações.
        </p>
        {alerts.length === 0 ? (
          <EmptyState title="Nenhum alerta aberto">
            Os monitores diários não encontraram nada para tratar.
          </EmptyState>
        ) : (
          alerts.map((i) => <HealthAlertCard key={i.id} issue={i} />)
        )}
      </section>
    </>
  );
}
