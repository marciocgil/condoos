import { FindingDetailView } from "@/components/condoos/FindingDetailView";
import { apiGet } from "@/lib/api";
import type { CaseRef, FindingDetail, Me } from "@/lib/types";

/** The manager validates or discards a serious finding before the síndico sees it. */
export default async function ValidateFindingPage({
  params,
}: {
  params: Promise<{ condoId: string; findingId: string }>;
}) {
  const { condoId, findingId } = await params;
  const [finding, cases, me] = await Promise.all([
    apiGet<FindingDetail>(`/condominiums/${condoId}/findings/${findingId}`),
    apiGet<CaseRef[]>(`/condominiums/${condoId}/findings/${findingId}/cases`),
    apiGet<Me>("/me"),
  ]);
  const canOpen = me.condominiums
    .find((c) => c.id === condoId)
    ?.permissions.includes("manage_cases");
  return (
    <div className="max-w-3xl">
      <FindingDetailView
        finding={finding}
        condominiumId={condoId}
        backHref="/admin/fila"
        backLabel="Fila de exceções"
        cases={cases}
        casePath={`/admin/assuntos/${condoId}/{id}`}
        newCaseHref={
          canOpen ? `/admin/assuntos/novo?condominio=${condoId}&achado=${findingId}` : undefined
        }
      />
    </div>
  );
}
