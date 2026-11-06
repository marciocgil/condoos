import { notFound } from "next/navigation";

import { ContractForm } from "@/components/condoos/ContractForm";
import { PageHeader } from "@/components/layout/PageHeader";
import { apiGet } from "@/lib/api";
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
  return (
    <>
      <PageHeader
        title="Editar contrato"
        subtitle={`${c.supplier_name ?? ""} · ${c.object}${c.amendments ? ` · ${c.amendments} aditivo(s): aqui ficam os termos originais; os aditivos valem a partir das datas deles` : ""}`}
      />
      <ContractForm
        condominiumId={condoId}
        contractId={contractId}
        initial={{
          supplier_cnpj: c.supplier_cnpj ?? "",
          supplier_name: c.supplier_name ?? "",
          object: c.object,
          scope: (c.scope_items ?? []).join("\n"),
          monthly_value: c.original_monthly_value ?? c.monthly_value,
          adjustment_index: c.adjustment_index,
          adjustment_base_month: c.adjustment_base_month ? String(c.adjustment_base_month) : "",
          start_date: c.start_date,
          end_date: c.end_date ?? "",
        }}
      />
    </>
  );
}
