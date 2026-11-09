import Link from "next/link";

import { CondoFilter } from "@/components/condoos/CondoFilter";
import { DataIssueCard } from "@/components/condoos/DataIssueCard";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import type { DataIssue, Portfolio, QueueItem } from "@/lib/types";

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
  const n = issues.length;
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
          {issues.map((i) => (
            <DataIssueCard key={i.id} issue={i} />
          ))}
        </div>
      )}
    </>
  );
}
