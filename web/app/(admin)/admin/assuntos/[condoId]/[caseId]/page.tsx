import { ActionsPreview } from "@/components/condoos/ActionsPreview";
import { CaseDetailView } from "@/components/condoos/CaseDetailView";
import { apiGet } from "@/lib/api";
import type { CaseDetail, Me } from "@/lib/types";

export default async function AssuntoAdminPage({
  params,
}: {
  params: Promise<{ condoId: string; caseId: string }>;
}) {
  const { condoId, caseId } = await params;
  const [detail, me] = await Promise.all([
    apiGet<CaseDetail>(`/condominiums/${condoId}/cases/${caseId}`),
    apiGet<Me>("/me"),
  ]);
  const canRequest = me.condominiums
    .find((c) => c.id === condoId)
    ?.permissions.includes("manage_cases");
  return (
    <div className="max-w-3xl space-y-6">
      <CaseDetailView
        detail={detail}
        backHref={`/admin/assuntos?condominio=${condoId}`}
        backLabel="Assuntos"
        findingPath={`/admin/achados/${condoId}/{id}`}
        casePath={`/admin/assuntos/${condoId}/{id}`}
      />
      <ActionsPreview
        condominiumId={condoId}
        caseId={caseId}
        title="Ações deste assunto"
        detailPath={`/admin/aprovacoes/${condoId}/{id}`}
        newHref={
          canRequest ? `/admin/aprovacoes/nova?condominio=${condoId}&assunto=${caseId}` : undefined
        }
      />
    </div>
  );
}
