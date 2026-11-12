import { notFound } from "next/navigation";

import { ContractClauses } from "@/components/condoos/ContractClauses";
import { ContractForm } from "@/components/condoos/ContractForm";
import { DocumentNewVersion } from "@/components/condoos/DocumentNewVersion";
import { RelationsList, type Relations } from "@/components/condoos/RelationsList";
import { PageHeader } from "@/components/layout/PageHeader";
import { apiGet } from "@/lib/api";
import { contractValue, formatBRL } from "@/lib/format";
import type { Contract } from "@/lib/types";

export default async function EditarContratoPage({
  params,
}: {
  params: Promise<{ condoId: string; contractId: string }>;
}) {
  const { condoId, contractId } = await params;
  const contracts = await apiGet<Contract[]>(`/condominiums/${condoId}/contracts`);
  const c = contracts.find((x) => x.id === contractId);
  if (!c) notFound();
  const relations = await apiGet<Relations>(
    `/condominiums/${condoId}/relations/contract/${contractId}`,
  );
  return (
    <>
      <PageHeader
        title="Editar contrato"
        subtitle={`${c.supplier_name ?? ""} · ${c.object}${c.amendments ? ` · ${c.amendments} aditivo(s): aqui ficam os termos originais; os aditivos valem a partir das datas deles` : ""}`}
      />
      {(c.nature === "pontual" || !c.supplier_id) && (
        <p className="mb-4 max-w-2xl text-sm text-fg-2" data-testid="contract-reading-note">
          {c.nature === "pontual" &&
            `Contrato pontual: ${contractValue(c)}${c.billed_total ? `, faturado até agora ${formatBRL(c.billed_total)}` : ""}. Sem reajuste e sem nota esperada todo mês. `}
          {!c.supplier_id &&
            "O contrato não traz o CNPJ da contratada: informe o CNPJ abaixo quando tiver, ou ele é preenchido pela primeira nota do fornecedor."}
        </p>
      )}
      <ContractForm
        condominiumId={condoId}
        contractId={contractId}
        initial={{
          supplier_cnpj: c.supplier_cnpj ?? "",
          supplier_name: c.supplier_name ?? "",
          object: c.object,
          scope: (c.scope_items ?? []).join("\n"),
          monthly_value: c.original_monthly_value ?? c.monthly_value ?? c.total_value ?? "",
          adjustment_index: c.adjustment_index,
          adjustment_index_other: c.adjustment_index_other ?? "",
          adjustment_base_month: c.adjustment_base_month ? String(c.adjustment_base_month) : "",
          start_date: c.start_date,
          end_date: c.end_date ?? "",
          indeterminate: c.end_date === null,
          billing_frequency_months: String(c.billing_frequency_months ?? 1),
        }}
      />
      <div className="mt-6 max-w-2xl space-y-3">
        <ContractClauses contract={c} />
        {c.source_document_id && (
          <DocumentNewVersion condominiumId={condoId} documentId={c.source_document_id} />
        )}
        <RelationsList data={relations} title="Relações do contrato" />
      </div>
    </>
  );
}
