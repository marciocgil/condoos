import { CaseForm } from "@/components/condoos/CaseForm";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import type { FindingDetail, Me } from "@/lib/types";

export default async function NovoAssuntoAdminPage({
  searchParams,
}: {
  searchParams: Promise<{ condominio?: string; achado?: string; titulo?: string }>;
}) {
  const { condominio, achado, titulo } = await searchParams;
  const me = await apiGet<Me>("/me");
  let condos = me.condominiums.filter((c) => c.permissions.includes("manage_cases"));
  if (condominio) condos = condos.filter((c) => c.id === condominio);
  if (condos.length === 0)
    return (
      <EmptyState title="Sem permissão">Seu papel não abre assuntos neste condomínio.</EmptyState>
    );
  const finding =
    achado && condominio
      ? await apiGet<FindingDetail>(`/condominiums/${condominio}/findings/${achado}`)
      : null;
  return (
    <div className="max-w-2xl">
      <CaseForm
        condos={condos.map((c) => ({ id: c.id, name: c.name }))}
        finding={
          finding && condominio
            ? { id: finding.id, title: finding.title, condominiumId: condominio }
            : undefined
        }
        detailPath="/admin/assuntos/{condo}/{case}"
        initialTitle={titulo}
      />
    </div>
  );
}
