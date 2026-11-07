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
  const [finding, cases, opportunities, me] = await Promise.all([
    apiGet<FindingDetail>(`/condominiums/${condoId}/findings/${findingId}`),
    apiGet<CaseRef[]>(`/condominiums/${condoId}/findings/${findingId}/cases`),
    apiGet<CaseRef[]>(`/condominiums/${condoId}/findings/${findingId}/opportunities`),
    apiGet<Me>("/me"),
  ]);
  const perms = me.condominiums.find((c) => c.id === condoId)?.permissions ?? [];
  const canOpen = perms.includes("manage_cases");
  // R02/R03 become opportunities, computed by code (D81); only the CondoOS team generates them.
  const canGenerate =
    perms.includes("view_opportunity_draft") &&
    ["R02", "R03"].includes(finding.rule_code) &&
    !["descartado", "superado", "ignorado"].includes(finding.status);
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
        opportunities={opportunities}
        opportunityPath={`/admin/oportunidades/${condoId}/{id}`}
        canGenerateOpportunity={canGenerate}
      />
    </div>
  );
}
