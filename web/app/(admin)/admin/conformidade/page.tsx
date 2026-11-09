import { CondoFilter } from "@/components/condoos/CondoFilter";
import { ComplianceList } from "@/components/condoos/ComplianceList";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import type { ComplianceList as ComplianceListData, Portfolio } from "@/lib/types";

/** Compliance and expiry dates on the desktop (D112), one condominium at a time. */
export default async function ConformidadeAdminPage({
  searchParams,
}: {
  searchParams: Promise<{ condominio?: string }>;
}) {
  const sp = await searchParams;
  const portfolio = await apiGet<Portfolio>("/portfolio");
  const condos = portfolio.condominiums;
  const selected = condos.some((c) => c.id === sp.condominio) ? sp.condominio! : null;
  const target = selected ?? (condos.length === 1 ? (condos[0]?.id ?? null) : null);
  const data = target
    ? await apiGet<ComplianceListData>(`/condominiums/${target}/compliance`)
    : null;
  return (
    <div className="max-w-3xl">
      <PageHeader
        title="Conformidade e vencimentos"
        subtitle="AVCB, seguro, laudos e manutenções obrigatórias"
      />
      <CondoFilter pathname="/admin/conformidade" condos={condos} selected={selected} />
      {target && data ? (
        <ComplianceList
          condominiumId={target}
          data={data}
          detailBase={`/admin/conformidade/${target}`}
        />
      ) : (
        <EmptyState title="Escolha um condomínio">
          A conformidade é vista e registrada por condomínio.
        </EmptyState>
      )}
    </div>
  );
}
