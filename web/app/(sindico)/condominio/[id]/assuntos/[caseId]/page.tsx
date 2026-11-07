import { CaseDetailView } from "@/components/condoos/CaseDetailView";
import { apiGet } from "@/lib/api";
import type { CaseDetail } from "@/lib/types";

export default async function AssuntoPage({
  params,
}: {
  params: Promise<{ id: string; caseId: string }>;
}) {
  const { id, caseId } = await params;
  const detail = await apiGet<CaseDetail>(`/condominiums/${id}/cases/${caseId}`);
  return (
    <CaseDetailView
      detail={detail}
      backHref={`/condominio/${id}/assuntos`}
      backLabel="Assuntos"
      findingPath={`/condominio/${id}/achados/{id}`}
      casePath={`/condominio/${id}/assuntos/{id}`}
    />
  );
}
