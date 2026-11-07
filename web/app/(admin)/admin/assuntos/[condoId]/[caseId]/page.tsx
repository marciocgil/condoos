import { CaseDetailView } from "@/components/condoos/CaseDetailView";
import { apiGet } from "@/lib/api";
import type { CaseDetail } from "@/lib/types";

export default async function AssuntoAdminPage({
  params,
}: {
  params: Promise<{ condoId: string; caseId: string }>;
}) {
  const { condoId, caseId } = await params;
  const detail = await apiGet<CaseDetail>(`/condominiums/${condoId}/cases/${caseId}`);
  return (
    <div className="max-w-3xl">
      <CaseDetailView
        detail={detail}
        backHref={`/admin/assuntos?condominio=${condoId}`}
        backLabel="Assuntos"
        findingPath={`/admin/achados/${condoId}/{id}`}
        casePath={`/admin/assuntos/${condoId}/{id}`}
      />
    </div>
  );
}
