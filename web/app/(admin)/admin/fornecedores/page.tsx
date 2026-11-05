import { Store } from "lucide-react";

import { SupplierTable } from "@/components/condoos/SupplierTable";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import type { SupplierRow } from "@/lib/types";

export default async function FornecedoresPage() {
  const rows = await apiGet<SupplierRow[]>("/portfolio/suppliers");
  const shared = rows.filter((r) => r.condominiums.length > 1).length;
  return (
    <>
      <PageHeader
        title="Fornecedores"
        subtitle={`${rows.length} fornecedores na carteira · ${shared} atendem mais de um condomínio`}
      />
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
