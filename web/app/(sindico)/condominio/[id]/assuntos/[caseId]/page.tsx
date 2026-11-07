import { ActionsPreview } from "@/components/condoos/ActionsPreview";
import { CaseDetailView } from "@/components/condoos/CaseDetailView";
import { apiGet } from "@/lib/api";
import type { CaseDetail, Me } from "@/lib/types";

export default async function AssuntoPage({
  params,
}: {
  params: Promise<{ id: string; caseId: string }>;
}) {
  const { id, caseId } = await params;
  const [detail, me] = await Promise.all([
    apiGet<CaseDetail>(`/condominiums/${id}/cases/${caseId}`),
    apiGet<Me>("/me"),
  ]);
  const canRequest = me.condominiums.find((c) => c.id === id)?.permissions.includes("manage_cases");
  return (
    <>
      <CaseDetailView
        detail={detail}
        backHref={`/condominio/${id}/assuntos`}
        backLabel="Assuntos"
        findingPath={`/condominio/${id}/achados/{id}`}
        casePath={`/condominio/${id}/assuntos/{id}`}
      />
      <ActionsPreview
        condominiumId={id}
        caseId={caseId}
        title="Ações deste assunto"
        detailPath={`/condominio/${id}/aprovacoes/{id}`}
        newHref={canRequest ? `/condominio/${id}/aprovacoes/nova?assunto=${caseId}` : undefined}
      />
    </>
  );
}
