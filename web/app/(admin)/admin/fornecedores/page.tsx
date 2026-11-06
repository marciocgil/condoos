import { Store } from "lucide-react";

import { CondoFilter } from "@/components/condoos/CondoFilter";
import { SupplierTable } from "@/components/condoos/SupplierTable";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import type { Portfolio, SupplierRow } from "@/lib/types";

export default async function FornecedoresPage({
  searchParams,
}: {
  searchParams: Promise<{ condominio?: string }>;
}) {
  const { condominio } = await searchParams;
  const portfolio = await apiGet<Portfolio>("/portfolio");
  const condos = portfolio.condominiums;
  const selected = condos.some((c) => c.id === condominio) ? condominio! : null;
  const rows = await apiGet<SupplierRow[]>(
    `/portfolio/suppliers${selected ? `?condominium_id=${selected}` : ""}`,
  );
  const shared = rows.filter((r) => r.condominiums.length > 1).length;
  return (
    <>
      <PageHeader
        title="Fornecedores"
        subtitle={
          selected
            ? `${rows.length} fornecedores deste condomínio`
            : `${rows.length} fornecedores na carteira · ${shared} atendem mais de um condomínio`
        }
      />
      <CondoFilter pathname="/admin/fornecedores" condos={condos} selected={selected} />
      {rows.length === 0 ? (
        <EmptyState icon={<Store size={28} />} title="Nenhum fornecedor ainda">
          Os fornecedores aparecem quando as primeiras despesas são processadas.
        </EmptyState>
      ) : (
        <SupplierTable rows={rows} />
      )}
    </>
  );
}
